"""Capture real lwIP TCP send/copy/checksum and lost-ACK recovery on RV32."""

import argparse
import gzip
import json
import platform
import shlex
import shutil
import subprocess
from pathlib import Path

from run_checksum import sha

from psf_lab.runner import QEMU_FLAGS
from psf_lab.tcp_report import analyze_run

ROOT = Path(__file__).resolve().parents[2]
VARIANTS = ("tcp_copy2", "tcp_copy3", "tcp_nocopy3")


def command(args, cwd, log):
    with log.open("wb") as stream:
        run = subprocess.run(args, cwd=cwd, stdout=stream, stderr=subprocess.STDOUT, timeout=600)
    run.check_returncode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--qemu", default=shutil.which("qemu-system-riscv32"))
    parser.add_argument(
        "--toolchain", type=Path, default=ROOT / ".tools/xpack-riscv-none-elf-gcc-15.2.0-1/bin"
    )
    args = parser.parse_args()
    dest = args.output.resolve()
    dest.mkdir(parents=True, exist_ok=False)
    toolchain = args.toolchain.resolve()
    source = json.loads((ROOT / "references/tcp/lwip/SOURCE.json").read_text())
    for name, expected in source["files"].items():
        if sha(ROOT / "references/tcp/lwip" / name) != expected:
            raise ValueError("Changed lwIP source: " + name)
    plugin = dest / ("trace.dylib" if platform.system() == "Darwin" else "trace.so")
    link = (
        ["-dynamiclib", "-undefined", "dynamic_lookup"]
        if platform.system() == "Darwin"
        else ["-shared", "-fPIC"]
    )
    plugin_command = [
        "cc",
        *link,
        "-O2",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-I" + str(ROOT / "third_party/qemu-cache"),
        str(ROOT / "tools/tcp/trace.c"),
        "-o",
        str(plugin),
        *shlex.split(subprocess.check_output(["pkg-config", "--cflags", "glib-2.0"], text=True)),
    ]
    command(plugin_command, ROOT, dest / "plugin-build.log")
    manifest = {
        "schema": "tcp-transfer-capture-v1",
        "upstream": source,
        "plugin_build": plugin_command,
        "plugin_sha256": sha(plugin),
        "sources": {},
        "builds": [],
        "tools": {},
        "runs": [],
    }
    for name, path in [("qemu", Path(args.qemu)), ("gcc", toolchain / "riscv-none-elf-gcc")]:
        manifest["tools"][name] = {
            "sha256": sha(path),
            "version": subprocess.check_output([str(path), "--version"], text=True).splitlines()[0],
        }
    for base in ("firmware", "src/psf_lab", "third_party/qemu-cache"):
        for path in (ROOT / base).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                manifest["sources"][str(path.relative_to(ROOT))] = sha(path)
    for name in ("tools/tcp/run_transfer.py", "tools/tcp/run_checksum.py", "tools/tcp/trace.c"):
        manifest["sources"][name] = sha(ROOT / name)
    rows = []
    for variant in VARIANTS:
        build = dest / ".build" / variant
        build_command = [
            "make",
            "-j4",
            "-C",
            str(ROOT / "firmware"),
            "CASE=" + variant,
            "OUT=" + str(build),
            "TOOLCHAIN=" + str(toolchain),
        ]
        command(build_command, ROOT, dest / (variant + "-build.log"))
        dependencies = {
            ROOT
            / "third_party/FreeRTOS/FreeRTOS/Demo/RISC-V_RV32_QEMU_VIRT_GCC/build/gcc/fake_rom.ld"
        }
        for dep in build.glob("*.d"):
            for token in shlex.split(dep.read_text().replace("\\\n", " ").split(":", 1)[1]):
                path = (ROOT / "firmware" / token).resolve()
                if not token.endswith(":") and path.is_file():
                    dependencies.add(path)
        manifest["builds"].append(
            {
                "case": variant,
                "command": build_command,
                "dependencies": {
                    str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p): sha(p)
                    for p in dependencies
                },
            }
        )
        elf = build / "firmware.elf"
        symbols = subprocess.check_output(
            [str(toolchain / "riscv-none-elf-nm"), "-S", str(elf)], text=True
        )
        addresses = {
            fields[3]: int(fields[0], 16)
            for line in symbols.splitlines()
            if len(fields := line.split()) == 4
        }
        sizes = subprocess.check_output(
            [str(toolchain / "riscv-none-elf-size"), str(elf)], text=True
        )
        text_size = int(sizes.splitlines()[1].split()[0])
        for repeat in (1, 2, 3):
            run = dest / f"{variant}-{repeat}"
            run.mkdir()
            shutil.copy2(elf, run / "firmware.elf")
            shutil.copy2(build / "firmware.map", run / "firmware.map")
            (run / "symbols.txt").write_text(symbols)
            (run / "size.txt").write_text(sizes)
            trace = run / "accesses.csv"
            parameters = (
                f"{plugin},begin={addresses['tcp_capture_begin']:x},"
                f"end={addresses['tcp_capture_end']:x},out={trace}"
            )
            cmd = [
                args.qemu,
                *QEMU_FLAGS,
                "-plugin",
                parameters,
                "-kernel",
                str(run / "firmware.elf"),
            ]
            command(cmd, run, run / "qemu.log")
            with trace.open("rb") as raw, gzip.open(run / "accesses.csv.gz", "wb") as compressed:
                shutil.copyfileobj(raw, compressed)
            trace.unlink()
            evidence = {
                "variant": variant,
                "repeat": repeat,
                "text_bytes": text_size,
                "command": cmd,
                "files": {p.name: sha(p) for p in run.iterdir()},
            }
            (run / "manifest.json").write_text(json.dumps(evidence, indent=2) + "\n")
            result = analyze_run(run)
            rows.extend(result)
            manifest["runs"].append(
                {"name": run.name, "manifest_sha256": sha(run / "manifest.json")}
            )
    for variant in VARIANTS:
        for kind in ("send", "retransmit"):
            values = [r for r in rows if r["variant"] == variant and r["kind"] == kind]
            for key in ("instructions", "l1i_misses", "l1d_misses", "l2_misses", "reads", "writes"):
                if len({r[key] for r in values}) != 1:
                    raise ValueError("Non-repeatable " + key)
    (dest / "results.json").write_text(
        json.dumps({"schema": "tcp-dashboard-v1", "rows": rows}, indent=2) + "\n"
    )
    manifest["results_sha256"] = sha(dest / "results.json")
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    shutil.rmtree(dest / ".build")
    print(f"PASS: 9 TCP sessions, 45 captured phases, {len(rows)} summary rows")


if __name__ == "__main__":
    main()
