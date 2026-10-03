import copy
import unittest

from psf_lab.harness import compare_cases


def logger_run(case, response):
    return {
        "manifest": {
            "source_commit": "same",
            "mtime_hz": 10000000,
            "time_model": "qemu-icount",
            "status": "pass",
        },
        "case": {
            "case_id": case,
            "parameters": {"requests": 8, "worker_ticks": 2, "logger_ticks": 8},
        },
        "oracle": {
            "requests": [
                {
                    "request_id": i,
                    "start_mtime": str(i * 200000),
                    "end_mtime": str(i * 200000 + response),
                }
                for i in range(8)
            ],
            "phases": [
                {"phase": p, "request_id": i}
                for i in range(8)
                for p in ["WORKER_END", "LOGGER_END"]
            ],
        },
        "trace": {"events": [], "quality": {"issues": []}},
        "analysis": {},
    }


class LoggerAssertionTests(unittest.TestCase):
    def test_controlled_improvement(self):
        self.assertEqual(
            compare_cases(
                "logger", [logger_run("logger_bad", 100000), logger_run("logger_fixed", 20000)]
            )["verdict"],
            "pass",
        )

    def test_missing_work_fails(self):
        b, f = logger_run("logger_bad", 100000), logger_run("logger_fixed", 20000)
        f["oracle"]["requests"].pop()
        r = compare_cases("logger", [b, f])
        self.assertEqual(r["verdict"], "fail")
        self.assertIn("workload_mismatch", r["issues"])

    def test_no_improvement_or_different_work_fails(self):
        b, f = logger_run("logger_bad", 100000), logger_run("logger_fixed", 100000)
        self.assertEqual(compare_cases("logger", [b, f])["verdict"], "fail")
        f = copy.deepcopy(b)
        f["case"]["case_id"] = "logger_fixed"
        f["case"]["parameters"]["worker_ticks"] = 1
        self.assertEqual(compare_cases("logger", [b, f])["verdict"], "fail")

    def test_mixed_source_or_clock_fails(self):
        for key in ["source_commit", "mtime_hz", "time_model"]:
            b, f = logger_run("logger_bad", 100000), logger_run("logger_fixed", 20000)
            f["manifest"][key] = "different"
            self.assertEqual(compare_cases("logger", [b, f])["verdict"], "fail")
