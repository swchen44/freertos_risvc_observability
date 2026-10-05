"""Recheck and summarize the fixed Os/O2 TCP IRQ experiment from the POC root."""

import csv
import gzip
import hashlib
import json
import re
import subprocess
from pathlib import Path

from psf_lab.live_cache import audit_accesses
from psf_lab.live_cache_irq import compare_irq, validate_irq_trace
from psf_lab.parser.semantic import parse_trace
from psf_lab.tcp_hotspots import rank_self_costs
from psf_lab.tcp_packets import decode_packet
from psf_lab.tcp_session import validate_session

root = Path.cwd()
output = root / "artifacts/verification/tcp-checksum-opt"
tools = root / ".tools/xpack-riscv-none-elf-gcc-15.2.0-1/bin"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


for filename, expected in json.loads((output / "inputs/SHA256.json").read_text()).items():
    assert sha(output / filename) == expected, filename

summary = {}
packet_reference = None
for opt, name in [("Os", "tcp-opt-os-v1"), ("O2", "tcp-opt-o2-v1")]:
    directory = root / "runs" / name
    manifest = json.loads((directory / "manifest.json").read_text())
    result = json.loads((directory / "results.json").read_text())
    assert result["passed"] and result["repeatable"]
    assert sha(directory / "results.json") == manifest["results_sha256"]
    for file, expected in manifest["sources"].items():
        assert sha(root / file) == expected, file
    compile_lines = [
        line
        for line in (directory / "build.log").read_text().splitlines()
        if " -c " in line and "riscv-none-elf-gcc" in line
    ]
    changed = [line for line in compile_lines if " -O2 " in line]
    assert len(changed) == (1 if opt == "O2" else 0)
    assert not changed or "inet_chksum.c" in changed[0]
    for run in manifest["runs"]:
        path = directory / run["name"]
        assert sha(path / "manifest.json") == run["sha256"]
        rm = json.loads((path / "manifest.json").read_text())
        for file, expected in rm["files"].items():
            assert sha(path / file) == expected, file
        entry = rm["result"]
        assert audit_accesses(path / "accesses.csv.gz") == entry["audit"]
        assert (
            validate_irq_trace(
                parse_trace((path / "trace.psf").read_bytes()), entry["measurement"], scenario="tcp"
            )
            == entry["switches"]
        )
        metrics = json.loads((path / "session.json").read_text())
        packets, hashes = [], []
        for index, packet in enumerate(metrics["packets"]):
            assert packet["file"] == f"packet-{index}.bin"
            blob = (path / packet["file"]).read_bytes()
            hashes.append(hashlib.sha256(blob).hexdigest())
            packets.append(dict(decode_packet(blob), direction=packet["direction"]))
        assert validate_session(packets, metrics) == entry["tcp"]
        if packet_reference is None:
            packet_reference = hashes
        assert hashes == packet_reference
    for comparison in result["comparisons"]:
        control = next(
            r for r in result["runs"] if not r["enabled"] and r["repeat"] == comparison["repeat"]
        )
        active = next(
            r for r in result["runs"] if r["enabled"] and r["repeat"] == comparison["repeat"]
        )
        checked = compare_irq(
            control["measurement"],
            active["measurement"],
            control["audit"],
            active["audit"],
            scenario="tcp",
        )
        assert checked == {k: v for k, v in comparison.items() if k not in ("accepted", "repeat")}
    active = next(r for r in result["runs"] if r["enabled"])
    path = directory / active["run"]
    symbols = []
    for line in (path / "symbols.txt").read_text().splitlines():
        parts = line.split()
        if len(parts) == 4 and parts[2] in ("T", "t"):
            symbols.append((int(parts[0], 16), int(parts[1], 16), parts[3]))
    named = {s[2]: s for s in symbols}
    with gzip.open(path / "accesses.csv.gz", "rt") as stream:
        profile = rank_self_costs(
            csv.DictReader(stream),
            symbols,
            stack_markers=(named["z0_stack_begin"][0], named["z0_stack_end"][0]),
        )
    assert profile["windows"] == 27 and profile["total_cycles"] == active["audit"]["cycles"]
    (output / f"hotspots-{opt}.json").write_text(json.dumps(profile, indent=2) + "\n")
    sizes = subprocess.check_output(
        [
            str(tools / "riscv-none-elf-size"),
            str(path / "firmware.elf"),
            str(output / "inputs" / opt / "inet_chksum.o"),
        ],
        text=True,
    )
    (output / f"size-{opt}.txt").write_text(sizes)
    elf_fields, object_fields = [line.split() for line in sizes.splitlines()[1:]]
    headers = subprocess.check_output(
        [str(tools / "riscv-none-elf-objdump"), "-h", str(path / "firmware.elf")], text=True
    )
    section = next(
        line.split() for line in headers.splitlines() if re.match(r"\s*\d+\s+\.text\s", line)
    )
    text_size, text_start = int(section[2], 16), int(section[3], 16)
    padding = sum(
        int(size, 16)
        for address, size in re.findall(
            r"\*fill\*\s+(0x[0-9a-f]+)\s+(0x[0-9a-f]+)",
            (output / "inputs" / opt / "firmware.map").read_text(),
        )
        if text_start <= int(address, 16) < text_start + text_size
    )
    disassembly = subprocess.check_output(
        [
            str(tools / "riscv-none-elf-objdump"),
            "-d",
            "--disassemble=lwip_standard_chksum",
            str(path / "firmware.elf"),
        ],
        text=True,
    )
    (output / f"checksum-{opt}.asm").write_text(disassembly)
    m = active["measurement"]
    summary[opt] = dict(
        run=name,
        manifest_sha256=sha(directory / "manifest.json"),
        guest_interval_ns=(m["after"] - m["before"]) * 100,
        instructions=active["audit"]["operations"]["I"],
        memory_service_cycles=active["audit"]["cycles"],
        checksum_function_bytes=named["lwip_standard_chksum"][1],
        checksum_object_text=int(object_fields[0]),
        elf_text=int(elf_fields[0]),
        elf_data=int(elf_fields[1]),
        elf_bss=int(elf_fields[2]),
        text_section_padding=padding,
        profile=profile,
    )
report = dict(
    variants=summary,
    verified_qemu_runs=12,
    packet_bytes_identical=True,
    changed_translation_units=["inet_chksum.c"],
    scope="model comparison, not hardware speed",
)
(output / "comparison.json").write_text(json.dumps(report, indent=2) + "\n")
with (output / "hotspots.csv").open("w", newline="") as stream:
    writer = csv.writer(stream)
    writer.writerow(
        [
            "variant",
            "function",
            "self_memory_cycles",
            "instruction_events",
            "stack_window_cycles",
            "harness_window_cycles",
        ]
    )
    for opt, entry in summary.items():
        for row in entry["profile"]["functions"]:
            writer.writerow(
                [
                    opt,
                    row["name"],
                    row["cycles"],
                    row["instructions"],
                    row["scope_cycles"].get("stack_window_including_preemption", 0),
                    row["scope_cycles"].get("harness_window", 0),
                ]
            )
print(
    json.dumps(
        {k: {a: b for a, b in v.items() if a != "profile"} for k, v in summary.items()}, indent=2
    )
)
