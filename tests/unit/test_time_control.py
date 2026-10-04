"""Validate guest-clock and scheduler effects independently of plugin claims."""

import copy
import unittest

from psf_lab.time_control import compare_probe


def fixture():
    control = dict(delta_mtime=100, immediate_mtime=1, delta_ticks=0, observer_woke=False)
    delayed = dict(delta_mtime=50100, immediate_mtime=50001, delta_ticks=5, observer_woke=True)
    return control, delayed


class TimeControlTests(unittest.TestCase):
    def test_guest_time_ticks_and_task_wakeup_all_advance(self):
        base, delayed = fixture()
        result = compare_probe(base, delayed, 5_000_000)
        self.assertEqual(result["additional_guest_ns"], 5_000_000)
        self.assertTrue(result["guest_clock_pass"])
        self.assertTrue(result["scheduler_pass"])

    def test_host_delay_without_guest_advance_is_rejected(self):
        base, _ = fixture()
        with self.assertRaisesRegex(ValueError, "guest clock"):
            compare_probe(base, base, 5_000_000)

    def test_guest_clock_without_ticks_is_rejected(self):
        base, delayed = fixture()
        delayed["delta_ticks"] = 0
        with self.assertRaisesRegex(ValueError, "timer"):
            compare_probe(base, delayed, 5_000_000)

    def test_tick_advance_without_task_wakeup_is_rejected(self):
        base, delayed = fixture()
        delayed["observer_woke"] = False
        with self.assertRaisesRegex(ValueError, "scheduler"):
            compare_probe(base, delayed, 5_000_000)

    def test_short_delay_does_not_require_two_tick_wakeup(self):
        base, _ = fixture()
        delayed = copy.deepcopy(base)
        delayed.update(delta_mtime=10100, immediate_mtime=10001, delta_ticks=1)
        self.assertTrue(compare_probe(base, delayed, 1_000_000)["guest_clock_pass"])
