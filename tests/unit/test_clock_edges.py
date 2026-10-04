"""Independent expectations for clock API boundaries, including negative cases."""

import unittest

from psf_lab.clock_edges import validate_edges


def fixture(enabled=True):
    phases, requests = [], []
    clock = 1000
    for i, delay in enumerate((1000000, 2000000, 0, 3000000, 1000000)):
        before = clock
        clock += (delay // 100 if enabled else 0) + 10
        phases.append(
            dict(
                id=i,
                before_mtime=before,
                after_mtime=clock,
                before_tick=4 if i == 4 else 0,
                after_tick=(5 if enabled else 4) if i == 4 else 0,
            )
        )
        requests.append(
            dict(
                id=i,
                delay_ns=delay,
                anchor_ns=before * 100,
                target_ns=0 if i == 2 else before * 100 + delay,
                applied=enabled,
                wfi_before=1 if i == 4 else 0,
            )
        )
        clock += 10000
    measurement = dict(
        phases=phases,
        masked_pending=enabled,
        restored_tick_delta=3 if enabled else 0,
        observer_after_restore=enabled,
        wfi_delta_mtime=9900,
        wfi_tick_delta=1,
    )
    receipt = dict(requests=requests, idle=0, resume=0, wfi_count=1, wfi_span_insns=500)
    return measurement, receipt


class ClockEdgesTests(unittest.TestCase):
    def test_enabled_guest_clock_irq_and_wfi(self):
        m, r = fixture()
        self.assertTrue(validate_edges(m, r, True)["passed"])

    def test_control_without_injection(self):
        m, r = fixture(False)
        self.assertTrue(validate_edges(m, r, False)["passed"])

    def test_no_timer_does_not_advance(self):
        m, r = fixture()
        m["phases"][0]["after_mtime"] = m["phases"][0]["before_mtime"] + 1
        with self.assertRaisesRegex(ValueError, "phase 0"):
            validate_edges(m, r, True)

    def test_stale_request_must_not_reverse_time(self):
        m, r = fixture()
        m["phases"][2]["after_mtime"] = m["phases"][2]["before_mtime"] - 1
        with self.assertRaisesRegex(ValueError, "monotonic"):
            validate_edges(m, r, True)

    def test_masked_irq_must_not_deliver_tick(self):
        m, r = fixture()
        m["phases"][3]["after_tick"] = 1
        with self.assertRaisesRegex(ValueError, "masked"):
            validate_edges(m, r, True)

    def test_restore_must_wake_task(self):
        m, r = fixture()
        m["observer_after_restore"] = False
        with self.assertRaisesRegex(ValueError, "restore"):
            validate_edges(m, r, True)

    def test_wfi_must_really_idle(self):
        m, r = fixture()
        r["requests"][4]["wfi_before"] = 0
        with self.assertRaisesRegex(ValueError, "WFI"):
            validate_edges(m, r, True)

    def test_target_must_match_guest_anchor(self):
        m, r = fixture()
        r["requests"][4]["target_ns"] -= 10000
        with self.assertRaisesRegex(ValueError, "target"):
            validate_edges(m, r, True)

    def test_shutdown_wfi_does_not_change_measured_window(self):
        m, r = fixture()
        r["wfi_count"] = 2
        self.assertTrue(validate_edges(m, r, True)["passed"])
