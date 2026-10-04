"""Hand-computed timing examples; they do not use the replay to build expectations."""

import unittest

from psf_lab.cache_model import Geometry
from psf_lab.memory_timing import MemoryTiming, Region


def model(**kwargs):
    return MemoryTiming(
        l1i=Geometry(64, 64, 1),
        l1d=Geometry(64, 64, 1),
        l2=Geometry(128, 64, 1),
        regions=[Region("ram", 0, 4096, True, 80, 20, 8)],
        **kwargs,
    )


class TimingTests(unittest.TestCase):
    def test_cold_l1_hit_and_l2_hit_have_distinct_costs(self):
        cache = model()
        # Cold read: 1 + 8 + (80 + 64/8) = 97.
        self.assertEqual(cache.access(0, 4, "R")["total"], 97)
        self.assertEqual(cache.access(4, 4, "R")["total"], 1)
        self.assertEqual(cache.access(64, 4, "R")["total"], 97)
        # Line 0 evicted from L1 but still present in L2.
        self.assertEqual(cache.access(0, 4, "R")["total"], 9)

    def test_instruction_and_data_l1_share_l2_only(self):
        cache = model(l1i_cycles=2)
        self.assertEqual(cache.access(0, 4, "I")["total"], 98)
        self.assertEqual(cache.access(0, 4, "R")["total"], 9)
        self.assertEqual(cache.access(4, 4, "I")["total"], 2)

    def test_l2_eviction_requires_ram_again(self):
        cache = model()
        cache.access(0, 4, "R")
        cache.access(128, 4, "R")
        self.assertEqual(cache.access(0, 4, "R")["ram_read"], 88)

    def test_cross_line_access_pays_two_lookups_and_two_fills(self):
        cache = model()
        self.assertEqual(cache.access(62, 4, "R")["total"], 194)

    def test_write_allocate_and_write_through_not_free_stores(self):
        cache = model()
        # Fill 88, L1/L2 lookup 9, 4-byte write 20 + one beat = 21.
        self.assertEqual(cache.access(0, 4, "W")["total"], 118)
        self.assertEqual(cache.access(4, 4, "W")["total"], 30)
        self.assertEqual(cache.result()["ram_write_transactions"], 2)

    def test_uncached_region_bypasses_all_cache_levels(self):
        cache = MemoryTiming(regions=[Region("device_ram", 0, 4096, False, 80, 20, 8)])
        for _ in range(2):
            cost = cache.access(0, 4, "R")
            self.assertEqual(cost, dict(l1i=0, l1d=0, l2=0, ram_read=81, ram_write=0, total=81))
        self.assertEqual(cache.result()["l1d"]["accesses"], 0)

    def test_region_latencies_are_selected_by_address(self):
        cache = MemoryTiming(
            regions=[
                Region("fast", 0, 64, False, 10, 5, 8),
                Region("slow", 64, 128, False, 80, 20, 8),
            ]
        )
        self.assertEqual(cache.access(60, 8, "R")["total"], 92)

    def test_slower_ram_changes_only_ram_service_cost(self):
        fast = model()
        slow = MemoryTiming(
            l1i=Geometry(64, 64, 1),
            l1d=Geometry(64, 64, 1),
            l2=Geometry(128, 64, 1),
            regions=[Region("ram", 0, 4096, True, 160, 20, 8)],
        )
        for address in (0, 4, 64, 0):
            fast.access(address, 4, "R")
            slow.access(address, 4, "R")
        a, b = fast.result(), slow.result()
        self.assertEqual(
            b["estimated_memory_service_cycles"] - a["estimated_memory_service_cycles"], 160
        )
        self.assertEqual(a["l1d"], b["l1d"])
        self.assertEqual(a["l2"], b["l2"])

    def test_invalid_or_unmapped_access_is_rejected_before_state_changes(self):
        cache = model()
        for address, size, op in [
            (4094, 4, "R"),
            (-1, 4, "R"),
            (0, 0, "R"),
            (0, 4, "X"),
            (True, 4, "R"),
        ]:
            with self.subTest(address=address, size=size, op=op):
                before = cache.result()
                with self.assertRaises(ValueError):
                    cache.access(address, size, op)
                self.assertEqual(cache.result(), before)

    def test_overlapping_regions_and_invalid_profiles_are_rejected(self):
        with self.assertRaises(ValueError):
            MemoryTiming(
                regions=[Region("a", 0, 128, True, 1, 1, 8), Region("b", 64, 192, True, 1, 1, 8)]
            )
        for field in ("l1i_cycles", "l1d_cycles", "l2_cycles"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                model(**{field: -1})
        with self.assertRaises(ValueError):
            Region("ram", 0, 64, True, 1, 1, 0)
