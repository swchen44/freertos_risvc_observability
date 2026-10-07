import unittest

from psf_lab import cost_attribution
from tests.unit.test_cost_attribution import owner


class AttributionReportTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(hasattr(cost_attribution, "aggregate_costs"))
        self.aggregate = cost_attribution.aggregate_costs
        self.ranges = cost_attribution.normalize_ranges(
            [owner(), owner(110, 114, role="runtime_library", object="libc.a(m.o)")]
        )
        self.rows = [
            dict(pc=100, address=100, operation="I", l1i=1, l1d=0, l2=8, ram_read=18, ram_write=0),
            dict(pc=102, address=110, operation="W", l1i=0, l1d=1, l2=8, ram_read=0, ram_write=11),
            dict(pc=110, address=110, operation="I", l1i=1, l1d=0, l2=0, ram_read=0, ram_write=0),
        ]

    def test_hand_computed_conservation(self):
        result = self.aggregate(self.rows, self.ranges, mode=1)
        self.assertEqual(result["totals"]["memory_cycles"], 48)
        self.assertEqual(result["totals"]["instructions"], 2)
        self.assertEqual(result["totals"]["accounted_model_ns"], 98)
        self.assertEqual(result["by_role"]["lwip"]["memory_cycles"], 47)
        self.assertEqual(result["by_role"]["lwip"]["instructions"], 1)
        for dimension in ("by_role", "by_function", "by_pc", "by_context", "matrix"):
            self.assertEqual(sum(r["memory_cycles"] for r in result[dimension].values()), 48)
        self.assertEqual(result["by_context"]["unknown"]["memory_cycles"], 48)
        self.assertEqual(result["context_quality"], "not_observed_in_A_trace")

    def test_unknown_cost_remains_in_denominator(self):
        rows = self.rows + [dict(self.rows[0], pc=999, l1i=7, l2=0, ram_read=0)]
        result = self.aggregate(rows, self.ranges, mode=1)
        self.assertEqual(result["totals"]["memory_cycles"], 55)
        self.assertEqual(result["by_role"]["lwip"]["shares"]["memory_cycles"]["denominator"], 55)
        self.assertEqual(result["unresolved"]["no_executable_owner"]["memory_cycles"], 7)

    def test_control_shadow_and_zero_denominator(self):
        result = self.aggregate([], self.ranges, mode=0)
        self.assertEqual(result["cost_semantics"], "shadow_model")
        self.assertNotIn("guest_elapsed_ns", result)
        self.assertIsNone(result["totals"]["shares"]["memory_cycles"]["percent"])

    def test_invalid_cost_or_operation_rejected(self):
        for value in (True, -1, 1.5, "1.2", "-1", " 1"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.aggregate([dict(self.rows[0], l1i=value)], self.ranges, mode=1)
        with self.assertRaises(ValueError):
            self.aggregate([dict(self.rows[0], operation="X")], self.ranges, mode=1)
        with self.assertRaises(ValueError):
            self.aggregate(self.rows, self.ranges, mode=True)

    def test_decimal_csv_values(self):
        rows = [{k: str(v) if isinstance(v, int) else v for k, v in r.items()} for r in self.rows]
        self.assertEqual(self.aggregate(rows, self.ranges, mode=1)["totals"]["memory_cycles"], 48)
