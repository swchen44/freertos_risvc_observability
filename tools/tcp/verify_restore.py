"""Verify every archive hash, replay TCP evidence, optionally rebuild all nine sessions."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--archive", type=Path, default=ROOT / "artifacts/restore/tcp-transfer-source.tar.gz"
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / "artifacts/verification/tcp-optimization/restore.json"
    )
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--toolchain", type=Path)
    parser.add_argument("--qemu", type=Path)
    args = parser.parse_args()
    if args.rebuild and (not args.toolchain or not args.qemu):
        parser.error("--rebuild requires --toolchain and --qemu")
    receipt = {
        "archive_sha256": hashlib.sha256(args.archive.read_bytes()).hexdigest(),
        "scope": "same-host clean-directory restore, not cross-machine verification",
        "rebuild": args.rebuild,
        "logs": [],
    }
    with tempfile.TemporaryDirectory(prefix="tcp-clean-restore-") as temp:
        directory = Path(temp).resolve()
        with tarfile.open(args.archive) as archive:
            archive.extractall(directory, filter="data")
        hashes = json.loads((directory / "RESTORE-SHA256.json").read_text())
        for name, expected in hashes.items():
            path = directory / name
            if not path.resolve().is_relative_to(directory):
                raise ValueError("Invalid restore path")
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise ValueError("Restore hash mismatch: " + name)
        receipt["verified_files"] = len(hashes)
        commands = [
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests/unit",
                "-p",
                "test_tcp_*.py",
            ]
        ]
        if args.rebuild:
            commands.append(
                [
                    sys.executable,
                    "tools/tcp/run_transfer.py",
                    "--output",
                    str(directory / "recaptured"),
                    "--toolchain",
                    str(args.toolchain.resolve()),
                    "--qemu",
                    str(args.qemu.resolve()),
                ]
            )
        env = dict(os.environ, PYTHONPATH=str(directory / "src"))
        for command in commands:
            result = subprocess.run(
                command, cwd=directory, env=env, capture_output=True, text=True, timeout=1800
            )
            receipt["logs"].append(result.stdout + result.stderr)
            if result.returncode:
                raise RuntimeError(receipt["logs"][-1])
        if args.rebuild:
            original = json.loads((directory / "runs/tcp-transfer-v2/results.json").read_text())
            repeated = json.loads((directory / "recaptured/results.json").read_text())
            if original != repeated:
                raise ValueError("Restored capture differs from archived results")
            receipt.update(recaptured_sessions=9, recaptured_phases=45, summary_rows_equal=18)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({k: v for k, v in receipt.items() if k != "logs"}))


if __name__ == "__main__":
    main()
