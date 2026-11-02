"""Authorized one-time cleanup; source deletion requires verified full restoration."""

import gzip
import hashlib
import json
import os
import shutil
import stat
import subprocess
import tarfile
from pathlib import Path

ROOT = Path.cwd().resolve()
OUT = Path(__file__).resolve().parent
STATE = dict(status="preflight", free_before=shutil.disk_usage(ROOT).free, actions=[])


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save():
    (OUT / "receipt.tmp").write_text(json.dumps(STATE, indent=2) + "\n")
    (OUT / "receipt.tmp").replace(OUT / "receipt.json")


def ignored(path):
    assert path.is_relative_to(ROOT) and not path.is_symlink() and path.is_dir()
    assert subprocess.run(["git", "check-ignore", "-q", str(path)], cwd=ROOT).returncode == 0
    assert not subprocess.check_output(["git", "ls-files", "-z", str(path)], cwd=ROOT)


def inventory(base):
    rows = []
    for path in sorted(base.rglob("*")):
        info = path.lstat()
        row = dict(path=path.relative_to(base).as_posix(), mode=stat.S_IMODE(info.st_mode))
        if stat.S_ISREG(info.st_mode):
            row.update(kind="file", bytes=info.st_size, sha256=sha(path))
        elif stat.S_ISLNK(info.st_mode):
            row.update(kind="symlink", target=os.readlink(path))
        else:
            assert stat.S_ISDIR(info.st_mode)
            row.update(kind="directory")
        rows.append(row)
    return rows


def verify_existing_copy(base, archive):
    ignored(base)
    actual = inventory(base)
    assert all(r["kind"] != "symlink" for r in actual)
    expected = {}
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar:
            if not member.isfile():
                assert member.isdir()
                continue
            parts = Path(member.name).parts
            assert len(parts) > 1 and ".." not in parts and not member.name.startswith("/")
            name = Path(*parts[1:]).as_posix()
            assert name not in expected
            expected[name] = dict(
                bytes=member.size,
                sha256=hashlib.file_digest(tar.extractfile(member), "sha256").hexdigest(),
            )
    files = [r for r in actual if r["kind"] == "file"]
    assert {r["path"] for r in files} == set(expected)
    assert all({k: r[k] for k in ("bytes", "sha256")} == expected[r["path"]] for r in files)
    shutil.rmtree(base)
    STATE["actions"].append(
        dict(
            kind="verified-duplicate",
            path=str(base.relative_to(ROOT)),
            archive=str(archive.relative_to(ROOT)),
            archive_sha256=sha(archive),
            removed_files=len(files),
            removed_bytes=sum(r["bytes"] for r in files),
        )
    )
    save()
    print("Removed verified archived duplicate:", base.name, flush=True)


def validate_members(members):
    names = set()
    links = set()
    for member in members:
        parts = Path(member.name).parts
        assert parts and parts[0] == "qemu-9.2.0" and ".." not in parts
        assert not member.name.startswith("/") and member.name not in names
        names.add(member.name)
        assert member.isfile() or member.isdir() or member.issym()
        if member.issym():
            links.add(member.name)
    # Preserve upstream symlink metadata (including X11), never extract through a link.
    assert not any(str(parent) in links for name in names for parent in Path(name).parents)


def archive_failed_source(label):
    base = ROOT / ".tools" / label / "qemu-9.2.0"
    ignored(base)
    assert label in ("c2b-clock-20261102", "c2b-clock-20261102-r2")
    assert not any(
        name.startswith(str(base.relative_to(ROOT)) + "/")
        for name in TOOLS["compiled_dependencies"]
    )
    assert shutil.disk_usage(ROOT).free > 1150 * 1024 * 1024, "Not enough safe restore headroom"
    before = inventory(base)
    inventory_path = OUT / (label + "-inventory.json.gz")
    inventory_path.write_bytes(gzip.compress(json.dumps(before).encode(), mtime=0))
    archive = OUT / (label + "-source.tar.gz")
    assert not archive.exists()
    print("Archiving failed source:", label, flush=True)
    with tarfile.open(archive, "w:gz", compresslevel=6) as tar:
        tar.add(base, arcname="qemu-9.2.0")
    archive_sha = sha(archive)
    restored = ROOT / "artifacts/local" / ("cleanup-restore-" + label)
    assert not restored.exists()
    restored.mkdir()
    print("Restoring and checking every file:", label, flush=True)
    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
        validate_members(members)
        tar.extractall(restored, members=members, filter="fully_trusted")
    assert inventory(restored / "qemu-9.2.0") == before
    assert inventory(base) == before
    # Only now are both full, verified redundant trees disposable.
    shutil.rmtree(base)
    shutil.rmtree(restored)
    parts = []
    combined = hashlib.sha256()
    with archive.open("rb") as stream:
        index = 0
        while chunk := stream.read(64 * 1024 * 1024):
            index += 1
            path = OUT / (label + f"-source.tar.gz.part{index:03d}")
            with path.open("xb") as target:
                target.write(chunk)
            combined.update(chunk)
            parts.append(dict(path=path.name, bytes=len(chunk), sha256=sha(path)))
    assert combined.hexdigest() == archive_sha
    archive.unlink()  # Exact duplicate of the verified parts only.
    entry = dict(
        kind="archived-failed-source",
        path=str(base.relative_to(ROOT)),
        archive_sha256=archive_sha,
        parts=parts,
        inventory=inventory_path.name,
        inventory_sha256=sha(inventory_path),
        restored_and_verified=True,
        entries=len(before),
        removed_files=sum(r["kind"] == "file" for r in before),
        removed_bytes=sum(r.get("bytes", 0) for r in before),
    )
    STATE["actions"].append(entry)
    save()
    print("Removed restored-and-verified source:", label, flush=True)


assert not (OUT / "receipt.json").exists(), "One-time execution; never overwrite a receipt"
TOOLS = json.loads((ROOT / "runs/local/c2b-tools-20261103/tools.json").read_text())
protected = {name: TOOLS[name] for name in ("legacy_qemu", "clock_qemu", "probe_elf")}
assert all(sha(Path(item["path"])) == item["sha256"] for item in protected.values())
save()
verify_existing_copy(
    ROOT / "runs/local/c2b-development-O-20261103",
    ROOT / "artifacts/verification/clock-anchor/task5-20261103/development-O.tar.gz",
)
runtime_archives = ROOT / "artifacts/verification/clock-anchor/task6-20261103"
for entry in json.loads((runtime_archives / "runtime-archives.json").read_text()):
    verify_existing_copy(ROOT / entry["original"], runtime_archives / entry["path"])
for label in ("c2b-clock-20261102", "c2b-clock-20261102-r2"):
    archive_failed_source(label)
assert all(sha(Path(item["path"])) == item["sha256"] for item in protected.values())
STATE.update(
    status="complete",
    free_after=shutil.disk_usage(ROOT).free,
    protected_tools_verified=protected,
    tracked_files_removed=0,
    unique_evidence_discarded=0,
)
STATE["observed_free_delta"] = STATE["free_after"] - STATE["free_before"]
save()
print(json.dumps({k: STATE[k] for k in ("status", "observed_free_delta", "free_after")}))
