"""Validated workload bundles and conservative cross-binary identities."""

import gzip
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

from psf_lab.attribution_evidence import contained
from psf_lab.hotspot_report import add_counts, empty_counts, validate_hotspot_report
from psf_lab.runner import digest

ROOT = Path(__file__).resolve().parents[2]
CATALOG = Path("artifacts/verification/hotspot/catalog.json")


def function_key(owner):
    if owner.get("role") == "unresolved" or not owner.get("function"):
        return None
    source = owner.get("source")
    obj = owner.get("object") or ""
    archive = re.search(r"([^/]+\.a\([^()]+\))$", obj)
    if archive:
        origin = archive[1]
    elif source and not source.startswith("/") and ".." not in Path(source).parts:
        origin = source
    else:
        return None
    return origin + "|" + owner["function"]


def function_totals(report):
    result = {fid: empty_counts() for fid in report["owners"]}
    for fact in report["facts"]:
        add_counts(result[fact["function_id"]], fact)
    return result


def pair_functions(baseline: dict, candidate: dict) -> list[dict]:
    for key in ("workload", "family", "mode", "repeat"):
        if baseline["identity"][key] != candidate["identity"][key]:
            raise ValueError("Incompatible comparison identity")
    if baseline["evidence"]["profile_sha256"] != candidate["evidence"]["profile_sha256"]:
        raise ValueError("Incompatible profiles")
    buckets = defaultdict(lambda: [[], []])
    for side, report in enumerate((baseline, candidate)):
        for fid, owner in report["owners"].items():
            key = function_key(owner) or f"unresolved:{side}:{fid}"
            buckets[key][side].append(fid)
    totals = [function_totals(r) for r in (baseline, candidate)]
    result = []
    for key, (left, right) in sorted(buckets.items()):
        status = (
            "matched"
            if len(left) == len(right) == 1
            else "ambiguous"
            if max(len(left), len(right)) > 1
            else "unmatched"
        )
        delta = percent = None
        if status == "matched":
            a, b = totals[0][left[0]], totals[1][right[0]]
            delta = {
                k: b[k] - a[k] for k in ("instructions", "memory_cycles", "accounted_model_ns")
            }
            percent = {k: 100 * v / a[k] if a[k] else None for k, v in delta.items()}
        result.append(
            dict(
                key=key, baseline=left, candidate=right, status=status, delta=delta, percent=percent
            )
        )
    return result


def context_labels(report):
    tasks = report["evidence"].get("task_objects", [])
    counts = defaultdict(int)
    for task in tasks:
        counts[task["name"]] += 1
    labels = {}
    for fact in report["facts"]:
        context = fact["context"]
        if context.startswith("task:"):
            matches = [t for t in tasks if int(t["address"], 16) == int(context.split(":")[1])]
            t = matches[0] if len(matches) == 1 else None
            labels[context] = dict(
                label=t["name"] if t else context,
                pair_key="task:" + t["name"] if t and counts[t["name"]] == 1 else None,
            )
        else:
            labels[context] = dict(
                label=context, pair_key=context if context != "unknown" else None
            )
    return labels


def build_workload_bundle(reports: list[dict]) -> dict:
    if not reports or len({r["identity"]["workload"] for r in reports}) != 1:
        raise ValueError("Expected one workload")
    if len({r["identity"]["run_id"] for r in reports}) != len(reports):
        raise ValueError("Duplicate run")
    pairs = {}
    for report in reports:
        validate_hotspot_report(report)
        report["context_labels"] = context_labels(report)
        if report["identity"]["variant"] == "pbuf":
            matching = [
                r
                for r in reports
                if r["identity"]["variant"] == "baseline"
                and all(
                    r["identity"][k] == report["identity"][k] for k in ("family", "mode", "repeat")
                )
            ]
            if len(matching) != 1:
                raise ValueError("Missing baseline")
            pairs[report["identity"]["run_id"]] = dict(
                baseline_run=matching[0]["identity"]["run_id"],
                functions=pair_functions(matching[0], report),
            )
    result = dict(
        schema="hotspot-workload-v1",
        workload=reports[0]["identity"]["workload"],
        reports=reports,
        pairs=pairs,
    )
    result["manifest_sha256"] = hashlib.sha256(
        json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return result


def publish_bundles(formal: Path, destination: Path) -> dict:
    from psf_lab.attribution_evidence import verify_file_hashes

    receipt = json.loads((formal / "completion.json").read_text())
    if receipt.get("passed") is not True:
        raise ValueError("Unaccepted analysis")
    destination.mkdir(parents=True, exist_ok=False)
    groups = defaultdict(list)
    for record in receipt["reports"]:
        path = contained(formal, record["path"])
        verify_file_hashes(
            path,
            record["files"],
            {
                "report.json.gz",
                "evidence.json",
                "summary.json",
                "facts.csv",
                "source-lines.json",
                "addr2line.txt",
            },
        )
        report = json.loads(gzip.decompress((path / "report.json.gz").read_bytes()))
        if report["identity"] != record["identity"]:
            raise ValueError("Report identity mismatch")
        groups[report["identity"]["workload"]].append(report)
    catalog = dict(schema="hotspot-catalog-v1", workloads=[])
    for workload, reports in sorted(groups.items()):
        data = build_workload_bundle(reports)
        path = destination / (workload + ".json")
        path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
        catalog["workloads"].append(
            dict(
                id=workload,
                path=path.name,
                sha256=digest(path),
                bytes=path.stat().st_size,
                runs=len(reports),
            )
        )
    (destination / "catalog.json").write_text(json.dumps(catalog, indent=2) + "\n")
    return catalog


def load_hotspot_catalog(root: Path = ROOT) -> dict:
    catalog = json.loads((root / CATALOG).read_text())
    ids = [r["id"] for r in catalog["workloads"]]
    if (
        catalog.get("schema") != "hotspot-catalog-v1"
        or len(set(ids)) != len(ids)
        or any(not re.fullmatch(r"A0[1-8]", i) for i in ids)
    ):
        raise ValueError("Invalid hotspot catalog")
    return catalog


def load_hotspot_workload(root: Path, workload: str) -> dict:
    entries = [e for e in load_hotspot_catalog(root)["workloads"] if e["id"] == workload]
    if len(entries) != 1:
        raise KeyError("Unknown workload")
    entry = entries[0]
    path = contained(root / CATALOG.parent, entry["path"])
    if digest(path) != entry["sha256"]:
        raise ValueError("Hotspot bundle hash mismatch")
    data = json.loads(path.read_text())
    if data.get("schema") != "hotspot-workload-v1" or data["workload"] != workload:
        raise ValueError("Hotspot identity mismatch")
    return data
