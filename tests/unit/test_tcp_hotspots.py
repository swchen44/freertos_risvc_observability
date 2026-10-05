import importlib.util
import unittest


class HotspotTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("psf_lab.tcp_hotspots"))
        from psf_lab.tcp_hotspots import rank_self_costs

        self.rank = rank_self_costs

    def test_self_cost_includes_data_access_pc_not_data_address(self):
        rows = [
            dict(pc=100, address=100, operation="I", l1i=1, l1d=0, l2=8, ram_read=18, ram_write=0),
            dict(pc=102, address=9999, operation="W", l1i=0, l1d=1, l2=8, ram_read=0, ram_write=11),
            dict(pc=110, address=110, operation="I", l1i=1, l1d=0, l2=0, ram_read=0, ram_write=0),
        ]
        result = self.rank(rows, [(100, 10, "checksum"), (110, 4, "caller")])
        self.assertEqual(result["total_cycles"], 48)
        self.assertEqual(result["functions"][0], dict(name="checksum", cycles=47, instructions=1))

    def test_end_exclusive_and_unresolved_are_not_attributed_to_previous_function(self):
        rows = [dict(pc=110, operation="I", l1i=1, l1d=0, l2=0, ram_read=0, ram_write=0)]
        result = self.rank(rows, [(100, 10, "checksum")])
        self.assertEqual(result["functions"][0]["name"], "assembly/unresolved")

    def test_stack_window_is_distinguished_from_harness(self):
        rows = [
            dict(pc=100, operation="I", l1i=1, l1d=0, l2=0, ram_read=0, ram_write=0),
            dict(pc=104, operation="W", l1i=0, l1d=1, l2=8, ram_read=0, ram_write=11),
            dict(pc=110, operation="I", l1i=1, l1d=0, l2=0, ram_read=0, ram_write=0),
        ]
        result = self.rank(
            rows, [(100, 10, "stack"), (110, 4, "harness")], stack_markers=(100, 110)
        )
        self.assertEqual(result["windows"], 1)
        self.assertEqual(
            result["scope_cycles"], dict(stack_window_including_preemption=21, harness_window=1)
        )
        with self.assertRaises(ValueError):
            self.rank(rows[:-1], [(100, 10, "stack")], stack_markers=(100, 110))
