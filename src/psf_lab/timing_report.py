"""Replay a captured Z0 session with explicit serialized memory latency profiles."""

import argparse
import bisect
import csv
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from psf_lab.memory_timing import COSTS, from_profile
from psf_lab.runner import digest, write_json
from psf_lab.tcp_report import verify_files


def replay_run(run, profile):
    model = from_profile(profile)
    manifest = json.loads((run / "manifest.json").read_text())
    required = {"accesses.csv.gz", "symbols.txt", "qemu.log"}
    if not required <= set(manifest["files"]):
        raise ValueError("Missing trace evidence hashes")
    verify_files(run, manifest)
    symbols = []
    for line in (run / "symbols.txt").read_text().splitlines():
        fields = line.split()
        if len(fields) == 4 and fields[2] in ("T", "t"):
            symbols.append((int(fields[0], 16), int(fields[1], 16), fields[3]))
    symbols.sort()
    starts = [s[0] for s in symbols]
    markers = {s[2]: s[0] for s in symbols if s[2] in ("z0_stack_begin", "z0_stack_end")}
    if len(markers) != 2:
        raise ValueError("Expected Z0 stack boundary symbols")
    active = False
    windows = 0
    count = 0
    totals = dict(stack_window=0, harness=0)
    functions = defaultdict(Counter)
    with gzip.open(run / "accesses.csv.gz", "rt") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ["phase", "pc", "address", "size", "operation"]:
            raise ValueError("Unexpected trace schema")
        for row in reader:
            phase, pc, address, size = (int(row[k]) for k in ("phase", "pc", "address", "size"))
            op = row["operation"]
            if phase != 0 or not 0x80000000 <= pc < 0x88000000:
                raise ValueError("Expected one continuous bare-metal Z0 capture")
            if op == "I":
                if pc != address or size not in (2, 4):
                    raise ValueError("Invalid instruction mapping")
                if pc == markers["z0_stack_begin"]:
                    if active:
                        raise ValueError("Nested stack window")
                    active = True
                    windows += 1
                if pc == markers["z0_stack_end"]:
                    if not active:
                        raise ValueError("Unexpected stack window end")
                    active = False
            cost = model.access(address, size, op)
            scope = "stack_window" if active else "harness"
            totals[scope] += cost["total"]
            index = bisect.bisect_right(starts, pc) - 1
            symbol = symbols[index] if index >= 0 else None
            name = symbol[2] if symbol and pc < symbol[0] + symbol[1] else "unresolved"
            functions[(scope, name)].update(cost)
            count += 1
    receipt = f"tcp_trace_complete={count},phases=1"
    if active or not windows or receipt not in (run / "qemu.log").read_text().splitlines():
        raise ValueError("Missing or incomplete trace completion receipt")
    return dict(
        schema="timing-report-v1",
        run=run.name,
        profile=profile,
        profile_sha256=hashlib.sha256(json.dumps(profile, sort_keys=True).encode()).hexdigest(),
        evidence={name: digest(run / name) for name in sorted(required | {"manifest.json"})},
        events=count,
        stack_windows=windows,
        scope_cost_cycles=totals,
        model=model.result(),
        attribution=(
            "self PC; stack windows include callbacks/assertions; cache state includes harness"
        ),
        functions=[
            dict(scope=scope, function=name, **cost)
            for (scope, name), cost in sorted(
                functions.items(), key=lambda item: (-item[1]["total"], item[0])
            )
        ],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--profile", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    reports = [replay_run(args.run, json.loads(p.read_text())) for p in args.profile]
    write_json(args.output / "timing.json", dict(schema="timing-comparison-v1", reports=reports))
    with (args.output / "functions.csv").open("w", newline="") as stream:
        columns = ["profile", "scope", "function", *COSTS, "total"]
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for report in reports:
            for row in report["functions"]:
                writer.writerow(dict(profile=report["profile"]["name"], **row))
    sources = [
        Path(__file__),
        Path(__file__).with_name("memory_timing.py"),
        Path(__file__).with_name("cache_model.py"),
        Path(__file__).with_name("tcp_report.py"),
        Path(__file__).with_name("runner.py"),
    ]
    write_json(
        args.output / "manifest.json",
        dict(
            schema="timing-replay-receipt-v1",
            sources={p.name: digest(p) for p in sources},
            files={p.name: digest(p) for p in args.output.iterdir()},
        ),
    )
    print(
        json.dumps(
            [
                dict(
                    profile=r["profile"]["name"],
                    estimated_memory_service_cycles=r["model"]["estimated_memory_service_cycles"],
                    guest_time_changed=False,
                )
                for r in reports
            ],
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
