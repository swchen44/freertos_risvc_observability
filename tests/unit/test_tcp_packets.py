import struct
import unittest

from psf_lab.tcp_checksum import internet_checksum
from psf_lab.tcp_packets import decode_packet


def packet():
    addresses = bytes([10, 0, 0, 1, 10, 0, 0, 2])
    tcp = bytearray(struct.pack("!HHIIBBHHH", 1234, 50000, 42, 1001, 80, 16, 5840, 0, 0) + b"abc")
    pseudo = addresses + b"\0\6" + len(tcp).to_bytes(2, "big")
    tcp[16:18] = internet_checksum(pseudo + tcp).to_bytes(2, "big")
    ip = bytearray(struct.pack("!BBHHHBBH", 69, 0, 20 + len(tcp), 0, 0, 64, 6, 0) + addresses)
    ip[10:12] = internet_checksum(ip).to_bytes(2, "big")
    return bytes(ip + tcp)


class PacketTests(unittest.TestCase):
    def test_independent_packet_oracle(self):
        value = decode_packet(packet())
        self.assertEqual(value["payload"], b"abc")
        self.assertEqual(value["seq"], 42)
        self.assertEqual(value["ack"], 1001)

    def test_reject_corrupted_payload(self):
        raw = bytearray(packet())
        raw[-1] ^= 1
        with self.assertRaisesRegex(ValueError, "TCP checksum"):
            decode_packet(raw)

    def test_reject_truncation(self):
        with self.assertRaises(ValueError):
            decode_packet(packet()[:-1])
