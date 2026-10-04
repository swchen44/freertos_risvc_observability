"""Build and validate Z0; output is exclusive and existing transfer runs are untouched."""

import argparse
import bisect
import csv
import gzip
import json
import platform
import shlex
import shutil
import subprocess
from collections import Counter
from pathlib import Path

from run_transfer import command

from psf_lab.parser.semantic import parse_trace
from psf_lab.runner import QEMU_FLAGS, digest, write_json
from psf_lab.tcp_cache import replay_split
from psf_lab.tcp_packets import decode_packet
from psf_lab.tcp_session import validate_session

ROOT = Path(__file__).resolve().parents[2]


def analyze(run):
    metrics = json.loads((run / "session.json").read_text())
    packets = []
    for index, entry in enumerate(metrics["packets"]):
        if entry["file"] != f"packet-{index}.bin":
            raise ValueError("Unexpected packet filename")
        packet = decode_packet((run / entry["file"]).read_bytes())
        rx = entry["direction"] == "rx"
        if (packet["src"], packet["dst"], packet["source_ip"], packet["destination_ip"]) != (
            (50000, 1234, [10, 0, 0, 2], [10, 0, 0, 1])
            if rx
            else (1234, 50000, [10, 0, 0, 1], [10, 0, 0, 2])
        ):
            raise ValueError("Peer address mismatch")
        packets.append(dict(packet, direction=entry["direction"]))
    result = validate_session(packets, metrics)
    oracle = json.loads((run / "oracle.json").read_text())
    if (
        oracle["case_id"] != "tcp_request_response"
        or not oracle["complete"]
        or oracle["sent_ids"] != [11680]
        or oracle["received_ids"] != [11680]
    ):
        raise ValueError("Incomplete firmware oracle")
    parsed = parse_trace((run / "trace.psf").read_bytes())
    markers = [(e["fields"].get("phase"), e["fields"].get("request_id")) for e in parsed["events"]]
    for name in ("TCP_SESSION_BEGIN", "TCP_SESSION_END"):
        if markers.count((name, 0)) != 1:
            raise ValueError("Missing PSF session marker")
    expected = (
        ["listen", "syn", "establish"]
        + [
            "request_rx",
            *[k for _ in range(4) for k in ("response_tx", "response_ack")],
            "timer_idle",
        ]
        * 2
        + ["peer_fin", "close", "final_ack", "listener_close"]
    )
    if [p["kind"] for p in metrics["phases"]] != expected:
        raise ValueError("Incomplete phase sequence")
    phases = Counter()
    for p in metrics["phases"]:
        if type(p["instructions"]) is not int or p["instructions"] <= 0:
            raise ValueError("Invalid phase count")
        phases[p["kind"]] += p["instructions"]
    symbols = []
    for line in (run / "symbols.txt").read_text().splitlines():
        parts = line.split()
        if len(parts) == 4 and parts[2] in ("T", "t"):
            symbols.append((int(parts[0], 16), int(parts[1], 16), parts[3]))
    symbols.sort()
    starts = [s[0] for s in symbols]
    hotspots = Counter()
    stack_hotspots = Counter()
    boundaries = {s[2]: s[0] for s in symbols if s[2] in ("z0_stack_begin", "z0_stack_end")}
    if len(boundaries) != 2:
        raise ValueError("Missing stack boundary symbols")
    count = 0
    active = False
    windows = 0

    def events():
        nonlocal count, active, windows
        with gzip.open(run / "accesses.csv.gz", "rt") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != ["phase", "pc", "address", "size", "operation"]:
                raise ValueError("Unexpected trace header")
            for row in reader:
                phase, pc, address, size = (int(row[k]) for k in ("phase", "pc", "address", "size"))
                if phase != 0 or not 0x80000000 <= address < address + size <= 0x88000000:
                    raise ValueError("Invalid continuous trace address or phase")
                op = row["operation"]
                if op == "I":
                    if pc == boundaries["z0_stack_begin"]:
                        if active:
                            raise ValueError("Nested stack window")
                        active = True
                        windows += 1
                    if pc == boundaries["z0_stack_end"]:
                        if not active:
                            raise ValueError("Stack window end without start")
                        active = False
                    if pc != address or size not in (2, 4):
                        raise ValueError("Instruction mapping mismatch")
                    index = bisect.bisect_right(starts, pc) - 1
                    symbol = symbols[index] if index >= 0 else None
                    name = symbol[2] if symbol and pc < symbol[0] + symbol[1] else "unresolved"
                    hotspots[name] += 1
                    if active:
                        stack_hotspots[name] += 1
                count += 1
                yield address, size, op

    model = replay_split(events())
    if active or windows != len(expected):
        raise ValueError("Incomplete stack windows")
    model["initial_state"] = "cold at session start; continuous including peer and snapshots"
    if f"tcp_trace_complete={count},phases=1" not in (run / "qemu.log").read_text():
        raise ValueError("Trace completion receipt missing")
    result.update(
        schema="tcp-session-z0-v1",
        phases=dict(phases),
        measurements=metrics,
        measured_stack_window_instructions=sum(phases.values()),
        cache=model,
        hotspots_including_harness=hotspots.most_common(20),
        stack_window_hotspots=stack_hotspots.most_common(20),
        stack_window_trace_instructions=sum(stack_hotspots.values()),
        scope="single-task NO_SYS=1; IRQ masked; peer and RAM snapshots in cache trace; no cycles",
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--qemu", default=shutil.which("qemu-system-riscv32"))
    parser.add_argument(
        "--toolchain", type=Path, default=ROOT / ".tools/xpack-riscv-none-elf-gcc-15.2.0-1/bin"
    )
    args = parser.parse_args()
    dest = args.output.resolve()
    dest.mkdir(parents=True, exist_ok=False)
    toolchain = args.toolchain.resolve()
    source = json.loads((ROOT / "references/tcp/lwip/SOURCE.json").read_text())
    for name, expected in source["files"].items():
        if digest(ROOT / "references/tcp/lwip" / name) != expected:
            raise ValueError("Changed lwIP source: " + name)
    plugin = dest / ("trace.dylib" if platform.system() == "Darwin" else "trace.so")
    link = (
        ["-dynamiclib", "-undefined", "dynamic_lookup"]
        if platform.system() == "Darwin"
        else ["-shared", "-fPIC"]
    )
    plugin_cmd = [
        "cc",
        *link,
        "-O2",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-I" + str(ROOT / "third_party/qemu-cache"),
        str(ROOT / "tools/tcp/trace.c"),
        "-o",
        str(plugin),
        *shlex.split(subprocess.check_output(["pkg-config", "--cflags", "glib-2.0"], text=True)),
    ]
    command(plugin_cmd, ROOT, dest / "plugin-build.log")
    build = dest / "build"
    build_cmd = [
        "make",
        "-j4",
        "-C",
        str(ROOT / "firmware"),
        "CASE=tcp_request_response",
        "OUT=" + str(build),
        "TOOLCHAIN=" + str(toolchain),
    ]
    command(build_cmd, ROOT, dest / "build.log")
    elf = build / "firmware.elf"
    symbols = subprocess.check_output(
        [str(toolchain / "riscv-none-elf-nm"), "-S", str(elf)], text=True
    )
    addresses = {
        p[3]: int(p[0], 16) for line in symbols.splitlines() if len(p := line.split()) == 4
    }
    manifest = dict(
        schema="tcp-session-capture-v1",
        source=source,
        build_command=build_cmd,
        plugin_command=plugin_cmd,
        runs=[],
        sources={},
        tools={},
    )
    for name, path in [("qemu", Path(args.qemu)), ("gcc", toolchain / "riscv-none-elf-gcc")]:
        manifest["tools"][name] = dict(
            sha256=digest(path),
            version=subprocess.check_output([str(path), "--version"], text=True).splitlines()[0],
        )
    dependencies = {
        ROOT / "firmware/Makefile",
        ROOT / "tools/tcp/run_session.py",
        ROOT / "tools/tcp/trace.c",
        ROOT / "third_party/qemu-cache/qemu-plugin.h",
        ROOT / "third_party/FreeRTOS/FreeRTOS/Demo/RISC-V_RV32_QEMU_VIRT_GCC/build/gcc/fake_rom.ld",
    }
    for dep in build.glob("*.d"):
        for token in shlex.split(dep.read_text().replace("\\\n", " ").split(":", 1)[1]):
            path = (ROOT / "firmware" / token).resolve()
            if not token.endswith(":") and path.is_file():
                dependencies.add(path)
    dependencies.update((ROOT / "src/psf_lab").rglob("*.py"))
    manifest["sources"] = {str(p.relative_to(ROOT)): digest(p) for p in dependencies}
    results = []
    for repeat in (1, 2, 3):
        run = dest / f"z0-{repeat}"
        run.mkdir()
        shutil.copy2(elf, run / "firmware.elf")
        shutil.copy2(build / "firmware.map", run / "firmware.map")
        (run / "symbols.txt").write_text(symbols)
        (run / "size.txt").write_text(
            subprocess.check_output([str(toolchain / "riscv-none-elf-size"), str(elf)], text=True)
        )
        raw = run / "accesses.csv"
        parameters = (
            f"{plugin},begin={addresses['tcp_capture_begin']:x},"
            f"end={addresses['tcp_capture_end']:x},out={raw}"
        )
        cmd = [args.qemu, *QEMU_FLAGS, "-plugin", parameters, "-kernel", str(run / "firmware.elf")]
        command(cmd, run, run / "qemu.log")
        with raw.open("rb") as f, gzip.open(run / "accesses.csv.gz", "wb") as target:
            shutil.copyfileobj(f, target)
        raw.unlink()
        result = analyze(run)
        write_json(run / "analysis.json", result)
        write_json(
            run / "manifest.json",
            dict(command=cmd, files={p.name: digest(p) for p in run.iterdir()}),
        )
        manifest["runs"].append(dict(name=run.name, manifest_sha256=digest(run / "manifest.json")))
        results.append(result)
    if any(r != results[0] for r in results[1:]):
        raise ValueError("Non-repeatable Z0 measurements")
    write_json(dest / "manifest.json", manifest)
    print(
        json.dumps(
            dict(
                status="PASS",
                repeats=3,
                packets_per_run=results[0]["packets"],
                phases=results[0]["phases"],
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
