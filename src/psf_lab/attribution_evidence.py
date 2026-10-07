"""Validate immutable A captures before deriving executable ownership."""

import gzip
import hashlib
import json
import re
import shlex
import subprocess
from pathlib import Path

from psf_lab.cost_attribution import classify_owner, normalize_ranges
from psf_lab.runner import digest

REQUIRED = {
    "firmware.elf",
    "symbols.txt",
    "accesses.csv.gz",
    "trace.psf",
    "session.json",
    "oracle.json",
    "live-cache.json",
}


def contained(base, name):
    path = Path(name)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError("Invalid relative evidence path")
    resolved = (base / path).resolve()
    if not resolved.is_relative_to(base.resolve()):
        raise ValueError("Evidence escapes base directory")
    return resolved


def verify_file_hashes(base: Path, hashes: dict, required: set[str]) -> None:
    if not required <= hashes.keys():
        raise ValueError("Missing required evidence hashes")
    for name, sha in hashes.items():
        path = contained(base, name)
        if not path.is_file() or digest(path) != sha:
            raise ValueError(f"Evidence hash mismatch: {name}")


def parse_link_map(text: str) -> list[dict]:
    active, pending, records = False, None, []
    for number, line in enumerate(text.splitlines(), 1):
        if line.startswith("Linker script and memory map"):
            active = True
        if not active:
            continue
        match = re.match(r"^ (\.[\w.$-]+)\s*(.*)$", line)
        if match:
            pending = match[1]
            rest = match[2]
        elif pending:
            rest = line.strip()
        else:
            continue
        values = re.fullmatch(r"(0x[\da-fA-F]+)\s+(0x[\da-fA-F]+)\s+(.+)", rest)
        if values:
            start, size = int(values[1], 16), int(values[2], 16)
            if start and size:
                records.append(
                    dict(
                        start=start,
                        end=start + size,
                        section=pending,
                        object=values[3],
                        evidence=f"map:{number}",
                    )
                )
            pending = None
        elif rest:
            pending = None
    return records


def build_role_ranges(evidence: dict, rules: dict) -> list[dict]:
    rows = []
    for record in evidence["map_records"]:
        start, end = record["start"], record["end"]
        sections = [
            s for s in evidence["executable_sections"] if s["start"] <= start and end <= s["end"]
        ]
        if not sections:
            if record["section"].startswith((".text", ".init")):
                raise ValueError("Map executable input outside ELF executable section")
            continue
        obj = record["object"]
        source = evidence["object_sources"].get(obj)
        symbols = [s for s in evidence["symbols"] if start <= s["start"] < end and s["size"]]
        if any(s["start"] + s["size"] > end for s in symbols):
            raise ValueError("Symbol exceeds map input section")
        boundaries = sorted(
            {start, end, *[p for s in symbols for p in (s["start"], s["start"] + s["size"])]}
        )
        for left, right in zip(boundaries, boundaries[1:], strict=False):
            owners = [s for s in symbols if s["start"] <= left and right <= s["start"] + s["size"]]
            # Keep partial symbol overlap as competing ranges for resolve_pc.
            if not owners:
                owners = [dict(start=left, size=right - left, function=None)]
            for symbol in owners:
                row = dict(
                    start=left,
                    end=right,
                    object=obj,
                    source=source,
                    function=symbol["function"],
                    aliases=[],
                    evidence=[record["evidence"], f"symbol:{symbol['function']}"],
                    reason=None,
                )
                classification = classify_owner(row, rules)
                row.update(role=classification["role"], reason=classification["reason"])
                row["evidence"].extend("rule:" + r for r in classification["rule_ids"])
                rows.append(row)
    return normalize_ranges(rows)


def source_label(value):
    if "/poc/" in value:
        return value.split("/poc/", 1)[1]
    return value


def load_capture_evidence(root: Path, runset: Path, mode: int, repeat: int = 1) -> dict:
    root, runset = root.resolve(), runset.resolve()
    if (
        type(mode) is not int
        or mode not in (0, 1)
        or type(repeat) is not int
        or repeat not in (1, 2, 3)
    ):
        raise ValueError("Invalid mode/repeat")
    comparison = root / "artifacts/verification/tcp-workload-matrix/results/comparison.json"
    pins = json.loads(comparison.read_text())["sources"]
    manifest_name = str((runset / "manifest.json").relative_to(root))
    verify_file_hashes(root, {manifest_name: pins[manifest_name]}, {manifest_name})
    manifest = json.loads((runset / "manifest.json").read_text())
    required_sources = {
        "firmware/Makefile",
        "firmware/app/cases/tcp_request_response.c",
        "tools/tcp/live_cache.c",
        "tools/qemu/live_timing.c",
        "tools/qemu/live_timing.h",
        "tools/tcp/run_live_cache.py",
        "src/psf_lab/tcp_session.py",
        "src/psf_lab/tcp_workload.py",
        "src/psf_lab/cache_model.py",
        "src/psf_lab/memory_timing.py",
        "cases/tcp/workload-matrix-v1.json",
        "cases/timing/sysram-10-small.json",
        str((runset / "workload.h").relative_to(root)),
    }
    if not required_sources <= manifest["sources"].keys():
        raise ValueError("Missing required source evidence")
    commit = manifest["source_commit"]
    if not re.fullmatch("[0-9a-f]{40}", commit):
        raise ValueError("Invalid source commit")
    for name, sha in manifest["sources"].items():
        path = contained(root, name)
        if path.is_file() and digest(path) == sha:
            continue
        old = subprocess.run(
            ["git", "show", f"{commit}:{name}"], cwd=root, capture_output=True, check=True
        )
        if hashlib.sha256(old.stdout).hexdigest() != sha:
            raise ValueError("Historical source hash mismatch: " + name)
    run_name = f"enabled-{mode}-{repeat}"
    matching = [r for r in manifest["runs"] if r["name"] == run_name]
    if len(matching) != 1:
        raise ValueError("Missing or duplicate capture")
    path = runset / run_name
    verify_file_hashes(
        runset,
        {
            run_name + "/manifest.json": matching[0]["sha256"],
            "results.json": manifest["results_sha256"],
        },
        {run_name + "/manifest.json", "results.json"},
    )
    receipt = json.loads((path / "manifest.json").read_text())
    verify_file_hashes(path, receipt["files"], REQUIRED)
    session = json.loads((path / "session.json").read_text())
    verify_file_hashes(path, receipt["files"], REQUIRED | {p["file"] for p in session["packets"]})
    result = receipt["result"]
    if not result["accepted"] or result["enabled"] != bool(mode):
        raise ValueError("Unaccepted capture or mode mismatch")
    with gzip.open(path / "accesses.csv.gz", "rb") as stream:
        raw_sha = hashlib.file_digest(stream, "sha256").hexdigest()
    if raw_sha != result["audit"]["stream_sha256"]:
        raise ValueError("Raw stream digest mismatch")
    toolchain = root / ".tools/xpack-riscv-none-elf-gcc-15.2.0-1/bin"
    elf = path / "firmware.elf"
    outputs, tools = {}, {}

    def run_tool(name, args):
        tool = toolchain / ("riscv-none-elf-" + name)
        output = subprocess.run(
            [str(tool), *args, str(elf)], text=True, capture_output=True, check=True
        ).stdout
        outputs[name] = output
        tools[name] = dict(
            sha256=digest(tool),
            version=subprocess.run(
                [str(tool), "--version"], text=True, capture_output=True, check=True
            ).stdout.splitlines()[0],
        )
        return output

    section_text = run_tool("readelf", ["-WS"])
    sections = []
    for line in section_text.splitlines():
        m = re.match(
            r"\s*\[\s*\d+\]\s+(\S+)\s+\S+\s+([\da-f]+)\s+[\da-f]+\s+([\da-f]+)\s+\S+\s+(\S+)", line
        )
        if m and "X" in m[4]:
            sections.append(dict(name=m[1], start=int(m[2], 16), end=int(m[2], 16) + int(m[3], 16)))
    nm_text = run_tool("nm", ["-S", "-n"])
    symbols = []
    for line in nm_text.splitlines():
        parts = line.split()
        if len(parts) == 4 and parts[2] in ("t", "T"):
            symbols.append(dict(start=int(parts[0], 16), size=int(parts[1], 16), function=parts[3]))
        elif len(parts) == 3 and parts[1] in ("t", "T"):
            symbols.append(dict(start=int(parts[0], 16), size=0, function=parts[2]))
    # addr2line's -e consumes ELF before address arguments, unlike other binutils.
    addr = toolchain / "riscv-none-elf-addr2line"
    addresses = sorted({s["start"] for s in symbols})
    outputs["addr2line"] = subprocess.run(
        [str(addr), "-a", "-f", "-i", "-e", str(elf), *[hex(a) for a in addresses]],
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    tools["addr2line"] = dict(
        sha256=digest(addr),
        version=subprocess.run(
            [str(addr), "--version"], text=True, capture_output=True, check=True
        ).stdout.splitlines()[0],
    )
    object_sources = {}
    for line in (runset / "build.log").read_text().splitlines():
        if " -c " not in line or "riscv-none-elf-gcc" not in line:
            continue
        args = shlex.split(line)
        source, obj = args[args.index("-c") + 1], args[args.index("-o") + 1]
        source = source_label(source) if Path(source).is_absolute() else "firmware/" + source
        if source not in manifest["sources"]:
            raise ValueError("Build source missing from capture provenance: " + source)
        object_sources[obj] = source
    map_path = runset / "build/firmware.map"
    # Build ELF equality prevents accidentally selecting another candidate's map/build pair.
    if digest(runset / "build/firmware.elf") != receipt["files"]["firmware.elf"]:
        raise ValueError("Build/capture ELF mismatch")
    return dict(
        run_path=str(path.relative_to(root)),
        workload=manifest["workload"],
        mode=mode,
        source_commit=commit,
        elf_path=str(elf),
        files_sha256=receipt["files"],
        raw_stream_sha256=raw_sha,
        audit=result["audit"],
        measurement=result["measurement"],
        packets=session["packets"],
        psf=str(path / "trace.psf"),
        executable_sections=sections,
        symbols=symbols,
        map_records=parse_link_map(map_path.read_text()),
        object_sources=object_sources,
        debug={},
        tool_hashes=tools,
        tool_outputs=outputs,
        map_sha256=digest(map_path),
        build_log_sha256=digest(runset / "build.log"),
        manifest_sha256=digest(runset / "manifest.json"),
        comparison_sha256=digest(comparison),
    )
