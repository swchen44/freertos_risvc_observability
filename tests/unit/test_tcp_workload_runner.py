import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class WorkloadRunnerTests(unittest.TestCase):
    def test_invalid_matrix_options_rejected_before_build(self):
        for args, message in [
            (["--workload-id", "A01", "--tcp-workload", "fragmented"], "mutually exclusive"),
            (["--workload-id", "missing"], "Unknown workload"),
            (["--workload-id", "A01", "--tcp-variant", "checksum"], "baseline/pbuf"),
            (["--workload-id", "A01", "--cache-profile", "standard"], "small"),
        ]:
            with self.subTest(args=args):
                cmd = [
                    str(ROOT / ".venv/bin/python"),
                    str(ROOT / "tools/tcp/run_live_cache.py"),
                    "--qemu",
                    "/missing",
                    "--output",
                    "/missing",
                    "--case",
                    "tcp-irq",
                    "--cache-profile",
                    "small",
                    *args,
                ]
                result = subprocess.run(cmd, capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)
