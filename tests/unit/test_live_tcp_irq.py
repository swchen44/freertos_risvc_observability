"""TCP timing checks must use TCP work and PSF task identities, not memory fixtures."""

import unittest

from psf_lab.live_cache_irq import compare_irq, validate_irq_trace


class TCPIRQTests(unittest.TestCase):
    def setUp(self):
        self.control = dict(
            before=100,
            after=3100,
            before_tick=0,
            ticks=0,
            work=11680,
            woke=0,
            observer_tick=0,
            observer_mtime=0,
        )
        self.active = dict(
            before=100,
            after=27100,
            before_tick=0,
            ticks=2,
            work=11680,
            woke=1,
            observer_tick=2,
            observer_mtime=22100,
        )
        self.ca = dict(operations=dict(I=299900), ns=2000000)
        self.aa = dict(operations=dict(I=309900), ns=2390000)

    def test_tcp_payload_completion_and_cost_conservation(self):
        result = compare_irq(self.control, self.active, self.ca, self.aa, scenario="tcp")
        self.assertEqual(result["extra_guest_ns"], 2400000)
        self.assertEqual(result["error_ns"], 0)

    def test_wrong_payload_total_rejected(self):
        with self.assertRaises(ValueError):
            compare_irq(
                self.control, dict(self.active, work=11679), self.ca, self.aa, scenario="tcp"
            )

    def test_tcp_psf_requires_tcp_session_resumption(self):
        def event(kind, timestamp, phase=None, request_id=0, object_id=None):
            return dict(
                kind=kind,
                timestamp_raw=timestamp,
                object_id=object_id,
                fields=dict(phase=phase, request_id=request_id),
            )

        trace = dict(
            objects=[
                dict(object_id="o", name="tcp_observer"),
                dict(object_id="w", name="tcp_session"),
            ],
            events=[
                event("user_event", 90, "TCP_SESSION_BEGIN"),
                event("task_switch", 22000, object_id="o"),
                event("user_event", 22200, "TCP_IRQ_OBSERVER", 2),
                event("task_switch", 22500, object_id="w"),
                event("user_event", 27200, "TCP_SESSION_END"),
                event("user_event", 28000, "COMPLETE"),
            ],
        )
        self.assertEqual(
            [s["name"] for s in validate_irq_trace(trace, self.active, scenario="tcp")],
            ["tcp_observer", "tcp_session"],
        )
        trace["objects"][1]["name"] = "cache_worker"
        with self.assertRaises(ValueError):
            validate_irq_trace(trace, self.active, scenario="tcp")

    def test_unknown_scenario_rejected(self):
        with self.assertRaises(ValueError):
            compare_irq(self.control, self.active, self.ca, self.aa, scenario="unknown")
