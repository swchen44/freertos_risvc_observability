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


def run_batch(root: Path, probe: Path, output: Path) -> dict:
    if output.exists():
        raise ValueError("Formal output must be new")
    if subprocess.run(["git", "check-ignore", "-q", str(output)], cwd=root).returncode:
        raise ValueError("Formal output must be ignored until captures finish; use runs/local")
    gate = json.loads((probe / "probe-gate.json").read_text())
    if (
        gate.get("passed") is not True
        or gate.get("runs") != 8
        or {r["candidate"] for r in gate["candidates"]} != set(CANDIDATES)
    ):
        raise ValueError("Invalid probe gate")
    for candidate in gate["candidates"]:
        folder = probe / candidate["candidate"]
        verify_file_hashes(
            folder, {"manifest.json": candidate["manifest_sha256"]}, {"manifest.json"}
        )
        manifest = json.loads((folder / "manifest.json").read_text())
        for record in manifest["runs"]:
            run = folder / f"enabled-{record['mode']}-{record['repeat']}"
            verify_file_hashes(
                run, {"manifest.json": record["run_manifest_sha256"]}, {"manifest.json"}
            )
            saved = json.loads((run / "manifest.json").read_text())
            verify_file_hashes(
                run,
                saved["files"],
                {
                    "firmware.elf",
                    "accesses.csv.gz",
                    "trace.psf",
                    "context-events.jsonl",
                    "parity.json",
                    "context-intervals.json",
                },
            )
            if any(
                record.get(k) is not True for k in ("accepted", "parity_passed", "context_exact")
            ):
                raise ValueError("Unaccepted probe")
    output.mkdir(parents=True)
    records = []
    for candidate in CANDIDATES:
        result = run_context_case(
            root,
            root / "runs/tcp-workload-matrix-v1" / candidate,
            output / candidate,
            repeats=3,
            context_enabled=True,
        )
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
