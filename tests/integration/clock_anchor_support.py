"""Explicit opt-in runtime probes with pinned inputs and retained partial runs."""

import json
import os
import signal
import subprocess
import uuid
from pathlib import Path

from psf_lab.provenance import require_clean_tree
from psf_lab.runner import QEMU_FLAGS, digest, write_json

LEGACY_SHA = "69969c3ec8cce8f9340215fc340c5c01f81c3ef978252d3766937d2d176816db"


def guest_probe_config(root: Path, qemu: Path, output: Path) -> Path:
    root, qemu, output = root.resolve(), qemu.resolve(), output.resolve()
    commit = require_clean_tree(root)
    if digest(qemu) != LEGACY_SHA:
        raise ValueError("Legacy QEMU identity mismatch")
    output.mkdir(parents=True, exist_ok=False)
    build = output / "build"
    toolchain = root / ".tools/xpack-riscv-none-elf-gcc-15.2.0-1/bin"
    cmd = [
        "make",
        "-j2",
        "-C",
        str(root / "firmware"),
        "CASE=clock_anchor_probe",
        "CLOCK_ANCHORS=1",
        "OUT=" + str(build),
        "TOOLCHAIN=" + str(toolchain),
    ]
    with (output / "build.log").open("wb") as log:
        p = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, timeout=300)
    write_json(output / "build-command.json", dict(command=cmd, exit=p.returncode))
    if p.returncode:
        raise RuntimeError("Guest probe build failed; retained build.log")
    elf = build / "firmware.elf"
    for tool, flags, name in (
        ("objdump", ["-d"], "disassembly.txt"),
        ("nm", ["-S"], "symbols.txt"),
        ("size", ["-A"], "size.txt"),
    ):
        command = [str(toolchain / f"riscv-none-elf-{tool}"), *flags, str(elf)]
        with (output / name).open("wb") as log:
            subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=30, check=True)
    config = dict(
        schema="c2b-runtime-config-v1",
        source_commit=commit,
        root=str(root),
        legacy_qemu=dict(path=str(qemu), sha256=digest(qemu)),
        probe_elf=dict(path=str(elf), sha256=digest(elf)),
        output_parent=str(output / "tests"),
        clock_qemu=None,
        plugins=None,
        candidates=None,
    )
    path = output / "runtime-tests.json"
    write_json(path, config)
    return path


def load_runtime_config() -> dict:
    path = os.environ.get("C2B_RUNTIME_CONFIG")
    if not path:
        raise AssertionError("C2B_REQUIRE_QEMU=1 requires C2B_RUNTIME_CONFIG")
    config = json.loads(Path(path).read_text())
    if config["schema"] != "c2b-runtime-config-v1":
        raise AssertionError("Invalid C2b runtime config")
    require_clean_tree(Path(config["root"]))
    if config["legacy_qemu"]["sha256"] != LEGACY_SHA:
        raise AssertionError("Unpinned legacy QEMU")
    for name in ("legacy_qemu", "probe_elf"):
        if digest(Path(config[name]["path"])) != config[name]["sha256"]:
            raise AssertionError(f"Changed runtime input: {name}")
    return config


def capture_probe(config: dict, arg: str | None, label: str) -> dict:
    out = Path(config["output_parent"]) / f"{label}-{uuid.uuid4().hex}"
    out.mkdir(parents=True, exist_ok=False)
    for name in ("legacy_qemu", "probe_elf"):
        if digest(Path(config[name]["path"])) != config[name]["sha256"]:
            raise AssertionError(f"Changed runtime input: {name}")
    flags = QEMU_FLAGS.copy()
    i = flags.index("-semihosting-config") + 1
    flags[i] = "enable=on,target=native" + (",arg=" + arg if arg is not None else "")
    cmd = [config["legacy_qemu"]["path"], *flags, "-kernel", config["probe_elf"]["path"]]
    timed_out = False
    with (out / "qemu.log").open("wb") as log:
        p = subprocess.Popen(
            cmd, cwd=out, stdout=log, stderr=subprocess.STDOUT, start_new_session=True
        )
        try:
            p.wait(timeout=120)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(p.pid, signal.SIGTERM)
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid, signal.SIGKILL)
                p.wait(timeout=5)
    receipt = dict(
        command=cmd,
        exit=p.returncode,
        timed_out=timed_out,
        elf_sha256=config["probe_elf"]["sha256"],
        files={p.name: digest(p) for p in out.iterdir() if p.is_file()},
    )
    write_json(out / "capture.json", receipt)
    return dict(output=out, **receipt)
