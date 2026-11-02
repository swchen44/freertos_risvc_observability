"""Capture identity, output containment and real owned-process timeout behavior."""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from psf_lab.clock_anchor_capture import (
    RunSpec,
    _check_qemu_sources,
    _check_smoke_files,
    _run_qemu,
    _validate_capture_contract,
    allocate_output,
    pilot_matrix,
    prepare_tools,
)


class ClockCaptureDriverTests(unittest.TestCase):
    def test_matrix_is_complete_smoke_first_and_mode_is_derived(self):
        rows = pilot_matrix()
        self.assertEqual(len(rows), 16)
        self.assertEqual(len(set(rows)), 16)
        self.assertEqual(
            [(r.candidate, r.configuration, r.injection) for r in rows[:4]],
            [("baseline", c, 1) for c in ("L", "C", "O", "M")],
        )
        self.assertEqual([r.marker_mode for r in rows[:4]], [1, 1, 1, 0])
        self.assertEqual([r.observer_enabled for r in rows[:4]], [False, False, True, True])
        for args in (
            ("other", "O", 1),
            ("baseline", "X", 1),
            ("baseline", "O", True),
            ("baseline", "O", 2),
            ("baseline", "O", 1, True),
            ("baseline", "O", 1, 2),
        ):
            with self.subTest(args=args), self.assertRaises(ValueError):
                RunSpec(*args)
        with self.assertRaises(AttributeError):
            rows[0].injection = 0

    def test_output_is_new_ignored_and_contained_but_supports_spaces(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
            (root / ".gitignore").write_text("runs/local/\n")
            output = root / "runs/local/has spaces"
            self.assertTrue(allocate_output(root, output).samefile(output))
            for p in (
                output,
                root / "src/no",
                root / "runs/tcp-workload-matrix-v1/no",
                root / "runs/local/comma,path",
            ):
                with self.subTest(path=p), self.assertRaises((ValueError, FileExistsError)):
                    allocate_output(root, p)
            outside = Path(tmp) / "outside"
            outside.mkdir()
            (root / "runs/local/link").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ValueError):
                allocate_output(root, root / "runs/local/link/escape")
            self.assertFalse((outside / "escape").exists())

    def test_dirty_sources_refuse_before_building_or_creating_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
            (root / "uncommitted").write_text("new source")
            output = root / "runs/local/no-build"
            with self.assertRaisesRegex(RuntimeError, "clean"):
                prepare_tools(root, root / "missing-build.json", root / "missing-qemu", output)
            self.assertFalse(output.exists())

    def test_qemu_overlay_checks_canonical_and_compiled_source_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "qemu"
            overlays = {}
            pairs = (
                ("tools/qemu/clock_anchor/poc-clock-state.c", "plugins/poc-clock-state.c"),
                ("tools/qemu/clock_anchor/poc-clock-state.h", "plugins/poc-clock-state.h"),
                ("tools/qemu/poc-clock-anchor-api.h", "include/qemu/poc-clock-anchor-api.h"),
            )
            for canonical, compiled in pairs:
                for path in (root / canonical, source / compiled):
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(b"independent source fixture\n")
                overlays[compiled] = hashlib.sha256(b"independent source fixture\n").hexdigest()
            build = dict(source=str(source), overlays=overlays)
            _check_qemu_sources(root, build)
            for canonical, compiled in pairs:
                for path in (root / canonical, source / compiled):
                    path.write_bytes(b"changed\n")
                    with self.subTest(path=path), self.assertRaises(ValueError):
                        _check_qemu_sources(root, build)
                    path.write_bytes(b"independent source fixture\n")

    def test_resume_checks_capture_and_data_before_expansion(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            state = dict(source_commit="fixed-source", runs=[])
            for config in ("L", "C", "O", "M"):
                run = output / config
                run.mkdir()
                (run / "trace.psf").write_bytes(b"original trace")
                capture = dict(
                    capture_source_commit="fixed-source",
                    files={
                        "trace.psf": dict(
                            path="/unused/old/location",
                            bytes=14,
                            sha256=hashlib.sha256(b"original trace").hexdigest(),
                        )
                    },
                )
                data = json.dumps(capture).encode()
                (run / "capture.json").write_bytes(data)
                state["runs"].append(
                    dict(path=config, capture_sha256=hashlib.sha256(data).hexdigest())
                )
            _check_smoke_files(output, state)
            (output / "O/trace.psf").write_bytes(b"tampered trace")
            with self.assertRaises(ValueError):
                _check_smoke_files(output, state)
            (output / "O/trace.psf").write_bytes(b"original trace")
            (output / "C/capture.json").write_text("{}")
            with self.assertRaises(ValueError):
                _check_smoke_files(output, state)
            state["runs"][0]["path"] = "../escape"
            with self.assertRaises(ValueError):
                _check_smoke_files(output, state)

    def test_timeout_retains_output_and_kills_owned_grandchild(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            child = (
                "import os,signal,time; from pathlib import Path;"
                "signal.signal(signal.SIGTERM,signal.SIG_IGN);"
                "Path('child.pid').write_text(str(os.getpid())); time.sleep(30)"
            )
            parent = (
                "import subprocess,sys,time; from pathlib import Path;"
                f"p=subprocess.Popen([sys.executable,'-c',{child!r}]);"
                "\nwhile not Path('child.pid').exists(): time.sleep(.01)"
                "\nprint('started',flush=True); time.sleep(30)"
            )
            result = _run_qemu([sys.executable, "-c", parent], root, timeout=2)
            self.assertTrue(result["timed_out"])
            self.assertNotEqual(result["exit_code"], 0)
            self.assertIn(b"started", (root / "qemu.log").read_bytes())
            pid = int((root / "child.pid").read_text())
            # A reparented zombie is no longer runnable; do not mistake it for a leak.
            end = time.monotonic() + 2
            live = True
            while live and time.monotonic() < end:
                p = subprocess.run(
                    ["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True
                )
                live = bool(p.stdout.strip()) and not p.stdout.strip().startswith("Z")
                if live:
                    time.sleep(0.02)
            if live:
                os.kill(pid, 9)
            self.assertFalse(live, "Owned child survived the timeout cleanup")

    def test_capture_contract_rejects_mode_binary_and_command_drift(self):
        spec = RunSpec("baseline", "O", 1)
        tools = dict(
            source_commit="compiled",
            legacy_qemu=dict(path="/old", sha256="a" * 64),
            clock_qemu=dict(path="/new", sha256="b" * 64),
            plugins=dict(new=dict(path="/plugin", sha256="c" * 64)),
            candidates=dict(
                baseline=dict(
                    elf=dict(sha256="d" * 64),
                    boundaries=dict(
                        context=dict(capture_begin_pc=0x80000000, capture_end_pc=0x80000004)
                    ),
                )
            ),
        )
        expected = dict(
            candidate="baseline",
            configuration="O",
            injection_enabled=True,
            observer_enabled=True,
            marker_mode=1,
            run_id=spec.run_id,
            qemu_sha256="b" * 64,
            plugin_sha256="c" * 64,
            elf_sha256="d" * 64,
        )
        from dataclasses import asdict

        from psf_lab.runner import QEMU_FLAGS

        flags = QEMU_FLAGS.copy()
        flags[flags.index("-semihosting-config") + 1] += ",arg=c2b-markers=1"
        command = [
            "/new",
            *flags,
            "-plugin",
            "/plugin,begin=80000000,end=80000004,enabled=1,out=/original/accesses.csv,"
            "context-config=/original/context.config,context-out=/original/context.jsonl,"
            "clock-config=/original/clock.config",
            "-kernel",
            "/original/firmware.elf",
        ]
        capture = dict(
            spec=asdict(spec),
            tools=tools,
            compiled_source_commit="compiled",
            command=command,
            files={"firmware.elf": dict(path="/original/firmware.elf")},
        )
        _validate_capture_contract(capture, expected)
        for changed in (
            dict(marker_mode=0),
            dict(qemu_sha256="a" * 64),
            dict(injection_enabled=False),
        ):
            with self.assertRaises(ValueError):
                _validate_capture_contract(capture, expected | changed)
        capture["command"] = command + ["-smp", "2"]
        with self.assertRaises(ValueError):
            _validate_capture_contract(capture, expected)
