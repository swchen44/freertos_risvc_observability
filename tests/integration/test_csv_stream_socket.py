"""Regression: a corrupt later chunk must fail the actual HTTP transfer."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class CsvStreamSocketTests(unittest.TestCase):
    def test_late_corruption_cannot_look_like_successful_download(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "probe"
            process = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools/tcp/verify_csv_stream_faults.py"),
                    "--output",
                    str(out),
                ],
                cwd=ROOT,
                env=dict(os.environ, PYTHONPATH=str(ROOT / "src") + os.pathsep + str(ROOT)),
                capture_output=True,
                text=True,
                timeout=25,
            )
            self.assertEqual(process.returncode, 0, process.stderr[-3000:])
            receipt = json.loads((out / "receipt.json").read_text())
            self.assertTrue(receipt["passed"])
            self.assertTrue(receipt["server_stopped"])
            self.assertEqual([c["status"] for c in receipt["cases"]], ["200", "200", "503"])
            self.assertNotEqual(receipt["cases"][1]["exit"], 0)
