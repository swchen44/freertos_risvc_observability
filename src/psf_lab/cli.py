"""Command-line entry points for PSF Lab."""

import argparse
import json
import sys
from pathlib import Path

from psf_lab.analysis import analyze
from psf_lab.doctor import inspect_tools
from psf_lab.parser.errors import ParseError
from psf_lab.parser.semantic import parse_trace
from psf_lab.runner import check_run, run_case, run_suite


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="psf-lab")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="Check the RISC-V build and simulation tools")
    decoder = commands.add_parser("decode", help="Decode selected PSF v14 schemas")
    decoder.add_argument("input", type=Path)
    decoder.add_argument("--output", type=Path, required=True)
    decoder.add_argument("--partial", action="store_true")
    runner = commands.add_parser("run", help="Build and capture a pinned QEMU case")
    runner.add_argument("case_id")
    checker = commands.add_parser("check", help="Recheck independent run evidence")
    checker.add_argument("directory", type=Path)
    analyzer = commands.add_parser("analyze", help="Derive scheduling intervals and requests")
    analyzer.add_argument("input", type=Path)
    analyzer.add_argument("--output", type=Path, required=True)
    suite = commands.add_parser("suite", help="Run seven cases and three comparisons")
    suite.add_argument("--repeat", type=int, default=3)
    server = commands.add_parser("serve", help="Start loopback-only local dashboard")
    server.add_argument("--host", choices=["127.0.0.1", "localhost", "::1"], default="127.0.0.1")
    server.add_argument("--port", type=int, default=8000)
    server.add_argument("--store", type=Path, default=Path("artifacts/local/store"))
    bench = commands.add_parser("benchmark", help="Measure synthetic parser capacity")
    bench.add_argument("--events", type=int, nargs="+", default=[1000, 10000, 100000])
    bench.add_argument("--output", type=Path, default=Path("artifacts/benchmarks"))
    commands.add_parser("verify-docs", help="Check local documentation and baseline hashes")
    args = parser.parse_args(argv)
    if args.command in {"benchmark", "verify-docs"}:
        from psf_lab.benchmark import benchmark
        from psf_lab.docs_validation import verify_docs

        try:
            result = (
                benchmark(args.events, args.output)
                if args.command == "benchmark"
                else verify_docs(Path.cwd())
            )
            print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
            return 0 if result.get("ok", True) else 1
        except (OSError, ValueError, RuntimeError) as error:
            print(str(error), file=sys.stderr)
            return 2
    if args.command == "serve":
        import uvicorn

        from psf_lab.server import create_app

        uvicorn.run(create_app(args.store), host=args.host, port=args.port)
        return 0
    if args.command == "suite":
        try:
            directory = run_suite(Path.cwd(), repeat=args.repeat)
            print(directory)
            return (
                0 if json.loads((directory / "index.json").read_text())["verdict"] == "pass" else 1
            )
        except (OSError, ValueError, RuntimeError) as error:
            print(str(error), file=sys.stderr)
            return 2
    if args.command == "analyze":
        try:
            if args.input.resolve() == args.output.resolve():
                raise ValueError("Analysis must not overwrite the input")
            result = analyze(json.loads(args.input.read_text()))
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
            return 0
        except (OSError, ValueError, KeyError, TypeError) as error:
            print(str(error), file=sys.stderr)
            return 2
    if args.command in {"run", "check"}:
        try:
            if args.command == "run":
                run = run_case(Path.cwd(), args.case_id)
                print(run)
                return json.loads((run / "manifest.json").read_text())["exit_code"]
            result = check_run(args.directory)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return {"pass": 0, "fail": 1, "capture_failed": 4}.get(result["verdict"], 3)
        except (OSError, ValueError, RuntimeError) as error:
            print(str(error), file=sys.stderr)
            return 2
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
