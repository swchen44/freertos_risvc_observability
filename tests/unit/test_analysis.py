import copy
import unittest

from psf_lab.analysis import analyze
from tests.fixtures.semantic_traces import event, schedule_trace


class AnalysisTests(unittest.TestCase):
    def test_known_schedule_and_no_mutation(self):
        trace = schedule_trace()
        original = copy.deepcopy(trace)
        a = analyze(trace)
        m = a["metrics"]
        self.assertEqual(m["known_ticks"], "30")
        self.assertEqual(m["task_share"]["A"]["running_ticks"], "10")
        self.assertEqual(m["task_share"]["B"]["running_ticks"], "20")
        self.assertAlmostEqual(m["task_share"]["A"]["fraction"], 1 / 3)
        self.assertEqual(trace, original)

    def test_response_and_execution_are_distinct(self):
        t = schedule_trace()
        t["events"][1:1] = [
            event(5, "user_event", "A", "START"),
            event(6, "user_event", "A", "WORKER_BEGIN"),
        ]
        t["events"].insert(-1, event(25, "user_event", "B", "WORKER_END"))
        r = analyze(t)["requests"][0]
        self.assertEqual(r["response_ticks"], "20")
        self.assertEqual(r["execution_ticks"], "4")

    def test_unfinished_request_and_open_tail(self):
        t = schedule_trace()
        t["events"][-1] = event(30, "user_event", "B", "START")
        a = analyze(t)
        self.assertIsNone(a["requests"][0]["response_ticks"])
        self.assertIsNone(a["intervals"][-1]["end_ticks"])

    def test_gap_invalidates_adjacent_interval_until_switch(self):
        t = schedule_trace()
        t["events"].insert(1, event(5, "unknown", quality=["sequence_gap"]))
        a = analyze(t)
        self.assertEqual(a["metrics"]["unknown_ticks"], "10")
        self.assertEqual(a["metrics"]["known_ticks"], "20")

    def test_unknown_prefix_and_same_timestamp(self):
        t = schedule_trace()
        t["events"] = [
            event(0, "object_name"),
            event(5, "task_switch", "A"),
            event(5, "task_switch", "B"),
            event(30, "user_event", "B", "COMPLETE"),
        ]
        m = analyze(t)["metrics"]
        self.assertEqual(m["unknown_ticks"], "5")
        self.assertEqual(m["task_share"]["B"]["running_ticks"], "25")

    def test_empty_zero_frequency_and_large_ticks(self):
        t = schedule_trace()
        t["events"] = []
        self.assertEqual(analyze(t)["metrics"]["window_ticks"], "0")
        t = schedule_trace()
        t["clock"]["frequency_hz"] = "0"
        self.assertIsNone(analyze(t)["metrics"]["window_seconds"])
        t = schedule_trace()
        for e in t["events"]:
            e["ticks"] = str(int(e["ticks"]) + 2**40)
        self.assertEqual(analyze(t)["metrics"]["window_ticks"], "30")

    def test_object_epochs_and_unknown_actor(self):
        t = schedule_trace()
        t["events"][0]["actor_id"] = "addr:0"
        t["events"][1]["actor_id"] = "addr:1"
        self.assertEqual(set(analyze(t)["metrics"]["task_share"]), {"addr:0", "addr:1"})
        t["events"][1]["actor_id"] = None
        self.assertEqual(analyze(t)["metrics"]["unknown_ticks"], "20")
