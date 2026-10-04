import unittest

from psf_lab.cache_suites import suite_spec


class SuiteTests(unittest.TestCase):
    def test_legacy_matrix_contract(self):
        spec = suite_spec('matrix')
        self.assertEqual(spec['checksum'], 8394752)
        self.assertEqual(spec['operations'], 16384)
        self.assertEqual(len(spec['variants']), 2)

    def test_layout_same_work(self):
        spec = suite_spec('layout')
        self.assertEqual(spec['checksum'], sum(4*i+4 for i in range(256)))
        self.assertEqual(spec['operations'], 256*2*2*2)
        self.assertEqual(spec['allocated_bytes'], 256*16*4)
        self.assertEqual(spec['hot_bytes'], 256*2*4)
        self.assertEqual(set(spec['variants']), {'cache_aos', 'cache_soa', 'cache_hotcold'})

    def test_unknown_rejected(self):
        with self.assertRaises(ValueError):
            suite_spec('../../other')

    def test_caller_cannot_mutate_contract(self):
        suite_spec('layout')['variants']['cache_aos'] = 'changed'
        self.assertEqual(suite_spec('layout')['variants']['cache_aos'], 'AoS')
