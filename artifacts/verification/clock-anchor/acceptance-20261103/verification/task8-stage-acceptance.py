"""Publish a faithful small preview and relocate the verified full bundle."""

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path.cwd()
LEDGER = ROOT / ".superpowers/sdd/20-c2b-clock-anchor-implementation"
RUNSET = ROOT / "runs/local/c2b-pilot-v1-3cdb7794"
DEST = ROOT / "artifacts/verification/clock-anchor/acceptance-20261103"
PACKAGE = ROOT / "artifacts/local/c2b-restore-3e8a5fe2"


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def main():
    DEST.mkdir(exist_ok=False)
    omitted = []
    for path in sorted(RUNSET.rglob("*")):
        if not path.is_file():
            continue
        assert not path.is_symlink()
        rel = path.relative_to(RUNSET)
        if path.name in {
            "accesses.csv.gz",
            "clock.jsonl.gz",
            "context.jsonl.gz",
            "pre-initfix-tools-and-runtime.tar.gz",
        }:
            omitted.append(dict(path=str(rel), bytes=path.stat().st_size, sha256=sha(path)))
            continue
        target = DEST / "preview" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        assert sha(path) == sha(target)
    write(
        DEST / "preview-index.json",
        dict(
            scope="Partial projection for reading; use restore/runset for validation",
            complete_data="restore/manifest.json plus parts; restored runset/",
            omitted_from_preview=omitted,
        ),
    )
    verification = DEST / "verification"
    verification.mkdir()
    for pattern in ("task8-*", "final-review-*", "baseline-format-debt.json"):
        for path in sorted(LEDGER.glob(pattern)):
            if path.is_file():
                shutil.copy2(path, verification / path.name)
    shutil.copy2(LEDGER / "progress.md", verification / "progress-before-publication.md")
    shutil.move(str(PACKAGE), str(DEST / "restore"))
    package = DEST / "restore"
    manifest = json.loads((package / "manifest.json").read_text())
    receipt = json.loads((package / "restore-check.json").read_text())
    assert receipt["manifest_sha256"] == sha(package / "manifest.json")
    count = 0
    for entry in manifest["files"]:
        for part in entry["parts"]:
            path = package / part["path"]
            assert path.stat().st_size == part["bytes"] <= 64 * 1024 * 1024
            assert sha(path) == part["sha256"]
            count += 1
    write(
        verification / "package-relocation.json",
        dict(
            status="relocated-and-rehashed",
            original_path=str(PACKAGE.relative_to(ROOT)),
            published_path=str(package.relative_to(ROOT)),
            manifest_sha256=receipt["manifest_sha256"],
            checked_parts=count,
            unchanged_restore_receipt=receipt,
            scope=(
                "Rehash after move; actual prior restore and nested source checks "
                "are separate receipts"
            ),
        ),
    )
    print(json.dumps(dict(status="staged", omitted=len(omitted), verified_parts=count)))


if __name__ == "__main__":
    main()
