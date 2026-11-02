"""Explicit unittest CLI for the new QEMU ABI, preserving every runtime rejection."""

import argparse
import json
import os
import platform
import shlex
import signal
import subprocess
import unittest
from pathlib import Path

from psf_lab.parser.semantic import parse_trace
from psf_lab.provenance import require_clean_tree
from psf_lab.runner import QEMU_FLAGS, digest, write_json

ROOT = Path(__file__).resolve().parents[2]


def run_suite(manifest: Path, guest_config: Path, output: Path) -> bool:
    require_clean_tree(ROOT)
    build = json.loads(manifest.read_text())
    guest = json.loads(guest_config.read_text())
    for artifact in (
        build["binary"],
        build["header"],
        build["abi_header"],
        guest["legacy_qemu"],
        guest["probe_elf"],
    ):
        if digest(Path(artifact["path"])) != artifact["sha256"]:
            raise ValueError("ABI suite input digest mismatch")
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    plugin = output / ("abi.dylib" if platform.system() == "Darwin" else "abi.so")
    flags = (
        ["-dynamiclib", "-undefined", "dynamic_lookup"]
        if platform.system() == "Darwin"
        else ["-shared", "-fPIC"]
    )
    command = [
        "cc",
        *flags,
        "-Wall",
        "-Wextra",
        "-Werror",
        "-O2",
        "-I" + str(Path(build["header"]["path"]).parent),
        str(ROOT / "tools/qemu/clock_anchor/abi_probe.c"),
        "-o",
        str(plugin),
        *shlex.split(subprocess.check_output(["pkg-config", "--cflags", "glib-2.0"], text=True)),
    ]
    result = subprocess.run(command, capture_output=True, timeout=30)
    (output / "plugin.stdout").write_bytes(result.stdout)
    (output / "plugin.stderr").write_bytes(result.stderr)
    write_json(output / "plugin.json", dict(command=command, exit=result.returncode))
    if result.returncode:
        raise RuntimeError("ABI plugin compilation failed; see retained plugin.stderr")

    class AbiTests(unittest.TestCase):
        def test_runtime_cases(self):
            for label in (
                "normal",
                "abi",
                "size",
                "handle",
                "no-icount",
                "shift-1",
                "smp-2",
                "legacy",
                "outside-cpu",
            ):
                with self.subTest(case=label):
                    out = output / label
                    out.mkdir()
                    flags = QEMU_FLAGS.copy()
                    if label == "no-icount":
                        i = flags.index("-icount")
                        del flags[i : i + 2]
                    if label == "shift-1":
                        flags[flags.index("-icount") + 1] = "shift=1,align=off,sleep=off"
                    if label == "smp-2":
                        flags[flags.index("-smp") + 1] = "2"
                    flags[flags.index("-semihosting-config") + 1] = (
                        "enable=on,target=native,arg=c2b-markers=1"
                    )
                    fault = {
                        "abi": "abi",
                        "size": "size",
                        "handle": "handle",
                        "outside-cpu": "context",
                    }.get(label)
                    binary = (
                        guest["legacy_qemu"]["path"]
                        if label == "legacy"
                        else build["binary"]["path"]
                    )
                    cmd = [
                        binary,
                        *flags,
                        "-plugin",
                        str(plugin) + (",fault=" + fault if fault else ""),
                        "-kernel",
                        guest["probe_elf"]["path"],
                    ]
                    timeout = False
                    with (out / "qemu.log").open("wb") as log:
                        p = subprocess.Popen(
                            cmd,
                            cwd=out,
                            stdout=log,
                            stderr=subprocess.STDOUT,
                            start_new_session=True,
                        )
                        try:
                            p.wait(timeout=120)
                        except subprocess.TimeoutExpired:
                            timeout = True
                            os.killpg(p.pid, signal.SIGTERM)
                            try:
                                p.wait(timeout=5)
                            except subprocess.TimeoutExpired:
                                os.killpg(p.pid, signal.SIGKILL)
                                p.wait(timeout=5)
                    write_json(
                        out / "receipt.json",
                        dict(
                            command=cmd,
                            exit=p.returncode,
                            timeout=timeout,
                            source_commit=require_clean_tree(ROOT),
                            binary_sha256=digest(Path(binary)),
                            plugin_sha256=digest(plugin),
                            elf_sha256=guest["probe_elf"]["sha256"],
                            files={p.name: digest(p) for p in out.iterdir() if p.is_file()},
                        ),
                    )
                    self.assertFalse(timeout)
                    text = (out / "qemu.log").read_text(errors="replace")
                    if label == "normal":
                        self.assertEqual(p.returncode, 0, text)
                        self.assertIn("C2b ABI probe finished", text)
                        trace = parse_trace((out / "trace.psf").read_bytes())
                        self.assertEqual(
                            sum(e["fields"].get("channel") == "C2B" for e in trace["events"]), 5
                        )
                    else:
                        self.assertNotEqual(p.returncode, 0)
                        if label == "outside-cpu":
                            self.assertIn("unsafe-applied-context", text)
                        elif label != "legacy":
                            self.assertIn("C2b ABI configure rejected", text)
                    self.assertEqual(list(out.glob("*.jsonl")), [])

    with (output / "unittest.log").open("w") as log:
        result = unittest.TextTestRunner(stream=log, verbosity=2).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(AbiTests)
        )
    write_json(
        output / "results.json",
        dict(
            passed=result.wasSuccessful(),
            tests=result.testsRun,
            subcases=9,
            failures=len(result.failures),
            errors=len(result.errors),
            skips=len(result.skipped),
        ),
    )
    return result.wasSuccessful()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--build-manifest", required=True, type=Path)
    p.add_argument("--guest-config", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    a = p.parse_args()
    raise SystemExit(0 if run_suite(a.build_manifest, a.guest_config, a.output) else 1)
