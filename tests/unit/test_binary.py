import hashlib
import struct
import unittest
from pathlib import Path

from psf_lab.parser.binary import parse_binary
from psf_lab.parser.errors import ParseError
from tests.fixtures.binary import event, stream

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures/desktop/trace.psf"


class BinaryTests(unittest.TestCase):
    def test_desktop_boundaries_and_hash(self):
        data = FIXTURE.read_bytes()
        self.assertEqual(
            hashlib.sha256(data).hexdigest(),
            "32f6421362bda37e3b91411afedb5df0c29741f99fe1df08389cf76e56f79d47",
        )
        trace = parse_binary(data)
        self.assertEqual(trace["platform"]["word_bytes"], 8)
        self.assertEqual(trace["events"][0]["offset"], 152)
        self.assertEqual(len(trace["events"]), 309)
        self.assertEqual(trace["source"]["byte_length"], 7152)
        self.assertEqual(trace["quality"]["status"], "valid")

    def test_rv32_offsets_and_raw_payload(self):
        trace = parse_binary(stream(event()))
        self.assertEqual(trace["events"][0]["offset"], 72)
        self.assertEqual(trace["events"][0]["payload_hex"], "34120000")
        self.assertEqual(trace["events"][0]["id"], 0x25)

    def test_header_truncation_every_byte(self):
        data = stream()
        for length in range(32):
            with self.subTest(length=length), self.assertRaises(ParseError) as caught:
                parse_binary(data[:length])
            self.assertEqual(caught.exception.code, "truncated_header")

    def test_metadata_truncation_even_in_partial_mode(self):
        data = stream()
        for length in range(32, 72):
            with self.subTest(length=length), self.assertRaises(ParseError):
                parse_binary(data[:length], strict=False)

    def test_event_truncation_strict_and_partial(self):
        data = stream(event(), event(sequence=6, words=(7, 8)))
        for length in range(85, len(data)):
            with self.subTest(length=length):
                with self.assertRaises(ParseError):
                    parse_binary(data[:length])
                trace = parse_binary(data[:length], strict=False)
                self.assertEqual(len(trace["events"]), 1)
                self.assertEqual(trace["quality"]["status"], "partial")

    def test_wrong_magic_version_and_big_endian_are_rejected(self):
        for offset, value, code in (
            (0, b"BAD!", "invalid_magic"),
            (0, b"PSF\0", "unsupported_endianness"),
            (4, b"\x0d\0", "unsupported_version"),
            (12, struct.pack("<I", 0x302), "unsupported_cores"),
            (12, struct.pack("<I", 0x201), "unsupported_stream_mode"),
        ):
            data = bytearray(stream())
            data[offset : offset + len(value)] = value
            with self.subTest(code=code), self.assertRaises(ParseError) as caught:
                parse_binary(bytes(data))
            self.assertEqual(caught.exception.code, code)

    def test_unbounded_metadata_is_rejected(self):
        for args in ({"entry_count": 2**32 - 1}, {"symbol_size": 2**32 - 1}, {"states": 7}):
            with self.subTest(args=args), self.assertRaises(ParseError):
                parse_binary(stream(**args))

    def test_unknown_id_and_maximum_words_preserved(self):
        trace = parse_binary(stream(event(0xFFF, words=tuple(range(15)))))
        self.assertEqual(trace["events"][0]["id"], 0xFFF)
        self.assertEqual(len(bytes.fromhex(trace["events"][0]["payload_hex"])), 60)

    def test_entry_name_padding_keeps_raw_bytes(self):
        record = struct.pack("<IIIII", 0x1234, 1, 2, 3, 0) + b"A\0tail" + bytes(22)
        trace = parse_binary(stream(record, event(), entry_count=1))
        entry = trace["raw_metadata"]["entries"][0]
        self.assertEqual(entry["name"], "A")
        self.assertTrue(entry["symbol_hex"].startswith("41007461696c"))
        self.assertEqual(trace["events"][0]["offset"], 120)

    def test_zero_frequency_is_visible(self):
        trace = parse_binary(stream(event(), frequency=0))
        self.assertEqual(trace["clock"]["frequency_hz"], "0")
        self.assertIn("invalid_frequency", [i["code"] for i in trace["quality"]["issues"]])

    def test_restart_is_rejected_without_guessing(self):
        with self.assertRaises(ParseError) as caught:
            parse_binary(stream(event()) + stream(event()))
        self.assertEqual(caught.exception.code, "multiple_sessions")
