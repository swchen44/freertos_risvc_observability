#!/usr/bin/env python3
"""Build and capture real lwIP checksum variants on FreeRTOS/RV32 QEMU."""

import argparse
import hashlib
import json
import shlex
import shutil
import subprocess
from pathlib import Path

from psf_lab.parser.semantic import parse_trace
from psf_lab.runner import QEMU_FLAGS
from psf_lab.tcp_checksum import internet_checksum

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--qemu", default=shutil.which("qemu-system-riscv32"))
    parser.add_argument(
        "--toolchain", type=Path, default=ROOT / ".tools/xpack-riscv-none-elf-gcc-15.2.0-1/bin"
    )
    parser.add_argument("--checksum-opt", choices=("Os", "O2"), default="Os")
    args = parser.parse_args()
    args.qemu = str(Path(args.qemu).resolve())
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    provenance = json.loads((ROOT / "references/tcp/lwip/SOURCE.json").read_text())
    for name, expected in provenance["files"].items():
        if sha(ROOT / "references/tcp/lwip" / name) != expected:
            raise ValueError("Upstream checksum source changed: " + name)
    manifest = {
        "scope": "checksum component only; no TCP connection or modeled caches",
        "checksum_opt": args.checksum_opt,
        "cache_target": {
            "l1i_bytes": 16384,
            "l1d_bytes": 16384,
            "l2_bytes": 65536,
            "simulated_in_this_run": False,
        },
        "upstream": provenance,
        "source_files": {
            str(p.relative_to(ROOT)): sha(p)
            for pattern in (
                "firmware/**/*",
                "src/psf_lab/tcp_checksum.py",
                "tools/tcp/*.py",
                "tests/unit/test_tcp_checksum.py",
            )
            for p in ROOT.glob(pattern)
            if p.is_file()
        },
        "tools": {},
        "builds": [],
        "dependency_files": {},
        "runs": [],
    }
    for name, path in [("qemu", Path(args.qemu)), ("gcc", args.toolchain / "riscv-none-elf-gcc")]:
        manifest["tools"][name] = {
            "sha256": sha(path),
            "version": subprocess.check_output([str(path), "--version"], text=True).splitlines()[0],
        }
    manifest["revisions"] = {}
    for name in (".", "third_party/FreeRTOS", "third_party/FreeRTOS/FreeRTOS/Source"):
        path = ROOT / name
        if (path / ".git").exists():
            manifest["revisions"][name] = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=path, text=True
            ).strip()
    rows = []
    for algorithm in (1, 2, 3):
        case = f"tcp_checksum{algorithm}"
        build_dir = output / ".build" / case
        command = [
            "make",
            "-C",
            str(ROOT / "firmware"),
            "CASE=" + case,
            "CHECKSUM_OPT=" + args.checksum_opt,
            "OUT=" + str(build_dir),
            "TOOLCHAIN=" + str(args.toolchain.resolve()),
        ]
        build = subprocess.run(command, capture_output=True, text=True)
        (output / f"{case}-build.log").write_text(build.stdout + build.stderr)
        build.check_returncode()
        manifest["builds"].append({"case": case, "command": command})
        dependencies = {
            ROOT / "third_party/FreeRTOS/FreeRTOS/Demo/"
            "RISC-V_RV32_QEMU_VIRT_GCC/build/gcc/fake_rom.ld"
        }
        for dep in build_dir.glob("*.d"):
            text = dep.read_text().replace("\\\n", " ")
            for token in shlex.split(text.split(":", 1)[1]):
                if token.endswith(":"):
                    continue
                path = (ROOT / "firmware" / token).resolve()
                if path.is_file():
                    dependencies.add(path)
        for path in dependencies:
            name = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
            manifest["dependency_files"][name] = sha(path)
        elf = build_dir / "firmware.elf"
        symbols = subprocess.check_output(
            [str(args.toolchain / "riscv-none-elf-nm"), "-S", str(elf)], text=True
        )
        code_size = int(
            next(s.split()[1] for s in symbols.splitlines() if s.endswith(" lwip_standard_chksum")),
            16,
        )
        for repeat in (1, 2, 3):
            run = output / f"{case}-{repeat}"
            run.mkdir()
            shutil.copy2(elf, run / "firmware.elf")
            shutil.copy2(elf.with_suffix(".map"), run / "firmware.map")
            (run / "symbols.txt").write_text(symbols)
            disassembly = subprocess.check_output(
                [
                    str(args.toolchain / "riscv-none-elf-objdump"),
                    "-d",
                    "--disassemble=lwip_standard_chksum",
                    str(elf),
                ],
                text=True,
            )
            (run / "checksum.asm").write_text(disassembly)
            command = [args.qemu, *QEMU_FLAGS, "-kernel", str(run / "firmware.elf")]
            result = subprocess.run(command, cwd=run, capture_output=True, timeout=30)
            (run / "qemu.stderr").write_bytes(result.stderr)
            result.check_returncode()
            metrics = json.loads((run / "tcp.json").read_text())
            oracle = json.loads((run / "oracle.json").read_text())
            trace = parse_trace((run / "trace.psf").read_bytes())
            if not oracle["complete"] or oracle["case_id"] != case:
                raise ValueError("Guest did not complete expected case")
            phases = [
                (e["fields"].get("phase"), e["fields"].get("request_id")) for e in trace["events"]
            ]
            if len(metrics["measurements"]) != 12 or metrics["algorithm"] != algorithm:
                raise ValueError("Incomplete measurements")
            expected_checksums = []
            for index, row in enumerate(metrics["measurements"]):
                size, offset = row["length"], row["offset"]
                if (size, offset) != ((20, 64, 511, 1460, 1461, 8192)[index // 2], index % 2):
                    raise ValueError("Unexpected workload")
                data = bytes((i * 17 + 31) % 256 for i in range(offset, offset + size))
                expected = internet_checksum(data)
                if row["checksum"] != expected or row["instructions"] <= 0:
                    raise ValueError("Checksum / instruction counter failed")
                if any(
                    phases.count((phase, index)) != 1
                    for phase in ("CHECKSUM_BEGIN", "CHECKSUM_END")
                ):
                    raise ValueError("Missing or duplicate PSF phase")
                expected_checksums.append(expected)
                rows.append(
                    dict(
                        row,
                        algorithm=algorithm,
                        repeat=repeat,
                        repetitions=32,
                        checksum_function_bytes=code_size,
                        run=run.name,
                    )
                )
            if (
                oracle["sent_ids"] != expected_checksums
                or oracle["received_ids"] != expected_checksums
            ):
                raise ValueError("Oracle disagrees with Python")
            manifest["runs"].append(
                {
                    "directory": run.name,
                    "command": command,
                    "files": {p.name: sha(p) for p in run.iterdir()},
                }
            )
    for algorithm in (1, 2, 3):
        for size in (20, 64, 511, 1460, 1461, 8192):
            for offset in (0, 1):
                values = [
                    r["instructions"]
                    for r in rows
                    if (r["algorithm"], r["length"], r["offset"]) == (algorithm, size, offset)
                ]
                if len(set(values)) != 1:
                    raise ValueError("QEMU instruction counts did not reproduce")
    (output / "results.json").write_text(json.dumps(rows, indent=2) + "\n")
    manifest["results_sha256"] = sha(output / "results.json")
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    shutil.rmtree(output / ".build")
    print(f"PASS: {len(rows)} measurements, 9 PSF captures; {output}")


if __name__ == "__main__":
    main()
