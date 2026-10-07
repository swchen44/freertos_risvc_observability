"""Replay A representative captures into conserved code-role reports."""

import argparse
import csv
import gzip
import json
from pathlib import Path

from psf_lab.attribution_evidence import build_role_ranges, load_capture_evidence
from psf_lab.cost_attribution import COST_KEYS, METRICS, aggregate_costs
from psf_lab.memory_timing import from_profile
from psf_lab.runner import digest, write_json


def audited_rows(path, profile):
    model = from_profile(profile)
    with gzip.open(path, "rt", newline="") as stream:
        for index, row in enumerate(csv.DictReader(stream)):
            expected = model.access(int(row["address"]), int(row["size"]), row["operation"])
            if any(expected[k] != int(row[k]) for k in COST_KEYS):
                raise ValueError(f"Raw model cost mismatch at row {index}")
            yield row


def export_csv(path, result):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["dimension", "key", *METRICS, *COST_KEYS, "function", "object", "reason"],
        )
        writer.writeheader()
        for dimension in ("by_role", "by_function", "by_pc", "by_context", "matrix", "unresolved"):
            for key, row in result[dimension].items():
                owner = row.get("owner", {})
                writer.writerow(
                    dict(
                        dimension=dimension,
                        key=key,
                        **{k: row[k] for k in METRICS},
                        **row["cost_cycles"],
                        function=owner.get("function"),
                        object=owner.get("object"),
                        reason=owner.get("reason"),
                    )
                )


def analyze_cost_batch(root: Path, runs: Path, output: Path) -> dict:
    root, runs, output = root.resolve(), runs.resolve(), output.resolve()
    expected = {f"A{i:02}-{v}" for i in range(1, 9) for v in ("baseline", "pbuf")}
    if output.exists() or output.is_relative_to(runs):
        raise ValueError("Output must be a new directory outside inputs")
    if {p.name for p in runs.iterdir() if p.is_dir()} != expected:
        raise ValueError("Expected sixteen A runsets")
    rules_path = root / "cases/timing/attribution-rules-v1.json"
    rules = json.loads(rules_path.read_text())
    profile = json.loads((root / "cases/timing/sysram-10-small.json").read_text())
    output.mkdir(parents=True)
    reports = {}
    for name in sorted(expected):
        evidence = load_capture_evidence(root, runs / name, 1)
        ranges = build_role_ranges(evidence, rules)
        result = aggregate_costs(
            audited_rows(root / evidence["run_path"] / "accesses.csv.gz", profile), ranges, mode=1
        )
        audit = evidence["audit"]
        if (
            result["events"] != audit["events"]
            or result["totals"]["memory_cycles"] != audit["cycles"]
            or result["totals"]["instructions"] != audit["operations"]["I"]
            or result["totals"]["cost_cycles"] != audit["costs"]
        ):
            raise ValueError("Saved audit mismatch: " + name)
        target = output / name
        target.mkdir()
        for tool, text in evidence.pop("tool_outputs").items():
            (target / (tool + ".txt")).write_text(text)
        result["evidence"] = dict(
            run_path=evidence["run_path"],
            raw_stream_sha256=evidence["raw_stream_sha256"],
            rules_sha256=digest(rules_path),
            elf_sha256=evidence["files_sha256"]["firmware.elf"],
        )
        write_json(target / "evidence.json", evidence)
        write_json(target / "ranges.json", ranges)
        write_json(target / "report.json", result)
        export_csv(target / "report.csv", result)
        reports[name] = dict(
            totals=result["totals"],
            measurement=evidence["measurement"],
            by_role=result["by_role"],
            by_function=result["by_function"],
            report_sha256=digest(target / "report.json"),
        )
        print(name, result["events"], result["totals"]["memory_cycles"], flush=True)
    deltas = {}
    for i in range(1, 9):
        workload = f"A{i:02}"
        a, b = reports[workload + "-baseline"], reports[workload + "-pbuf"]

        def comparable(rows, dimension):
            if dimension == "by_role":
                return rows
            groups = {}
            for row in rows.values():
                owner = row["owner"]
                # Cross-ELF comparison uses source/object basename + function, not absolute PC.
                object_name = Path(owner.get("object") or "unknown").name
                key = f"{owner.get('source')}|{object_name}|{owner['function']}"
                target = groups.setdefault(key, dict.fromkeys(METRICS, 0))
                for metric in METRICS:
                    target[metric] += row[metric]
            return groups

        delta = {}
        for dimension in ("by_role", "by_function"):
            left, right = comparable(a[dimension], dimension), comparable(b[dimension], dimension)
            delta[dimension] = {
                k: {m: right.get(k, {}).get(m, 0) - left.get(k, {}).get(m, 0) for m in METRICS}
                for k in sorted(left.keys() | right.keys())
            }
        delta["accounted_model_ns"] = (
            b["totals"]["accounted_model_ns"] - a["totals"]["accounted_model_ns"]
        )
        delta["mtime_elapsed_ns"] = 100 * (
            (b["measurement"]["after"] - b["measurement"]["before"])
            - (a["measurement"]["after"] - a["measurement"]["before"])
        )
        delta["boundary_difference_ns"] = delta["mtime_elapsed_ns"] - delta["accounted_model_ns"]
        deltas[workload] = delta
    write_json(output / "deltas.json", deltas)
    with (output / "deltas.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["workload", "dimension", "key", *METRICS])
        writer.writeheader()
        for workload, delta in deltas.items():
            for dimension in ("by_role", "by_function"):
                for key, values in delta[dimension].items():
                    writer.writerow(dict(workload=workload, dimension=dimension, key=key, **values))
    receipt = dict(
        schema="cost-attribution-b1-v1",
        passed=True,
        captures=len(reports),
        context_quality="not_observed_in_A_trace",
        B_status="partial",
        reports={k: v["report_sha256"] for k, v in reports.items()},
        a02={k: v for k, v in deltas["A02"].items() if not k.startswith("by_")},
    )
    write_json(output / "completion.json", receipt)
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    analyze_cost_batch(Path.cwd(), args.runs, args.output)
