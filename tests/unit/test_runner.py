import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from psf_lab.runner import allocate_run, run_guest, validate_case_id


class RunnerTests(unittest.TestCase):
    def test_allowlist(self):
        for name in ["../queue_baseline", "unknown", "queue_baseline;id"]:
            with self.assertRaises(ValueError):
                validate_case_id(name)
        validate_case_id("queue_baseline")

    def test_unique_run_directories(self):
        with tempfile.TemporaryDirectory() as d:
            a = allocate_run(Path(d), "queue_baseline")
            b = allocate_run(Path(d), "queue_baseline")
            self.assertNotEqual(a, b)
            self.assertTrue(a.is_dir() and b.is_dir())

    def test_timeout_keeps_manifest_console_and_nonzero(self):
        with tempfile.TemporaryDirectory() as d:
            run = Path(d)
            with patch(
                "psf_lab.runner.subprocess.run",
                side_effect=subprocess.TimeoutExpired(["qemu"], 1, stderr=b"timeout detail"),
            ):
                manifest = run_guest(run, ["qemu"], timeout_s=1, manifest={})
            self.assertEqual(manifest["exit_code"], 4)
            self.assertEqual(manifest["status"], "timeout")
            self.assertTrue((run / "console.log").exists())
            self.assertEqual(json.loads((run / "manifest.json").read_text())["exit_code"], 4)
