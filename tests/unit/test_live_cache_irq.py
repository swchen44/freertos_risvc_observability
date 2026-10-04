"""IRQ acceptance must allow changed instruction paths, but reject missing wakeups."""

import importlib.util
import unittest


class LiveIRQTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(
            importlib.util.find_spec("psf_lab.live_cache_irq"), "IRQ validator not implemented"
        )
        from psf_lab.live_cache_irq import compare_irq, validate_mmio

        self.compare = compare_irq
        self.mmio = validate_mmio
        self.control = dict(
            before=100,
            after=2100,
            before_tick=0,
            ticks=0,
            work=210677760,
            woke=0,
            observer_tick=0,
            observer_mtime=0,
        )
        self.active = dict(
            before=100,
            after=34200,
            before_tick=0,
            ticks=3,
            work=210677760,
            woke=1,
            observer_tick=2,
            observer_mtime=20100,
        )
        self.ca = dict(operations=dict(I=199900), ns=1000000)
        self.aa = dict(operations=dict(I=209900), ns=3200000)

    def test_clock_conservation_accounts_for_extra_isr_instructions(self):
        result = self.compare(self.control, self.active, self.ca, self.aa)
        self.assertEqual(result["extra_guest_ns"], 3210000)
        self.assertEqual(result["extra_instruction_ns"], 10000)
        self.assertEqual(result["error_ns"], 0)

    def test_no_wakeup_or_no_ticks_is_rejected(self):
        for change in [
            dict(woke=0),
            dict(ticks=0),
            dict(observer_tick=1),
            dict(observer_mtime=99),
            dict(work=0),
        ]:
            with self.assertRaises(ValueError):
                self.compare(self.control, dict(self.active, **change), self.ca, self.aa)

    def test_time_cost_loss_is_rejected(self):
        with self.assertRaises(ValueError):
            self.compare(self.control, dict(self.active, after=30000), self.ca, self.aa)

    def test_unexpected_control_wakeup_is_rejected(self):
        with self.assertRaises(ValueError):
            self.compare(dict(self.control, woke=1), self.active, self.ca, self.aa)

    def test_only_clint_mtime_read_and_mtimecmp_write_are_exempt(self):
        self.mmio(0x0200BFF8, 4, "R")
        self.mmio(0x0200BFFC, 4, "R")
        self.mmio(0x02004000, 4, "W")
        self.mmio(0x02004004, 4, "W")
        for args in [
            (0x10000000, 4, "R"),
            (0x0200BFF8, 4, "W"),
            (0x02004000, 4, "R"),
            (0x02004004, 8, "W"),
        ]:
            with self.assertRaises(ValueError):
                self.mmio(*args)


class IRQPSFTests(unittest.TestCase):
    def setUp(self):
        from psf_lab import live_cache_irq

        self.assertTrue(
            hasattr(live_cache_irq, "validate_irq_trace"), "PSF task interval validator not exposed"
        )
        self.validate = live_cache_irq.validate_irq_trace
        self.m = dict(before=100, after=400, woke=1, observer_tick=2, observer_mtime=220)

        def event(kind, timestamp, phase=None, request_id=0, object_id=None):
            return dict(
                kind=kind,
                timestamp_raw=timestamp,
                object_id=object_id,
                fields=dict(phase=phase, request_id=request_id),
            )

        self.trace = dict(
            objects=[
                dict(object_id="o", name="cache_observer"),
                dict(object_id="w", name="cache_worker"),
            ],
            events=[
                event("user_event", 90, "IRQ_CACHE_BEGIN"),
                event("task_switch", 200, object_id="o"),
                event("user_event", 230, "IRQ_OBSERVER", 2),
                event("task_switch", 250, object_id="w"),
                event("user_event", 410, "IRQ_CACHE_END"),
                event("user_event", 500, "COMPLETE"),
            ],
        )

    def test_preempt_and_resume_interval_matches_guest(self):
        self.assertEqual(
            [s["name"] for s in self.validate(self.trace, self.m)],
            ["cache_observer", "cache_worker"],
        )

    def test_missing_resume_or_bad_guest_timestamp_rejected(self):
        with self.assertRaises(ValueError):
            self.validate(self.trace, dict(self.m, observer_mtime=260))
        self.trace["events"].pop(3)
        with self.assertRaises(ValueError):
            self.validate(self.trace, self.m)

    def test_wrong_marker_order_rejected(self):
        self.trace["events"][0], self.trace["events"][-2] = (
            self.trace["events"][-2],
            self.trace["events"][0],
        )
        with self.assertRaises(ValueError):
            self.validate(self.trace, self.m)
