"""Command-line entry points for PSF Lab."""

import argparse
import json

from psf_lab.doctor import inspect_tools


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="psf-lab")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="Check the RISC-V build and simulation tools")
    parser.parse_args(argv)
    result = inspect_tools(("qemu-system-riscv32", "riscv-none-elf-gcc", "dtc"))
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 2
