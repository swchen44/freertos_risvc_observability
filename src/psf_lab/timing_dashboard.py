"""Present hash-pinned T3b/T3c reports; do not imply a fresh raw-trace replay."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCES = (
    ("tcp-os-small-cache", "tcp-os-small-cache-v1"),
    ("tcp-pbuf-holdout", "tcp-pbuf-holdout-v1"),
    ("tcp-workload-matrix", "tcp-workload-matrix-v1"),
)


def validate_comparison(data, schema):
    if data.get("schema") != schema or data.get("passed") is not True:
        raise ValueError("Invalid comparison schema or verdict")
    rows = data["results"]
    expected = {
        "tcp-os-small-cache-v1": {"standard", "baseline", "layout", "checksum", "pbuf"},
        "tcp-pbuf-holdout-v1": {
            "linear-baseline",
            "linear-pbuf",
            "fragmented-baseline",
            "fragmented-pbuf",
        },
        "tcp-workload-matrix-v1": {
            f"A{i:02}-{v}" for i in range(1, 9) for v in ("baseline", "pbuf")
        },
    }.get(schema)
    if expected is None:
        raise ValueError("Unsupported comparison schema")
    if schema == "tcp-workload-matrix-v1":
        from psf_lab.tcp_workload import validate_workload

        workloads = {}
        for row in rows:
            workload = validate_workload(row["workload"])
            if (
                row["label"] != workload["id"] + "-" + row["variant"]
                or row["workload_id"] != workload["id"]
            ):
                raise ValueError("Workload identity mismatch")
            if workload["id"] in workloads and workloads[workload["id"]] != workload:
                raise ValueError("Paired workload mismatch")
            workloads[workload["id"]] = workload
    if len(rows) != len(expected) or {r["label"] for r in rows} != expected:
        raise ValueError("Unexpected comparison candidates")
    for row in rows:
        if row["label"] == "standard":
            continue  # Historical geometry excluded from this view and metric validation.
        numeric = ["guest_ns", "instructions", "cycles", "stack_cycles", "harness_cycles"]
        numeric += [
            f"{level}_{suffix}"
            for level in ("l1i", "l1d", "l2")
            for suffix in ("accesses", "misses", "compulsory", "conflict", "capacity")
        ]
        if any(type(row[k]) is not int or row[k] < 0 for k in numeric):
            raise ValueError("Invalid metric")
        if not row["guest_ns"] or row["cycles"] != sum(row["cost_cycles"].values()):
            raise ValueError("Cost conservation failed")
        if row["stack_cycles"] + row["harness_cycles"] != row["cycles"]:
            raise ValueError("Window conservation failed")
        for level in ("l1i", "l1d", "l2"):
            if (
                sum(row[f"{level}_{k}"] for k in ("compulsory", "conflict", "capacity"))
                != row[f"{level}_misses"]
                or not row[f"{level}_accesses"]
                or row[f"{level}_misses"] > row[f"{level}_accesses"]
            ):
                raise ValueError("Miss conservation failed")


def load_dashboard(root=ROOT):
    manifest = json.loads((root / "cases/timing/dashboard-sources.json").read_text())
    required = {f"artifacts/verification/{source}/results/comparison.json" for source, _ in SOURCES}
    required.add("cases/timing/sysram-10-small.json")
    if not required <= manifest["files"].keys():
        raise ValueError("Missing required evidence hash")
    for name, expected in manifest["files"].items():
        path = Path(name)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("Invalid evidence path")
        if hashlib.sha256((root / path).read_bytes()).hexdigest() != expected:
            raise ValueError("Evidence hash mismatch: " + name)
    rows = []
    environments = []
    for source, schema in SOURCES:
        name = f"artifacts/verification/{source}/results/comparison.json"
        data = json.loads((root / name).read_text())
        validate_comparison(data, schema)
        environments.append(data["environment"])
        for row in data["results"]:
            if row["label"] == "standard":
                continue  # 16/16/64 KiB reference is not part of the small-cache view.
            if schema == "tcp-workload-matrix-v1":
                group = row["workload_id"]
                baseline_label = group + "-baseline"
            else:
                group = (
                    "T3b"
                    if source == SOURCES[0][0]
                    else ("T3c-linear" if row["label"].startswith("linear-") else "T3c-chain")
                )
                baseline_label = {
                    "T3b": "baseline",
                    "T3c-linear": "linear-baseline",
                    "T3c-chain": "fragmented-baseline",
                }[group]
            baseline = next(r for r in data["results"] if r["label"] == baseline_label)
            value = {
                **row,
                "group": group,
                "id": group + "/" + row["label"],
                "source": name,
                "baseline": baseline_label,
                "improvement_pct": 100
                * (baseline["guest_ns"] - row["guest_ns"])
                / baseline["guest_ns"],
                "guest_ms": row["guest_ns"] / 1e6,
            }
            for level in ("l1i", "l1d", "l2"):
                value[level + "_miss_pct"] = 100 * row[level + "_misses"] / row[level + "_accesses"]
            value["request_bytes"] = row.get("workload", {}).get("request_bytes", 64)
            value["request_shape"] = "+".join(
                map(
                    str,
                    row.get("workload", {}).get(
                        "request_segments",
                        row.get("request_pbufs", [{}])[0].get("lengths", [64])
                        if row.get("request_pbufs")
                        else [64],
                    ),
                )
            )
            value["packets"] = row.get("packets", 25)
            rows.append(value)
    if any(env != environments[0] for env in environments[1:]):
        raise ValueError("Mismatched experiment environments")
    return {
        "schema": "timing-dashboard-v1",
        "rows": rows,
        "profile": json.loads((root / "cases/timing/sysram-10-small.json").read_text()),
        "environment": environments[0],
        "sources": manifest["files"],
        "verification": "Hash-pinned comparison reports; no raw trace replay at page load",
    }


def export_dashboard(output, root=ROOT):
    from psf_lab.cache_report import render_offline

    html = render_offline(
        load_dashboard(root),
        (root / "web/timing.html")
        .read_text()
        .replace("timing-data", "cache-data")
        .replace("/assets/timing.", "/assets/cache."),
        (root / "web/dist/assets/timing.js").read_text().replace("timing-data", "cache-data"),
        (root / "web/dist/assets/timing.css").read_text(),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    export_dashboard(parser.parse_args().output)
