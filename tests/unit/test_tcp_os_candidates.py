"""Candidate C functions vs independent byte oracle and real pbuf chains."""

import ctypes
import random
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class OsCandidateTests(unittest.TestCase):
    def test_checksum_alignment_tail_and_carry(self):
        source = ROOT / "firmware/tcp_stack/os_checksum.c"
        self.assertTrue(source.exists(), "Endpoint checksum candidate not implemented")
        with tempfile.TemporaryDirectory() as tmp:
            lib = Path(tmp) / "checksum.so"
            subprocess.run(
                [
                    "cc",
                    "-shared",
                    "-fPIC",
                    "-Os",
                    "-fno-strict-aliasing",
                    str(source),
                    "-o",
                    str(lib),
                ],
                check=True,
            )
            fn = ctypes.CDLL(str(lib)).poc_endpoint_chksum
            fn.argtypes = [ctypes.c_void_p, ctypes.c_int]
            fn.restype = ctypes.c_uint16
            rng = random.Random(8332)
            for length in [*range(80), 127, 255, 511, 1460, 1461, 8192, 65535]:
                for offset in range(4):
                    for data in (rng.randbytes(length), b"\xff" * length):
                        buf = ctypes.create_string_buffer(b"\x00" * offset + data)
                        padded = data + (b"\x00" if length % 2 else b"")
                        total = sum(
                            int.from_bytes(padded[i : i + 2], "little")
                            for i in range(0, len(padded), 2)
                        )
                        while total >> 16:
                            total = (total & 65535) + (total >> 16)
                        self.assertEqual(
                            fn(ctypes.addressof(buf) + offset, length), total, (length, offset)
                        )

    def test_pbuf_chain_empty_segments_and_bad_payload(self):
        header = ROOT / "firmware/tcp_stack/os_pbuf.h"
        self.assertTrue(header.exists(), "Single-walk pbuf candidate not implemented")
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "test.c"
            src.write_text("""
#include "os_pbuf.h"
int main(void) {
 unsigned char bytes[64]; for(unsigned i=0;i<64;i++) bytes[i]=(unsigned char)(250+i);
 struct pbuf tail={0}, empty={0}, head={0};
 tail.payload=bytes+13;tail.len=51;tail.tot_len=51;
 empty.next=&tail;empty.len=0;empty.tot_len=51;
 head.next=&empty;head.payload=bytes;head.len=13;head.tot_len=64;
 if(!poc_validate_request(&head,250,64)) return 1;
 bytes[63]^=1; if(poc_validate_request(&head,250,64)) return 2;
 bytes[63]^=1; tail.len=50; if(poc_validate_request(&head,250,64)) return 3;
 tail.len=51; if(poc_validate_request(&head,250,63)) return 4;
 if(poc_validate_request(0,250,64)) return 5;
 return 0;
}
""")
            exe = Path(tmp) / "test"
            subprocess.run(
                [
                    "cc",
                    "-Os",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    "-I" + str(ROOT / "firmware/tcp_stack"),
                    "-I" + str(ROOT / "references/tcp/lwip/src/include"),
                    str(src),
                    "-o",
                    str(exe),
                ],
                check=True,
            )
            subprocess.run([str(exe)], check=True)

    def test_rv32_endpoint_avoids_division_setup(self):
        toolchain = ROOT / ".tools/xpack-riscv-none-elf-gcc-15.2.0-1/bin"
        with tempfile.TemporaryDirectory() as tmp:
            obj = Path(tmp) / "checksum.o"
            subprocess.run(
                [
                    str(toolchain / "riscv-none-elf-gcc"),
                    "-Os",
                    "-march=rv32imac_zicsr",
                    "-mabi=ilp32",
                    "-fno-strict-aliasing",
                    "-c",
                    str(ROOT / "firmware/tcp_stack/os_checksum.c"),
                    "-o",
                    str(obj),
                ],
                check=True,
            )
            asm = subprocess.check_output(
                [str(toolchain / "riscv-none-elf-objdump"), "-d", str(obj)], text=True
            )
            import re

            self.assertFalse(
                re.search(r"\t(?:divu?|remu?)\s", asm),
                "Loop setup must not introduce integer division",
            )
