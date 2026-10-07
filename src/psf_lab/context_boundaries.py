"""Derive context anchors from each pinned RV32 little-endian ELF."""

import struct
from pathlib import Path

from psf_lab.runner import digest


def build_boundaries(evidence: dict) -> dict:
    path = Path(evidence["elf_path"])
    if digest(path) != evidence["files_sha256"]["firmware.elf"]:
        raise ValueError("ELF changed")
    data = path.read_bytes()
    if (
        len(data) < 52
        or data[:7] != b"\x7fELF\x01\x01\x01"
        or struct.unpack_from("<H", data, 18)[0] != 243
    ):
        raise ValueError("Requires RV32 little-endian ELF")
    symbols = {}
    for line in evidence["tool_outputs"]["nm"].splitlines():
        fields = line.split()
        if len(fields) in (3, 4):
            symbols.setdefault(fields[-1], []).append(int(fields[0], 16))
    mapping = dict(
        capture_begin_pc="tcp_capture_begin",
        capture_end_pc="tcp_capture_end",
        trap_entry_pc="freertos_risc_v_trap_handler",
        selected_task_pc="xTraceTaskSwitch",
        current_tcb_address="pxCurrentTCB",
    )
    result = dict(schema="context-boundaries-v1", elf_sha256=digest(path), xlen=32, endian="little")
    for key, name in mapping.items():
        if len(symbols.get(name, [])) != 1:
            raise ValueError("Missing or ambiguous boundary: " + name)
        value = symbols[name][0]
        if value % 2 or not 0x80000000 <= value < 0x88000000:
            raise ValueError("Invalid boundary address")
        result[key] = value
    if result["current_tcb_address"] % 4:
        raise ValueError("Unaligned TCB pointer")
    phoff = struct.unpack_from("<I", data, 28)[0]
    phsize, phcount = struct.unpack_from("<HH", data, 42)
    if phsize != 32 or phoff + phsize * phcount > len(data):
        raise ValueError("Invalid program headers")
    segments = []
    for i in range(phcount):
        kind, offset, va, _, size, _, flags, _ = struct.unpack_from(
            "<IIIIIIII", data, phoff + i * phsize
        )
        if kind == 1 and flags & 1:
            if offset + size > len(data):
                raise ValueError("Truncated ELF segment")
            segments.append((va, va + size, offset))
    instructions = []
    for section in evidence["executable_sections"]:
        pc, end = section["start"], section["end"]
        matches = [s for s in segments if s[0] <= pc and end <= s[1]]
        if len(matches) != 1:
            raise ValueError("Executable section not in unique ELF segment")
        start, _, offset = matches[0]
        while pc < end:
            pos = offset + pc - start
            half = int.from_bytes(data[pos : pos + 2], "little")
            size = 4 if half & 3 == 3 else 2
            if pc + size > end:
                raise ValueError("Truncated executable instruction")
            opcode = int.from_bytes(data[pos : pos + size], "little")
            instructions.append(
                dict(pc=pc, opcode=opcode, size=size, source_ref="ELF:" + section["name"])
            )
            pc += size
    pcs = {r["pc"] for r in instructions}
    for key in ("capture_begin_pc", "capture_end_pc", "trap_entry_pc", "selected_task_pc"):
        if result[key] not in pcs:
            raise ValueError("Boundary is not instruction-aligned")
    trap = result["trap_entry_pc"]
    sections = [
        r
        for r in evidence["map_records"]
        if r["start"] <= trap < r["end"]
        and any(
            s["start"] <= r["start"] and r["end"] <= s["end"]
            for s in evidence["executable_sections"]
        )
    ]
    if len(sections) != 1:
        raise ValueError("Ambiguous trap executable ownership")
    section = sections[0]
    result["mret_pcs"] = [
        r["pc"]
        for r in instructions
        if section["start"] <= r["pc"] < section["end"] and r["opcode"] == 0x30200073
    ]
    if not result["mret_pcs"]:
        raise ValueError("Missing trap mret opcode")
    result["evidence"] = instructions
    return result


def boundary_config_text(boundaries: dict) -> str:
    values = dict(
        version=1,
        xlen=32,
        endian=1,
        **{
            key: boundaries[key]
            for key in (
                "capture_begin_pc",
                "capture_end_pc",
                "trap_entry_pc",
                "selected_task_pc",
                "current_tcb_address",
            )
        },
        mret_count=len(boundaries["mret_pcs"]),
    )
    values.update({f"mret_{n}": pc for n, pc in enumerate(boundaries["mret_pcs"])})
    return "".join(f"{key}={value}\n" for key, value in values.items())
