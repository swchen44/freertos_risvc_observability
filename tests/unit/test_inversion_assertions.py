import unittest

from psf_lab.harness import compare_cases


def priority_run(case, inheritance=True):
    phases = (
        [
            "LOW_HOLD",
            "HIGH_ATTEMPT",
            "HIGH_BLOCKED",
            "LOW_RELEASE",
            "HIGH_ACQUIRED",
            "MEDIUM_END",
            "LOW_RESTORED",
        ]
        if case == "inheritance"
        else [
            "LOW_HOLD",
            "HIGH_ATTEMPT",
            "HIGH_BLOCKED",
            "MEDIUM_END",
            "LOW_RELEASE",
            "HIGH_ACQUIRED",
            "LOW_RESTORED",
        ]
    )
    events = (
        [
            {"kind": "task_prio_inherit", "object_id": "L", "fields": {"priority": 4}},
            {"kind": "task_prio_disinherit", "object_id": "L", "fields": {"priority": 2}},
        ]
        if case == "inheritance" and inheritance
        else []
    )
    return {
        "manifest": {
            "source_commit": "same",
            "mtime_hz": 10000000,
            "time_model": "qemu-icount",
            "status": "pass",
        },
        "case": {"case_id": case, "parameters": {"low_ticks": 2, "medium_ticks": 6}},
        "oracle": {
            "complete": True,
            "phases": [
                {"phase": p, "request_id": 2 if p == "LOW_RESTORED" else 0, "mtime": str(i * 1000)}
                for i, p in enumerate(phases)
            ],
        },
        "trace": {"events": events, "quality": {"issues": []}},
    }


class PriorityAssertionTests(unittest.TestCase):
    def test_boost_and_release_order(self):
        self.assertEqual(
            compare_cases("priority", [priority_run("inversion"), priority_run("inheritance")])[
                "verdict"
            ],
            "pass",
        )

    def test_missing_inheritance_is_not_success(self):
        r = compare_cases(
            "priority", [priority_run("inversion"), priority_run("inheritance", False)]
        )
        self.assertNotEqual(r["verdict"], "pass")
        self.assertIn("missing_inheritance_evidence", r["issues"])

    def test_loss_is_indeterminate(self):
        a, b = priority_run("inversion"), priority_run("inheritance")
        b["trace"]["quality"]["issues"] = [{"code": "sequence_gap"}]
        self.assertEqual(compare_cases("priority", [a, b])["verdict"], "indeterminate")

    def test_wrong_order_fails(self):
        a, b = priority_run("inversion"), priority_run("inheritance")
        b["oracle"]["phases"][3]["mtime"] = "99000"
        self.assertNotEqual(compare_cases("priority", [a, b])["verdict"], "pass")
