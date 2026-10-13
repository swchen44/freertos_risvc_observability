"""Build full C2a chunks from verified captures; preserves partial failed output."""

import argparse
import json
import subprocess
from pathlib import Path

from psf_lab.event_window import build_event_run, canonical, sha
from psf_lab.hotspot_evidence import catalog_inputs


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workload", choices=[f"A{i:02}" for i in range(1, 9)])
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    root = Path.cwd()
    out = a.output.resolve()
    if out.is_relative_to(root / "runs") or out.exists():
        raise ValueError("New output outside capture directories required")
    out.mkdir(parents=True)
    receipt = dict(
        passed=False,
        runs=[],
        generator_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        source_sha256={
            str(f.relative_to(root)): sha(f.read_bytes())
            for f in [
                root / "src/psf_lab" / n
                for n in [
                    "hotspot_events.py",
                    "hotspot_evidence.py",
                    "event_window.py",
                    "memory_timing.py",
                    "tcp_hotspots.py",
                ]
            ]
        },
    )
    try:
        for entry in catalog_inputs(root, workload=a.workload):
            folder = out / entry["run_id"]
            manifest = build_event_run(root, entry, folder)
            receipt["runs"].append(
                dict(
                    run_id=entry["run_id"],
                    workload=entry["workload"],
                    events=manifest["events"],
                    sha256=sha((folder / "manifest.json").read_bytes()),
                )
            )
            print(entry["run_id"], manifest["events"], flush=True)
        receipt["passed"] = True
        (out / "catalog.json").write_bytes(
            canonical(dict(schema="event-window-catalog-v1", runs=receipt["runs"]))
        )
    finally:
        (out / "completion.json").write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    main()
