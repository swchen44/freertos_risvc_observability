"""Restore a failed QEMU source from verified parts into an exclusive new folder."""

import argparse
import gzip
import hashlib
import json
import os
import stat
import tarfile
import tempfile
from pathlib import Path


def inventory(base):
    result = []
    for path in sorted(base.rglob("*")):
        info = path.lstat()
        row = dict(path=path.relative_to(base).as_posix(), mode=stat.S_IMODE(info.st_mode))
        if stat.S_ISREG(info.st_mode):
            with path.open("rb") as stream:
                value = hashlib.file_digest(stream, "sha256").hexdigest()
            row.update(kind="file", bytes=info.st_size, sha256=value)
        elif stat.S_ISLNK(info.st_mode):
            row.update(kind="symlink", target=os.readlink(path))
        elif stat.S_ISDIR(info.st_mode):
            row.update(kind="directory")
        else:
            raise ValueError("Special file in restored source")
        result.append(row)
    return result


def restore(entry, package, output):
    if output.exists() or output.is_symlink():
        raise FileExistsError(output)
    inv = package / entry["inventory"]
    if Path(entry["inventory"]).name != entry["inventory"]:
        raise ValueError("Inventory path")
    if hashlib.sha256(inv.read_bytes()).hexdigest() != entry["inventory_sha256"]:
        raise ValueError("Inventory SHA mismatch")
    expected = json.loads(gzip.decompress(inv.read_bytes()))
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryFile(dir=output.parent) as joined:
        combined = hashlib.sha256()
        for part in entry["parts"]:
            if Path(part["path"]).name != part["path"]:
                raise ValueError("Part path")
            actual = hashlib.sha256()
            size = 0
            with (package / part["path"]).open("rb") as src:
                while chunk := src.read(65536):
                    actual.update(chunk)
                    combined.update(chunk)
                    size += len(chunk)
                    joined.write(chunk)
            if actual.hexdigest() != part["sha256"] or size != part["bytes"]:
                raise ValueError("Part SHA/size mismatch")
        if combined.hexdigest() != entry["archive_sha256"]:
            raise ValueError("Joined archive SHA mismatch")
        joined.seek(0)
        with tarfile.open(fileobj=joined, mode="r:gz") as tar:
            members = tar.getmembers()
            names, links = set(), set()
            for member in members:
                path = Path(member.name)
                if (
                    path.is_absolute()
                    or ".." in path.parts
                    or not path.parts
                    or path.parts[0] != "qemu-9.2.0"
                    or member.name in names
                    or not (member.isfile() or member.isdir() or member.issym())
                ):
                    raise ValueError("Unsafe archive member")
                names.add(member.name)
                if member.issym():
                    links.add(member.name)
            if any(str(p) in links for name in names for p in Path(name).parents):
                raise ValueError("Archive writes through symlink")
            output.mkdir(exist_ok=False)
            # All paths checked; keep original upstream symlinks as metadata only.
            tar.extractall(output, members=members, filter="fully_trusted")
    if inventory(output / "qemu-9.2.0") != expected:
        raise ValueError("Restored inventory mismatch; partial output retained")
    return dict(status="restored-verified", entries=len(expected), output=str(output))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--label", required=True, choices=("c2b-clock-20261102", "c2b-clock-20261102-r2")
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    package = Path(__file__).resolve().parent
    receipt = json.loads((package / "receipt.json").read_text())
    entries = [
        e
        for e in receipt["actions"]
        if e["kind"] == "archived-failed-source" and e["path"] == f".tools/{args.label}/qemu-9.2.0"
    ]
    if len(entries) != 1:
        raise ValueError("Missing or duplicate source entry")
    print(json.dumps(restore(entries[0], package, args.output.resolve())))


if __name__ == "__main__":
    main()
