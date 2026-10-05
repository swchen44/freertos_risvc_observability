"""Verify exploratory probe using archived source versions; run from POC root."""

import json
from pathlib import Path

from psf_lab.runner import digest, write_json

out = Path("artifacts/verification/tcp-pbuf-holdout")
directory = Path("runs/tcp-chain-probe-v1")
overrides = {
    "firmware/app/cases/tcp_request_response.c": out / "probe-source.c",
    "src/psf_lab/tcp_session.py": out / "probe-validator.py",
}
manifest = json.loads((directory / "manifest.json").read_text())
for name, expected in manifest["sources"].items():
    assert digest(overrides.get(name, Path(name))) == expected, name
for run in manifest["runs"]:
    path = directory / run["name"]
    assert digest(path / "manifest.json") == run["sha256"]
    record = json.loads((path / "manifest.json").read_text())
    for name, expected in record["files"].items():
        assert digest(path / name) == expected, path / name
assert digest(directory / "results.json") == manifest["results_sha256"]
assert json.loads((directory / "results.json").read_text())["passed"]
write_json(
    out / "probe-receipt.json",
    dict(
        passed=True,
        runs=2,
        source_overrides={k: str(v) for k, v in overrides.items()},
        reason="Exploratory probe before strict receipt typing and preserving linear save path.",
    ),
)
