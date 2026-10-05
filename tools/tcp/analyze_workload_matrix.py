"""Verify all 96 captured attempts before producing matrix comparison JSON/CSV."""

import argparse
from pathlib import Path

from psf_lab.tcp_workload_matrix import analyze_matrix

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--runs", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    analyze_matrix(Path.cwd(), args.runs.resolve(), args.output.resolve())
