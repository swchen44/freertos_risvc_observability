import unittest
from pathlib import Path

from psf_lab.harness import compare_cases
from psf_lab.runner import load_run, run_case

ROOT = Path(__file__).resolve().parents[2]


class InversionPairTests(unittest.TestCase):
    def test_real_priority_pair(self):
        runs = [
            load_run(run_case(ROOT, c, output_root=ROOT / "runs/local"))
            for c in ["inversion", "inheritance"]
        ]
        result = compare_cases("priority", runs)
        self.assertEqual(result["verdict"], "pass", result)
