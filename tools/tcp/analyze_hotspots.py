"""Replay existing accepted captures into a new C1 evidence directory."""

import argparse
from pathlib import Path
from psf_lab.hotspot_evidence import analyze_hotspots

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workload", choices=[f"A{i:02}" for i in range(1, 9)])
    p.add_argument("--output", required=True, type=Path)
    a = p.parse_args()
    analyze_hotspots(Path.cwd(), a.output, workload=a.workload)
