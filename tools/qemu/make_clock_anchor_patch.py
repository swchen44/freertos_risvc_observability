"""Generate the bounded QEMU overlay diff and verify canonical core copies."""

import argparse
import difflib
import hashlib
import json
from pathlib import Path

ALLOWED = frozenset(
    (
        "plugins/api.c",
        "plugins/poc-clock-observer.c",
        "plugins/poc-clock-state.c",
        "plugins/poc-clock-state.h",
        "plugins/meson.build",
        "include/qemu/qemu-plugin.h",
        "include/qemu/poc-clock-anchor-api.h",
        "include/sysemu/poc-clock-observer.h",
        "hw/intc/riscv_aclint.c",
    )
)
COPIES = {
    "tools/qemu/clock_anchor/poc-clock-state.c": "plugins/poc-clock-state.c",
    "tools/qemu/clock_anchor/poc-clock-state.h": "plugins/poc-clock-state.h",
    "tools/qemu/poc-clock-anchor-api.h": "include/qemu/poc-clock-anchor-api.h",
}


def check_tool_versions(packages: dict, reported: dict) -> dict:
    expected = {"meson": "1.12.1", "ninja": "1.13.2"}
    if packages != expected or set(reported) != set(expected):
        raise ValueError("Build distribution version mismatch")
    accepted = {"meson": {"1.12.1"}, "ninja": {"1.13.2", "1.13.2.git.kitware.jobserver-pipe-1"}}
    if any(reported[name] not in accepted[name] for name in expected):
        raise ValueError("Build executable version mismatch")
    return {
        name: dict(version=expected[name], reported_version=reported[name]) for name in expected
    }


def verify_overlays(root: Path, source: Path) -> dict:
    result = {}
    for canonical, copied in COPIES.items():
        a, b = root / canonical, source / copied
        if not a.is_file() or not b.is_file() or b.is_symlink() or a.read_bytes() != b.read_bytes():
            raise ValueError("Overlay mismatch: " + copied)
        result[copied] = hashlib.sha256(b.read_bytes()).hexdigest()
    return result


def generate_clock_patch(base: Path, edited: Path, output: Path) -> dict:
    if output.exists():
        raise FileExistsError(output)
    base, edited = base.resolve(), edited.resolve()
    for path in edited.rglob("*"):
        name = path.relative_to(edited).as_posix()
        if path.is_symlink():
            raise ValueError("Symlink in edited source: " + name)
        if path.is_file() and name not in ALLOWED:
            original = base / name
            if not original.is_file() or original.read_bytes() != path.read_bytes():
                raise ValueError("Change outside patch scope: " + name)
    chunks, hashes = [], {}
    for name in sorted(ALLOWED):
        a, b = base / name, edited / name
        if not b.is_file():  # Sparse edit trees omit unchanged files; no deletions in v1.
            continue
        before = a.read_bytes() if a.exists() else b""
        after = b.read_bytes()
        if before == after:
            continue
        if (before and not before.endswith(b"\n")) or not after.endswith(b"\n"):
            raise ValueError("Source requires final LF: " + name)
        chunks.extend(
            difflib.unified_diff(
                before.decode("utf-8").splitlines(keepends=True),
                after.decode("utf-8").splitlines(keepends=True),
                fromfile="a/" + name if a.exists() else "/dev/null",
                tofile="b/" + name,
                n=0,  # Pinned base; avoid whitespace-only patch context lines.
            )
        )
        hashes[name] = hashlib.sha256(after).hexdigest()
    with output.open("x") as stream:
        stream.write("".join(chunks))
    return dict(
        paths=list(hashes),
        files_sha256=hashes,
        patch_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path)
    parser.add_argument("--edited", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify-overlays", type=Path)
    args = parser.parse_args()
    if args.verify_overlays:
        if any((args.base, args.edited, args.output)):
            parser.error("--verify-overlays cannot be combined with generation")
        result = verify_overlays(Path(__file__).resolve().parents[2], args.verify_overlays)
    else:
        if not all((args.base, args.edited, args.output)):
            parser.error("--base, --edited and --output are required")
        result = generate_clock_patch(args.base, args.edited, args.output)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
