"""Boundary evidence for event packaging and failed batch publication."""

import copy
import csv
import gzip
import json
import runpy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from psf_lab.event_window import build_event_run, canonical, sha
from psf_lab.hotspot_report import build_hotspot_report
from psf_lab.parser.semantic import parse_trace
from tests.fixtures.binary import event, stream
from tests.unit import test_event_window as event_fixtures
from tests.unit.test_cost_attribution import owner
from tests.unit.test_hotspot_report import profile, rows_for


class EventContractTests(unittest.TestCase):
    def test_shifted_chunk_range_is_rejected(self):
        fixture = event_fixtures.EventWindowTests()
        fixture.setUp()
        try:
            manifest = fixture.build()
            bad = copy.deepcopy(manifest)
            bad["chunks"][1]["start"] = "1023"
            bad["chunks"][1]["end"] = "1024"
            with self.assertRaisesRegex(ValueError, "discontinuity"):
                fixture.m.validate_event_manifest(bad)
        finally:
            fixture.doCleanups()

    def test_failed_batch_preserves_receipt_without_published_catalog(self):
        script = Path(__file__).resolve().parents[2] / "tools/tcp/build_event_windows.py"
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "failed"
            with (
                patch.object(sys, "argv", [str(script), "--output", str(out)]),
                patch("psf_lab.hotspot_evidence.catalog_inputs", return_value=[{"run_id": "toy"}]),
                patch(
                    "psf_lab.event_window.build_event_run",
                    side_effect=ValueError("injected capture failure"),
                ),
                self.assertRaisesRegex(ValueError, "injected capture failure"),
            ):
                runpy.run_path(str(script), run_name="__main__")
            receipt = json.loads((out / "completion.json").read_text())
            self.assertFalse(receipt["passed"])
            self.assertEqual(receipt["runs"], [])
            self.assertFalse((out / "catalog.json").exists())

    def test_builder_preserves_same_capture_psf_clock_order_and_quality(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = root / "capture/raw.csv.gz"
            raw.parent.mkdir()
            rows = rows_for([(100, 100, 4, "I")])
            with gzip.open(raw, "wt", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            payload = stream(
                event(0x37, 7, 0xFFFFFFFE),
                event(0x37, 10, 2),
                event(0xFFF, 11, 2),
                event(0x37, 12, 3),
            )
            (raw.parent / "trace.psf").write_bytes(payload)
            entry = dict(
                run_id="A02-baseline-b1-1-1",
                workload="A02",
                variant="baseline",
                family="b1",
                mode=1,
                repeat=1,
            )
            report = build_hotspot_report(
                rows, [owner(0, 512)], profile(), identity=entry, contexts=None
            )
            report["source_lines"] = {}
            old = (
                root / "artifacts/verification/hotspot/formal" / entry["run_id"] / "report.json.gz"
            )
            old.parent.mkdir(parents=True)
            old.write_bytes(gzip.compress(canonical(report), mtime=0))
            source = dict(
                raw_path=raw,
                ranges=[owner(0, 512)],
                profile=profile(),
                contexts=None,
                evidence={"capture": "fixture"},
            )
            with patch("psf_lab.hotspot_evidence.load_hotspot_input", return_value=source):
                manifest = build_event_run(root, entry, root / "new-run")
            expected = parse_trace(payload)
            self.assertEqual(
                manifest["psf"],
                dict(
                    clock=expected["clock"],
                    events=expected["events"],
                    quality=expected["quality"],
                    sha256=sha(payload),
                ),
            )
            self.assertEqual([e["sequence"] for e in manifest["psf"]["events"]], [7, 10, 11, 12])
            self.assertEqual([e["ticks"] for e in manifest["psf"]["events"]], ["0", "4", "4", "5"])
            self.assertEqual(manifest["psf"]["clock"]["origin_ticks"], str(0xFFFFFFFE))
            self.assertIn("sequence_gap", [i["code"] for i in manifest["psf"]["quality"]["issues"]])
            self.assertTrue(manifest["parity"]["passed"])
