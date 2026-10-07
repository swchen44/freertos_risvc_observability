"""Build reproducible context/role reports from accepted formal captures."""

import argparse
import csv
import gzip
import json
from pathlib import Path

from run_context_batch import validate_context_batch

from psf_lab.attribution_evidence import (
    build_role_ranges,
    load_capture_evidence,
    verify_file_hashes,
)
from psf_lab.cost_attribution import COST_KEYS, METRICS, aggregate_costs
from psf_lab.execution_context import context_intervals, validate_context_anchors
from psf_lab.runner import digest, write_json


def analyze_context_reports(root: Path, formal: Path, output: Path) -> dict:
    if output.exists():
        raise ValueError("Report output must be new")
    receipt = json.loads((formal / "completion.json").read_text())
    if receipt.get("passed") is not True or len(receipt["runs"]) != 24:
        raise ValueError("Expected accepted formal batch")
    validate_context_batch(receipt["runs"])
    output.mkdir(parents=True)
    reports = []
    identities = {}
    for record in receipt["runs"]:
        candidate = record["candidate"]
        mode = record["mode"]
        repeat = record["repeat"]
        folder = formal / candidate
        run = folder / f"enabled-{mode}-{repeat}"
        verify_file_hashes(run, {"manifest.json": record["run_manifest_sha256"]}, {"manifest.json"})
        manifest = json.loads((run / "manifest.json").read_text())
        if manifest["result"] != {k: v for k, v in record.items() if k != "run_manifest_sha256"}:
            raise ValueError("Formal run identity mismatch")
        runset = json.loads((folder / "manifest.json").read_text())
        verify_file_hashes(
            folder,
            {
                "boundaries.json": runset["boundary_sha256"],
                "boundaries.conf": runset["boundary_config_sha256"],
            },
            {"boundaries.json", "boundaries.conf"},
        )
        boundaries = json.loads((folder / "boundaries.json").read_text())
        if boundaries["elf_sha256"] != manifest["files"]["firmware.elf"]:
            raise ValueError("Boundary/ELF binding mismatch")
        verify_file_hashes(
            run,
            manifest["files"],
            {
                "context-events.jsonl",
                "accesses.csv.gz",
                "trace.psf",
                "context-intervals.json",
                "task-identities.json",
            },
        )
        task_objects = json.loads((run / "task-identities.json").read_text())
        events = [
            json.loads(line) for line in (run / "context-events.jsonl").read_text().splitlines()
        ]
        intervals = context_intervals(
            events,
            raw_events=record["audit"]["events"],
            task_ids={int(o["address"], 16) for o in task_objects},
        )
        with gzip.open(run / "accesses.csv.gz", "rt", newline="") as stream:
            validate_context_anchors(
                events, csv.DictReader(stream), json.loads((folder / "boundaries.json").read_text())
            )
        if intervals["quality"] != "exact":
            raise ValueError("Non-exact formal context")
        b1 = root / "artifacts/verification/cost-attribution/b1" / candidate
        ranges = json.loads((b1 / "ranges.json").read_text())
        capture = load_capture_evidence(
            root, root / "runs/tcp-workload-matrix-v1" / candidate, mode
        )
        rules_path = root / "cases/timing/attribution-rules-v1.json"
        if ranges != build_role_ranges(capture, json.loads(rules_path.read_text())):
            raise ValueError("B1 ranges differ from pinned ELF ownership")
        if capture["files_sha256"]["firmware.elf"] != manifest["files"]["firmware.elf"]:
            raise ValueError("Formal/B1 ELF mismatch")
        with gzip.open(run / "accesses.csv.gz", "rt", newline="") as stream:
            result = aggregate_costs(
                csv.DictReader(stream), ranges, mode=mode, contexts=intervals["intervals"]
            )
        if result["totals"]["memory_cycles"] != record["audit"]["cycles"]:
            raise ValueError("Context report cost mismatch")
        result["context_quality"] = intervals["quality"]
        result["evidence"] = dict(
            run_manifest_sha256=record["run_manifest_sha256"],
            raw_stream_sha256=record["audit"]["stream_sha256"],
            task_objects=task_objects,
            boundary_sha256=digest(folder / "boundaries.json"),
            ranges_sha256=digest(b1 / "ranges.json"),
            rules_sha256=digest(rules_path),
        )
        destination = output / candidate / f"enabled-{mode}-{repeat}"
        destination.mkdir(parents=True)
        with gzip.open(destination / "full-report.json.gz", "wt", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False)
        summary = {k: v for k, v in result.items() if k not in ("by_pc", "by_function")}
        write_json(destination / "summary.json", summary)
        with (destination / "context-role.csv").open("w", newline="") as stream:
            writer = csv.DictWriter(
                stream,
                fieldnames=["candidate", "mode", "repeat", "context", "role", *METRICS, *COST_KEYS],
            )
            writer.writeheader()
            for key, row in result["matrix"].items():
                context, role = key.split("|")
                writer.writerow(
                    dict(
                        candidate=candidate,
                        mode=mode,
                        repeat=repeat,
                        context=context,
                        role=role,
                        **{k: row[k] for k in METRICS},
                        **row["cost_cycles"],
                    )
                )
        key = (candidate, mode)
        identity = dict(
            totals=result["totals"], matrix=result["matrix"], intervals=intervals["intervals"]
        )
        if key in identities and identities[key] != identity:
            raise ValueError("Same-mode repeats differ")
        identities[key] = identity
        reports.append(
            dict(
                candidate=candidate,
                mode=mode,
                repeat=repeat,
                summary_sha256=digest(destination / "summary.json"),
                full_report_sha256=digest(destination / "full-report.json.gz"),
            )
        )
        print(candidate, mode, repeat, "conserved", flush=True)
    completion = dict(
        schema="context-reports-v1",
        passed=True,
        reports=reports,
        exact_candidates=4,
        other_B1_candidates_context="unknown",
        same_mode_repeats_identical=True,
    )
    write_json(output / "completion.json", completion)
    return completion


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--formal", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    analyze_context_reports(Path.cwd(), args.formal, args.output)
