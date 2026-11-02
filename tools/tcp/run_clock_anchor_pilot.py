#!/usr/bin/env python3
"""Capture and independently validate the four-run smoke or remaining twelve runs."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from psf_lab.clock_anchor_capture import run_pilot  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tools", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--stage", choices=("smoke", "full"), required=True)
    args = parser.parse_args()
    state = run_pilot(ROOT, args.output, json.loads(args.tools.read_text()), stage=args.stage)
    key = "smoke_passed" if args.stage == "smoke" else "passed"
    print(json.dumps(dict(runs=len(state["runs"]), stage=args.stage, passed=state.get(key, False))))
    return 0 if state.get(key, False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
