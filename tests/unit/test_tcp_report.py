import json
import shutil
import tempfile
import unittest
from pathlib import Path

from psf_lab.tcp_report import analyze_run, load_transfer

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "runs/tcp-transfer-v2"


class TCPReportTests(unittest.TestCase):
    def test_real_capture_and_optimization(self):
        data = load_transfer(DATA)
        self.assertEqual(len(data["rows"]), 18)
        first = {r["variant"]: r for r in data["rows"] if r["repeat"] == 1 and r["kind"] == "send"}
        self.assertLess(first["tcp_copy3"]["instructions"], first["tcp_copy2"]["instructions"])
        self.assertLess(first["tcp_nocopy3"]["writes"], first["tcp_copy3"]["writes"])
        replayed = analyze_run(DATA / "tcp_nocopy3-1")
        self.assertEqual(replayed[0], first["tcp_nocopy3"])

    def test_missing_runs_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            shutil.copy2(DATA / "results.json", p / "results.json")
            manifest = json.loads((DATA / "manifest.json").read_text())
            manifest["runs"] = []
            (p / "manifest.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "nine"):
                load_transfer(p)
