"""Verify historical exploratory checksum v1 using its archived C source."""

import json
from pathlib import Path

from psf_lab.runner import digest, write_json

root = Path.cwd()
archive = Path("artifacts/verification/tcp-os-small-cache")
directory = Path("runs/tcp-small-checksum-v1")
manifest = json.loads((directory / "manifest.json").read_text())
for file, expected in manifest["sources"].items():
    source = (
        archive / "checksum-v1-source.c"
        if file == "firmware/tcp_stack/os_checksum.c"
        else root / file
    )
    assert digest(source) == expected, file
for run in manifest["runs"]:
    path = directory / run["name"]
    assert digest(path / "manifest.json") == run["sha256"]
    record = json.loads((path / "manifest.json").read_text())
    for file, expected in record["files"].items():
        assert digest(path / file) == expected, path / file
assert digest(directory / "results.json") == manifest["results_sha256"]
assert json.loads((directory / "results.json").read_text())["passed"]
write_json(
    archive / "checksum-v1-receipt.json",
    dict(
        passed=True,
        runs=6,
        source_override={"firmware/tcp_stack/os_checksum.c": str(archive / "checksum-v1-source.c")},
        reason=(
            "Signed division rejected after binary inspection; "
            "v2 uses unsigned endpoint arithmetic."
        ),
    ),
)
