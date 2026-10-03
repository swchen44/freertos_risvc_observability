import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from psf_lab.runner import run_suite


class SuiteTests(unittest.TestCase):
    def test_timeout_still_records_all_21_attempts_and_fails(self):
        calls = []

        def fake_run(root, case_id, **kwargs):
            calls.append(case_id)
            p = kwargs["output_root"] / str(len(calls))
            p.mkdir()
            failed = len(calls) == 8
            (p / "manifest.json").write_text(
                json.dumps(
                    {
                        "case_id": case_id,
                        "status": "timeout" if failed else "pass",
                        "exit_code": 4 if failed else 0,
                    }
                )
            )
            return p

        with (
            tempfile.TemporaryDirectory() as directory,
            patch("psf_lab.runner.require_clean_tree", return_value="abc"),
            patch("psf_lab.runner.verify_environment", return_value={}),
            patch("psf_lab.runner.source_snapshot", return_value={}),
            patch("psf_lab.runner.check_session"),
            patch("psf_lab.runner.run_case", side_effect=fake_run),
            patch("psf_lab.runner.load_run", return_value={}),
            patch("psf_lab.runner.compare_cases", return_value={"verdict": "pass"}),
        ):
            root = Path(directory)
            r = run_suite(root, repeat=3)
            index = json.loads((r / "index.json").read_text())
            self.assertEqual(len(calls), 21)
            self.assertEqual(len(index["attempts"]), 21)
            self.assertEqual(index["verdict"], "fail")
