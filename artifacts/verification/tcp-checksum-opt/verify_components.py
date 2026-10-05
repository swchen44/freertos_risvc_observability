"""Validate saved component matrices and export algorithm-3 size/alignment comparison."""

import csv
import hashlib
import json
from pathlib import Path

from psf_lab.tcp_checksum import internet_checksum

root = Path.cwd()
output = root / "artifacts/verification/tcp-checksum-opt"
variants = {}
receipts = []
for opt, name in [("Os", "tcp-opt-checksum-os-v1"), ("O2", "tcp-opt-checksum-o2-v2")]:
    path = root / "runs" / name
    manifest = json.loads((path / "manifest.json").read_text())
    rows = json.loads((path / "results.json").read_text())
    assert len(rows) == 108 and len(manifest["runs"]) == 9
    assert (
        hashlib.sha256((path / "results.json").read_bytes()).hexdigest()
        == manifest["results_sha256"]
    )
    for category in ("source_files", "dependency_files"):
        for file, expected in manifest[category].items():
            assert hashlib.sha256((root / file).read_bytes()).hexdigest() == expected, file
    for run in manifest["runs"]:
        for file, expected in run["files"].items():
            assert (
                hashlib.sha256((path / run["directory"] / file).read_bytes()).hexdigest()
                == expected
            ), file
    for row in rows:
        data = bytes(
            (i * 17 + 31) % 256 for i in range(row["offset"], row["offset"] + row["length"])
        )
        assert row["checksum"] == internet_checksum(data)
    variants[opt] = {
        (r["length"], r["offset"]): r["instructions"]
        for r in rows
        if r["algorithm"] == 3 and r["repeat"] == 1
    }
    receipts.append(
        dict(
            variant=opt,
            runs=9,
            measurements=108,
            manifest_sha256=hashlib.sha256((path / "manifest.json").read_bytes()).hexdigest(),
        )
    )
with (output / "component-comparison.csv").open("w", newline="") as stream:
    w = csv.writer(stream)
    w.writerow(
        [
            "length",
            "offset",
            "Os_instructions_32_calls",
            "O2_instructions_32_calls",
            "instruction_reduction_percent",
        ]
    )
    for key, a in variants["Os"].items():
        b = variants["O2"][key]
        w.writerow([*key, a, b, (a - b) / a * 100])
(output / "components-receipt.json").write_text(json.dumps(receipts, indent=2) + "\n")
print("Verified 216 checksum measurements, 18 PSFs and all source/artifact hashes")
