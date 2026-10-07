"""Capture a pinned A ELF with optional context sidecar and full parity checks."""

import argparse
from pathlib import Path

from psf_lab.context_capture import run_context_case

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-runset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, choices=(1, 3), required=True)
    parser.add_argument("--context", choices=("on", "off"), required=True)
    parser.add_argument("--timing-mode", choices=("both", "control", "injection"), default="both")
    args = parser.parse_args()
    result = run_context_case(
        Path.cwd(),
        args.source_runset,
        args.output,
        repeats=args.repeats,
        context_enabled=args.context == "on",
        timing_modes={"both": (0, 1), "control": (0,), "injection": (1,)}[args.timing_mode],
    )
    print("passed=", result["passed"], "runs=", len(result["runs"]))
    raise SystemExit(0 if result["passed"] else 1)
