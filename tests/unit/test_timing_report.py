"""Exercise actual compressed trace replay and evidence integrity checks."""

import gzip
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from psf_lab.timing_report import replay_run

ROOT = Path(__file__).resolve().parents[2]


class TimingReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.run = Path(self.temp.name)
        self.profile = json.loads((ROOT / "cases/timing/illustrative-ram.json").read_text())
        trace = "phase,pc,address,size,operation\n"
        trace += "0,2147483648,2147483648,4,I\n"
        trace += "0,2147483648,2147483712,4,R\n"
        trace += "0,2147483652,2147483652,4,I\n"
        trace += "0,2147483656,2147483712,4,W\n"
        with gzip.open(self.run / "accesses.csv.gz", "wt") as f:
            f.write(trace)
        (self.run / "symbols.txt").write_text(
            "80000000 00000004 T z0_stack_begin\n"
            "80000004 00000004 T z0_stack_end\n"
            "80000008 00000004 T harness\n"
        )
        (self.run / "qemu.log").write_text("tcp_trace_complete=4,phases=1\n")
        self.seal()

    def seal(self):
        files = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in self.run.iterdir()
            if p.name != "manifest.json"
        }
        (self.run / "manifest.json").write_text(json.dumps(dict(files=files)))

    def test_stream_replay_separates_stack_and_harness(self):
        report = replay_run(self.run, self.profile)
        self.assertEqual(report["model"]["estimated_memory_service_cycles"], 225)
        self.assertEqual(report["scope_cost_cycles"], {"stack_window": 194, "harness": 31})
        self.assertEqual(report["stack_windows"], 1)
        self.assertFalse(report["model"]["guest_time_changed"])
        self.assertEqual(sum(r["total"] for r in report["functions"]), 225)

    def test_tampered_trace_is_rejected(self):
        with (self.run / "accesses.csv.gz").open("ab") as f:
            f.write(b"invalid")
        with self.assertRaisesRegex(ValueError, "hash"):
            replay_run(self.run, self.profile)

    def test_missing_completion_or_incomplete_capture_is_rejected(self):
        (self.run / "qemu.log").write_text("tcp_trace_complete=3,phases=1\n")
        self.seal()
        with self.assertRaisesRegex(ValueError, "completion"):
            replay_run(self.run, self.profile)

    def test_unsupported_write_policy_is_rejected(self):
        self.profile["write_policy"] = "write-back"
        with self.assertRaises(ValueError):
            replay_run(self.run, self.profile)
