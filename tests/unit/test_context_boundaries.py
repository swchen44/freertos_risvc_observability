import hashlib
import importlib.util
import struct
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def toy_elf(path, base):
    data = bytearray(0x140)
    data[:7] = b"\x7fELF\x01\x01\x01"
    struct.pack_into("<H", data, 18, 243)
    struct.pack_into("<I", data, 28, 52)
    struct.pack_into("<HH", data, 42, 32, 1)
    struct.pack_into("<IIIIIIII", data, 52, 1, 0x100, base, base, 64, 64, 5, 2)
    for offset in range(0x100, 0x140, 4):
        struct.pack_into("<I", data, offset, 0x13)
    struct.pack_into("<I", data, 0x130, 0x30200073)
    path.write_bytes(data)
    names = [
        "tcp_capture_begin",
        "tcp_capture_end",
        "freertos_risc_v_trap_handler",
        "xTraceTaskSwitch",
        "pxCurrentTCB",
    ]
    nm = "\n".join(
        f"{address:08x} T {name}"
        for name, address in zip(
            names, [base, base + 4, base + 16, base + 8, 0x80080000], strict=True
        )
    )
    return dict(
        elf_path=str(path),
        files_sha256={"firmware.elf": hashlib.sha256(data).hexdigest()},
        executable_sections=[dict(start=base, end=base + 64, name=".text")],
        map_records=[dict(start=base + 16, end=base + 64, section=".text", object="portASM.o")],
        tool_outputs={"nm": nm},
    )


class BoundariesTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("psf_lab.context_boundaries"))
        from psf_lab.context_boundaries import build_boundaries

        self.build = build_boundaries

    def test_each_elf_uses_own_addresses_and_opcode(self):
        with TemporaryDirectory() as tmp:
            for base in (0x80000000, 0x80001000):
                evidence = toy_elf(Path(tmp) / "firmware.elf", base)
                result = self.build(evidence)
                self.assertEqual(result["capture_begin_pc"], base)
                self.assertEqual(result["mret_pcs"], [base + 48])
                self.assertEqual(result["current_tcb_address"], 0x80080000)

    def test_missing_duplicate_symbol_wrong_endian_opcode_rejected(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "firmware.elf"
            for mutation in ("missing", "duplicate", "endian", "opcode"):
                evidence = toy_elf(path, 0x80000000)
                if mutation == "missing":
                    evidence["tool_outputs"]["nm"] = evidence["tool_outputs"]["nm"].replace(
                        "pxCurrentTCB", "other"
                    )
                elif mutation == "duplicate":
                    evidence["tool_outputs"]["nm"] += "\n80000030 T freertos_risc_v_trap_handler"
                else:
                    data = bytearray(path.read_bytes())
                    if mutation == "endian":
                        data[5] = 2
                    else:
                        data[0x130:0x134] = b"\x13\0\0\0"
                    path.write_bytes(data)
                    evidence["files_sha256"]["firmware.elf"] = hashlib.sha256(data).hexdigest()
                with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                    self.build(evidence)
