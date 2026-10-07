"""Serial context formal batch, gated on independently verified probe evidence."""

import argparse
import json
import re
import subprocess
from pathlib import Path

from psf_lab.attribution_evidence import verify_file_hashes
from psf_lab.context_capture import run_context_case
from psf_lab.runner import digest, write_json

CANDIDATES = ("A02-baseline", "A02-pbuf", "A08-baseline", "A08-pbuf")


def validate_context_batch(records: list[dict]) -> None:
    expected = {(c, m, r) for c in CANDIDATES for m in (0, 1) for r in (1, 2, 3)}
    if len(records) != 24:
        raise ValueError("Expected exactly 24 formal captures")
    observed = set()
    for record in records:
        if (
            type(record.get("mode")) is not int
            or type(record.get("repeat")) is not int
            or any(
                record.get(k) is not True
                for k in ("context_enabled", "parity_passed", "context_exact")
            )
            or record.get("nested")
            or not re.fullmatch("[0-9a-f]{64}", record.get("run_manifest_sha256", ""))
        ):
            raise ValueError("Invalid formal capture evidence")
        observed.add((record["candidate"], record["mode"], record["repeat"]))
    if observed != expected:
        raise ValueError("Formal capture coverage mismatch")


def validate_probe_gate(probe: Path) -> None:
    gate = json.loads((probe / "probe-gate.json").read_text())
    candidates = gate.get("candidates", [])
    if (
        gate.get("schema") != "context-probe-gate-v1"
        or gate.get("passed") is not True
        or gate.get("runs") != 8
        or len(candidates) != 4
        or {r.get("candidate") for r in candidates} != set(CANDIDATES)
    ):
        raise ValueError("Invalid probe gate")
    collector = None
    for candidate in candidates:
        folder = probe / candidate["candidate"]
        verify_file_hashes(
            folder, {"manifest.json": candidate["manifest_sha256"]}, {"manifest.json"}
        )
        manifest = json.loads((folder / "manifest.json").read_text())
        runs = manifest.get("runs", [])
        if (
            manifest.get("candidate") != candidate["candidate"]
            or manifest.get("passed") is not True
            or len(runs) != 2
            or len(manifest.get("pair_checks", [])) != 1
            or any(type(r.get("mode")) is not int or type(r.get("repeat")) is not int for r in runs)
            or {(r["mode"], r["repeat"]) for r in runs} != {(0, 1), (1, 1)}
        ):
            raise ValueError("Expected two accepted probe modes per candidate")
        plugin = (
            "live_context.dylib" if (folder / "live_context.dylib").exists() else "live_context.so"
        )
        hashes = {
            "boundaries.json": manifest["boundary_sha256"],
            "boundaries.conf": manifest["boundary_config_sha256"],
            plugin: manifest["plugin_sha256"],
        }
        verify_file_hashes(folder, hashes, set(hashes))
        identity = (manifest["collector_source_commit"], manifest["collector_sources"])
        if collector is not None and collector != identity:
            raise ValueError("Mixed probe collector provenance")
        collector = identity
        for record in runs:
            if record.get("candidate") != candidate["candidate"] or any(
                record.get(k) is not True
                for k in ("context_enabled", "accepted", "parity_passed", "context_exact")
            ):
                raise ValueError("Invalid probe identity/acceptance")
            run = folder / f"enabled-{record['mode']}-{record['repeat']}"
            verify_file_hashes(
                run, {"manifest.json": record["run_manifest_sha256"]}, {"manifest.json"}
            )
            saved = json.loads((run / "manifest.json").read_text())
            if saved["result"] != {k: v for k, v in record.items() if k != "run_manifest_sha256"}:
                raise ValueError("Probe run/runset identity mismatch")
            verify_file_hashes(
                run,
                saved["files"],
                {
                    "firmware.elf",
                    "symbols.txt",
                    "accesses.csv.gz",
                    "trace.psf",
                    "session.json",
                    "oracle.json",
                    "live-cache.json",
                    "context-events.jsonl",
                    "parity.json",
                    "context-intervals.json",
                },
            )
            if saved["files"]["firmware.elf"] != manifest["guest_elf_sha256"]:
                raise ValueError("Probe ELF identity mismatch")
            session = json.loads((run / "session.json").read_text())
            verify_file_hashes(run, saved["files"], {p["file"] for p in session["packets"]})


def run_batch(root: Path, probe: Path, output: Path) -> dict:
    if output.exists():
        raise ValueError("Formal output must be new")
    if subprocess.run(["git", "check-ignore", "-q", str(output)], cwd=root).returncode:
        raise ValueError("Formal output must be ignored until captures finish; use runs/local")
    validate_probe_gate(probe)
    output.mkdir(parents=True)
    collector_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()
    records = []
    for candidate in CANDIDATES:
        result = run_context_case(
            root,
            root / "runs/tcp-workload-matrix-v1" / candidate,
            output / candidate,
            repeats=3,
            context_enabled=True,
        )
        if result["collector_source_commit"] != collector_commit:
            raise ValueError("Collector commit changed during formal batch")
        records.extend(result["runs"])
        write_json(output / "progress.json", dict(runs=records, complete=False))
        if not result["passed"]:
            raise ValueError("Formal candidate failed: " + candidate)
        print(candidate, "6 accepted", flush=True)
    validate_context_batch(records)
    result = dict(
        schema="context-formal-batch-v1",
        passed=True,
        runs=records,
        probe_gate_sha256=digest(probe / "probe-gate.json"),
    )
    write_json(output / "completion.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run_batch(Path.cwd(), args.probe.resolve(), args.output.resolve())
