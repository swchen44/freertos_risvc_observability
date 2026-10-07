import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


class ContextReportCliTests(unittest.TestCase):
    def test_report_refuses_existing_output_without_touching_it(self):
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "output"
            output.mkdir()
            marker = output / "keep"
            marker.write_text("existing")
            result = subprocess.run(
                [
                    sys.executable,
                    "tools/tcp/analyze_context_batch.py",
                    "--formal",
                    str(Path(tmp) / "missing"),
                    "--output",
                    str(output),
                ],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Report output must be new", result.stderr)
            self.assertEqual(marker.read_text(), "existing")
