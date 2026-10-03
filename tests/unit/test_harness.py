import copy
import unittest

from psf_lab.harness import check_case


def queue_evidence():
    case = {"case_id": "queue_baseline", "expected_outcome": "normal", "parameters": {"count": 2}}
    events = []
    for phase in ["SEND", "RECEIVE"]:
        for value in range(2):
            events.append(
                {
                    "kind": "user",
                    "fields": {"case_id": "queue_baseline", "phase": phase, "message_id": value},
                }
            )
    events += [
        {"kind": k, "object_id": "queue:1", "fields": {}}
        for k in ["queue_create", "queue_send", "queue_send", "queue_receive", "queue_receive"]
    ]
    events.append({"kind": "user", "fields": {"case_id": "queue_baseline", "phase": "COMPLETE"}})
    trace = {
        "platform": {"name": "FreeRTOS", "schema": "1.2.0", "word_bytes": 4},
        "clock": {"frequency_hz": "10000000", "tick_hz": 1000},
        "quality": {"issues": []},
        "events": events,
    }
    oracle = {
        "case_id": "queue_baseline",
        "complete": True,
        "outcome": "normal",
        "transport_ok": True,
        "sent_ids": [0, 1],
        "received_ids": [0, 1],
        "mtime_hz": 10000000,
        "tick_hz": 1000,
    }
    return case, trace, oracle


class HarnessTests(unittest.TestCase):
    def test_valid_independent_evidence(self):
        self.assertEqual(check_case(*queue_evidence())["verdict"], "pass")

    def test_missing_oracle_id_fails(self):
        c, t, o = queue_evidence()
        o["received_ids"] = [0]
        self.assertEqual(check_case(c, t, o)["verdict"], "fail")

    def test_incomplete_capture_never_passes(self):
        for field in ["complete", "transport_ok"]:
            c, t, o = queue_evidence()
            o[field] = False
            result = check_case(c, t, o)
            self.assertNotEqual(result["verdict"], "pass")
            if field == "complete":
                self.assertIn("oracle_incomplete", result["issues"])

    def test_missing_marker_or_queue_event_fails(self):
        for kind in ["user", "queue_send", "queue_create"]:
            c, t, o = queue_evidence()
            t["events"] = [e for e in t["events"] if e["kind"] != kind]
            self.assertNotEqual(check_case(c, t, o)["verdict"], "pass")

    def test_loss_or_wrong_clock_never_passes(self):
        c, t, o = queue_evidence()
        damaged = copy.deepcopy(t)
        damaged["quality"]["issues"] = [{"code": "sequence_gap"}]
        self.assertNotEqual(check_case(c, damaged, o)["verdict"], "pass")
        t["clock"]["frequency_hz"] = "25000000"
        self.assertNotEqual(check_case(c, t, o)["verdict"], "pass")
