"""Bind context and SDK hook PCs to actual RV32 ELF instructions."""

import re
import struct
import subprocess
from pathlib import Path

from psf_lab.attribution_evidence import parse_link_map
from psf_lab.context_boundaries import boundary_config_text, build_boundaries
from psf_lab.runner import digest, write_json

HOOKS = {
    "enter_pc": "poc_clock_anchor_enter",
    "sampled_pc": "poc_clock_anchor_sampled",
    "leave_pc": "poc_clock_anchor_leave",
}


def derive_boundaries(evidence: dict) -> dict:
    context = build_boundaries(evidence)
    symbols = {}
    for line in evidence["tool_outputs"]["nm"].splitlines():
        fields = line.split()
        if len(fields) not in (3, 4):
            continue
        name = fields[-1]
        if any(name.startswith(hook + ".") for hook in HOOKS.values()):
            raise ValueError("Cloned marker symbol")
        if name in HOOKS.values():
            if fields[-2] not in ("t", "T"):
                raise ValueError("Marker is not executable")
            symbols.setdefault(name, []).append(int(fields[0], 16))
    pcs = {i["pc"] for i in context["evidence"]}
    result = {}
    for key, name in HOOKS.items():
        values = symbols.get(name, [])
        if len(values) != 1 or values[0] not in pcs:
            raise ValueError("Missing, ambiguous or unaligned marker: " + name)
        result[key] = values[0]
    forbidden = {
        context[k]
        for k in ("capture_begin_pc", "capture_end_pc", "trap_entry_pc", "selected_task_pc")
    }
    if len(set(result.values())) != 3 or forbidden & set(result.values()):
        raise ValueError("Aliased marker boundary")
    return dict(
        schema="clock-anchor-boundaries-v1",
        elf_sha256=context["elf_sha256"],
        marker_pcs=result,
        context=context,
    )


def collect_boundaries(
    root: Path, elf: Path, map_path: Path, toolchain: Path, output: Path
) -> dict:
    root, elf, map_path = root.resolve(), elf.resolve(), map_path.resolve()
    if not elf.is_relative_to(root) or not map_path.is_relative_to(root):
        raise ValueError("ELF/map outside the experiment workspace")
    if elf.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("ELF exceeds metadata budget")
    with elf.open("rb") as f:
        header = f.read(52)
    if (
        len(header) != 52
        or header[:7] != b"\x7fELF\x01\x01\x01"
        or struct.unpack_from("<HH", header, 16) != (2, 243)
    ):
        raise ValueError("Requires executable RV32 little-endian ELF")
    output.mkdir(parents=True, exist_ok=False)
    outputs, tools = {}, {}
    for name, flags in (
        ("nm", ["-S", "-n"]),
        ("readelf", ["-WS"]),
        ("objdump", ["-d"]),
        ("size", ["-A"]),
    ):
        tool = (toolchain / ("riscv-none-elf-" + name)).resolve()
        cmd = [str(tool), *flags, str(elf)]
        p = subprocess.run(cmd, capture_output=True, timeout=30)
        (output / (name + ".txt")).write_bytes(p.stdout)
        (output / (name + ".stderr")).write_bytes(p.stderr)
        write_json(output / (name + "-command.json"), dict(command=cmd, exit=p.returncode))
        if p.returncode:
            raise ValueError("ELF tool failed: " + name)
        outputs[name] = p.stdout.decode("utf-8")
        version = subprocess.check_output([str(tool), "--version"], text=True, timeout=10)
        tools[name] = dict(path=str(tool), sha256=digest(tool), version=version.splitlines()[0])
    sections = []
    for line in outputs["readelf"].splitlines():
        match = re.match(
            r"\s*\[\s*\d+\]\s+(\S+)\s+\S+\s+([\da-f]+)\s+[\da-f]+\s+"
            r"([\da-f]+)\s+\S+\s+(\S+)",
            line,
        )
        if match and "X" in match[4]:
            start, size = int(match[2], 16), int(match[3], 16)
            if size:
                sections.append(dict(name=match[1], start=start, end=start + size))
    if not sections:
        raise ValueError("No executable sections")
    evidence = dict(
        elf_path=str(elf),
        files_sha256={"firmware.elf": digest(elf)},
        executable_sections=sections,
        map_records=parse_link_map(map_path.read_text()),
        tool_outputs=outputs,
    )
    result = derive_boundaries(evidence)
    result.update(
        map_sha256=digest(map_path),
        tools=tools,
        executable_sections=sections,
        metadata_files={p.name: digest(p) for p in output.iterdir() if p.is_file()},
    )
    (output / "context.config").write_text(boundary_config_text(result["context"]))
    write_json(output / "boundaries.json", result)
    return result
