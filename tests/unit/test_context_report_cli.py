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

    def test_duplicate_formal_entries_rejected_before_reading_capture(self):
        import json

        with TemporaryDirectory() as tmp:
            formal = Path(tmp) / "formal"
            formal.mkdir()
            row = dict(
                candidate="A02-baseline",
                mode=0,
                repeat=1,
                context_enabled=True,
                parity_passed=True,
                context_exact=True,
                run_manifest_sha256="a" * 64,
            )
            (formal / "completion.json").write_text(json.dumps(dict(passed=True, runs=[row] * 24)))
            result = subprocess.run(
                [
                    sys.executable,
                    "tools/tcp/analyze_context_batch.py",
                    "--formal",
                    str(formal),
                    "--output",
                    str(Path(tmp) / "new"),
                ],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Formal capture coverage mismatch", result.stderr)
