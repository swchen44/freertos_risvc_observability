import importlib
import unittest

from psf_lab.hotspot_report import build_hotspot_report
from tests.unit.test_cost_attribution import owner
from tests.unit.test_hotspot_report import profile, rows_for


def report(variant="baseline", name="f"):
    identity = dict(run_id=variant, workload="A02", variant=variant, family="b1", mode=1, repeat=1)
    r = build_hotspot_report(
        rows_for([(100, 100, 4, "I")]),
        [owner(100, 104, function=name, source="firmware/f.c", object="/build/a.o")],
        profile(),
        identity=identity,
        contexts=None,
    )
    r["evidence"] = {"profile_sha256": "profile", "elf_sha256": variant, "task_objects": []}
    return r


class HotspotDashboardTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("psf_lab.hotspot_dashboard"))
        self.m = importlib.import_module("psf_lab.hotspot_dashboard")

    def test_unique_function_pair_and_unmatched(self):
        a, b = report(), report("pbuf")
        pair = self.m.pair_functions(a, b)
        self.assertEqual(pair[0]["status"], "matched")
        self.assertEqual(pair[0]["delta"]["memory_cycles"], 0)
        b["owners"][next(iter(b["owners"]))]["function"] = "other"
        self.assertTrue(all(p["delta"] is None for p in self.m.pair_functions(a, b)))

    def test_ambiguous_owner_not_merged(self):
        a, b = report(), report("pbuf")
        b["owners"]["duplicate"] = dict(next(iter(b["owners"].values())))
        pairs = self.m.pair_functions(a, b)
        self.assertEqual(pairs[0]["status"], "ambiguous")
        self.assertIsNone(pairs[0]["delta"])

    def test_bundle_rejects_mixed_workload_or_duplicate_run(self):
        a, b = report(), report("pbuf")
        self.assertEqual(self.m.build_workload_bundle([a, b])["workload"], "A02")
        with self.assertRaises(ValueError):
            self.m.build_workload_bundle([a, a, b])
        b["identity"]["workload"] = "A08"
        with self.assertRaises(ValueError):
            self.m.build_workload_bundle([a, b])

    def test_zero_baseline_and_mode_rejected(self):
        a, b = report(), report("pbuf")
        b["identity"]["mode"] = 0
        with self.assertRaises(ValueError):
            self.m.pair_functions(a, b)
