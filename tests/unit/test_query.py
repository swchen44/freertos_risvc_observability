import unittest

from psf_lab.analysis import analyze
from psf_lab.query import query_events, query_view
from tests.fixtures.query_trace import trace_250
from tests.fixtures.semantic_traces import schedule_trace


class QueryTests(unittest.TestCase):
    def test_half_open_numeric_sort_and_page(self):
        p = query_events(
            trace_250(),
            {"start_ticks": "10", "end_ticks": "240"},
            [{"field": "ticks", "direction": "desc"}],
            limit=20,
        )
        self.assertEqual(p["total"], 230)
        self.assertEqual(len(p["rows"]), 20)
        self.assertEqual(p["rows"][0]["ticks"], "239")

    def test_actor_object_channel_and_literal_search(self):
        t = trace_250()
        self.assertEqual(
            query_events(
                t,
                {
                    "task_ids": ["A"],
                    "object_ids": ["queue"],
                    "channels": ["POC"],
                    "search": "含引號",
                },
                [],
            )["total"],
            125,
        )
        self.assertEqual(query_events(t, {"task_ids": ["queue"]}, [])["total"], 0)
        self.assertEqual(query_events(t, {"search": ".*"}, [])["total"], 0)

    def test_null_last_ties_and_large_ticks(self):
        t = trace_250()
        t["events"] = t["events"][:4]
        for e, v in zip(t["events"], [None, str(2**60), str(2**60 + 1), str(2**60)], strict=True):
            e["ticks"] = v
        r = query_events(t, {}, [{"field": "ticks", "direction": "desc"}])["rows"]
        self.assertEqual([e["offset"] for e in r], [2, 1, 3, 0])

    def test_invalid_query_rejected(self):
        for f, s in [
            ({"start_ticks": "20", "end_ticks": "10"}, []),
            ({"surprise": 1}, []),
            ({}, [{"field": "payload", "direction": "asc"}]),
            ({"task_ids": "A"}, []),
        ]:
            with self.assertRaises(ValueError):
                query_events(trace_250(), f, s)
        with self.assertRaises(ValueError):
            query_events(trace_250(), {}, [], limit=2001)

    def test_task_visibility_does_not_change_denominator(self):
        t = schedule_trace()
        t["objects"] = []
        view = query_view(t, analyze(t), {"start_ticks": "5", "end_ticks": "25", "task_ids": ["A"]})
        self.assertEqual(view["metrics"]["window_ticks"], "20")
        self.assertEqual(view["metrics"]["task_share"]["A"]["running_ticks"], "5")
        self.assertEqual(view["metrics"]["task_share"]["B"]["running_ticks"], "15")
        self.assertTrue(all(i["object_id"] == "A" for i in view["intervals"]))

    def test_empty_window_data_is_explicit(self):
        t = schedule_trace()
        t["events"] = []
        t["objects"] = []
        v = query_view(t, analyze(t), {})
        self.assertEqual(v["metrics"]["window_ticks"], "0")
        self.assertEqual(v["intervals"], [])
