import json
import unittest
from pathlib import Path

from psf_lab.runner import SUITE_CASES, check_run

ROOT = Path(__file__).resolve().parents[2]


class CaseSuiteTests(unittest.TestCase):
    def test_committed_suite_has_21_verified_attempts(self):
        indexes = sorted((ROOT / "runs").glob("suite-*/index.json"))
        self.assertTrue(indexes, "No suite evidence; run the suite first")
        path = indexes[-1]
        index = json.loads(path.read_text())
        self.assertEqual(index["verdict"], "pass")
        self.assertEqual(len(index["attempts"]), 21)
        for case in SUITE_CASES:
            self.assertEqual(sum(a["case_id"] == case for a in index["attempts"]), 3)
        for attempt in index["attempts"]:
            self.assertEqual(check_run(path.parent / attempt["run_id"])["verdict"], "pass")
        self.assertEqual(len(index["comparisons"]), 9)
        self.assertTrue(all(c["verdict"] == "pass" for c in index["comparisons"]))
