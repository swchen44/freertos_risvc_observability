import importlib
import unittest

from tests.unit.test_cost_attribution import owner
from tests.unit.test_hotspot_report import profile, rows_for


class HotspotEventsTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("psf_lab.hotspot_events"))
        self.iterate = importlib.import_module("psf_lab.hotspot_events").iter_hotspot_events

    def test_warm_cache_survives_context_switch(self):
        rows = rows_for([(100, 100, 4, "I")] * 2)
        contexts = [dict(start=0, end=1, context="task:A"), dict(start=1, end=2, context="irq:7")]
        items = list(self.iterate(rows, [owner(0, 512)], profile(), contexts=contexts))
        self.assertEqual([r["index"] for r in items], [0, 1])
        self.assertEqual([r["context"] for r in items], ["task:A", "irq:7"])
        self.assertEqual([r["memory_cycles"] for r in items], [27, 1])
        self.assertEqual(items[1]["cache"]["l1i"]["misses"], 0)
        self.assertEqual(sum(r["instructions"] for r in items), 2)

    def test_cross_line_write_and_snapshot_independence(self):
        rows = rows_for([(100, 0, 4, "R"), (100, 0, 4, "W"), (100, 62, 4, "R")])
        items = list(self.iterate(rows, [], profile(), contexts=None))
        self.assertEqual([r["cache"]["l1d"]["accesses"] for r in items], [1, 1, 2])
        self.assertEqual(items[1]["cost_cycles"]["ram_write"], 11)
        self.assertEqual(items[1]["cache"]["l2"]["accesses"], 1)
        self.assertEqual(items[0]["role"], "unresolved")
        self.assertTrue(all(r["context"] == "unknown" for r in items))

    def test_reject_missing_coverage_and_wrong_cost(self):
        rows = rows_for([(100, 100, 4, "I")])
        for contexts in [[], [dict(start=0, end=2, context="task:A")]]:
            with self.assertRaises(ValueError):
                list(self.iterate(rows, [], profile(), contexts=contexts))
        with self.assertRaises(ValueError):
            list(self.iterate([dict(rows[0], l1i=7)], [], profile(), contexts=None))
