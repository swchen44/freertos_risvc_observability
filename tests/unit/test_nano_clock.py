import copy
import unittest

from psf_lab.nano_clock import compare_nano


def fixture():
    control, active, receipts = [], [], []
    for i, delay in enumerate((10, 20, 50, 100, 1000)):
        control.append(dict(id=i, delay_ns=delay, repeats=1000, before=1000, after=2000, ticks=0))
        active.append(
            dict(id=i, delay_ns=delay, repeats=1000, before=1000, after=2000 + delay * 10, ticks=0)
        )
        receipts.append(dict(id=i, requests=1000, requested_ns=delay * 1000, insns=10000))
    return control, active, receipts


class NanoClockTests(unittest.TestCase):
    def test_full_delivery(self):
        c, a, r = fixture()
        self.assertTrue(compare_nano(c, a, r, r)["all_delays_reliable"])

    def test_completed_requests_can_all_be_lost(self):
        c, _, r = fixture()
        result = compare_nano(c, c, r, r)
        self.assertFalse(result["all_delays_reliable"])
        self.assertTrue(all(row["observed_extra_ns"] == 0 for row in result["rows"]))

    def test_partial_delivery_is_not_a_pass(self):
        c, a, r = fixture()
        a[0]["after"] -= 50
        self.assertFalse(compare_nano(c, a, r, r)["rows"][0]["reliable"])

    def test_changed_instruction_work_is_rejected(self):
        c, a, r = fixture()
        other = copy.deepcopy(r)
        other[0]["insns"] += 1
        with self.assertRaisesRegex(ValueError, "instruction"):
            compare_nano(c, a, r, other)

    def test_incomplete_requests_are_rejected(self):
        c, a, r = fixture()
        r[0]["requests"] -= 1
        with self.assertRaisesRegex(ValueError, "request"):
            compare_nano(c, a, r, r)

    def test_timer_interference_is_rejected(self):
        c, a, r = fixture()
        a[1]["ticks"] = 1
        with self.assertRaisesRegex(ValueError, "timer"):
            compare_nano(c, a, r, r)

    def test_clock_reversal_is_rejected(self):
        c, a, r = fixture()
        a[0]["after"] = 0
        with self.assertRaisesRegex(ValueError, "clock"):
            compare_nano(c, a, r, r)
