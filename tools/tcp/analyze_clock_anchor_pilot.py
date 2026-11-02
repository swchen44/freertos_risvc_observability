#!/usr/bin/env python3
"""Verify a C2b runset and write a new JSON/CSV/Markdown evidence report."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from psf_lab.clock_anchor_analysis import write_pilot_report  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = write_pilot_report(args.runset, args.output)
    print(json.dumps(dict(status=report["status"], runs=len(report["runs"]))))
    return 0 if report["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
