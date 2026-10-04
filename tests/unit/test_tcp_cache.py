import unittest

from psf_lab.cache_model import Geometry
from psf_lab.tcp_cache import replay_split


class SplitCacheTests(unittest.TestCase):
    def test_instruction_data_share_l2_but_have_separate_l1(self):
        g = Geometry(128, 64, 1)
        result = replay_split([(0, 4, "I"), (0, 4, "R"), (4, 4, "I")], g, g, g)
        self.assertEqual(result["l1i"]["misses"], 1)
        self.assertEqual(result["l1d"]["misses"], 1)
        self.assertEqual(result["l2"]["accesses"], 2)
        self.assertEqual(result["l2"]["misses"], 1)

    def test_cross_line_store_and_cold_restart(self):
        g = Geometry(128, 64, 1)
        for _ in range(2):
            result = replay_split([(62, 4, "W")], g, g, g)
            self.assertEqual(result["l1d"]["write_misses"], 2)
            self.assertEqual(result["l2"]["misses"], 2)
            self.assertEqual(result["l1d"]["spatial"]["observed_used_bytes"], 4)

    def test_reject_unknown_access(self):
        with self.assertRaises(ValueError):
            replay_split([(0, 4, "X")])
