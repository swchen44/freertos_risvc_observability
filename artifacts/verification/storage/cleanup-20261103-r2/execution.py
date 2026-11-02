"""One-time approved cleanup: verify exact archives, keep evidence and active tools."""

import gzip
import hashlib
import json
import shutil
import stat
import subprocess
import tarfile
from pathlib import Path

ROOT = Path.cwd().resolve()
OUT = ROOT / "artifacts/verification/storage/cleanup-20261103-r2"
OUT.mkdir(exist_ok=False)
AUDIT = json.loads((ROOT / "artifacts/verification/storage/20261103/audit.json").read_text())
STATE = dict(status="preflight", authorization="OK, contine jobs; recommended conservative scope",
             free_bytes_before=shutil.disk_usage(ROOT).free, removed_files=0,
             removed_logical_bytes=0, actions=[])


def sha(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def save():
    temp = OUT / "receipt.tmp"
    temp.write_text(json.dumps(STATE, indent=2) + "\n")
    temp.replace(OUT / "receipt.json")


def ignored(path):
    assert path.is_relative_to(ROOT) and not path.is_symlink(), path
    assert subprocess.run(["git", "check-ignore", "-q", str(path)], cwd=ROOT).returncode == 0
    tracked = subprocess.check_output(["git", "ls-files", "-z", str(path)], cwd=ROOT)
    assert not tracked, path


def listing(base):
    rows = []
    for p in sorted(base.rglob("*")):
        assert not p.is_symlink(), p
        if p.is_file():
            rows.append(dict(path=str(p.relative_to(base)), bytes=p.stat().st_size,
                             sha256=sha(p), mode=stat.S_IMODE(p.stat().st_mode)))
    return rows


protected = {
    ROOT / ".tools/qemu-time-control/qemu-system-riscv32-relative":
        "69969c3ec8cce8f9340215fc340c5c01f81c3ef978252d3766937d2d176816db",
    ROOT / ".tools/c2b-clock-20261102-r3/qemu-system-riscv32-clock-anchor":
        "eab95b72dabe404d652bba976d821892b276b0c06be1f92fd305c7bdb30f42e6",
}
probe = json.loads((ROOT / "runs/local/c2b-guest-probe-20261102/runtime-tests.json").read_text())
protected[Path(probe["probe_elf"]["path"])] = probe["probe_elf"]["sha256"]
for p, digest in protected.items():
    assert sha(p) == digest, p
assert sha(ROOT / ".tools/qemu-time-control/qemu-9.2.0.tar.xz") == (
    "f859f0bc65e1f533d040bbe8c92bcfecee5af2c921a6687c652fb44d089bd894")

copies = []
for entry in AUDIT["verified_archived_copies"]:
    base, archive = ROOT / entry["path"], ROOT / entry["archive"]
    ignored(base)
    actual = listing(base)
    expected = {}
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar:
            if member.isfile():
                parts = Path(member.name).parts
                assert len(parts) > 1 and ".." not in parts and not Path(member.name).is_absolute()
                name = Path(*parts[1:]).as_posix()
                assert name not in expected
                expected[name] = dict(bytes=member.size,
                    sha256=hashlib.file_digest(tar.extractfile(member), "sha256").hexdigest())
            else:
                assert member.isdir()
    assert {x["path"] for x in actual} == set(expected)
    assert all(expected[x["path"]] == {k: x[k] for k in ("bytes", "sha256")} for x in actual)
    copies.append((base, actual, dict(path=entry["path"], archive=entry["archive"],
                                    archive_sha256=sha(archive), files=len(actual))))

clone = ROOT / "artifacts/local/github-clone-verification"
ignored(clone)
clone_heads = []
for repo in (clone, clone / "poc"):
    assert not subprocess.check_output(["git", "status", "--porcelain=v1",
                                       "--untracked-files=all"], cwd=repo)
    names = subprocess.check_output(["git", "ls-files", "--others", "--ignored",
                                     "--exclude-standard", "-z"], cwd=repo).decode().split("\0")
    assert all("__pycache__/" in n and n.endswith(".pyc") for n in names if n)
    clone_heads.append(dict(path=str(repo.relative_to(ROOT)), commit=subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()))
clone_files = listing(clone)
(OUT / "clone-files.json.gz").write_bytes(gzip.compress(json.dumps(clone_files).encode(), mtime=0))

objects = []
for entry in AUDIT["rebuildable_objects"]:
    base = ROOT / entry["path"]
    ignored(base)
    assert base.parent.name in ("c2b-clock-20261102", "c2b-clock-20261102-r2", "qemu-time-control")
    assert (base.parent / "qemu-9.2.0").is_dir()
    ninja = base.parent / "venv/bin/ninja"
    if not ninja.is_file():
        ninja = base.parent / "build-venv/bin/ninja"
    p = subprocess.run([str(ninja), "-t", "compdb"], cwd=base, capture_output=True, timeout=30)
    assert p.returncode == 0
    (OUT / (base.parent.name + "-compile-commands.json.gz")).write_bytes(
        gzip.compress(p.stdout, mtime=0))
    for name in (".ninja_log", "build.ninja", "rules.ninja", "config-host.h", "config-host.mak"):
        source = base / name
        if source.is_file():
            (OUT / (base.parent.name + "-" + name.lstrip(".") + ".gz")).write_bytes(
                gzip.compress(source.read_bytes(), mtime=0))
    for f in sorted(base.rglob("*")):
        if f.is_file() and not f.is_symlink() and f.suffix in (".o", ".a", ".fa"):
            objects.append(dict(path=str(f.relative_to(ROOT)), bytes=f.stat().st_size,
                                sha256=sha(f)))
(OUT / "removed-objects.json.gz").write_bytes(gzip.compress(json.dumps(objects).encode(), mtime=0))
(OUT / "archive-verification.json").write_text(json.dumps([c[2] for c in copies], indent=2)+"\n")
STATE.update(status="preflight-verified", clone_heads=clone_heads, generated_objects=len(objects),
             unique_trace_files_removed=0, tracked_files_removed=0)
save()

for base, files, evidence in copies:
    shutil.rmtree(base)
    assert not base.exists()
    STATE["removed_files"] += len(files)
    STATE["removed_logical_bytes"] += sum(f["bytes"] for f in files)
    STATE["actions"].append(dict(kind="archived-copy", **evidence))
    save()
    if base.name == "guest-probe" and not any(base.parent.iterdir()):
        base.parent.rmdir()

shutil.rmtree(clone)
assert not clone.exists()
STATE["removed_files"] += len(clone_files)
STATE["removed_logical_bytes"] += sum(f["bytes"] for f in clone_files)
STATE["actions"].append(dict(kind="disposable-clean-clone", path=str(clone.relative_to(ROOT)),
    files=len(clone_files), recovery="Clone current repository; no unique worktree changes."))
save()

with (OUT / "removed-objects-progress.jsonl").open("w") as progress:
    for entry in objects:
        f = ROOT / entry["path"]
        assert f.is_file() and not f.is_symlink() and sha(f) == entry["sha256"]
        f.unlink()
        STATE["removed_files"] += 1
        STATE["removed_logical_bytes"] += entry["bytes"]
        progress.write(json.dumps(dict(path=entry["path"], removed=True)) + "\n")
STATE["actions"].append(dict(kind="rebuildable-object-cache", files=len(objects),
    bytes=sum(x["bytes"] for x in objects), recovery="Source, logs, binaries and compdb retained."))
for p, digest in protected.items():
    assert sha(p) == digest
STATE.update(status="complete", protected_inputs_verified=True,
             free_bytes_after=shutil.disk_usage(ROOT).free)
STATE["observed_free_bytes_delta"] = STATE["free_bytes_after"] - STATE["free_bytes_before"]
save()
print(json.dumps(STATE, indent=2))
