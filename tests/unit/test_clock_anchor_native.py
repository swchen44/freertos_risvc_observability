"""Native FIFO/lifecycle failures and C-to-Python wire interoperability."""

import hashlib
import json
import subprocess
import unittest
import uuid
from pathlib import Path

from psf_lab.clock_anchor_wire import ClockEvidenceError, iter_clock_records

ROOT = Path(__file__).resolve().parents[2]


class ClockNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = ROOT / "runs/local/c2b-native-state-tests" / uuid.uuid4().hex
        cls.out.mkdir(parents=True)
        cls.binary = cls.out / "state"
        cls.sources = [
            ROOT / "tests/native/clock_anchor_state.c",
            ROOT / "tools/qemu/clock_anchor/poc-clock-state.c",
        ]
        cmd = [
            "cc",
            "-std=c11",
            "-O1",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-I" + str(ROOT / "tools/qemu/clock_anchor"),
            "-I" + str(ROOT / "tools/qemu"),
            *map(str, cls.sources),
            "-o",
            str(cls.binary),
        ]
        p = subprocess.run(cmd, capture_output=True, timeout=20)
        cls.save("compile", cmd, p)
        if p.returncode:
            raise AssertionError(p.stderr.decode(errors="replace"))

    @classmethod
    def save(cls, name, cmd, p):
        (cls.out / (name + ".stdout")).write_bytes(p.stdout)
        (cls.out / (name + ".stderr")).write_bytes(p.stderr)
        hashes = {
            str(s.relative_to(ROOT)): hashlib.sha256(s.read_bytes()).hexdigest()
            for s in [
                *cls.sources,
                ROOT / "tools/qemu/poc-clock-anchor-api.h",
                ROOT / "tools/qemu/clock_anchor/poc-clock-state.h",
            ]
            if s.is_file()
        }
        (cls.out / (name + ".json")).write_text(
            json.dumps(dict(command=cmd, exit=p.returncode, sources=hashes), indent=2) + "\n"
        )

    def run_case(self, name):
        cmd = [str(self.binary), name]
        p = subprocess.run(cmd, capture_output=True, timeout=5)
        self.save(name, cmd, p)
        return p

    def test_end_freezes_cursor_but_pending_costs_can_apply(self):
        p = self.run_case("normal")
        self.assertEqual(p.returncode, 0, p.stderr)
        rows = list(iter_clock_records(self.out / "normal.stdout"))
        self.assertEqual(
            [r["kind"] for r in rows],
            ["header", "capture_begin", "cost_request", "capture_end", "cost_applied", "footer"],
        )
        self.assertEqual(rows[0]["run_id"], "native-O-1")
        self.assertIsNone(rows[2]["request_clock_ns"])
        self.assertEqual(rows[4]["raw_cursor"], "1")
        self.assertEqual(rows[4]["before_ns"], "100")
        self.assertEqual(rows[4]["after_ns"], "102")
        self.assertEqual(rows[5]["pending"], "0")
        self.assertEqual(rows[5]["record_count"], "6")
        self.assertTrue(rows[5]["complete"])

    def test_two_fifo_items_apply_after_end_at_same_cursor(self):
        p = self.run_case("deferred")
        self.assertEqual(p.returncode, 0, p.stderr)
        rows = list(iter_clock_records(self.out / "deferred.stdout"))
        applies = [r for r in rows if r["kind"] == "cost_applied"]
        self.assertEqual(
            [(r["request_id"], r["raw_cursor"], r["after_ns"]) for r in applies],
            [("1", "2", "102"), ("2", "2", "106")],
        )

    def test_observer_off_never_calls_sink_and_marker_off_still_charges(self):
        p = self.run_case("off")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout, b"")
        self.assertIn(b"writes=0", p.stderr)
        p = self.run_case("normal")
        self.assertEqual(p.returncode, 0, p.stderr)
        rows = list(iter_clock_records(self.out / "normal.stdout"))
        self.assertEqual(rows[0]["marker_mode"], "0")
        self.assertEqual(rows[-1]["requests"], "1")

    def test_native_and_plugin_mmio_phases_are_distinct(self):
        p = self.run_case("mmio")
        self.assertEqual(p.returncode, 0, p.stderr)
        rows = list(iter_clock_records(self.out / "mmio.stdout"))
        io = [r for r in rows if r["kind"] in ("mtime_read", "mtimecmp_write")]
        self.assertEqual(
            [(r["kind"], r["source"], r["native_io_seq"]) for r in io],
            [
                ("mtime_read", "device", "1"),
                ("mtime_read", "plugin", "1"),
                ("mtimecmp_write", "device", "2"),
                ("mtimecmp_write", "plugin", "2"),
            ],
        )
        self.assertEqual(io[0]["virtual_ns"], "1007")
        self.assertEqual(io[0]["mtime64"], "10")
        self.assertIsNone(io[1]["virtual_ns"])
        self.assertIsNone(io[3]["value32"])

    def test_marker_sequence_includes_all_three_hook_phases(self):
        p = self.run_case("markers")
        self.assertEqual(p.returncode, 0, p.stderr)
        rows = list(iter_clock_records(self.out / "markers.stdout"))
        markers = [r for r in rows if r["kind"].startswith("marker_")]
        self.assertEqual(len(markers), 15)
        self.assertEqual(
            [r["marker_seq"] for r in markers],
            ["1"] * 3 + ["2"] * 3 + ["3"] * 3 + ["4"] * 3 + ["5"] * 3,
        )
        self.assertEqual(markers[1]["sample64"], "101")

    def test_failures_cannot_finish_as_success(self):
        cases = {
            "duplicate": "request-order",
            "skip": "request-order",
            "order": "apply-order-or-range",
            "overflow": "apply-order-or-range",
            "cursor": "raw-cursor",
            "capacity": "pending-limit",
            "raw-limit": "raw-limit",
            "end-request": "request-state",
            "pending": "finish-pending",
            "nested": "apply-in-progress",
            "mismatch": "applied-mismatch",
            "no-injection": "request-disabled",
            "wrong-note-size": "note-layout",
            "epoch": "epoch-change",
            "note-unused": "note-layout",
            "mmio-missing": "finish-io",
            "mmio-mismatch": "mmio-pair",
            "mmio-repeat": "native-io-pending",
            "mmio-value": "native-value",
            "disabled-marker": "marker-order",
            "invalid-marker": "marker-order",
            "missing-marker": "finish-markers",
            "bad-abi": "configure",
            "bad-size": "configure",
            "bad-id": "configure",
            "sink": "sink-write",
            "footer-sink": "sink-write",
        }
        for name, reason in cases.items():
            with self.subTest(case=name):
                p = self.run_case(name)
                self.assertNotEqual(p.returncode, 0)
                self.assertIn(reason.encode(), p.stderr)
                if name in ("sink", "footer-sink"):
                    with self.assertRaises(ClockEvidenceError):
                        list(iter_clock_records(self.out / (name + ".stdout")))
                else:
                    rows = (
                        list(iter_clock_records(self.out / (name + ".stdout"))) if p.stdout else []
                    )
                    self.assertFalse(any(r["kind"] == "footer" and r["complete"] for r in rows))
