"""Run fixed sysram-10/500 MHz live-cost control and injection pairs on QEMU API4."""

import argparse
import gzip
import json
import platform
import re
import shlex
import shutil
import subprocess
import time
from pathlib import Path

from run_transfer import command

from psf_lab.live_cache import audit_accesses, compare_guest
from psf_lab.live_cache_irq import compare_irq, validate_irq_trace, validate_mmio
from psf_lab.parser.semantic import parse_trace
from psf_lab.provenance import require_clean_tree
from psf_lab.runner import QEMU_FLAGS, digest, write_json
from psf_lab.tcp_packets import decode_packet
from psf_lab.tcp_session import validate_request_pbufs, validate_session
from psf_lab.tcp_workload import load_workload

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qemu", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, choices=(1, 3), default=3)
    parser.add_argument(
        "--case", choices=("synthetic", "tcp", "irq", "tcp-irq"), default="synthetic"
    )
    parser.add_argument("--checksum-opt", choices=("Os", "O2"), default="Os")
    parser.add_argument("--cache-profile", choices=("standard", "small"), default="standard")
    parser.add_argument(
        "--tcp-variant", choices=("baseline", "layout", "checksum", "pbuf"), default="baseline"
    )
    parser.add_argument("--tcp-workload", choices=("linear", "fragmented"), default="linear")
    parser.add_argument("--workload-id")
    args = parser.parse_args()
    workload = None
    if args.workload_id:
        if args.tcp_workload != "linear":
            parser.error("--workload-id and --tcp-workload fragmented are mutually exclusive")
        if args.case != "tcp-irq" or args.tcp_variant not in ("baseline", "pbuf"):
            parser.error("Matrix requires tcp-irq and baseline/pbuf")
        if args.cache_profile != "small" or args.checksum_opt != "Os":
            parser.error("Matrix requires small cache and Os")
        try:
            workload = load_workload(ROOT / "cases/tcp/workload-matrix-v1.json", args.workload_id)
        except ValueError as error:
            parser.error(str(error))
    is_tcp = args.case in ("tcp", "tcp-irq")
    if args.checksum_opt != "Os" and not is_tcp:
        parser.error("--checksum-opt requires tcp or tcp-irq")
    if args.tcp_variant != "baseline" and (not is_tcp or args.checksum_opt != "Os"):
        parser.error("TCP variants require tcp/tcp-irq and -Os")
    if args.tcp_workload != "linear" and not is_tcp:
        parser.error("--tcp-workload requires tcp or tcp-irq")
    has_irq = args.case in ("irq", "tcp-irq")
    irq_scenario = "tcp" if is_tcp else "memory"
    case = "tcp_request_response" if is_tcp else ("live_cache_irq" if has_irq else "live_cache")
    dest, qemu = args.output.resolve(), args.qemu.resolve()
    decision = json.loads((ROOT / "cases/timing-experiments/500mhz.json").read_text())
    if (
        decision["frequency_hz"] != 500000000
        or decision["profile"] != "cases/timing/sysram-10.json"
    ):
        parser.error("This bounded plugin supports only sysram-10 at 500 MHz")
    # Native model parameters are fixed. Reject drift from its validated profile.
    expected_profile = json.loads(
        (ROOT / "artifacts/verification/timing-500mhz/conversion.json").read_text()
    )["profile_sha256"]
    if digest(ROOT / decision["profile"]) != expected_profile:
        parser.error("Fixed native model profile changed; revalidate before running")
    profile_path = (
        "cases/timing/sysram-10" + ("-small" if args.cache_profile == "small" else "") + ".json"
    )
    profile = json.loads((ROOT / profile_path).read_text())
    expected = json.loads((ROOT / decision["profile"]).read_text())
    if args.cache_profile == "small":
        expected["name"] = "sysram-10-small"
        for cache in expected["caches"].values():
            cache["size"] //= 2
    if profile != expected:
        parser.error("Unsupported native timing profile")
    source_commit = require_clean_tree(ROOT) if workload else None
    dest.mkdir(parents=True, exist_ok=False)
    toolchain = ROOT / ".tools/xpack-riscv-none-elf-gcc-15.2.0-1/bin"
    build = dest / "build"
    build_cmd = [
        "make",
        "-j4",
        "-C",
        str(ROOT / "firmware"),
        "CASE=" + case,
        "CHECKSUM_OPT=" + args.checksum_opt,
        "TCP_VARIANT=" + args.tcp_variant,
        "TCP_WORKLOAD=" + args.tcp_workload,
        "OUT=" + str(build),
        "TOOLCHAIN=" + str(toolchain),
    ]
    if is_tcp:
        build_cmd.append(
            "CASE_SRC=" + ("tcp_request_response_irq" if has_irq else "tcp_request_response_live")
        )
    if workload:
        header = dest / "workload.h"
        header.write_text(
            "#define POC_MATRIX_REQUEST 1\n#define POC_REQUEST_BYTES "
            + str(workload["request_bytes"])
            + "\n#define POC_REQUEST_SEGMENTS "
            + ",".join(map(str, workload["request_segments"]))
            + "\n"
        )
        build_cmd.append("WORKLOAD_HEADER=" + str(header))
    command(build_cmd, ROOT, dest / "build.log")
    plugin = dest / ("live_cache.dylib" if platform.system() == "Darwin" else "live_cache.so")
    flags = (
        ["-dynamiclib", "-undefined", "dynamic_lookup"]
        if platform.system() == "Darwin"
        else ["-shared", "-fPIC"]
    )
    plugin_cmd = [
        "cc",
        *flags,
        "-O2",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-I" + str(ROOT / "references/qemu-time-control/include/qemu"),
        str(ROOT / "tools/tcp/live_cache.c"),
        str(ROOT / "tools/qemu/live_timing.c"),
        "-o",
        str(plugin),
        *shlex.split(subprocess.check_output(["pkg-config", "--cflags", "glib-2.0"], text=True)),
    ]
    if args.cache_profile == "small":
        plugin_cmd.append("-DPOC_SMALL_CACHE")
    if has_irq:
        plugin_cmd.append("-DPOC_LIVE_IRQ")
    command(plugin_cmd, ROOT, dest / "plugin-build.log")
    elf = build / "firmware.elf"
    symbols = subprocess.check_output(
        [str(toolchain / "riscv-none-elf-nm"), "-S", str(elf)], text=True
    )
    addresses = {
        p[3]: int(p[0], 16) for line in symbols.splitlines() if len(p := line.split()) == 4
    }
    markers = (
        ("live_cache_begin", "live_cache_end")
        if not is_tcp
        else ("tcp_capture_begin", "tcp_capture_end")
    )
    begin, end = (addresses[n] for n in markers)
    dependencies = {
        ROOT / name
        for name in (
            "firmware/Makefile",
            "tools/tcp/live_cache.c",
            "tools/tcp/run_live_cache.py",
            "tools/tcp/run_transfer.py",
            "tools/qemu/live_timing.c",
            "tools/qemu/live_timing.h",
            "tools/qemu/poc-clock-api.h",
            "src/psf_lab/live_cache.py",
            "src/psf_lab/live_cache_irq.py",
            "src/psf_lab/memory_timing.py",
            "src/psf_lab/cache_model.py",
            "src/psf_lab/tcp_packets.py",
            "src/psf_lab/tcp_session.py",
            "src/psf_lab/runner.py",
            "references/qemu-time-control/include/qemu/qemu-plugin.h",
            "cases/timing-experiments/500mhz.json",
            "cases/timing/sysram-10.json",
            "artifacts/verification/timing-500mhz/conversion.json",
            "third_party/FreeRTOS/FreeRTOS/Demo/RISC-V_RV32_QEMU_VIRT_GCC/build/gcc/fake_rom.ld",
        )
    }
    dependencies.add(ROOT / profile_path)
    if workload:
        dependencies.update(
            {
                ROOT / "cases/tcp/workload-matrix-v1.json",
                ROOT / "src/psf_lab/tcp_workload.py",
                header,
            }
        )
    if args.tcp_variant == "layout":
        dependencies.add(ROOT / "firmware/tcp_stack/hot-layout.ld")
    dependencies.update((ROOT / "src/psf_lab/parser").glob("*.py"))
    for dep in build.glob("*.d"):
        for token in shlex.split(dep.read_text().replace("\\\n", " ").split(":", 1)[1]):
            path = (ROOT / "firmware" / token).resolve()
            if not token.endswith(":") and path.is_file():
                dependencies.add(path)
    manifest = dict(
        build_command=build_cmd,
        plugin_command=plugin_cmd,
        qemu_sha256=digest(qemu),
        plugin_sha256=digest(plugin),
        gcc_sha256=digest(toolchain / "riscv-none-elf-gcc"),
        frequency_hz=500000000,
        checksum_opt=args.checksum_opt,
        tcp_variant=args.tcp_variant,
        tcp_workload=args.tcp_workload,
        cache_profile=profile_path,
        icount_shift=0,
        time_policy="existing 1 ns/instruction plus full serial memory service",
        sources={str(p.relative_to(ROOT)): digest(p) for p in dependencies},
        runs=[],
    )
    if workload:
        manifest.update(
            workload=workload,
            source_commit=source_commit,
            registry_sha256=digest(ROOT / "cases/tcp/workload-matrix-v1.json"),
        )
    results = []
    for enabled in (0, 1):
        for repeat in range(1, args.repeats + 1):
            run = dest / f"enabled-{enabled}-{repeat}"
            run.mkdir()
            shutil.copy2(elf, run / "firmware.elf")
            (run / "symbols.txt").write_text(symbols)
            cmd = [
                str(qemu),
                *QEMU_FLAGS,
                "-plugin",
                f"{plugin},begin={begin:x},end={end:x},enabled={enabled},out={run}/accesses.csv",
                "-kernel",
                str(run / "firmware.elf"),
            ]
            result = dict(run=run.name, enabled=bool(enabled), repeat=repeat, accepted=False)
            start = time.monotonic()
            with (run / "qemu.log").open("wb") as log:
                try:
                    proc = subprocess.run(
                        cmd, cwd=run, stdout=log, stderr=subprocess.STDOUT, timeout=20
                    )
                    result["exit_code"] = proc.returncode
                except subprocess.TimeoutExpired:
                    result["exit_code"] = None
            result["host_wall_seconds"] = time.monotonic() - start
            try:
                if result["exit_code"] != 0:
                    raise ValueError("QEMU failed or timed out")
                receipt = re.search(
                    r"live_cache_complete events=(\d+) cycles=(\d+) api_calls=(\d+)",
                    (run / "qemu.log").read_text(),
                )
                if receipt is None:
                    raise ValueError("Missing completion receipt")
                if has_irq:
                    mmio = re.findall(
                        r"live_cache_mmio pc=(\d+) address=(\d+) size=(\d+) op=([RW])",
                        (run / "qemu.log").read_text(),
                    )
                    count = re.search(
                        r"live_cache_mmio_count=(\d+)", (run / "qemu.log").read_text()
                    )
                    if count is None or int(count[1]) != len(mmio):
                        raise ValueError("Missing MMIO audit receipt")
                    for pc, address, size, op in mmio:
                        if not 0x80000000 <= int(pc) < 0x88000000:
                            raise ValueError("MMIO instruction PC outside RAM")
                        validate_mmio(int(address), int(size), op)
                    result["clint_mmio_excluded"] = len(mmio)
                audit = audit_accesses(run / "accesses.csv", profile=profile)
                if tuple(map(int, receipt.groups())) != (
                    audit["events"],
                    audit["cycles"],
                    audit["events"] if enabled else 0,
                ):
                    raise ValueError("Plugin receipt does not match audited stream")
                if args.case == "synthetic" and (
                    audit["operations"]["R"] != 2560 or audit["operations"]["W"] != 2560
                ):
                    raise ValueError("Synthetic load/store count disagrees with workload")
                m = json.loads((run / "live-cache.json").read_text())
                oracle = json.loads((run / "oracle.json").read_text())
                if m["case"] != case or not oracle["complete"] or oracle["case_id"] != m["case"]:
                    raise ValueError("Guest did not complete")
                if (
                    m["work"]
                    != {"synthetic": 13090560, "tcp": 11680, "irq": 210677760, "tcp-irq": 11680}[
                        args.case
                    ]
                ):
                    raise ValueError("Unexpected work checksum")
                if is_tcp:
                    metrics = json.loads((run / "session.json").read_text())
                    packets = []
                    for index, entry in enumerate(metrics["packets"]):
                        if entry["file"] != f"packet-{index}.bin":
                            raise ValueError("Unexpected packet filename")
                        packet = decode_packet((run / entry["file"]).read_bytes())
                        rx = entry["direction"] == "rx"
                        if (
                            packet["src"],
                            packet["dst"],
                            packet["source_ip"],
                            packet["destination_ip"],
                        ) != (
                            (50000, 1234, [10, 0, 0, 2], [10, 0, 0, 1])
                            if rx
                            else (1234, 50000, [10, 0, 0, 1], [10, 0, 0, 2])
                        ):
                            raise ValueError("Peer address mismatch")
                        packets.append(dict(packet, direction=entry["direction"]))
                    result["tcp"] = validate_session(packets, metrics, workload=workload)
                    result["pbuf_receipt"] = validate_request_pbufs(
                        metrics, args.tcp_workload, workload=workload
                    )
                    if oracle["sent_ids"] != [11680] or oracle["received_ids"] != [11680]:
                        raise ValueError("Incomplete TCP firmware oracle")
                trace = parse_trace((run / "trace.psf").read_bytes())
                marks = [
                    (e["fields"]["phase"], e["fields"].get("request_id"), e["timestamp_raw"])
                    for e in trace["events"]
                    if e["fields"].get("phase")
                ]
                if has_irq:
                    result["switches"] = validate_irq_trace(trace, m, scenario=irq_scenario)
                else:
                    begin_mark, end_mark = (
                        ("CACHE_BEGIN", "CACHE_END")
                        if args.case == "synthetic"
                        else ("TCP_SESSION_BEGIN", "TCP_SESSION_END")
                    )
                    if [(n, i) for n, i, _ in marks] != [
                        (begin_mark, 0),
                        (end_mark, 0),
                        ("COMPLETE", 0),
                    ] or not marks[0][2] <= m["before"] <= m["after"] <= marks[1][2]:
                        raise ValueError("PSF boundaries disagree with guest clock")
                result.update(accepted=True, audit=audit, measurement=m)
            except (ValueError, KeyError, OSError) as error:
                result["error"] = str(error)
            raw = run / "accesses.csv"
            if raw.exists():
                (run / "accesses.csv.gz").write_bytes(gzip.compress(raw.read_bytes(), mtime=0))
                raw.unlink()
            write_json(
                run / "manifest.json",
                dict(command=cmd, result=result, files={p.name: digest(p) for p in run.iterdir()}),
            )
            manifest["runs"].append(dict(name=run.name, sha256=digest(run / "manifest.json")))
            results.append(result)
            print(json.dumps(result), flush=True)
    comparisons = []
    if all(r["accepted"] for r in results):
        for repeat in range(1, args.repeats + 1):
            control = next(r for r in results if not r["enabled"] and r["repeat"] == repeat)
            active = next(r for r in results if r["enabled"] and r["repeat"] == repeat)
            try:
                if not has_irq and control["audit"] != active["audit"]:
                    raise ValueError("Control and injection access streams differ")
                comparisons.append(
                    dict(
                        accepted=True,
                        repeat=repeat,
                        **(
                            compare_irq(
                                control["measurement"],
                                active["measurement"],
                                control["audit"],
                                active["audit"],
                                scenario=irq_scenario,
                            )
                            if has_irq
                            else compare_guest(
                                control["measurement"], active["measurement"], active["audit"]["ns"]
                            )
                        ),
                    )
                )
            except ValueError as error:
                comparisons.append(dict(accepted=False, repeat=repeat, error=str(error)))
    repeatable = all(r["accepted"] for r in results) and all(
        r["audit"] == next(x["audit"] for x in results if x["enabled"] == r["enabled"])
        for r in results
    )
    passed = (
        repeatable and len(comparisons) == args.repeats and all(c["accepted"] for c in comparisons)
    )
    write_json(
        dest / "results.json",
        dict(passed=passed, repeatable=repeatable, runs=results, comparisons=comparisons),
    )
    manifest["results_sha256"] = digest(dest / "results.json")
    write_json(dest / "manifest.json", manifest)
    print(json.dumps(comparisons, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
