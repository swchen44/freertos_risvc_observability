import struct
import unittest

from psf_lab.parser.errors import ParseError
from psf_lab.parser.semantic import parse_trace, resolve_kind
from tests.fixtures.binary import event, stream
from tests.unit.test_binary import FIXTURE


def name_event(handle, text, sequence=4, timestamp=90, width=4):
    payload = handle.to_bytes(width, "little") + text
    payload += bytes(-len(payload) % width)
    words = struct.unpack("<" + ("I" if width == 4 else "Q") * (len(payload) // width), payload)
    return event(3, sequence, timestamp, words, width)


class SemanticTests(unittest.TestCase):
    def test_sdk_no_task_sentinel_is_not_a_running_task(self):
        trace = parse_trace(stream(event(1, words=(2,))))
        self.assertIsNone(trace["events"][0]["actor_id"])
        self.assertFalse(any(o["address"] == "0x2" for o in trace["objects"]))

    def test_id_dispatch_uses_platform(self):
        self.assertEqual(resolve_kind("my_krnl", 0x20), "task_ready")
        self.assertEqual(resolve_kind("FreeRTOS", 0x20), "task_delete")
        self.assertEqual(resolve_kind("FreeRTOS", 0x25), "eventgroup_delete")

    def test_desktop_cycles_and_counter(self):
        trace = parse_trace(FIXTURE.read_bytes())
        self.assertEqual(
            [e["id"] for e in trace["events"]][9:], [0x20, 0x25, 0x61, 0x52, 0x62, 0x25] * 50
        )
        self.assertEqual(
            [e["fields"]["counter"] for e in trace["events"] if e["id"] == 0x52], list(range(50))
        )
        self.assertTrue(
            all(
                e["fields"]["message"].startswith("Counter: ")
                for e in trace["events"]
                if e["id"] == 0x52
            )
        )
        self.assertIn("Task2", [o["name"] for o in trace["objects"]])

    def test_wrap_and_equal_timestamp(self):
        trace = parse_trace(
            stream(event(0x37, 65535, 0xFFFFFFFE), event(0x37, 0, 2), event(0x37, 1, 2))
        )
        self.assertEqual([e["ticks"] for e in trace["events"]], ["0", "4", "4"])
        self.assertNotIn("sequence_gap", [i["code"] for i in trace["quality"]["issues"]])
        self.assertIn("less_than_one_wrap_between_events", trace["clock"]["assumptions"])

    def test_gap_invalidates_actor_until_switch(self):
        trace = parse_trace(
            stream(event(0x37, 5, 100), event(0x50, 7, 110, words=(9, 0)), event(0x37, 8, 120))
        )
        self.assertIsNone(trace["events"][1]["actor_id"])
        self.assertIn("sequence_gap", [i["code"] for i in trace["quality"]["issues"]])
        self.assertIsNotNone(trace["events"][2]["actor_id"])

    def test_object_address_reuse_does_not_merge_lifetimes(self):
        trace = parse_trace(
            stream(
                event(0x10, 5, 100, (7, 2)), event(0x20, 6, 110, (7,)), event(0x10, 7, 120, (7, 3))
            )
        )
        self.assertNotEqual(trace["events"][0]["object_id"], trace["events"][2]["object_id"])
        self.assertEqual([o["epoch"] for o in trace["objects"]], [0, 1])

    def test_name_padding_and_large_handle(self):
        large = 2**60 + 17
        trace = parse_trace(stream(name_event(large, b"A\0trailing", width=8), width=8))
        self.assertEqual(trace["objects"][0]["name"], "A")
        self.assertEqual(trace["objects"][0]["address"], hex(large))

    def test_unknown_event_preserves_payload(self):
        trace = parse_trace(stream(event(0xFFF, words=(3,))))
        self.assertEqual(trace["events"][0]["kind"], "unknown")
        self.assertEqual(trace["events"][0]["payload_hex"], "03000000")
        self.assertIn("unknown_event", [i["code"] for i in trace["quality"]["issues"]])

    def test_wrong_platform_schema_is_rejected(self):
        data = bytearray(stream(event()))
        data[22] = 9
        with self.assertRaises(ParseError) as caught:
            parse_trace(bytes(data))
        self.assertEqual(caught.exception.code, "unsupported_schema")

    def test_malformed_known_event_is_rejected(self):
        with self.assertRaises(ParseError):
            parse_trace(stream(event(0x10, words=())))

    def test_unsupported_timer_has_no_derived_time(self):
        data = bytearray(stream(event()))
        struct.pack_into("<I", data, 32, 3)
        trace = parse_trace(bytes(data))
        self.assertIsNone(trace["events"][0]["ticks"])
        self.assertIn("unsupported_timer", [i["code"] for i in trace["quality"]["issues"]])

    def test_poc_user_event_fields(self):
        message = b"POC|queue_baseline|SEND|%u\0"
        payload = struct.pack("<II", 4, 7) + message
        payload += bytes(-len(payload) % 4)
        words = struct.unpack("<" + "I" * (len(payload) // 4), payload)
        trace = parse_trace(stream(name_event(4, b"POC\0"), event(0x92, 5, 100, words)))
        fields = trace["events"][-1]["fields"]
        self.assertEqual(fields["case_id"], "queue_baseline")
        self.assertEqual(fields["phase"], "SEND")
        self.assertEqual(fields["message_id"], 7)
        self.assertEqual(fields["channel"], "POC")

    def test_unresolved_fixed_string_is_reported(self):
        trace = parse_trace(stream(event(0x99, words=(4, 5, 7))))
        self.assertIn("unresolved_string", [i["code"] for i in trace["quality"]["issues"]])

    def test_literal_percent_and_negative_integer(self):
        message = b"value=%d %%\0"
        payload = struct.pack("<II", 4, 0xFFFFFFFF) + message
        payload += bytes(-len(payload) % 4)
        words = struct.unpack("<" + "I" * (len(payload) // 4), payload)
        trace = parse_trace(stream(event(0x92, words=words)))
        self.assertEqual(trace["events"][0]["fields"]["message"], "value=-1 %")
        self.assertNotIn("unsupported_format", trace["events"][0]["quality"])

    def test_unsupported_format_is_kept_literal(self):
        message = b"value=%n\0"
        payload = struct.pack("<II", 4, 1) + message
        payload += bytes(-len(payload) % 4)
        words = struct.unpack("<" + "I" * (len(payload) // 4), payload)
        trace = parse_trace(stream(event(0x92, words=words)))
        self.assertEqual(trace["events"][0]["fields"]["message"], "value=%n")
        self.assertIn("unsupported_format", trace["events"][0]["quality"])
