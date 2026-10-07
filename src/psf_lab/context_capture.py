"""Same-ELF context experiments, strict identity/parity and retained failures."""

import csv
import gzip
import json
import platform
import re
import shlex
import shutil
import subprocess
import time
from pathlib import Path

from psf_lab.attribution_evidence import load_capture_evidence
from psf_lab.context_boundaries import boundary_config_text, build_boundaries
from psf_lab.execution_context import context_intervals, validate_context_anchors
from psf_lab.live_cache import audit_accesses
from psf_lab.live_cache_irq import compare_irq, validate_irq_trace, validate_mmio
from psf_lab.parser.semantic import parse_trace
from psf_lab.provenance import require_clean_tree
from psf_lab.runner import QEMU_FLAGS, digest, write_json
from psf_lab.tcp_packets import decode_packet
from psf_lab.tcp_session import validate_request_pbufs, validate_session

FIELDS = ("candidate", "mode", "elf_sha256", "raw_stream_sha256", "packets", "psf", "measurement")
MEASUREMENTS = {
    "case",
    "before",
    "after",
    "before_tick",
    "ticks",
    "work",
    "woke",
    "observer_tick",
    "observer_mtime",
}


def compare_context_capture(reference: dict, observed: dict) -> dict:
    for record in (reference, observed):
        if (
            not set(FIELDS) <= record.keys()
            or not MEASUREMENTS <= record["measurement"].keys()
            or not {"objects", "switches", "markers"} <= record["psf"].keys()
        ):
            raise ValueError("Incomplete parity identity")
        for key in ("elf_sha256", "raw_stream_sha256"):
            if not re.fullmatch("[0-9a-f]{64}", record[key]):
                raise ValueError("Invalid parity digest")
    mismatches = [key for key in FIELDS if reference[key] != observed[key]]
    return dict(passed=not mismatches, mismatches=mismatches)


def capture_identity(path, candidate, mode, audit):
    trace = parse_trace((path / "trace.psf").read_bytes())
    session = json.loads((path / "session.json").read_text())
    packets = []
    for index, packet in enumerate(session["packets"]):
        if packet["file"] != f"packet-{index}.bin":
            raise ValueError("Unsafe packet path")
        packets.append(dict(direction=packet["direction"], sha256=digest(path / packet["file"])))
    return dict(
        candidate=candidate,
        mode=mode,
        elf_sha256=digest(path / "firmware.elf"),
        raw_stream_sha256=audit["stream_sha256"],
        packets=packets,
        psf=dict(
            objects=[dict(id=o["object_id"], name=o["name"]) for o in trace["objects"]],
            switches=[
                [e["object_id"], e["timestamp_raw"]]
                for e in trace["events"]
                if e["kind"] == "task_switch"
            ],
            markers=[
                [e["fields"]["phase"], e["fields"].get("request_id"), e["timestamp_raw"]]
                for e in trace["events"]
                if e["fields"].get("phase")
            ],
        ),
        measurement=json.loads((path / "live-cache.json").read_text()),
    )


def run_context_case(
    root: Path,
    source_runset: Path,
    output: Path,
    *,
    repeats: int,
    context_enabled: bool,
    timing_modes: tuple[int, ...] = (0, 1),
) -> dict:
    root, source_runset, output = root.resolve(), source_runset.resolve(), output.resolve()
    if output.exists() or output.is_relative_to(source_runset):
        raise ValueError("Output must be new and separate from source")
    if (
        type(repeats) is not int
        or repeats not in (1, 3)
        or type(context_enabled) is not bool
        or timing_modes not in ((0, 1), (0,), (1,))
    ):
        raise ValueError("Invalid run configuration")
    collector_commit = require_clean_tree(root)
    references = {mode: load_capture_evidence(root, source_runset, mode) for mode in timing_modes}
    evidence = references[timing_modes[0]]
    boundaries = build_boundaries(evidence)
    output.mkdir(parents=True)
    write_json(output / "boundaries.json", boundaries)
    (output / "boundaries.conf").write_text(boundary_config_text(boundaries))
    plugin = output / ("live_context.dylib" if platform.system() == "Darwin" else "live_context.so")
    flags = (
        ["-dynamiclib", "-undefined", "dynamic_lookup"]
        if platform.system() == "Darwin"
        else ["-shared", "-fPIC"]
    )
    compile_command = [
        "cc",
        *flags,
        "-O2",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-I" + str(root / "references/qemu-time-control/include/qemu"),
        *shlex.split(subprocess.check_output(["pkg-config", "--cflags", "glib-2.0"], text=True)),
        "-DPOC_SMALL_CACHE",
        "-DPOC_LIVE_IRQ",
        "-DPOC_CONTEXT",
        str(root / "tools/tcp/live_cache.c"),
        str(root / "tools/tcp/live_context.c"),
        str(root / "tools/qemu/live_timing.c"),
        "-o",
        str(plugin),
    ]
    compile_result = subprocess.run(compile_command, capture_output=True, text=True)
    (output / "plugin-build.log").write_text(compile_result.stdout + compile_result.stderr)
    write_json(output / "build-command.json", compile_command)
    if compile_result.returncode:
        raise ValueError("Context plugin compilation failed")
    qemu = root / ".tools/qemu-time-control/qemu-system-riscv32-relative"
    original = json.loads((source_runset / "manifest.json").read_text())
    if digest(qemu) != original["qemu_sha256"]:
        raise ValueError("QEMU differs from A")
    profile = json.loads((root / "cases/timing/sysram-10-small.json").read_text())
    results = []
    for mode in timing_modes:
        reference = references[mode]
        source = root / reference["run_path"]
        reference_identity = capture_identity(source, source_runset.name, mode, reference["audit"])
        for repeat in range(1, repeats + 1):
            run = output / f"enabled-{mode}-{repeat}"
            run.mkdir()
            for name in ("firmware.elf", "symbols.txt"):
                shutil.copy2(source / name, run / name)
            arg = (
                f"{plugin},begin={boundaries['capture_begin_pc']:x},end={boundaries['capture_end_pc']:x},"
                f"enabled={mode},out={run}/accesses.csv"
            )
            if context_enabled:
                arg += (
                    f",context-config={output}/boundaries.conf"
                    f",context-out={run}/context-events.jsonl"
                )
            command = [str(qemu), *QEMU_FLAGS, "-plugin", arg, "-kernel", str(run / "firmware.elf")]
            result = dict(
                candidate=source_runset.name,
                mode=mode,
                repeat=repeat,
                context_enabled=context_enabled,
                parity_passed=False,
                context_exact=False,
                accepted=False,
            )
            with (run / "qemu.log").open("wb") as log:
                start = time.monotonic()
                try:
                    process = subprocess.run(
                        command, cwd=run, stdout=log, stderr=subprocess.STDOUT, timeout=20
                    )
                    result["exit_code"] = process.returncode
                except subprocess.TimeoutExpired:
                    result["exit_code"] = None
                result["host_wall_seconds"] = time.monotonic() - start
            try:
                if result["exit_code"] != 0:
                    raise ValueError("QEMU failed or timed out")
                audit = audit_accesses(run / "accesses.csv", profile=profile)
                log = (run / "qemu.log").read_text()
                match = re.search(
                    r"live_cache_complete events=(\d+) cycles=(\d+) api_calls=(\d+)", log
                )
                if not match or tuple(map(int, match.groups())) != (
                    audit["events"],
                    audit["cycles"],
                    audit["events"] if mode else 0,
                ):
                    raise ValueError("Native audit receipt mismatch")
                mmio = re.findall(
                    r"live_cache_mmio pc=(\d+) address=(\d+) size=(\d+) op=([RW])", log
                )
                count = re.search(r"live_cache_mmio_count=(\d+)", log)
                if not count or int(count[1]) != len(mmio):
                    raise ValueError("Missing MMIO receipt")
                for pc, address, size, op in mmio:
                    if not 0x80000000 <= int(pc) < 0x88000000:
                        raise ValueError("MMIO PC outside RAM")
                    validate_mmio(int(address), int(size), op)
                identity = capture_identity(run, source_runset.name, mode, audit)
                parity = compare_context_capture(reference_identity, identity)
                write_json(run / "parity.json", parity)
                result["parity_passed"] = parity["passed"]
                if not parity["passed"]:
                    raise ValueError("A parity mismatch: " + ",".join(parity["mismatches"]))
                session = json.loads((run / "session.json").read_text())
                packets = [
                    dict(decode_packet((run / p["file"]).read_bytes()), direction=p["direction"])
                    for p in session["packets"]
                ]
                validate_session(packets, session, workload=evidence["workload"])
                validate_request_pbufs(session, "matrix", workload=evidence["workload"])
                oracle = json.loads((run / "oracle.json").read_text())
                if (
                    not oracle["complete"]
                    or oracle["sent_ids"] != [11680]
                    or oracle["received_ids"] != [11680]
                ):
                    raise ValueError("Guest oracle incomplete")
                trace = parse_trace((run / "trace.psf").read_bytes())
                validate_irq_trace(trace, identity["measurement"], scenario="tcp")
                quality = "not_collected"
                if context_enabled:
                    events = [
                        json.loads(line)
                        for line in (run / "context-events.jsonl").read_text().splitlines()
                    ]
                    objects = [o for o in trace["objects"] if o["kind"] == "task"]
                    if len({o["address"] for o in objects}) != len(objects):
                        raise ValueError("Reused task address unsupported")
                    task_ids = {int(o["address"], 16) for o in objects}
                    intervals = context_intervals(
                        events, raw_events=audit["events"], task_ids=task_ids
                    )
                    with (run / "accesses.csv").open(newline="") as stream:
                        validate_context_anchors(events, csv.DictReader(stream), boundaries)
                    selected = [e["task_id"] for e in events if e["kind"] == "selected_task"]
                    begin, end = identity["measurement"]["before"], identity["measurement"]["after"]
                    switches = [
                        int(e["object_id"].split(":")[0], 16)
                        for e in trace["events"]
                        if e["kind"] == "task_switch" and begin <= e["timestamp_raw"] <= end
                    ]
                    if selected != switches:
                        raise ValueError("Sidecar/PSF selection order mismatch")
                    write_json(run / "context-intervals.json", intervals)
                    write_json(run / "task-identities.json", objects)
                    quality = intervals["quality"]
                    result["context_exact"] = quality == "exact"
                    if quality != "exact":
                        raise ValueError("Non-exact context")
                result.update(
                    audit=audit,
                    measurement=identity["measurement"],
                    context_quality=quality,
                    accepted=True,
                    raw_rows=audit["events"],
                    events_per_second=audit["events"] / result["host_wall_seconds"],
                )
            except (ValueError, KeyError, OSError, json.JSONDecodeError) as error:
                result["error"] = str(error)
            raw = run / "accesses.csv"
            if raw.exists():
                result["raw_bytes"] = raw.stat().st_size
                with (
                    raw.open("rb") as source_stream,
                    gzip.open(run / "accesses.csv.gz", "wb", compresslevel=6) as zipped,
                ):
                    shutil.copyfileobj(source_stream, zipped)
                raw.unlink()
                result["raw_disk_bytes"] = (run / "accesses.csv.gz").stat().st_size
            sidecar = run / "context-events.jsonl"
            result["sidecar_bytes"] = sidecar.stat().st_size if sidecar.exists() else 0
            result["sidecar_disk_bytes"] = result["sidecar_bytes"]
            write_json(
                run / "manifest.json",
                dict(
                    command=command,
                    result=result,
                    files={p.name: digest(p) for p in run.iterdir() if p.is_file()},
                ),
            )
            result["run_manifest_sha256"] = digest(run / "manifest.json")
            results.append(result)
    pair_checks = []
    if timing_modes == (0, 1) and all(r["accepted"] for r in results):
        for repeat in range(1, repeats + 1):
            a, b = [
                next(r for r in results if r["mode"] == mode and r["repeat"] == repeat)
                for mode in (0, 1)
            ]
            pair_checks.append(
                compare_irq(
                    a["measurement"], b["measurement"], a["audit"], b["audit"], scenario="tcp"
                )
            )
    sources = [
        "tools/tcp/live_cache.c",
        "tools/tcp/live_context.c",
        "tools/tcp/live_context.h",
        "tools/qemu/live_timing.c",
        "tools/qemu/live_timing.h",
        "src/psf_lab/context_capture.py",
        "src/psf_lab/context_boundaries.py",
        "src/psf_lab/execution_context.py",
        "cases/timing/attribution-rules-v1.json",
    ]
    manifest = dict(
        schema="context-runset-v1",
        candidate=source_runset.name,
        guest_source_commit=evidence["source_commit"],
        collector_source_commit=collector_commit,
        source_runset=str(source_runset.relative_to(root)),
        guest_elf_sha256=boundaries["elf_sha256"],
        qemu_sha256=digest(qemu),
        plugin_sha256=digest(plugin),
        compiler_sha256=digest(Path(shutil.which("cc")).resolve()),
        collector_sources={p: digest(root / p) for p in sources},
        rules_sha256=digest(root / "cases/timing/attribution-rules-v1.json"),
        boundary_sha256=digest(output / "boundaries.json"),
        boundary_config_sha256=digest(output / "boundaries.conf"),
        pair_checks=pair_checks,
        runs=results,
        passed=all(r["accepted"] for r in results),
    )
    write_json(output / "manifest.json", manifest)
    return manifest
