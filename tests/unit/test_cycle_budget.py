"""Check frequency conversion against total-work arithmetic, not per-event rounding."""

import unittest

from psf_lab.cycle_budget import CycleBudget


class CycleBudgetTests(unittest.TestCase):
    def test_ten_cycles_at_500mhz(self):
        budget = CycleBudget(500_000_000)
        self.assertEqual(budget.add(10), 20)
        self.assertEqual(budget.elapsed_ns, 20)

    def test_fractional_cycles_carry_between_events(self):
        budget = CycleBudget(3_000_000_000)
        self.assertEqual([budget.add(1) for _ in range(6)], [0, 0, 1, 0, 0, 1])

    def test_partition_does_not_change_total(self):
        split, whole = CycleBudget(777_777_777), CycleBudget(777_777_777)
        chunks = [10, 27, 1, 10, 9, 1] * 1000
        self.assertEqual(sum(split.add(c) for c in chunks), whole.add(sum(chunks)))
        self.assertEqual(split.elapsed_ns, sum(chunks) * 1_000_000_000 // 777_777_777)

    def test_zero_cost_does_not_advance(self):
        self.assertEqual(CycleBudget(500_000_000).add(0), 0)

    def test_invalid_frequency(self):
        for value in (True, 0, -1, "500000000", 1.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                CycleBudget(value)

    def test_invalid_cost_preserves_state(self):
        budget = CycleBudget(3_000_000_000)
        budget.add(1)
        for value in (True, -1, 1.2):
            with self.subTest(value=value), self.assertRaises(ValueError):
                budget.add(value)
        self.assertEqual(budget.add(2), 1)

    def test_signed_ns_overflow_preserves_state(self):
        budget = CycleBudget(1_000_000_000)
        budget.add(4)
        with self.assertRaises(OverflowError):
            budget.add(2**63)
        self.assertEqual(budget.elapsed_ns, 4)
        self.assertEqual(budget.add(1), 1)
