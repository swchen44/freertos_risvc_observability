"""Run the approved two batches from a clean checkout into an ignored output path."""

import argparse
import concurrent.futures
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    relative = output.relative_to(ROOT)
    if output.exists():
        parser.error("Output must be a new directory")
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT).strip():
        parser.error("Commit source changes before capture")
    if subprocess.run(["git", "check-ignore", "-q", str(relative / "probe")], cwd=ROOT).returncode:
        parser.error("Output must be ignored, for example runs/local/matrix-rerun")
    logs = output.parent / (output.name + "-logs")
    if subprocess.run(
        ["git", "check-ignore", "-q", str((logs / "probe").relative_to(ROOT))], cwd=ROOT
    ).returncode:
        parser.error("Sibling log directory must also be ignored")
    logs.mkdir(parents=True, exist_ok=False)

    def run(case, variant):
        name = f"A{case:02}-{variant}"
        command = [
            sys.executable,
            "tools/tcp/run_live_cache.py",
            "--qemu",
            ".tools/qemu-time-control/qemu-system-riscv32-relative",
            "--case",
            "tcp-irq",
            "--cache-profile",
            "small",
            "--tcp-variant",
            variant,
            "--workload-id",
            f"A{case:02}",
            "--repeats",
            "3",
            "--output",
            str(relative / name),
        ]
        start = time.monotonic()
        with (logs / (name + ".log")).open("w") as stream:
            result = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
        return dict(
            name=name, command=command, exit=result.returncode, seconds=time.monotonic() - start
        )

    records = []
    for batch in (range(1, 5), range(5, 9)):
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(run, case, variant)
                for case in batch
                for variant in ("baseline", "pbuf")
            ]
            current = [future.result() for future in futures]
        records.extend(current)
        (logs / "execution.json").write_text(json.dumps(records, indent=2) + "\n")
        if any(row["exit"] for row in current):
            raise SystemExit("Batch failed; inspect saved logs before continuing")
        print("Batch passed:", list(batch), flush=True)


if __name__ == "__main__":
    main()
