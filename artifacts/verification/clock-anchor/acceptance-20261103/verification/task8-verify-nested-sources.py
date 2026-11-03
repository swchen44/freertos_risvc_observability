"""Verify owned source snapshots in isolated temporary directories, never via links."""

import gzip
import hashlib
import json
import os
import shutil
import stat
import tarfile
import tempfile
from pathlib import Path

ROOT = Path.cwd().resolve()
RESTORED = ROOT / "artifacts/local/c2b-restored-3e8a5fe2"
OUT = ROOT / ".superpowers/sdd/20-c2b-clock-anchor-implementation/task8-nested-source-restore.json"


def sha(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def extract(archive, folder):
    with tarfile.open(archive, "r:gz") as t:
        members = t.getmembers()
        names = set()
        links = set()
        for m in members:
            p = Path(m.name)
            if p.is_absolute() or ".." in p.parts or not p.parts or m.name in names:
                raise ValueError("Unsafe or duplicate member")
            if not (m.isfile() or m.isdir() or m.issym()):
                raise ValueError("Special/hardlink source member")
            names.add(m.name)
            if m.issym():
                links.add(m.name)
        if any(str(p) in links for name in names for p in Path(name).parents):
            raise ValueError("Extraction through a link")
        t.extractall(folder, members=members, filter="fully_trusted")
        return len(members)


def inventory(base):
    rows = []
    for p in sorted(base.rglob("*")):
        name = p.relative_to(base).as_posix()
        if p.is_symlink():
            rows.append(dict(path=name, kind="symlink", target=os.readlink(p)))
        elif p.is_file():
            rows.append(
                dict(
                    path=name,
                    kind="file",
                    bytes=p.stat().st_size,
                    mode=stat.S_IMODE(p.stat().st_mode),
                    sha256=sha(p),
                )
            )
        elif not p.is_dir():
            raise ValueError("Special extracted entry")
    return rows


receipt = dict(status="in-progress", source_root=str(RESTORED), checks=[])
expected = json.loads(
    gzip.decompress((RESTORED / "sources/qemu-source-inventory.json.gz").read_bytes())
)
if shutil.disk_usage(ROOT).free < sum(r.get("bytes", 0) for r in expected) + 256 * 1024 * 1024:
    raise RuntimeError("Insufficient safe source restore space")
with tempfile.TemporaryDirectory(
    prefix="c2b-qemu-source-check-", dir=ROOT / "artifacts/local"
) as tmp:
    archive = RESTORED / "sources/qemu-9.2.0-patched.tar.gz"
    count = extract(archive, Path(tmp))
    actual = inventory(Path(tmp) / "qemu-9.2.0")
    if actual != expected:
        raise ValueError("QEMU source inventory mismatch")
    receipt["checks"].append(
        dict(
            kind="qemu-source",
            archive_sha256=sha(archive),
            tar_members=count,
            verified_entries=len(actual),
            regular_files=sum(r["kind"] == "file" for r in actual),
            symlinks=sum(r["kind"] == "symlink" for r in actual),
            result="passed",
        )
    )
    print("QEMU source inventory verified", len(actual), flush=True)
with tempfile.TemporaryDirectory(
    prefix="c2b-project-source-check-", dir=ROOT / "artifacts/local"
) as tmp:
    archive = RESTORED / "sources/project-source.tar.gz"
    folder = Path(tmp)
    count = extract(archive, folder)
    actual = inventory(folder)
    for row in actual:
        p = ROOT / row["path"]
        if row["kind"] == "symlink":
            if not p.is_symlink() or os.readlink(p) != row["target"]:
                raise ValueError("Project link mismatch")
        elif (
            not p.is_file()
            or p.stat().st_size != row["bytes"]
            or sha(p) != row["sha256"]
            or stat.S_IMODE(p.stat().st_mode) != row["mode"]
        ):
            raise ValueError("Project source mismatch: " + row["path"])
    receipt["checks"].append(
        dict(
            kind="selected-project-source",
            archive_sha256=sha(archive),
            tar_members=count,
            verified_entries=len(actual),
            result="passed",
        )
    )
    print("Selected project source verified", len(actual), flush=True)
receipt.update(
    status="source-restored-verified",
    scope="Same-host content/mode/symlink metadata checks; no rebuild or cross-host acceptance",
)
OUT.write_text(json.dumps(receipt, indent=2) + "\n")
