"""Pinned same-ELF C2b builds and sequential, losslessly compressed captures."""

import gzip
import hashlib
import json
import os
import platform
import resource
import shlex
import shutil
import signal
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from psf_lab.clock_anchor_boundaries import collect_boundaries
from psf_lab.provenance import require_clean_tree
from psf_lab.runner import QEMU_FLAGS, digest, write_json
from psf_lab.tcp_workload import load_workload

LEGACY_COMMIT = "9b0152c708a1b635d56ed147f4768e124cb5c670"
LEGACY_SHA = "69969c3ec8cce8f9340215fc340c5c01f81c3ef978252d3766937d2d176816db"
PROFILE = "cases/timing/sysram-10-small.json"
REGISTRY = "cases/tcp/workload-matrix-v1.json"
QEMU_OVERLAYS = {
    "tools/qemu/clock_anchor/poc-clock-state.c": "plugins/poc-clock-state.c",
    "tools/qemu/clock_anchor/poc-clock-state.h": "plugins/poc-clock-state.h",
    "tools/qemu/poc-clock-anchor-api.h": "include/qemu/poc-clock-anchor-api.h",
}


@dataclass(frozen=True)
class RunSpec:
    candidate: str
    configuration: str
    injection: int
    repeat: int = 1

    def __post_init__(self):
        if (
            self.candidate not in ("baseline", "pbuf")
            or self.configuration not in ("L", "C", "O", "M")
            or type(self.injection) is not int
            or self.injection not in (0, 1)
            or type(self.repeat) is not int
            or self.repeat != 1
        ):
            raise ValueError("Unsupported clock pilot identity")

    @property
    def marker_mode(self):
        return 0 if self.configuration == "M" else 1

    @property
    def observer_enabled(self):
        return self.configuration in ("O", "M")

    @property
    def run_id(self):
        return f"{self.candidate}-{self.configuration}-i{self.injection}-r{self.repeat}"


def pilot_matrix() -> list[RunSpec]:
    return [
        RunSpec(candidate, config, injection)
        for candidate in ("baseline", "pbuf")
        for injection in (1, 0)
        for config in ("L", "C", "O", "M")
    ]


def _plugin_path(path: Path) -> Path:
    path = path.absolute()
    if any(c in str(path) for c in (",", "\n", "\r", "\0")):
        raise ValueError("Path cannot be represented in a QEMU plugin argument")
    return path


def allocate_output(root: Path, output: Path) -> Path:
    root = root.resolve()
    original = _plugin_path(output)
    allowed = root / "runs/local"
    if allowed.is_symlink() or original.is_symlink():
        raise ValueError("Symlink output")
    output = original.resolve()
    if not output.is_relative_to(allowed) or output == allowed:
        raise ValueError("Output must be a new directory inside runs/local")
    if subprocess.run(["git", "check-ignore", "-q", str(output)], cwd=root).returncode:
        raise ValueError("Capture output must be Git ignored")
    output.mkdir(parents=True, exist_ok=False)
    return output


def _run_qemu(command: list[str], output: Path, *, timeout: float = 120) -> dict:
    if not 0 < timeout <= 120:
        raise ValueError("Capture timeout must be at most 120 seconds")
    started = time.monotonic()
    cpu = resource.getrusage(resource.RUSAGE_CHILDREN)
    timed_out = False
    with (output / "qemu.log").open("wb") as log:
        proc = subprocess.Popen(
            command, cwd=output, stdout=log, stderr=subprocess.STDOUT, start_new_session=True
        )
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait(timeout=5)
        finally:
            # A child may survive SIGTERM even if the QEMU parent already exited.
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    return dict(
        exit_code=proc.returncode,
        timed_out=timed_out,
        host_wall_seconds=time.monotonic() - started,
        host_child_cpu_seconds=(after.ru_utime + after.ru_stime) - (cpu.ru_utime + cpu.ru_stime),
    )


def _identity(path: Path) -> dict:
    return dict(path=str(path.resolve()), sha256=digest(path), bytes=path.stat().st_size)


def _check_identity(item: dict):
    path = Path(item["path"])
    _plugin_path(path)
    if not path.is_file() or digest(path) != item["sha256"]:
        raise ValueError("Changed pinned input: " + path.name)


def _command(command, root, log, *, timeout=300):
    with log.open("wb") as f:
        p = subprocess.run(command, cwd=root, stdout=f, stderr=subprocess.STDOUT, timeout=timeout)
    write_json(log.with_suffix(".command.json"), dict(command=command, exit=p.returncode))
    if p.returncode:
        raise RuntimeError("Build/tool failed; retained " + str(log))


def _frozen(root: Path, name: str) -> bytes:
    return subprocess.check_output(["git", "show", LEGACY_COMMIT + ":" + name], cwd=root)


def _check_qemu_sources(root: Path, build: dict):
    root = root.resolve()
    source = Path(build["source"]).resolve()
    if not source.is_relative_to(root):
        raise ValueError("QEMU source outside workspace")
    for canonical, compiled in QEMU_OVERLAYS.items():
        expected = build["overlays"][compiled]
        for path in (root / canonical, source / compiled):
            if not path.is_file() or digest(path) != expected:
                raise ValueError("QEMU overlay changed: " + canonical)


def _check_smoke_files(output: Path, state: dict):
    output = output.resolve()
    for entry in state["runs"][:4]:
        run = (output / entry["path"]).resolve()
        if not run.is_relative_to(output) or run == output:
            raise ValueError("Smoke path escaped runset")
        capture = run / "capture.json"
        if digest(capture) != entry["capture_sha256"]:
            raise ValueError("Smoke capture changed")
        captured = json.loads(capture.read_text())
        if captured["capture_source_commit"] != state["source_commit"]:
            raise ValueError("Smoke source changed")
        for name, identity in captured["files"].items():
            path = (run / name).resolve()
            if (
                Path(name).name != name
                or not path.is_relative_to(run)
                or not path.is_file()
                or path.stat().st_size != identity["bytes"]
                or digest(path) != identity["sha256"]
            ):
                raise ValueError("Smoke artifact changed: " + name)


def _validate_tools(root: Path, tools: dict):
    if tools["schema"] != "clock-anchor-tools-v1":
        raise ValueError("Clock tools schema")
    if tools["legacy_qemu"]["sha256"] != LEGACY_SHA:
        raise ValueError("Legacy QEMU identity")
    for name in ("legacy_qemu", "clock_qemu", "qemu_build_manifest", "profile", "registry"):
        _check_identity(tools[name])
    for item in tools["plugins"].values():
        _check_identity(item)
    for candidate in tools["candidates"].values():
        for name in ("elf", "map", "symbols", "context_config", "boundaries_file"):
            _check_identity(candidate[name])
    for name, sha in tools["compiled_dependencies"].items():
        path = (root / name).resolve()
        if not path.is_relative_to(root) or not path.is_file() or digest(path) != sha:
            raise ValueError("Compiled dependency changed: " + name)
    build = json.loads(Path(tools["qemu_build_manifest"]["path"]).read_text())
    _check_qemu_sources(root, build)
    if build["binary"]["sha256"] != tools["clock_qemu"]["sha256"]:
        raise ValueError("New QEMU build identity")
    for name, sha in build["patches"].items():
        if digest(root / name) != sha:
            raise ValueError("QEMU patch changed")


def prepare_tools(root: Path, qemu_build: Path, legacy_qemu: Path, output: Path) -> dict:
    root = root.resolve()
    commit = require_clean_tree(root)
    if digest(legacy_qemu) != LEGACY_SHA:
        raise ValueError("Legacy QEMU hash mismatch")
    build = json.loads(qemu_build.read_text())
    if build["schema"] != "c2b-qemu-build-v1":
        raise ValueError("New QEMU manifest schema")
    _check_identity(build["binary"])
    _check_identity(build["header"])
    _check_identity(build["abi_header"])
    _check_qemu_sources(root, build)
    for name in (PROFILE, REGISTRY):
        if (root / name).read_bytes() != _frozen(root, name):
            raise ValueError("Locked profile/registry changed")
    output = allocate_output(root, output)
    toolchain = root / ".tools/xpack-riscv-none-elf-gcc-15.2.0-1/bin"
    gcc = toolchain / "riscv-none-elf-gcc"
    if "15.2.0" not in subprocess.check_output([str(gcc), "--version"], text=True, timeout=10):
        raise ValueError("RISC-V compiler version")
    api = output / "api4-new"
    api.mkdir()
    # Only the standalone API headers go on -I; full include/qemu shadows libc headers.
    shutil.copy2(build["header"]["path"], api / "qemu-plugin.h")
    shutil.copy2(build["abi_header"]["path"], api / "poc-clock-anchor-api.h")
    legacy = output / "legacy-source"
    frozen_names = [
        "tools/tcp/live_cache.c",
        "tools/tcp/live_context.c",
        "tools/tcp/live_context.h",
        "tools/qemu/live_timing.c",
        "tools/qemu/live_timing.h",
        "tools/qemu/poc-clock-api.h",
        "references/qemu-time-control/include/qemu/qemu-plugin.h",
    ]
    for name in frozen_names:
        dest = legacy / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(_frozen(root, name))
    cflags = shlex.split(subprocess.check_output(["pkg-config", "--cflags", "glib-2.0"], text=True))
    shared = (
        ["-dynamiclib", "-undefined", "dynamic_lookup"]
        if platform.system() == "Darwin"
        else ["-shared", "-fPIC"]
    )
    plugins = {}
    dependencies = {
        root / "firmware/Makefile",
        gcc,
        root / PROFILE,
        root / REGISTRY,
        Path(build["header"]["path"]),
        Path(build["abi_header"]["path"]),
    }
    dependencies.update(root / name for name in build["patches"])
    dependencies.update(root / name for name in QEMU_OVERLAYS)
    for label, base in (("legacy", legacy), ("new", root)):
        plugin = output / (label + (".dylib" if platform.system() == "Darwin" else ".so"))
        source_names = [
            "tools/tcp/live_cache.c",
            "tools/tcp/live_context.c",
            "tools/qemu/live_timing.c",
        ]
        if label == "new":
            source_names.append("tools/tcp/clock_anchor.c")
        header = api if label == "new" else legacy / "references/qemu-time-control/include/qemu"
        cmd = [
            "cc",
            *shared,
            "-O2",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-DPOC_CONTEXT",
            "-DPOC_LIVE_IRQ",
            "-DPOC_SMALL_CACHE",
            "-I" + str(header),
            *(str(base / name) for name in source_names),
            "-o",
            str(plugin),
            *cflags,
        ]
        if label == "new":
            cmd.append("-DPOC_CLOCK_ANCHOR")
        _command(cmd, root, output / (label + "-plugin-build.log"))
        plugins[label] = _identity(plugin)
        dependencies.update(base / name for name in source_names)
        dependencies.update((base / "tools/tcp").glob("*.h"))
        dependencies.update((base / "tools/qemu").glob("*.h"))
    dependencies.update(api.iterdir())
    dependencies.update(legacy / name for name in frozen_names)
    workload = load_workload(root / REGISTRY, "A02")
    if workload != dict(id="A02", request_bytes=64, request_segments=[13, 0, 51], rounds=2):
        raise ValueError("A02 workload identity")
    candidates = {}
    for candidate in ("baseline", "pbuf"):
        dest = output / candidate
        dest.mkdir()
        header = dest / "workload.h"
        header.write_text(
            "#define POC_MATRIX_REQUEST 1\n#define POC_REQUEST_BYTES 64\n"
            "#define POC_REQUEST_SEGMENTS 13,0,51\n"
        )
        out = dest / "build"
        cmd = [
            "make",
            "-j2",
            "-C",
            str(root / "firmware"),
            "CASE=tcp_request_response",
            "CASE_SRC=tcp_request_response_irq",
            "CLOCK_ANCHORS=1",
            "CHECKSUM_OPT=Os",
            "TCP_WORKLOAD=linear",
            "TCP_VARIANT=" + candidate,
            "WORKLOAD_HEADER=" + str(header),
            "TOOLCHAIN=" + str(toolchain),
            "OUT=" + str(out),
        ]
        _command(cmd, root, dest / "build.log")
        elf, map_path = out / "firmware.elf", out / "firmware.map"
        metadata = dest / "metadata"
        boundaries = collect_boundaries(root, elf, map_path, toolchain, metadata)
        candidates[candidate] = dict(
            candidate=candidate,
            elf=_identity(elf),
            map=_identity(map_path),
            symbols=_identity(metadata / "nm.txt"),
            context_config=_identity(metadata / "context.config"),
            boundaries_file=_identity(metadata / "boundaries.json"),
            boundaries=boundaries,
            build_command=cmd,
        )
        dependencies.add(header)
        for dep in out.glob("*.d"):
            for token in shlex.split(dep.read_text().replace("\\\n", " ").split(":", 1)[1]):
                path = (root / "firmware" / token).resolve()
                if not token.endswith(":") and path.is_file():
                    dependencies.add(path)
    # Reuse the already verified capability ELF, without rebuilding a second candidate ELF.
    probe_config = root / "runs/local/c2b-guest-probe-20261102/runtime-tests.json"
    probe = json.loads(probe_config.read_text())
    _check_identity(probe["probe_elf"])
    tools = dict(
        schema="clock-anchor-tools-v1",
        source_commit=commit,
        legacy_source_commit=LEGACY_COMMIT,
        legacy_qemu=_identity(legacy_qemu),
        clock_qemu=build["binary"],
        qemu_build_manifest=_identity(qemu_build),
        plugins=plugins,
        candidates=candidates,
        profile=_identity(root / PROFILE),
        registry=_identity(root / REGISTRY),
        workload=workload,
        compiled_dependencies={str(p.relative_to(root)): digest(p) for p in sorted(dependencies)},
        probe_elf=probe["probe_elf"],
    )
    _validate_tools(root, tools)
    write_json(output / "tools.json", tools)
    write_json(
        output / "runtime-tests.json",
        dict(
            schema="c2b-runtime-config-v1",
            source_commit=commit,
            root=str(root),
            legacy_qemu=tools["legacy_qemu"],
            probe_elf=probe["probe_elf"],
            output_parent=str(output / "runtime-tests"),
            clock_qemu=tools["clock_qemu"],
            plugins=plugins,
            candidates=candidates,
            tools_manifest=str(output / "tools.json"),
        ),
    )
    return tools


def _compress(path: Path) -> dict:
    uncompressed_hash, original_bytes = digest(path), path.stat().st_size
    dest = path.with_suffix(path.suffix + ".gz")
    with path.open("rb") as src, dest.open("xb") as raw:
        with gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as zipped:
            shutil.copyfileobj(src, zipped, length=65536)
    with gzip.open(dest, "rb") as f:
        if hashlib.file_digest(f, "sha256").hexdigest() != uncompressed_hash:
            raise ValueError("Compression roundtrip changed content")
    path.unlink()
    return dict(path=dest.name, content_sha256=uncompressed_hash, content_bytes=original_bytes)


def capture_one(root: Path, spec: RunSpec, tools: dict, elf: dict, output: Path) -> dict:
    root = root.resolve()
    commit = require_clean_tree(root)
    _validate_tools(root, tools)
    if elf != tools["candidates"][spec.candidate]:
        raise ValueError("Candidate ELF identity mismatch")
    out = allocate_output(root, output)
    for src, dest in (
        (elf["elf"], "firmware.elf"),
        (elf["map"], "firmware.map"),
        (elf["symbols"], "symbols.txt"),
        (elf["context_config"], "context.config"),
    ):
        shutil.copy2(src["path"], out / dest)
    legacy = spec.configuration == "L"
    qemu = tools["legacy_qemu"] if legacy else tools["clock_qemu"]
    plugin = tools["plugins"]["legacy" if legacy else "new"]
    context = elf["boundaries"]["context"]
    argument = (
        f"{plugin['path']},begin={context['capture_begin_pc']:x},"
        f"end={context['capture_end_pc']:x},enabled={spec.injection},out={out}/accesses.csv,"
        f"context-config={out}/context.config,context-out={out}/context.jsonl"
    )
    expected = dict(
        run_id=spec.run_id,
        candidate=spec.candidate,
        configuration=spec.configuration,
        injection_enabled=bool(spec.injection),
        observer_enabled=spec.observer_enabled,
        marker_mode=spec.marker_mode,
        expected_frequency_hz=10000000,
        qemu_sha256=qemu["sha256"],
        elf_sha256=elf["elf"]["sha256"],
        profile_sha256=tools["profile"]["sha256"],
        plugin_sha256=plugin["sha256"],
        profile_path=tools["profile"]["path"],
        raw_rows=None,
    )
    if not legacy:
        config = dict(
            version=1,
            observer=int(spec.observer_enabled),
            injection=spec.injection,
            marker_mode=spec.marker_mode,
            run_id=spec.run_id,
            configuration=spec.configuration,
            **{
                k: expected[k]
                for k in ("qemu_sha256", "elf_sha256", "profile_sha256", "plugin_sha256")
            },
            sidecar=str(out / "clock.jsonl") if spec.observer_enabled else "-",
            **elf["boundaries"]["marker_pcs"],
        )
        (out / "clock.config").write_text("".join(f"{k}={v}\n" for k, v in config.items()))
        argument += f",clock-config={out}/clock.config"
    flags = QEMU_FLAGS.copy()
    flags[flags.index("-semihosting-config") + 1] += f",arg=c2b-markers={spec.marker_mode}"
    command = [qemu["path"], *flags, "-plugin", argument, "-kernel", str(out / "firmware.elf")]
    result = dict(
        schema="clock-anchor-capture-v1",
        run_id=spec.run_id,
        spec=asdict(spec),
        capture_source_commit=commit,
        compiled_source_commit=tools["source_commit"],
        tools=tools,
        command=command,
        expected=expected,
        status="failed",
        streams={},
    )
    try:
        result.update(_run_qemu(command, out))
        required = {
            "accesses.csv",
            "context.jsonl",
            "trace.psf",
            "oracle.json",
            "session.json",
            "live-cache.json",
            "console.log",
        }
        if spec.observer_enabled:
            required.add("clock.jsonl")
        missing = sorted(name for name in required if not (out / name).is_file())
        if result["exit_code"] == 0 and not result["timed_out"] and not missing:
            result["status"] = "captured-unvalidated"
        else:
            result["error"] = "QEMU failed/timed out or missing artifacts"
            result["missing"] = missing
        for name in ("accesses.csv", "context.jsonl", "clock.jsonl"):
            if (out / name).is_file():
                result["streams"][name] = _compress(out / name)
    except (OSError, ValueError, subprocess.SubprocessError) as e:
        result.update(status="failed", error=str(e))
    result["files"] = {p.name: _identity(p) for p in out.iterdir() if p.is_file()}
    write_json(out / "capture.json", result)
    return result


def run_pilot(root: Path, output: Path, tools: dict, *, stage: str) -> dict:
    if stage not in ("smoke", "full"):
        raise ValueError("Stage must be smoke or full")
    root = root.resolve()
    commit = require_clean_tree(root)
    _validate_tools(root, tools)
    matrix = pilot_matrix()
    if stage == "smoke":
        output = allocate_output(root, output)
        state = dict(
            schema="clock-anchor-runset-v1",
            source_commit=commit,
            tools=tools,
            requested_runs=[asdict(s) for s in matrix],
            runs=[],
            smoke_passed=False,
        )
    else:
        output = output.resolve()
        state = json.loads((output / "runset.json").read_text())
        if (
            state["source_commit"] != commit
            or state["tools"] != tools
            or state["requested_runs"] != [asdict(s) for s in matrix]
            or len(state["runs"]) != 4
            or not state["smoke_passed"]
        ):
            raise ValueError("Smoke source/identity/validation mismatch; use a new output")
        _check_smoke_files(output, state)
    # Formal expansion uses the independent validator/comparator from Tasks6/7.
    from psf_lab.clock_anchor_analysis import compare_transparent
    from psf_lab.clock_anchor_evidence import verify_clock_capture

    selected = matrix[:4] if stage == "smoke" else matrix[4:]
    write_json(output / "runset.json", state)
    for spec in selected:
        run = output / spec.run_id
        captured = capture_one(root, spec, tools, tools["candidates"][spec.candidate], run)
        entry = dict(
            run_id=spec.run_id,
            path=spec.run_id,
            spec=asdict(spec),
            capture_sha256=digest(run / "capture.json"),
            valid=False,
        )
        if captured["status"] == "captured-unvalidated":
            try:
                validation = verify_clock_capture(run, captured["expected"])
                entry.update(
                    valid=validation["application_status"] == "passed"
                    and validation["evidence_status"] == "valid",
                    validation=validation,
                )
            except (ValueError, OSError) as e:
                entry["error"] = str(e)
        else:
            entry["error"] = captured.get("error", "capture failed")
        state["runs"].append(entry)
        write_json(output / "runset.json", state)
        if not entry["valid"]:
            return state
    # Recheck frozen smoke captures even when resuming, never trust a passed flag alone.
    _check_smoke_files(output, state)
    groups = {}
    for entry in state["runs"]:
        run = output / entry["path"]
        if digest(run / "capture.json") != entry["capture_sha256"]:
            raise ValueError("Smoke capture changed")
        captured = json.loads((run / "capture.json").read_text())
        key = (entry["spec"]["candidate"], entry["spec"]["injection"])
        groups.setdefault(key, {})[entry["spec"]["configuration"]] = verify_clock_capture(
            run, captured["expected"]
        )
    checks = []
    for (candidate, injection), summaries in groups.items():
        comparisons = [
            compare_transparent(summaries[a], summaries[b]) for a, b in (("L", "C"), ("C", "O"))
        ]
        checks.append(
            dict(
                candidate=candidate,
                injection=injection,
                comparisons=comparisons,
                passed=all(c["passed"] for c in comparisons)
                and summaries["O"]["alignment_status"] == "verified-bounds",
            )
        )
    state["group_checks"] = checks
    state["smoke_passed"] = checks[0]["passed"]
    state["passed"] = len(state["runs"]) == 16 and all(c["passed"] for c in checks)
    write_json(output / "runset.json", state)
    return state
