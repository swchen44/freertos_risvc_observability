import json
import tempfile
import unittest
from pathlib import Path

from psf_lab.runner import check_run, run_case

ROOT = Path(__file__).resolve().parents[2]


class QueueE2ETests(unittest.TestCase):
    def test_formal_clean_queue_run(self):
        with tempfile.TemporaryDirectory() as directory:
            run = run_case(ROOT, "queue_baseline", output_root=Path(directory))
            manifest = json.loads((run / "manifest.json").read_text())
            self.assertEqual(manifest["exit_code"], 0, manifest.get("error"))
            self.assertEqual(check_run(run)["verdict"], "pass")
            self.assertFalse(manifest["source_dirty"])
            self.assertGreater(manifest["event_count"], 32)
