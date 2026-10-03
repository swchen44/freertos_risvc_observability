"""Bounded QEMU execution with immutable raw evidence and pinned inputs."""

import hashlib
import json
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from psf_lab.harness import check_case
from psf_lab.parser.semantic import parse_trace
from psf_lab.provenance import require_clean_tree

CASE_IDS = (
    "queue_baseline",
    "clock_probe",
    "logger_bad",
    "logger_fixed",
    "inversion_semaphore",
    "inversion_mutex",
    "deadlock_abba",
    "deadlock_ordered",
)
QEMU_FLAGS = [
    "-machine",
    "virt",
    "-cpu",
    "rv32",
    "-smp",
    "1",
    "-m",
    "128M",
    "-bios",
    "none",
    "-display",
    "none",
    "-monitor",
    "none",
    "-serial",
    "file:console.log",
    "-accel",
    "tcg,thread=single",
    "-icount",
    "shift=0,align=off,sleep=off",
    "-semihosting-config",
    "enable=on,target=native",
]


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def digest(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def validate_case_id(case_id):
    if case_id not in CASE_IDS:
        raise ValueError("Case must be a supported case ID")


def allocate_run(parent: Path, case_id: str) -> Path:
    validate_case_id(case_id)
    parent.mkdir(parents=True, exist_ok=True)
    run = parent / (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + "-"
        + case_id
        + "-"
        + uuid.uuid4().hex[:10]
    )
    run.mkdir(exist_ok=False)
    return run


def source_snapshot(root):
    names = subprocess.check_output(["git", "ls-files", "-z"], cwd=root).decode().split("\0")
    return {
        n: digest(root / n)
        for n in names
        if n and (root / n).is_file() and not n.startswith(("runs/", "artifacts/"))
    }


def verify_environment(root):
    lock = json.loads((root / "tools/toolchain-lock.json").read_text())
    for name, item in lock["tools"].items():
        p = Path(item["path"])
        if not p.is_file() or digest(p) != item["sha256"]:
            raise RuntimeError("Pinned tool changed or missing: " + name)
    archive = root / ".tools/xpack.tar.gz"
    if digest(archive) != lock["gcc_archive"]["sha256"]:
        raise RuntimeError("Compiler archive changed")
    for relative, expected in [
        ("third_party/FreeRTOS", lock["freertos_commit"]),
        ("third_party/FreeRTOS/FreeRTOS/Source", lock["kernel_commit"]),
    ]:
        p = root / relative
        actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=p, text=True).strip()
        if actual != expected:
            raise RuntimeError("Pinned upstream commit changed: " + relative)
        status = subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=all"], cwd=p, text=True
        )
        if status:
            raise RuntimeError("Upstream has uncommitted changes: " + relative)
    return lock


def run_guest(run: Path, command: list, *, timeout_s: float, manifest: dict) -> dict:
    (run / "console.log").touch()
    manifest.update(command=command, started_at=datetime.now(timezone.utc).isoformat())
    try:
        p = subprocess.run(command, cwd=run, capture_output=True, timeout=timeout_s)
        (run / "qemu.stderr").write_bytes(p.stderr)
        manifest.update(
            guest_exit_code=p.returncode,
            exit_code=0 if p.returncode == 0 else 4,
            status="captured" if p.returncode == 0 else "crash",
        )
    except subprocess.TimeoutExpired as error:
        (run / "qemu.stderr").write_bytes(error.stderr or b"")
        manifest.update(guest_exit_code=None, exit_code=4, status="timeout")
    except OSError as error:
        (run / "qemu.stderr").write_text(str(error))
        manifest.update(guest_exit_code=None, exit_code=4, status="launch_failed")
    manifest["ended_at"] = datetime.now(timezone.utc).isoformat()
    write_json(run / "manifest.json", manifest)
    return manifest


def check_run(run: Path) -> dict:
    manifest = json.loads((run / "manifest.json").read_text())
    if manifest["exit_code"] == 4:
        return dict(
            case_id=manifest["case_id"],
            verdict="capture_failed",
            assertions=[],
            issues=[manifest["status"]],
        )
    for name in ["trace.psf", "oracle.json", "case.json"]:
        if digest(run / name) != manifest["files"][name]["sha256"]:
            raise ValueError("Run evidence hash mismatch: " + name)
    trace = parse_trace((run / "trace.psf").read_bytes(), source_name="trace.psf")
    return check_case(
        json.loads((run / "case.json").read_text()),
        trace,
        json.loads((run / "oracle.json").read_text()),
    )


def run_case(
    root: Path, case_id: str, *, timeout_s: float = 30.0, output_root: Path | None = None
) -> Path:
    root = root.resolve()
    validate_case_id(case_id)
    commit = require_clean_tree(root)
    lock = verify_environment(root)
    before = source_snapshot(root)
    case = json.loads((root / "cases" / f"{case_id}.json").read_text())
    run = allocate_run(output_root or root / "runs", case_id)
    write_json(run / "case.json", case)
    manifest = dict(
        run_id=run.name,
        case_id=case_id,
        source_commit=commit,
        source_dirty=False,
        source_hashes=before,
        tools=lock["tools"],
        time_model="qemu-icount",
        mtime_hz=lock["timebase_hz"],
        files={},
    )
    command = ["make", "-B", "-C", "firmware", f"CASE={case_id}"]
    manifest["build_command"] = command
    try:
        p = subprocess.run(command, cwd=root, capture_output=True, timeout=120)
        (run / "build.log").write_bytes(p.stdout + p.stderr)
        if p.returncode:
            raise RuntimeError("firmware build failed")
        if source_snapshot(root) != before:
            raise RuntimeError("Sources changed during build")
        for name in ["firmware.elf", "firmware.map", "tasks.i", "queue.i"]:
            shutil.copyfile(root / "build" / case_id / name, run / name)
        command = [
            lock["tools"]["qemu-system-riscv32"]["path"],
            *QEMU_FLAGS,
            "-kernel",
            str(run / "firmware.elf"),
        ]
        run_guest(run, command, timeout_s=timeout_s, manifest=manifest)
        if source_snapshot(root) != before:
            raise RuntimeError("Sources changed during capture")
        verify_environment(root)
        if manifest["exit_code"] == 0:
            trace = parse_trace((run / "trace.psf").read_bytes(), source_name="trace.psf")
            oracle = json.loads((run / "oracle.json").read_text())
            result = check_case(case, trace, oracle)
            trace["clock"]["time_model"] = "qemu-icount"
            trace["quality"]["capture_complete"] = result["verdict"] == "pass"
            write_json(run / "trace.json", trace)
            write_json(run / "assertions.json", result)
            manifest.update(
                exit_code=0 if result["verdict"] == "pass" else 1,
                status=result["verdict"],
                quality=trace["quality"],
                event_count=len(trace["events"]),
            )
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        manifest.update(exit_code=4, status="capture_failed", error=str(error))
    for name in [
        "case.json",
        "trace.psf",
        "oracle.json",
        "firmware.elf",
        "firmware.map",
        "tasks.i",
        "queue.i",
        "trace.json",
        "assertions.json",
    ]:
        p = run / name
        manifest["files"][name] = (
            {"sha256": digest(p), "bytes": p.stat().st_size} if p.is_file() else {"missing": True}
        )
    write_json(run / "manifest.json", manifest)
    return run
