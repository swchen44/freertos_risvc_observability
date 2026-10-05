"""Verify complete workload pairs and their saved source/protocol/timing evidence."""

import csv
import gzip
import hashlib
import json
import subprocess
from pathlib import Path

from psf_lab.live_cache_irq import compare_irq, validate_irq_trace
from psf_lab.parser.semantic import parse_trace
from psf_lab.runner import digest, write_json
from psf_lab.tcp_hotspots import profile_misses
from psf_lab.tcp_packets import decode_packet
from psf_lab.tcp_session import validate_request_pbufs, validate_session
from psf_lab.tcp_workload import load_workload


def validate_attempts(rows):
    expected = {(bool(e), n) for e in (0, 1) for n in (1, 2, 3)}
    if (
        len(rows) != 6
        or any(
            type(r.get("enabled")) is not bool
            or type(r.get("repeat")) is not int
            or r.get("accepted") is not True
            for r in rows
        )
        or {(r["enabled"], r["repeat"]) for r in rows} != expected
    ):
        raise ValueError("Expected six accepted control/injection attempts")


def checked(path, sha):
    if digest(path) != sha:
        raise ValueError("Evidence hash mismatch: " + str(path))


def require_keys(mapping, expected):
    if not isinstance(mapping, dict) or not set(expected) <= mapping.keys():
        raise ValueError("Missing required hash entries")


def plugin_contract(root, runset, manifest):
    command = manifest["plugin_command"][:]
    if command.count("-o") != 1:
        raise ValueError("Invalid plugin output argument")
    index = command.index("-o") + 1
    path = Path(command[index])
    # Saved absolute build paths are provenance; restored trees resolve the basename locally.
    if path.name not in {"live_cache.dylib", "live_cache.so"} or path.parent.name != runset.name:
        raise ValueError("Invalid plugin output path")
    checked(runset / path.name, manifest["plugin_sha256"])
    command[index] = "<plugin-output>"
    return command


def analyze_matrix(root, directory, output):
    output.mkdir(parents=True, exist_ok=False)
    registry = root / "cases/tcp/workload-matrix-v1.json"
    expected = {f"A{i:02}-{v}" for i in range(1, 9) for v in ("baseline", "pbuf")}
    if {p.name for p in directory.iterdir() if p.is_dir()} != expected:
        raise ValueError("Expected all sixteen workload/variant groups")
    profile = json.loads((root / "cases/timing/sysram-10-small.json").read_text())
    toolchain = root / ".tools/xpack-riscv-none-elf-gcc-15.2.0-1/bin"
    environment, packet_references, rows, sources = None, {}, [], {}
    plugin_reference, plugin_hashes, attempts = None, {}, {}
    for name in sorted(expected):
        runset = directory / name
        manifest = json.loads((runset / "manifest.json").read_text())
        case_id, variant = name.split("-")
        workload = load_workload(registry, case_id)
        if (
            manifest.get("workload") != workload
            or not manifest.get("source_commit")
            or manifest["tcp_variant"] != variant
            or manifest["checksum_opt"] != "Os"
            or manifest["cache_profile"] != "cases/timing/sysram-10-small.json"
        ):
            raise ValueError("Workload or tool configuration mismatch")
        checked(registry, manifest["registry_sha256"])
        contract = plugin_contract(root, runset, manifest)
        if plugin_reference is not None and contract != plugin_reference:
            raise ValueError("Mixed plugin build commands")
        plugin_reference = contract
        plugin_hashes[name] = manifest["plugin_sha256"]
        require_keys(
            manifest["sources"],
            {
                "firmware/Makefile",
                "firmware/app/cases/tcp_request_response.c",
                "tools/tcp/live_cache.c",
                "tools/qemu/live_timing.c",
                "tools/qemu/live_timing.h",
                "tools/tcp/run_live_cache.py",
                "src/psf_lab/tcp_session.py",
                "src/psf_lab/tcp_workload.py",
                "cases/tcp/workload-matrix-v1.json",
                "cases/timing/sysram-10-small.json",
                str((runset / "workload.h").relative_to(root)),
            },
        )
        env = {
            k: manifest[k] for k in ("qemu_sha256", "gcc_sha256", "frequency_hz", "icount_shift")
        }
        if environment is not None and environment != env:
            raise ValueError("Mixed tool environments")
        environment = env
        for path, sha in manifest["sources"].items():
            if Path(path).is_absolute() or ".." in Path(path).parts:
                raise ValueError("Invalid source path")
            checked(root / path, sha)
        sources[str((runset / "manifest.json").relative_to(root))] = digest(
            runset / "manifest.json"
        )
        checked(runset / "results.json", manifest["results_sha256"])
        results = json.loads((runset / "results.json").read_text())
        validate_attempts(results["runs"])
        attempts[name] = results["runs"]
        if results["passed"] is not True or results["repeatable"] is not True:
            raise ValueError("Unsuccessful runset")
        compile_lines = [
            line
            for line in (runset / "build.log").read_text().splitlines()
            if " -c " in line and "riscv-none-elf-gcc" in line
        ]
        if not compile_lines or any(
            {w for w in line.split() if w.startswith("-O")} != {"-Os"} for line in compile_lines
        ):
            raise ValueError("Compiler optimization mismatch")
        expected_names = {r["run"] for r in results["runs"]}
        if (
            len(manifest["runs"]) != 6
            or {r["name"] for r in manifest["runs"]} != expected_names
            or expected_names != {f"enabled-{e}-{n}" for e in (0, 1) for n in (1, 2, 3)}
        ):
            raise ValueError("Run manifest coverage mismatch")
        for record in manifest["runs"]:
            path = runset / record["name"]
            checked(path / "manifest.json", record["sha256"])
            receipt = json.loads((path / "manifest.json").read_text())
            require_keys(
                receipt["files"],
                {
                    "firmware.elf",
                    "symbols.txt",
                    "trace.psf",
                    "session.json",
                    "accesses.csv.gz",
                    "oracle.json",
                    "live-cache.json",
                },
            )
            for file, sha in receipt["files"].items():
                if Path(file).name != file:
                    raise ValueError("Invalid evidence path")
                checked(path / file, sha)
            result = next(r for r in results["runs"] if r["run"] == record["name"])
            if receipt["result"] != result:
                raise ValueError("Per-run result mismatch")
            session = json.loads((path / "session.json").read_text())
            require_keys(receipt["files"], {p["file"] for p in session["packets"]})
            packets = []
            for index, p in enumerate(session["packets"]):
                if p["file"] != f"packet-{index}.bin":
                    raise ValueError("Invalid packet path")
                packets.append(
                    dict(decode_packet((path / p["file"]).read_bytes()), direction=p["direction"])
                )
            if validate_session(packets, session, workload=workload) != result["tcp"]:
                raise ValueError("Protocol oracle disagreement")
            if (
                validate_request_pbufs(session, "matrix", workload=workload)
                != result["pbuf_receipt"]
            ):
                raise ValueError("Pbuf oracle disagreement")
            if any("addresses" not in shape for shape in session["request_pbufs"]):
                raise ValueError("Missing observed payload addresses")
            hashes = [digest(path / p["file"]) for p in session["packets"]]
            if case_id in packet_references and packet_references[case_id] != hashes:
                raise ValueError("Same-workload wire bytes changed")
            packet_references[case_id] = hashes
            switches = validate_irq_trace(
                parse_trace((path / "trace.psf").read_bytes()),
                result["measurement"],
                scenario="tcp",
            )
            if switches != result["switches"]:
                raise ValueError("PSF switches changed")
            # Each stream was independently audited during capture. Recheck its uncompressed
            # digest here; replay a representative stream below after repeat identity checks.
            with gzip.open(path / "accesses.csv.gz", "rb") as stream:
                if (
                    hashlib.file_digest(stream, "sha256").hexdigest()
                    != result["audit"]["stream_sha256"]
                ):
                    raise ValueError("Raw stream changed")
        if len(results["comparisons"]) != 3:
            raise ValueError("Missing timing pairs")
        for n in (1, 2, 3):
            pair = [
                next(r for r in results["runs"] if r["repeat"] == n and r["enabled"] == e)
                for e in (False, True)
            ]
            comparison = compare_irq(
                pair[0]["measurement"],
                pair[1]["measurement"],
                pair[0]["audit"],
                pair[1]["audit"],
                scenario="tcp",
            )
            saved = next(r for r in results["comparisons"] if r["repeat"] == n)
            if saved != dict(repeat=n, accepted=True, **comparison):
                raise ValueError("Timing comparison changed")
        for enabled in (False, True):
            repeats = [r for r in results["runs"] if r["enabled"] == enabled]
            if any(
                r["audit"] != repeats[0]["audit"] or r["measurement"] != repeats[0]["measurement"]
                for r in repeats
            ):
                raise ValueError("Non-repeatable model results")
        entry = next(r for r in results["runs"] if r["enabled"] and r["repeat"] == 1)
        path = runset / entry["run"]
        symbols = []
        for line in (path / "symbols.txt").read_text().splitlines():
            fields = line.split()
            if len(fields) == 4 and fields[2] in ("T", "t"):
                symbols.append((int(fields[0], 16), int(fields[1], 16), fields[3]))
        named = {s[2]: s for s in symbols}
        with gzip.open(path / "accesses.csv.gz", "rt") as stream:
            stats = profile_misses(
                csv.DictReader(stream),
                profile,
                symbols,
                stack_markers=(named["z0_stack_begin"][0], named["z0_stack_end"][0]),
            )
        if (
            stats["totals"]["cycles"] != entry["audit"]["cycles"]
            or stats["events"] != entry["audit"]["events"]
        ):
            raise ValueError("Replay total mismatch")
        for level in ("l1i", "l1d", "l2"):
            for key in ("accesses", "misses", "compulsory", "conflict", "capacity"):
                stats["totals"].setdefault(level + "_" + key, 0)
        write_json(output / (name + "-profile.json"), stats)
        for suffix, args in [("assembly.txt", ["objdump", "-d"]), ("size.txt", ["size"])]:
            text = subprocess.check_output(
                [
                    str(toolchain / ("riscv-none-elf-" + args[0])),
                    *args[1:],
                    str(path / "firmware.elf"),
                ],
                text=True,
            )
            (output / (name + "-" + suffix)).write_text(text)
        text, data, bss = map(
            int, (output / (name + "-size.txt")).read_text().splitlines()[1].split()[:3]
        )
        session = json.loads((path / "session.json").read_text())
        m = entry["measurement"]
        rows.append(
            dict(
                label=name,
                workload_id=case_id,
                workload=workload,
                variant=variant,
                run=str(runset.relative_to(root)),
                repeats=3,
                guest_ns=(m["after"] - m["before"]) * 100,
                text=text,
                data=data,
                bss=bss,
                ticks=m["ticks"],
                packets=entry["tcp"]["packets"],
                request_pbufs=session["request_pbufs"],
                pbuf_receipt=entry["pbuf_receipt"],
                request_phase_instructions=[
                    p["instructions"] for p in session["phases"] if p["kind"] == "request_rx"
                ],
                **stats["totals"],
                stack_cycles=stats["scopes"]["stack_window_including_preemption"]["cycles"],
                harness_cycles=stats["scopes"]["harness_window"]["cycles"],
                cost_cycles=stats["model"]["cost_cycles"],
                function_sizes={
                    k: dict(address=hex(v[0]), size=v[1])
                    for k, v in named.items()
                    if k
                    in ("on_recv", "tcp_input", "tcp_output", "tcp_receive", "lwip_standard_chksum")
                },
            )
        )
        print(name, "verified", flush=True)
    report = dict(
        schema="tcp-workload-matrix-v1",
        passed=True,
        environment=environment,
        packet_hashes_by_workload=packet_references,
        results=rows,
        sources=sources,
        attempts=attempts,
        representative="Each row is injection repeat 1; all six attempts per group are in attempts",
        plugin_build_contract=plugin_reference,
        plugin_hashes=plugin_hashes,
        analysis_sources={str(Path(__file__).resolve().relative_to(root)): digest(Path(__file__))},
    )
    write_json(output / "comparison.json", report)
    keys = [
        "label",
        "workload_id",
        "variant",
        "guest_ns",
        "instructions",
        "cycles",
        "l1i_misses",
        "l1d_misses",
        "l2_misses",
        "stack_cycles",
        "text",
        "data",
        "bss",
        "packets",
    ]
    with (output / "comparison.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return report
