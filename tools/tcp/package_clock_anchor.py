#!/usr/bin/env python3
"""Bounded per-file gzip parts and self-contained C2b data/source restoration."""

import argparse
import gzip
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

MAX_PART = 64 * 1024 * 1024


def sha(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def safe_name(name):
    if (
        not isinstance(name, str)
        or not name
        or any(c in name for c in ("\\", ":", "\0"))
        or name.startswith("/")
        or any(p in ("", ".", "..") for p in name.split("/"))
    ):
        raise ValueError("Unsafe relative member path")
    return PurePosixPath(name)


def regular(path):
    if path.is_symlink() or not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError("Only regular files are package members")


def tree_files(base, prefix):
    if base.is_symlink():
        raise ValueError("Symlink input tree")
    for path in sorted(base.rglob("*")):
        if path.is_symlink():
            raise ValueError("Symlink input")
        if path.is_file():
            regular(path)
            yield prefix + "/" + path.relative_to(base).as_posix(), path
        elif not path.is_dir():
            raise ValueError("Special input file")


class PartWriter:
    def __init__(self, output, index, limit):
        self.output, self.index, self.limit = output, index, limit
        self.parts = []
        self.total = 0
        self.overall = hashlib.sha256()
        self.file = None

    def write(self, data):
        length = len(data)
        while data:
            if self.file is None:
                self.path = self.output / "parts" / f"{self.index:06d}-{len(self.parts):06d}.part"
                self.file = self.path.open("xb")
                self.current = hashlib.sha256()
                self.size = 0
            piece = data[: self.limit - self.size]
            self.file.write(piece)
            self.current.update(piece)
            self.overall.update(piece)
            self.size += len(piece)
            self.total += len(piece)
            data = data[len(piece) :]
            if self.size == self.limit:
                self._close_part()
        return length

    def _close_part(self):
        if self.file is not None:
            self.file.close()
            self.parts.append(
                dict(
                    path=self.path.relative_to(self.output).as_posix(),
                    bytes=self.size,
                    sha256=self.current.hexdigest(),
                )
            )
            self.file = None

    def flush(self):
        if self.file is not None:
            self.file.flush()

    def finish(self):
        self._close_part()


def tar_snapshot(paths, destination):
    def filtered(info):
        if any(p in (".git", "__pycache__") for p in PurePosixPath(info.name).parts):
            return None
        if info.name.endswith(".pyc"):
            return None
        if not (info.isfile() or info.isdir() or info.issym()):
            raise ValueError("Special source archive entry")
        return info

    with tarfile.open(destination, "w:gz", compresslevel=6) as archive:
        for source, name in paths:
            archive.add(source, arcname=name, filter=filtered)


def full_inputs(tools, stage):
    """Host closure is explicit; nested source tarballs remain opaque on restore."""
    from psf_lab.clock_anchor_capture import _validate_tools
    from psf_lab.provenance import require_clean_tree

    commit = require_clean_tree(ROOT)
    _validate_tools(ROOT, tools)
    extras = []
    build = json.loads(Path(tools["qemu_build_manifest"]["path"]).read_text())
    for name in ("legacy_qemu", "clock_qemu", "qemu_build_manifest"):
        path = Path(tools[name]["path"])
        extras.append(("host-tools/" + name + "/" + path.name, path))
    build_root = Path(build["source"]).parent
    for path in sorted(build_root.iterdir()):
        if path.is_file() and not path.is_symlink() and path.suffix in (".log", ".json", ".txt"):
            extras.append(("qemu-build/" + path.name, path))
    for name in ("build.ninja", "rules.ninja", "config-host.h", "config-host.mak", ".ninja_log"):
        path = build_root / "build" / name
        if path.is_file():
            extras.append(("qemu-build/config/" + name, path))
    tools_root = Path(tools["candidates"]["baseline"]["elf"]["path"]).parents[2]
    extras.extend(tree_files(tools_root, "compiled-tools"))
    source = Path(build["source"])
    qemu_archive = stage / "qemu-9.2.0-patched.tar.gz"
    tar_snapshot([(source, "qemu-9.2.0")], qemu_archive)
    extras.append(("sources/" + qemu_archive.name, qemu_archive))
    qemu_inventory = []
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            qemu_inventory.append(
                dict(
                    path=path.relative_to(source).as_posix(),
                    kind="symlink",
                    target=os.readlink(path),
                )
            )
        elif (
            path.is_file()
            and "__pycache__" not in path.parts
            and path.suffix != ".pyc"
            and ".git" not in path.parts
        ):
            qemu_inventory.append(
                dict(
                    path=path.relative_to(source).as_posix(),
                    kind="file",
                    bytes=path.stat().st_size,
                    mode=stat.S_IMODE(path.stat().st_mode),
                    sha256=sha(path),
                )
            )
    inv = stage / "qemu-source-inventory.json.gz"
    inv.write_bytes(gzip.compress(json.dumps(qemu_inventory).encode(), mtime=0))
    extras.append(("sources/" + inv.name, inv))
    names = [
        "firmware",
        "src",
        "tests",
        "tools/qemu",
        "tools/tcp",
        "cases",
        "tools/toolchain-lock.json",
        "pyproject.toml",
        "requirements-runtime.lock",
        "requirements-dev.lock",
        "third_party/FreeRTOS/FreeRTOS/Source",
        "third_party/FreeRTOS/FreeRTOS/Demo/RISC-V_RV32_QEMU_VIRT_GCC",
        "references/baseline/percepio/TraceRecorder",
        "references/tcp/lwip",
        "docs/design/c2b-clock-anchor-pilot-v1.md",
        "docs/plans/20-c2b-clock-anchor-implementation.md",
    ]
    project = stage / "project-source.tar.gz"
    tar_snapshot([(ROOT / n, n) for n in names], project)
    extras.append(("sources/" + project.name, project))
    for candidate in ("baseline", "pbuf"):
        old = ROOT / f"runs/tcp-context-v1/probe/A02-{candidate}/enabled-1-1"
        for name in ("firmware.elf", "manifest.json", "symbols.txt"):
            extras.append((f"references/{candidate}/" + name, old / name))
    info = stage / "source-and-host-requirements.json"
    write_json(
        info,
        dict(
            package_source_commit=commit,
            compiled_source_commit=tools["source_commit"],
            qemu_build=build,
            offline_rebuild="unavailable",
            cross_host_validation="not-performed",
            scope="Data/source byte restoration, not a closed portable host environment",
            not_bundled=[
                "RISC-V GCC host distribution",
                "host GLib and system libraries",
                "Python/Meson/Ninja offline wheel closure",
            ],
            nested_archives="Original files/symlink metadata; not automatically extracted",
        ),
    )
    extras.append(("sources/" + info.name, info))
    _validate_tools(ROOT, tools)
    if require_clean_tree(ROOT) != commit:
        raise ValueError("Source changed while snapshotting")
    return extras


def package_clock_anchor(runset: Path, output: Path, *, max_part_bytes=MAX_PART):
    if type(max_part_bytes) is not int or not 0 < max_part_bytes <= MAX_PART:
        raise ValueError("Part limit must be 1..64MiB")
    if runset.is_symlink() or output.is_symlink():
        raise ValueError("Symlink package path")
    runset, output = runset.resolve(), output.resolve()
    if output.is_relative_to(runset):
        raise ValueError("Package output cannot nest input")
    if output.exists():
        raise FileExistsError(output)
    sources = list(tree_files(runset, "runset"))
    state = json.loads((runset / "runset.json").read_text())
    output.mkdir(parents=True, exist_ok=False)
    (output / "parts").mkdir()
    files, seen = [], set()
    with tempfile.TemporaryDirectory(prefix="c2b-package-stage-", dir=output.parent) as tmp:
        if state.get("tools"):
            sources.extend(full_inputs(state["tools"], Path(tmp)))
        for index, (name, path) in enumerate(sources):
            safe_name(name)
            regular(path)
            if name.casefold() in seen:
                raise ValueError("Duplicate member")
            seen.add(name.casefold())
            before = path.stat()
            if stat.S_IMODE(before.st_mode) & ~0o777:
                raise ValueError("Special permission bits")
            parts = PartWriter(output, index, max_part_bytes)
            content = hashlib.sha256()
            size = 0
            try:
                with (
                    path.open("rb") as src,
                    gzip.GzipFile(filename="", fileobj=parts, mode="wb", mtime=0) as gz,
                ):
                    while chunk := src.read(65536):
                        gz.write(chunk)
                        content.update(chunk)
                        size += len(chunk)
            finally:
                parts.finish()
            if path.stat().st_mtime_ns != before.st_mtime_ns or size != before.st_size:
                raise ValueError("Input changed during packaging")
            files.append(
                dict(
                    path=name,
                    original_bytes=size,
                    original_sha256=content.hexdigest(),
                    mode=stat.S_IMODE(before.st_mode),
                    gzip_bytes=parts.total,
                    gzip_sha256=parts.overall.hexdigest(),
                    parts=parts.parts,
                )
            )
    manifest = dict(
        schema="clock-anchor-package-v1",
        codec="gzip-file-parts-v1",
        status="packaged-not-restore-verified",
        max_part_bytes=max_part_bytes,
        files=files,
        nested_archives="opaque bytes; source symlinks are metadata in source snapshots",
    )
    write_json(output / "manifest.json", manifest)
    write_json(
        output / "inventory.json",
        {
            f["path"]: dict(bytes=f["original_bytes"], sha256=f["original_sha256"], mode=f["mode"])
            for f in files
        },
    )
    return manifest


def verify_restore(package: Path, temporary_output: Path):
    if package.is_symlink() or temporary_output.is_symlink():
        raise ValueError("Symlink restore path")
    package, output = package.resolve(), temporary_output.resolve()
    if output.exists():
        raise FileExistsError(output)
    if output.is_relative_to(package):
        raise ValueError("Restore output cannot nest package")
    manifest_path = package / "manifest.json"
    regular(manifest_path)
    if manifest_path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError("Manifest resource limit")
    manifest = json.loads(manifest_path.read_text())
    if (
        manifest.get("schema") != "clock-anchor-package-v1"
        or manifest.get("codec") != "gzip-file-parts-v1"
    ):
        raise ValueError("Unsupported package/codec; tar and zip are not restore containers")
    files = manifest["files"]
    if not isinstance(files, list) or len(files) > 65536:
        raise ValueError("Member limit")
    names = set()
    part_names = set()
    for entry in files:
        name = safe_name(entry["path"]).as_posix()
        if name.casefold() in names:
            raise ValueError("Duplicate restore member")
        names.add(name.casefold())
        if (
            any(
                type(entry[k]) is not int or entry[k] < 0
                for k in ("original_bytes", "gzip_bytes", "mode")
            )
            or entry["mode"] & ~0o777
        ):
            raise ValueError("Invalid size/mode")
        if any(
            not isinstance(entry[k], str) or not re.fullmatch("[0-9a-f]{64}", entry[k])
            for k in ("original_sha256", "gzip_sha256")
        ):
            raise ValueError("Invalid content hash")
        if not entry["parts"]:
            raise ValueError("Missing parts")
        for part in entry["parts"]:
            rel = safe_name(part["path"])
            if rel.as_posix() in part_names or rel.parts[0] != "parts":
                raise ValueError("Duplicate/non-part path")
            part_names.add(rel.as_posix())
            path = package / rel
            if any(p.is_symlink() for p in (path, *path.parents) if p.is_relative_to(package)):
                raise ValueError("Symlink part path")
            regular(path)
            if type(part["bytes"]) is not int or not 0 < part["bytes"] <= MAX_PART:
                raise ValueError("Part size limit")
            if path.stat().st_size != part["bytes"] or sha(path) != part["sha256"]:
                raise ValueError("Part SHA/size mismatch")
    if any(str(p).casefold() in names for n in names for p in PurePosixPath(n).parents):
        raise ValueError("File/parent path collision")
    required = (
        sum(e["original_bytes"] for e in files)
        + max((e["gzip_bytes"] for e in files), default=0)
        + 64 * 1024 * 1024
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(output.parent).free < required:
        raise ValueError("Insufficient restore space")
    output.mkdir(exist_ok=False)
    total = 0
    for entry in files:
        with tempfile.TemporaryFile(dir=output.parent) as joined:
            compressed = hashlib.sha256()
            gzip_bytes = 0
            for part in entry["parts"]:
                with (package / part["path"]).open("rb") as src:
                    while chunk := src.read(65536):
                        joined.write(chunk)
                        compressed.update(chunk)
                        gzip_bytes += len(chunk)
            if compressed.hexdigest() != entry["gzip_sha256"] or gzip_bytes != entry["gzip_bytes"]:
                raise ValueError("Joined gzip changed")
            joined.seek(0)
            dest = output / entry["path"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            actual = hashlib.sha256()
            size = 0
            with gzip.GzipFile(fileobj=joined, mode="rb") as gz, dest.open("xb") as target:
                while chunk := gz.read(65536):
                    size += len(chunk)
                    if size > entry["original_bytes"]:
                        raise ValueError("Expansion exceeds declared size")
                    target.write(chunk)
                    actual.update(chunk)
            if (
                size != entry["original_bytes"]
                or actual.hexdigest() != entry["original_sha256"]
                or sha(dest) != entry["original_sha256"]
            ):
                raise ValueError("Restored bytes mismatch")
            os.chmod(dest, entry["mode"])
            if stat.S_IMODE(dest.stat().st_mode) != entry["mode"]:
                raise ValueError("Restored mode mismatch")
            total += size
    return dict(
        status="restored-verified",
        verified_files=len(files),
        verified_bytes=str(total),
        manifest_sha256=sha(manifest_path),
        scope="regular files; nested source archives remain opaque",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--restore-check", type=Path)
    args = parser.parse_args()
    manifest = package_clock_anchor(args.runset, args.output)
    result = dict(status=manifest["status"], files=len(manifest["files"]))
    if args.restore_check:
        result = verify_restore(args.output, args.restore_check)
        write_json(args.output / "restore-check.json", result)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
