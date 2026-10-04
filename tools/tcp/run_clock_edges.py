"""Run observed clock boundaries; process completion alone is not acceptance."""

import argparse
import json
import platform
import shlex
import shutil
import subprocess
from pathlib import Path

from run_transfer import command

from psf_lab.clock_edges import validate_edges
from psf_lab.parser.semantic import parse_trace
from psf_lab.runner import QEMU_FLAGS, digest, write_json

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--qemu", type=Path, required=True)
    parser.add_argument("--repeats", type=int, choices=(1, 3), default=3)
    parser.add_argument("--relative", action="store_true")
    args = parser.parse_args()
    dest, qemu = args.output.resolve(), args.qemu.resolve()
    dest.mkdir(parents=True, exist_ok=False)
    toolchain = ROOT / ".tools/xpack-riscv-none-elf-gcc-15.2.0-1/bin"
    build = dest / "build"
    build_cmd = [
        "make",
        "-j4",
        "-C",
        str(ROOT / "firmware"),
        "CASE=clock_edges",
        "OUT=" + str(build),
        "TOOLCHAIN=" + str(toolchain),
    ]
    command(build_cmd, ROOT, dest / "build.log")
    plugin = dest / ("clock_edges.dylib" if platform.system() == "Darwin" else "clock_edges.so")
    flags = (
        ["-dynamiclib", "-undefined", "dynamic_lookup"]
        if platform.system() == "Darwin"
        else ["-shared", "-fPIC"]
    )
    plugin_cmd = [
        "cc",
        *flags,
        "-O2",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-I" + str(ROOT / "references/qemu-time-control/include/qemu"),
        str(ROOT / "tools/tcp/clock_edges.c"),
        "-o",
        str(plugin),
        *shlex.split(subprocess.check_output(["pkg-config", "--cflags", "glib-2.0"], text=True)),
    ]
    if args.relative:
        plugin_cmd.append("-DPOC_RELATIVE")
    command(plugin_cmd, ROOT, dest / "plugin-build.log")
    elf = build / "firmware.elf"
    symbols = subprocess.check_output(
        [str(toolchain / "riscv-none-elf-nm"), "-S", str(elf)], text=True
    )
    trigger = next(
        int(p[0], 16)
        for line in symbols.splitlines()
        if len(p := line.split()) == 4 and p[3] == "clock_edge_request"
    )
    dependencies = {
        ROOT / name
        for name in (
            "firmware/Makefile",
            "tools/tcp/clock_edges.c",
            "tools/tcp/run_clock_edges.py",
            "tools/tcp/run_transfer.py",
            "src/psf_lab/clock_edges.py",
            "tools/qemu/poc-clock-api.h",
            "src/psf_lab/runner.py",
            "references/qemu-time-control/include/qemu/qemu-plugin.h",
            "third_party/FreeRTOS/FreeRTOS/Demo/RISC-V_RV32_QEMU_VIRT_GCC/build/gcc/fake_rom.ld",
        )
    }
    for dep in build.glob("*.d"):
        for token in shlex.split(dep.read_text().replace("\\\n", " ").split(":", 1)[1]):
            path = (ROOT / "firmware" / token).resolve()
            if not token.endswith(":") and path.is_file():
                dependencies.add(path)
    manifest = dict(
        clock_mode="relative_async_cost" if args.relative else "guest_anchor_absolute",
        build_command=build_cmd,
        plugin_command=plugin_cmd,
        qemu_sha256=digest(qemu),
        plugin_sha256=digest(plugin),
        gcc_sha256=digest(toolchain / "riscv-none-elf-gcc"),
        sources={str(p.relative_to(ROOT)): digest(p) for p in dependencies},
        runs=[],
    )
    results = []
    for enabled in (False, True):
        for repeat in range(1, args.repeats + 1):
            run = dest / f"enabled-{int(enabled)}-{repeat}"
            run.mkdir()
            shutil.copy2(elf, run / "firmware.elf")
            (run / "symbols.txt").write_text(symbols)
            cmd = [
                str(qemu),
                *QEMU_FLAGS,
                "-plugin",
                f"{plugin},trigger={trigger:x},enabled={int(enabled)},out={run}/plugin.json",
                "-kernel",
                str(run / "firmware.elf"),
            ]
            result = dict(run=run.name, enabled=enabled, repeat=repeat, accepted=False)
            with (run / "qemu.log").open("wb") as log:
                try:
                    proc = subprocess.run(
                        cmd, cwd=run, stdout=log, stderr=subprocess.STDOUT, timeout=5
                    )
                    result.update(
                        exit_code=proc.returncode,
                        status="completed" if proc.returncode == 0 else "failed",
                    )
                except subprocess.TimeoutExpired:
                    result.update(exit_code=None, status="timeout")
            if result["status"] == "completed":
                try:
                    m = json.loads((run / "clock-edges.json").read_text())
                    r = json.loads((run / "plugin.json").read_text())
                    o = json.loads((run / "oracle.json").read_text())
                    if (
                        m["case"] != "clock_edges"
                        or o["case_id"] != "clock_edges"
                        or not o["complete"]
                    ):
                        raise ValueError("Incomplete guest")
                    trace = parse_trace((run / "trace.psf").read_bytes())
                    marks = [
                        (e["fields"].get("phase"), e["fields"].get("request_id"))
                        for e in trace["events"]
                        if e["fields"].get("phase")
                    ]
                    expected = [
                        (name, i)
                        for i in range(4)
                        for name in ("CLOCK_EDGE_BEGIN", "CLOCK_EDGE_END")
                    ]
                    expected += [
                        ("CLOCK_WFI_BEGIN", 0),
                        ("CLOCK_WFI_END", 0),
                        ("CLOCK_EDGE_BEGIN", 4),
                        ("CLOCK_EDGE_END", 4),
                    ]
                    expected.append(("COMPLETE", 0))
                    if marks != expected:
                        raise ValueError("PSF boundaries missing or out of order")
                    for phase in m["phases"]:
                        ends = {
                            e["fields"]["phase"]: e["timestamp_raw"]
                            for e in trace["events"]
                            if e["fields"].get("request_id") == phase["id"]
                            and e["fields"].get("phase") in ("CLOCK_EDGE_BEGIN", "CLOCK_EDGE_END")
                        }
                        if not (
                            ends["CLOCK_EDGE_BEGIN"]
                            <= phase["before_mtime"]
                            <= phase["after_mtime"]
                            <= ends["CLOCK_EDGE_END"]
                        ):
                            raise ValueError("PSF and guest mtime boundaries disagree")
                    result["acceptance"] = validate_edges(m, r, enabled)
                    result["accepted"] = True
                except (ValueError, KeyError, OSError) as error:
                    result["acceptance_error"] = str(error)
            write_json(
                run / "manifest.json",
                dict(command=cmd, result=result, files={p.name: digest(p) for p in run.iterdir()}),
            )
            manifest["runs"].append(dict(name=run.name, sha256=digest(run / "manifest.json")))
            results.append(result)
            print(f"{run.name}: {result}", flush=True)
    write_json(
        dest / "results.json",
        dict(
            accepted=all(r["accepted"] for r in results),
            cases=results,
            boundary="Clock API, not cache stalls",
        ),
    )
    manifest["results_sha256"] = digest(dest / "results.json")
    write_json(dest / "manifest.json", manifest)


if __name__ == "__main__":
    main()
