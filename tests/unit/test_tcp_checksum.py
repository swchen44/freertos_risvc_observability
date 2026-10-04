"""Independent RFC 1071 oracle against unmodified upstream implementations."""

import ctypes
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from psf_lab.tcp_checksum import internet_checksum

ROOT = Path(__file__).resolve().parents[2]


class ChecksumTests(unittest.TestCase):
    def test_rfc1071_example(self):
        self.assertEqual(internet_checksum(bytes.fromhex("0001f203f4f5f6f7")), 0x220D)
        self.assertEqual(internet_checksum(b""), 0xFFFF)
        self.assertEqual(internet_checksum(b"\x01"), 0xFEFF)
        self.assertEqual(internet_checksum(b"\xff" * 1460), 0)

    def test_upstream_algorithms_alignment_and_lengths(self):
        source = ROOT / "references/tcp/lwip"
        with tempfile.TemporaryDirectory() as tmp:
            for algorithm in (1, 2, 3):
                library = Path(tmp) / f"checksum{algorithm}.so"
                subprocess.run(
                    [
                        "cc",
                        "-shared",
                        "-fPIC",
                        "-O2",
                        "-fno-strict-aliasing",
                        f"-DLWIP_CHKSUM_ALGORITHM={algorithm}",
                        "-I" + str(ROOT / "firmware/tcp"),
                        "-I" + str(source / "src/include"),
                        str(source / "src/core/inet_chksum.c"),
                        str(source / "src/core/def.c"),
                        "-o",
                        str(library),
                    ],
                    check=True,
                    capture_output=True,
                )
                checksum = ctypes.CDLL(str(library)).inet_chksum
                checksum.argtypes = [ctypes.c_void_p, ctypes.c_uint16]
                checksum.restype = ctypes.c_uint16
                data = bytes((i * 17 + 31) % 256 for i in range(1608))
                buffer = ctypes.create_string_buffer(data)
                for offset in range(8):
                    for length in (*range(65), 127, 128, 255, 511, 1459, 1460, 1500, 1600):
                        with self.subTest(algorithm=algorithm, offset=offset, length=length):
                            value = checksum(ctypes.addressof(buffer) + offset, length)
                            network = int.from_bytes(value.to_bytes(2, sys.byteorder), "big")
                            self.assertEqual(
                                network, internet_checksum(data[offset : offset + length])
                            )
