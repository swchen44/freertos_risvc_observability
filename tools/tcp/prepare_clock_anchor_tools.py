#!/usr/bin/env python3
"""Build the pinned C2b candidate ELFs and legacy/new collectors."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from psf_lab.clock_anchor_capture import prepare_tools  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qemu-build-manifest", type=Path, required=True)
    parser.add_argument("--legacy-qemu", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    tools = prepare_tools(
        ROOT, args.qemu_build_manifest.resolve(), args.legacy_qemu.resolve(), args.output
    )
    print("Built pinned C2b tools at", args.output)
    print("Source:", tools["source_commit"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
