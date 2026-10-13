"""Verified saved captures for C1; never invokes QEMU or modifies input evidence."""

import csv
import gzip
import hashlib
import json
from pathlib import Path

from psf_lab.attribution_evidence import (
    build_role_ranges,
    load_capture_evidence,
    verify_file_hashes,
    verify_git_files,
)
from psf_lab.execution_context import context_intervals, validate_context_anchors
from psf_lab.runner import digest

B_COMMIT = "ea3efd982a034a0d554f67a8ebecc9474f2bd7d7"
FORMAL = Path("runs/tcp-context-v1/formal")


def formal_records(root):
    data = json.loads((root / FORMAL / "completion.json").read_text())
    expected = {
        (f"{w}-{v}", m, r)
        for w in ("A02", "A08")
        for v in ("baseline", "pbuf")
        for m in (0, 1)
        for r in (1, 2, 3)
    }
    rows = data["runs"]
    if (
        data.get("passed") is not True
        or len(rows) != 24
        or {(r["candidate"], r["mode"], r["repeat"]) for r in rows} != expected
        or any(r.get("accepted") is not True or r.get("context_exact") is not True for r in rows)
    ):
        raise ValueError("Expected exact accepted formal batch")
    return rows


def catalog_inputs(root: Path, *, workload: str | None = None) -> list[dict]:
    workloads = [f"A{i:02}" for i in range(1, 9)]
    if workload is not None and workload not in workloads:
        raise ValueError("Unknown workload")
    entries = []
    for w in workloads:
        for v in ("baseline", "pbuf"):
            entries.append(dict(workload=w, variant=v, family="b1", mode=1, repeat=1))
    for row in formal_records(root):
        w, v = row["candidate"].split("-")
        entries.append(
            dict(workload=w, variant=v, family="b2", mode=row["mode"], repeat=row["repeat"])
        )
    for e in entries:
        e["run_id"] = f"{e['workload']}-{e['variant']}-{e['family']}-{e['mode']}-{e['repeat']}"
    return [e for e in entries if workload is None or e["workload"] == workload]


def load_formal_context(root, candidate, mode, repeat):
    rows = formal_records(root)
    matching = [
        r for r in rows if (r["candidate"], r["mode"], r["repeat"]) == (candidate, mode, repeat)
    ]
    if len(matching) != 1:
        raise ValueError("Unknown formal identity")
    record = matching[0]
    folder = root / FORMAL / candidate
    run = folder / f"enabled-{mode}-{repeat}"
    verify_file_hashes(run, {"manifest.json": record["run_manifest_sha256"]}, {"manifest.json"})
    manifest = json.loads((run / "manifest.json").read_text())
    if manifest["result"] != {k: v for k, v in record.items() if k != "run_manifest_sha256"}:
        raise ValueError("Run identity mismatch")
    verify_file_hashes(
        run,
        manifest["files"],
        {
            "firmware.elf",
            "accesses.csv.gz",
            "trace.psf",
            "context-events.jsonl",
            "context-intervals.json",
            "task-identities.json",
        },
    )
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
        raise ValueError("Boundary ELF mismatch")
    tasks = json.loads((run / "task-identities.json").read_text())
    events = [json.loads(s) for s in (run / "context-events.jsonl").read_text().splitlines()]
    intervals = context_intervals(
        events,
        raw_events=record["audit"]["events"],
        task_ids={int(t["address"], 16) for t in tasks},
    )
    with gzip.open(run / "accesses.csv.gz", "rt", newline="") as stream:
        validate_context_anchors(events, csv.DictReader(stream), boundaries)
    if intervals["quality"] != "exact":
        raise ValueError("Nonexact formal context")
    with gzip.open(run / "accesses.csv.gz", "rb") as stream:
        raw_hash = hashlib.file_digest(stream, "sha256").hexdigest()
    if raw_hash != record["audit"]["stream_sha256"]:
        raise ValueError("Raw stream mismatch")
    return dict(
        run=run, manifest=manifest, record=record, contexts=intervals["intervals"], tasks=tasks
    )


def load_hotspot_input(root: Path, entry: dict) -> dict:
    if entry not in catalog_inputs(root, workload=entry.get("workload")):
        raise ValueError("Invalid catalog entry")
    candidate = entry["workload"] + "-" + entry["variant"]
    capture = load_capture_evidence(
        root, root / "runs/tcp-workload-matrix-v1" / candidate, entry["mode"]
    )
    pins = [
        "cases/timing/sysram-10-small.json",
        "cases/timing/attribution-rules-v1.json",
        f"artifacts/verification/cost-attribution/b1/{candidate}/ranges.json",
    ]
    if entry["family"] == "b2":
        pins += [str(FORMAL / "completion.json"), str(FORMAL / candidate / "manifest.json")]
    verified = verify_git_files(root, B_COMMIT, pins)
    profile = json.loads((root / pins[0]).read_text())
    if [profile["caches"][k]["size"] for k in ("l1i", "l1d", "l2")] != [8192, 8192, 32768]:
        raise ValueError("Wrong cache profile")
    ranges = build_role_ranges(capture, json.loads((root / pins[1]).read_text()))
    if ranges != json.loads((root / pins[2]).read_text()):
        raise ValueError("Saved ownership differs from ELF")
    run = root / capture["run_path"]
    contexts = None
    tasks = []
    extra = {}
    if entry["family"] == "b2":
        formal = load_formal_context(root, candidate, entry["mode"], entry["repeat"])
        run = formal["run"]
        contexts = formal["contexts"]
        tasks = formal["tasks"]
        if formal["manifest"]["files"]["firmware.elf"] != capture["files_sha256"]["firmware.elf"]:
            raise ValueError("Formal/A ELF mismatch")
        extra = dict(
            formal_record=formal["record"], formal_manifest_sha256=digest(run / "manifest.json")
        )
    evidence = dict(
        elf_sha256=capture["files_sha256"]["firmware.elf"],
        raw_file_sha256=digest(run / "accesses.csv.gz"),
        raw_stream_sha256=capture["raw_stream_sha256"],
        profile_sha256=digest(root / pins[0]),
        pins=verified,
        task_objects=tasks,
        tool_hashes=capture["tool_hashes"],
        capture=capture,
        **extra,
    )
    return dict(
        raw_path=run / "accesses.csv.gz",
        ranges=ranges,
        profile=profile,
        identity=entry,
        contexts=contexts,
        evidence=evidence,
    )


def analyze_hotspots(root: Path, output: Path, *, workload: str | None = None) -> dict:
    import subprocess
    import time

    from psf_lab.cost_attribution import METRICS, aggregate_costs
    from psf_lab.hotspot_report import build_hotspot_report
    from psf_lab.tcp_hotspots import profile_misses

    if output.exists():
        raise ValueError("Report output must be new")
    entries = catalog_inputs(root, workload=workload)
    output.mkdir(parents=True)
    records = []
    completion = dict(
        schema="hotspot-analysis-v1",
        passed=False,
        reports=records,
        generator=dict(
            commit=subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=root, text=True
            ).strip(),
            source_sha256={
                str(p.relative_to(root)): digest(p)
                for p in [
                    root / "src/psf_lab/hotspot_report.py",
                    root / "src/psf_lab/hotspot_events.py",
                    root / "src/psf_lab/hotspot_evidence.py",
                    root / "src/psf_lab/memory_timing.py",
                    root / "src/psf_lab/tcp_hotspots.py",
                ]
            },
        ),
    )

    def save(path, data):
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")

    try:
        for entry in entries:
            started = time.monotonic()
            data = load_hotspot_input(root, entry)
            with gzip.open(data["raw_path"], "rt", newline="") as stream:
                report = build_hotspot_report(
                    csv.DictReader(stream),
                    data["ranges"],
                    data["profile"],
                    identity=entry,
                    contexts=data["contexts"],
                )
            with gzip.open(data["raw_path"], "rt", newline="") as stream:
                old = aggregate_costs(
                    csv.DictReader(stream),
                    data["ranges"],
                    mode=entry["mode"],
                    contexts=data["contexts"],
                )
            for key in METRICS:
                if report["totals"][key] != old["totals"][key]:
                    raise ValueError("B cost marginal mismatch")
            for dimension, factkey in [
                ("by_role", "role"),
                ("by_context", "context"),
                ("by_pc", "pc"),
            ]:
                actual = {}
                for fact in report["facts"]:
                    key = fact[factkey]
                    actual[key] = actual.get(key, 0) + fact["memory_cycles"]
                if actual != {k: v["memory_cycles"] for k, v in old[dimension].items()}:
                    raise ValueError("B dimension mismatch")
            with gzip.open(data["raw_path"], "rt", newline="") as stream:
                misses = profile_misses(csv.DictReader(stream), data["profile"], [])
            for level, counts in report["totals"]["cache"].items():
                for key, value in counts.items():
                    if value != misses["totals"].get(level + "_" + key, 0):
                        raise ValueError("3C total mismatch")
            report["context_quality"] = "exact" if data["contexts"] is not None else "unknown"
            capture = data["evidence"].pop("capture")
            report["evidence"] = data["evidence"]
            destination = output / entry["run_id"]
            destination.mkdir()
            pcs = sorted({f["pc"] for f in report["facts"]})
            tool = root / ".tools/xpack-riscv-none-elf-gcc-15.2.0-1/bin/riscv-none-elf-addr2line"
            command = [str(tool), "-a", "-f", "-i", "-e", capture["elf_path"]]
            proc = subprocess.run(
                command,
                input="\n".join(hex(p) for p in pcs) + "\n",
                text=True,
                capture_output=True,
                check=True,
            )
            (destination / "addr2line.txt").write_text(proc.stdout)
            locations = {}
            pc = None
            lines = proc.stdout.splitlines()
            i = 0
            while i < len(lines):
                if lines[i].startswith("0x"):
                    pc = str(int(lines[i], 16))
                    locations[pc] = []
                    i += 1
                elif pc is not None and i + 1 < len(lines):
                    locations[pc].append(
                        dict(
                            function=lines[i],
                            location=lines[i + 1] if not lines[i + 1].startswith("??") else None,
                        )
                    )
                    i += 2
                else:
                    i += 1
            report["source_lines"] = locations
            report["evidence"]["addr2line"] = dict(
                command=command,
                stdin_sha256=hashlib.sha256(
                    ("\n".join(hex(p) for p in pcs) + "\n").encode()
                ).hexdigest(),
                stdout_sha256=digest(destination / "addr2line.txt"),
                tool_sha256=digest(tool),
            )
            save(destination / "evidence.json", dict(capture=capture, hotspot=report["evidence"]))
            save(destination / "source-lines.json", locations)
            blob = json.dumps(report, ensure_ascii=False, separators=(",", ":")).encode()
            (destination / "report.json.gz").write_bytes(gzip.compress(blob, mtime=0))
            save(
                destination / "summary.json",
                {k: v for k, v in report.items() if k not in ("facts", "owners", "source_lines")},
            )
            with (destination / "facts.csv").open("w", newline="") as stream:
                fields = [
                    "run_id",
                    "context",
                    "role",
                    "function_id",
                    "pc",
                    *METRICS,
                    *report["totals"]["cost_cycles"],
                    *[f"{level}_{k}" for level, v in report["totals"]["cache"].items() for k in v],
                ]
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                for f in report["facts"]:
                    writer.writerow(
                        dict(
                            run_id=entry["run_id"],
                            **{k: f[k] for k in fields[1:9]},
                            **f["cost_cycles"],
                            **{
                                f"{level}_{k}": v
                                for level, cs in f["cache"].items()
                                for k, v in cs.items()
                            },
                        )
                    )
            records.append(
                dict(
                    identity=entry,
                    path=str(destination.relative_to(output)),
                    files={p.name: digest(p) for p in destination.iterdir()},
                    facts=len(report["facts"]),
                    json_bytes=len(blob),
                    elapsed_seconds=time.monotonic() - started,
                )
            )
            save(output / "completion.json", completion)
            print(entry["run_id"], len(report["facts"]), "conserved", flush=True)
        completion["passed"] = True
    except Exception as exc:
        completion["error"] = type(exc).__name__ + ": " + str(exc)
        raise
    finally:
        save(output / "completion.json", completion)
    return completion
