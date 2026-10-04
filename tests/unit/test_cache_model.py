import unittest

from psf_lab.cache_model import Geometry, replay


class CacheModelTests(unittest.TestCase):
    def test_cold_warm_reads_writes(self):
        r = replay([(0, 4, 'R'), (4, 4, 'W'), (0, 4, 'R')], Geometry(128, 64, 1))
        self.assertEqual(r['l1']['read_misses'], 1)
        self.assertEqual(r['l1']['write_misses'], 0)
        self.assertEqual(r['l1']['accesses'], 3)

    def test_conflict_l2_retains(self):
        r = replay([(a, 4, 'R') for a in [0, 128, 0]], Geometry(128, 64, 1),
                   Geometry(256, 64, 2))
        self.assertEqual(r['l1']['misses'], 3)
        self.assertEqual(r['l2']['accesses'], 3)
        self.assertEqual(r['l2']['misses'], 2)

    def test_lru(self):
        r = replay([(a, 4, 'R') for a in [0, 64, 0, 128, 0, 64]], Geometry(128, 64, 2))
        self.assertEqual(r['l1']['misses'], 4)

    def test_cross_line_write_allocate(self):
        r = replay([(60, 8, 'W'), (64, 4, 'R')], Geometry(128, 64, 1))
        self.assertEqual(r['memory_operations'], 2)
        self.assertEqual(r['l1']['accesses'], 3)
        self.assertEqual(r['l1']['write_misses'], 2)
        self.assertEqual(r['l1']['read_misses'], 0)

    def test_empty_without_l2(self):
        r = replay([], Geometry(128, 64, 1))
        self.assertEqual(r['l1']['misses'], 0)
        self.assertIsNone(r['l1']['miss_rate'])
        self.assertIsNone(r['l2'])

    def test_invalid_geometry(self):
        for args in [(0, 64, 1), (128, 0, 1), (128, 64, 0), (192, 64, 1),
                     (64, 128, 1), (128, 64, -1)]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                Geometry(*args)

    def test_invalid_access(self):
        for event in [(-1, 4, 'R'), (0, 0, 'R'), (0, 4, 'X'), (2**64-1, 2, 'W')]:
            with self.subTest(event=event), self.assertRaises(ValueError):
                replay([event], Geometry(128, 64, 1))

    def test_line_sizes_must_match(self):
        with self.assertRaises(ValueError):
            replay([], Geometry(128, 64, 1), Geometry(256, 128, 1))

    def test_spatial_use_separates_evicted_and_resident(self):
        r = replay([(0, 4, 'R'), (64, 4, 'R')], Geometry(64, 64, 1))
        self.assertEqual(r['l1']['spatial']['evicted_unused_bytes'], 60)
        self.assertEqual(r['l1']['spatial']['resident_unobserved_bytes'], 60)
        self.assertEqual(r['l1']['spatial']['observed_utilization'], 4/64)

    def test_repeated_bytes_count_once_per_residency(self):
        r = replay([(0, 4, 'R'), (0, 4, 'W'), (4, 4, 'R')], Geometry(64, 64, 1))
        self.assertEqual(r['l1']['spatial']['observed_used_bytes'], 8)
