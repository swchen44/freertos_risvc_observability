"""Reject lossy or malformed evidence before any causal analysis."""

import copy
import gzip
import json
import tempfile
import unittest
from pathlib import Path

from psf_lab.clock_anchor_wire import (
    ClockEvidenceError,
    ClockUnavailable,
    decimal,
    iter_access_rows,
    iter_clock_records,
    mtime_quantum,
)
from psf_lab.parser.semantic import parse_trace
from tests.fixtures.clock_anchor import minimal_wire, psf_markers, record, write_wire


class WireTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.temp = Path(self.directory.name)

    def test_canonical_integer_and_field_range(self):
        for value, expected in (
            ("0", 0),
            ("18446744073709551615", (1 << 64) - 1),
            ("9" * 40, int("9" * 40)),
        ):
            self.assertEqual(decimal(value), expected)
        for value in (True, -1, 1, "", "01", "+1", " 1", "1\n", "9" * 41, "١"):
            with self.subTest(value=value), self.assertRaises(ClockEvidenceError):
                decimal(value)
        self.assertEqual(decimal("255", bits=8), 255)
        with self.assertRaises(ClockEvidenceError):
            decimal("256", bits=8)

    def test_offset_wrap_and_signed_clock_edge(self):
        self.assertEqual(mtime_quantum(3, 1, 10_000_000), (200, 300))
        self.assertEqual(mtime_quantum(1, (1 << 64) - 1, 10_000_000), (200, 300))
        q = ((1 << 63) - 1) // 100
        self.assertEqual(mtime_quantum(q, 0, 10_000_000), (q * 100, 1 << 63))
        for t, d in ((True, 0), (-1, 0), (1 << 64, 0), (0, -1), (0, 1 << 64), (q + 1, 0)):
            with self.subTest(t=t, d=d), self.assertRaises(ClockEvidenceError):
                mtime_quantum(t, d, 10_000_000)
        for hz in (0, 1_000_000):
            with self.assertRaises(ClockUnavailable):
                mtime_quantum(3, 1, hz)
        with self.assertRaises(ClockEvidenceError):
            mtime_quantum(3, 1, True)

    def test_plain_and_gzip_preserve_wire_strings(self):
        rows = minimal_wire()
        path = self.temp / "clock.jsonl"
        write_wire(path, rows)
        zipped = self.temp / "clock.jsonl.gz"
        zipped.write_bytes(gzip.compress(path.read_bytes()))
        self.assertEqual(list(iter_clock_records(path)), rows)
        self.assertEqual(list(iter_clock_records(zipped)), rows)

    def test_json_number_limits_and_truncated_gzip_are_evidence_errors(self):
        path = self.temp / "huge-number.jsonl"
        path.write_bytes(b'{"record_seq":' + b"9" * 5000 + b"}\n")
        with self.assertRaises(ClockEvidenceError):
            list(iter_clock_records(path))
        zipped = self.temp / "broken.jsonl.gz"
        zipped.write_bytes(gzip.compress(b"{}\n")[:-6])
        with self.assertRaises(ClockEvidenceError):
            list(iter_clock_records(zipped))

    def test_duplicate_keys_truncation_and_line_limit(self):
        for data in (
            b'{"kind":"header","kind":"footer"}\n',
            b'{"schema":"clock-anchor-record-v1"}',
            b"\xff\n",
            b"{}\n\n",
            b"x" * 16385 + b"\n",
            b"[]\n",
            b'{"x":NaN}\n',
            b'{"x":Infinity}\n',
            b"{}\r\n",
        ):
            with self.subTest(data=data[:40]):
                path = self.temp / "bad.jsonl"
                path.write_bytes(data)
                with self.assertRaises(ClockEvidenceError):
                    list(iter_clock_records(path))

    def test_line_limit_includes_lf_and_reader_is_lazy(self):
        line = json.dumps(minimal_wire()[0]).encode() + b"\n"
        path = self.temp / "bounded.jsonl"
        path.write_bytes(line + b"bad\n")
        records = iter_clock_records(path, max_line_bytes=len(line))
        self.assertEqual(next(records)["kind"], "header")
        with self.assertRaises(ClockEvidenceError):
            next(records)
        with self.assertRaises(ClockEvidenceError):
            list(iter_clock_records(path, max_line_bytes=len(line) - 1))

    def test_schema_types_and_unknown_keys_fail_closed(self):
        mutations = (
            {"cpu": "1"},
            {"schema": "other"},
            {"record_seq": 0},
            {"injection_enabled": 1},
            {"marker_mode": "2"},
            {"qemu_sha256": "Z" * 64},
            {"surprise": "1"},
            {"kind": "future"},
            {"phase": "instruction_before"},
            {"run_id": "bad\nrun"},
            {"abi_version": "2"},
        )
        for changes in mutations:
            rows = minimal_wire()
            rows[0].update(changes)
            with self.subTest(changes=changes), self.assertRaises(ClockEvidenceError):
                path = self.temp / "schema.jsonl"
                write_wire(path, rows)
                list(iter_clock_records(path))
        rows = minimal_wire()
        del rows[0]["clock_domains"]
        write_wire(self.temp / "missing", rows)
        with self.assertRaises(ClockEvidenceError):
            list(iter_clock_records(self.temp / "missing"))

    def test_mmio_plugin_cannot_claim_native_clock(self):
        row = record(
            "mtime_read",
            2,
            1,
            "memory_after_success",
            source="plugin",
            native_io_seq="1",
            pc="2147483648",
            address="33603576",
            size="4",
            virtual_ns=None,
            timebase_hz=None,
            time_delta=None,
            mtime64=None,
            value32=None,
        )
        path = self.temp / "io.jsonl"
        write_wire(path, [row])
        self.assertEqual(list(iter_clock_records(path)), [row])
        bad = copy.deepcopy(row)
        bad["virtual_ns"] = "0"
        write_wire(path, [bad])
        with self.assertRaises(ClockEvidenceError):
            list(iter_clock_records(path))

    def test_request_has_no_clock_and_ns_is_signed_range(self):
        row = record(
            "cost_request",
            2,
            1,
            "instruction_before",
            request_id="1",
            request_event_index="0",
            delta_ns="2",
            request_clock_ns=None,
            pc="2147483648",
        )
        path = self.temp / "request.jsonl"
        write_wire(path, [row])
        self.assertEqual(list(iter_clock_records(path)), [row])
        for delta, clock in (("0", None), (str(1 << 63), None), ("2", "0")):
            bad = dict(row, delta_ns=delta, request_clock_ns=clock)
            write_wire(path, [bad])
            with self.assertRaises(ClockEvidenceError):
                list(iter_clock_records(path))

    def test_raw_csv_strict_schema_ranges_and_gzip(self):
        data = (
            b"pc,address,size,operation,l1i,l1d,l2,ram_read,ram_write\n"
            b"2147483648,2147483648,4,I,1,0,8,10,0\n"
            b"2147483652,2147491840,4,R,0,1,0,0,0\n"
        )
        path = self.temp / "accesses.csv"
        path.write_bytes(data)
        expected = [
            dict(
                index=0,
                pc=2147483648,
                address=2147483648,
                size=4,
                operation="I",
                l1i=1,
                l1d=0,
                l2=8,
                ram_read=10,
                ram_write=0,
            ),
            dict(
                index=1,
                pc=2147483652,
                address=2147491840,
                size=4,
                operation="R",
                l1i=0,
                l1d=1,
                l2=0,
                ram_read=0,
                ram_write=0,
            ),
        ]
        self.assertEqual(list(iter_access_rows(path)), expected)
        zipped = self.temp / "accesses.csv.gz"
        zipped.write_bytes(gzip.compress(data))
        self.assertEqual(list(iter_access_rows(zipped)), expected)
        for bad in (
            data.replace(b",I,", b",X,"),
            data.replace(b",1,0,8,", b",-1,0,8,"),
            data.replace(b",4,I,", b",3,I,"),
            data + b"1,2\n",
            data.replace(b"operation,", b"wrong,"),
            data.replace(b",4,R,", b",0,R,"),
        ):
            with self.subTest(data=bad[:80]), self.assertRaises(ClockEvidenceError):
                path.write_bytes(bad)
                list(iter_access_rows(path))

    def test_handpacked_psf_preserves_wrap_payload_and_offsets(self):
        trace = parse_trace(psf_markers(base=(1 << 32) - 25, sequence_start=65533))
        events = [e for e in trace["events"] if e["kind"] == "user_event_fixed"]
        self.assertEqual(len(events), 5)
        self.assertEqual(events[0]["fields"]["arguments"], ["1", "1", "4294967281", "0"])
        self.assertEqual(events[2]["fields"]["arguments"], ["3", "3", "5", "1"])
        self.assertEqual(events[0]["timestamp_raw"], 4294967282)
        self.assertEqual(events[2]["timestamp_raw"], 6)
        self.assertEqual(events[0]["sequence"], 65535)
        self.assertEqual(events[1]["sequence"], 0)
        self.assertEqual(events[1]["offset"] - events[0]["offset"], 32)
        self.assertEqual(trace["quality"]["issues"], [])
