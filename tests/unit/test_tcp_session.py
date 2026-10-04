"""Independent transcript checks: reject corrupt delivery, ACK and cleanup claims."""

import copy
import unittest

from psf_lab.tcp_session import validate_session


def fixture():
    def event(direction, seq, ack, flags, payload=b""):
        return dict(direction=direction, seq=seq, ack=ack, flags=flags, payload=payload)

    packets = [event("rx", 1000, 0, 2), event("tx", 9000, 1001, 18), event("rx", 1001, 9001, 16)]
    client, server = 1001, 9001
    for round_id in range(2):
        request = bytes((round_id + i) % 256 for i in range(64))
        packets.append(event("rx", client, server, 24, request))
        client += 64
        for chunk in range(4):
            payload = bytes((i * 17 + round_id + chunk) % 256 for i in range(1460))
            packets.append(event("tx", server, client, 24, payload))
            server += 1460
            packets.append(event("rx", client, server, 16))
    packets.extend(
        [
            event("rx", client, server, 17),
            event("tx", server, client + 1, 16),
            event("tx", server, client + 1, 17),
            event("rx", client + 1, server + 1, 16),
        ]
    )
    metrics = dict(
        request_bytes=128,
        acked_bytes=11680,
        retained_bytes=0,
        peak_retained_bytes=1460,
        peer_closed=True,
        resources_before=[0] * 6,
        resources_after=[0] * 6,
        active_pcbs=0,
        timewait_pcbs=0,
    )
    return packets, metrics


class SessionTests(unittest.TestCase):
    def test_complete_bidirectional_session(self):
        packets, metrics = fixture()
        result = validate_session(packets, metrics)
        self.assertEqual(result["unique_response_bytes"], 11680)
        self.assertEqual(result["request_bytes"], 128)

    def test_wrong_payload_rejected_even_if_length_matches(self):
        packets, metrics = fixture()
        packets[4]["payload"] = bytes(1460)
        with self.assertRaisesRegex(ValueError, "payload"):
            validate_session(packets, metrics)

    def test_ack_beyond_transmitted_data_rejected(self):
        packets, metrics = fixture()
        packets[5]["ack"] += 1
        with self.assertRaisesRegex(ValueError, "ACK"):
            validate_session(packets, metrics)

    def test_missing_final_ack_rejected(self):
        packets, metrics = fixture()
        with self.assertRaises(ValueError):
            validate_session(packets[:-1], metrics)

    def test_resource_leak_and_retained_buffer_rejected(self):
        packets, metrics = fixture()
        for key, value in [
            ("retained_bytes", 1460),
            ("resources_after", [0, 1, 0, 0, 0, 0]),
            ("active_pcbs", 1),
            ("acked_bytes", 10000),
        ]:
            with self.subTest(key=key):
                broken = copy.deepcopy(metrics)
                broken[key] = value
                with self.assertRaises(ValueError):
                    validate_session(packets, broken)

    def test_unexpected_extra_packet_rejected(self):
        packets, metrics = fixture()
        with self.assertRaises(ValueError):
            validate_session(packets + [packets[-1]], metrics)
