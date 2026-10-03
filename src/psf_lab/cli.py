"""Command-line entry points for PSF Lab."""

import argparse
import json
import sys
from pathlib import Path

from psf_lab.doctor import inspect_tools
from psf_lab.parser.errors import ParseError
from psf_lab.parser.semantic import parse_trace


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="psf-lab")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="Check the RISC-V build and simulation tools")
    decoder = commands.add_parser("decode", help="Decode selected PSF v14 schemas")
    decoder.add_argument("input", type=Path)
    decoder.add_argument("--output", type=Path, required=True)
    decoder.add_argument("--partial", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "decode":
        try:
            if args.input.resolve() == args.output.resolve():
                raise ValueError("Output must not overwrite the input PSF")
            if args.input.stat().st_size > 16 * 1024 * 1024:
                raise ValueError("PSF exceeds 16 MiB")
            trace = parse_trace(
                args.input.read_bytes(), source_name=args.input.name, strict=not args.partial
            )
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(trace, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
            )
            return 0
        except (OSError, ParseError, ValueError) as error:
            print(str(error), file=sys.stderr)
            return 2
    result = inspect_tools(("qemu-system-riscv32", "riscv-none-elf-gcc", "dtc"))
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 2
