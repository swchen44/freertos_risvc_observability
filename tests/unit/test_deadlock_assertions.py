import unittest

from psf_lab.harness import lock_graph


class DeadlockAssertionTests(unittest.TestCase):
    def evidence(self):
        return {
            "quality": {"issues": []},
            "events": [
                {"kind": k, "actor_id": a, "object_id": o, "quality": []}
                for k, a, o in [
                    ("mutex_take", "T1", "A"),
                    ("mutex_take", "T2", "B"),
                    ("mutex_take_block", "T1", "B"),
                    ("mutex_take_block", "T2", "A"),
                ]
            ],
        }

    def test_two_owner_wait_edges_prove_cycle(self):
        result = lock_graph(self.evidence())
        self.assertTrue(result["cycle"])
        self.assertEqual(result["status"], "known")

    def test_missing_edge_cannot_prove_deadlock(self):
        for i in range(4):
            t = self.evidence()
            t["events"].pop(i)
            self.assertFalse(lock_graph(t)["cycle"])

    def test_quiet_or_loss_never_proves_deadlock(self):
        t = self.evidence()
        t["events"] = []
        self.assertFalse(lock_graph(t)["cycle"])
        t = self.evidence()
        t["quality"]["issues"] = [{"code": "sequence_gap"}]
        self.assertEqual(lock_graph(t)["status"], "indeterminate")

    def test_give_breaks_cycle(self):
        t = self.evidence()
        t["events"].append(
            {"kind": "mutex_give", "actor_id": "T1", "object_id": "A", "quality": []}
        )
        self.assertFalse(lock_graph(t)["cycle"])
