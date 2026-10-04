"""Record a bounded time-control feasibility matrix; timeouts are failures, not passes."""

import argparse
import json
import platform
import shlex
import shutil
import subprocess
from pathlib import Path

from run_transfer import command

from psf_lab.parser.semantic import parse_trace
from psf_lab.runner import QEMU_FLAGS, digest, write_json
from psf_lab.time_control import compare_probe

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--qemu", default=shutil.which("qemu-system-riscv32"))
    parser.add_argument(
        "--toolchain", type=Path, default=ROOT / ".tools/xpack-riscv-none-elf-gcc-15.2.0-1/bin"
    )
    args = parser.parse_args()
    dest = args.output.resolve()
    dest.mkdir(parents=True, exist_ok=False)
    toolchain = args.toolchain.resolve()
    build = dest / "build"
    cmd = [
        "make",
        "-j4",
        "-C",
        str(ROOT / "firmware"),
        "CASE=time_control_probe",
        "OUT=" + str(build),
        "TOOLCHAIN=" + str(toolchain),
    ]
    command(cmd, ROOT, dest / "build.log")
    plugin = dest / ("time_probe.dylib" if platform.system() == "Darwin" else "time_probe.so")
    link = (
        ["-dynamiclib", "-undefined", "dynamic_lookup"]
        if platform.system() == "Darwin"
        else ["-shared", "-fPIC"]
    )
    plugin_cmd = [
        "cc",
        *link,
        "-O2",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-I" + str(ROOT / "third_party/qemu-cache"),
        str(ROOT / "tools/tcp/time_probe.c"),
        "-o",
        str(plugin),
        *shlex.split(subprocess.check_output(["pkg-config", "--cflags", "glib-2.0"], text=True)),
    ]
    command(plugin_cmd, ROOT, dest / "plugin-build.log")
    elf = build / "firmware.elf"
    symbols = subprocess.check_output(
        [str(toolchain / "riscv-none-elf-nm"), "-S", str(elf)], text=True
    )
    addresses = {
        p[3]: int(p[0], 16) for line in symbols.splitlines() if len(p := line.split()) == 4
    }
    manifest = dict(
        schema="time-control-probe-v1",
        build_command=cmd,
        plugin_command=plugin_cmd,
        qemu=dict(
            sha256=digest(Path(args.qemu)),
            version=subprocess.check_output([args.qemu, "--version"], text=True).splitlines()[0],
        ),
        gcc_sha256=digest(toolchain / "riscv-none-elf-gcc"),
        sources={},
        runs=[],
    )
    dependencies = {
        ROOT / "firmware/Makefile",
        ROOT / "tools/tcp/time_probe.c",
        ROOT / "tools/tcp/run_time_probe.py",
        ROOT / "tools/tcp/run_transfer.py",
        ROOT / "src/psf_lab/time_control.py",
        ROOT / "src/psf_lab/runner.py",
        ROOT / "third_party/qemu-cache/qemu-plugin.h",
        ROOT / "third_party/FreeRTOS/FreeRTOS/Demo/RISC-V_RV32_QEMU_VIRT_GCC/build/gcc/fake_rom.ld",
    }
    for dep in build.glob("*.d"):
        for token in shlex.split(dep.read_text().replace("\\\n", " ").split(":", 1)[1]):
            path = (ROOT / "firmware" / token).resolve()
            if not token.endswith(":") and path.is_file():
                dependencies.add(path)
    manifest["sources"] = {str(p.relative_to(ROOT)): digest(p) for p in dependencies}
    results = []
    for delay in (0, 1_000_000, 5_000_000):
        for repeat in (1, 2, 3):
            run = dest / f"delay-{delay}-{repeat}"
            run.mkdir()
            shutil.copy2(elf, run / "firmware.elf")
            (run / "symbols.txt").write_text(symbols)
            cmd = [
                args.qemu,
                *QEMU_FLAGS,
                "-plugin",
                f"{plugin},trigger={addresses['time_probe_charge']:x},delay={delay},out={run}/plugin.json",
                "-kernel",
                str(run / "firmware.elf"),
            ]
            result = dict(run=run.name, delay_ns=delay, repeat=repeat, timeout_seconds=3)
            with (run / "qemu.log").open("wb") as log:
                try:
                    process = subprocess.run(
                        cmd, cwd=run, stdout=log, stderr=subprocess.STDOUT, timeout=3
                    )
                    result["exit_code"] = process.returncode
                    result["status"] = "completed" if process.returncode == 0 else "failed"
                except subprocess.TimeoutExpired:
                    result.update(exit_code=None, status="timeout")
            if result["status"] == "completed":
                measurement = json.loads((run / "time-probe.json").read_text())
                oracle = json.loads((run / "oracle.json").read_text())
                if (
                    measurement["case"] != "time_control_probe"
                    or measurement["work"] != 523776
                    or measurement["mtime_hz"] != 10000000
                    or measurement["tick_hz"] != 1000
                    or not oracle["complete"]
                    or oracle["case_id"] != "time_control_probe"
                ):
                    raise ValueError("Incomplete guest oracle")
                trace = parse_trace((run / "trace.psf").read_bytes())
                markers = [
                    (e["fields"].get("phase"), e["fields"].get("request_id"))
                    for e in trace["events"]
                ]
                for marker in ("TIME_PROBE_BEGIN", "TIME_PROBE_END"):
                    if markers.count((marker, 0)) != 1:
                        raise ValueError("Missing PSF probe boundary")
                receipt = json.loads((run / "plugin.json").read_text())
                if receipt["fired"] != 1 or receipt["delay_ns"] != delay:
                    raise ValueError("Invalid plugin receipt")
                result["measurement"] = measurement
            write_json(
                run / "manifest.json",
                dict(command=cmd, result=result, files={p.name: digest(p) for p in run.iterdir()}),
            )
            manifest["runs"].append(
                dict(name=run.name, manifest_sha256=digest(run / "manifest.json"))
            )
            results.append(result)
            print(f"{run.name}: {result['status']}", flush=True)
    controls = [r for r in results if r["delay_ns"] == 0]
    if any(r["status"] != "completed" for r in controls):
        raise ValueError("Control did not complete")
    comparisons = []
    for r in results:
        if r["delay_ns"] and r["status"] == "completed":
            try:
                comparisons.append(
                    compare_probe(
                        controls[r["repeat"] - 1]["measurement"], r["measurement"], r["delay_ns"]
                    )
                )
            except ValueError as error:
                r["acceptance_error"] = str(error)
    supported = len(comparisons) == 6
    write_json(
        dest / "results.json",
        dict(
            probe_executed=True,
            time_control_supported=supported,
            cases=results,
            comparisons=comparisons,
            boundary="Fixed-jump API probe only; no cache model and no per-load stall",
        ),
    )
    manifest["results_sha256"] = digest(dest / "results.json")
    write_json(dest / "manifest.json", manifest)
    print(f"time_control_supported={supported}")


if __name__ == "__main__":
    main()
