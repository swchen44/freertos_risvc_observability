"""Apply generated patches and exercise build preflight without installing tools."""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.qemu.make_clock_anchor_patch import (
    check_tool_versions,
    generate_clock_patch,
    verify_overlays,
)

ROOT = Path(__file__).resolve().parents[2]
EXPORTS = [
    "qemu_plugin_poc_clock_configure",
    "qemu_plugin_poc_clock_note",
    "qemu_plugin_poc_add_ns_tagged",
    "qemu_plugin_poc_clock_finish",
]


class ClockBuildTests(unittest.TestCase):
    def test_pinned_distributions_keep_exact_cli_build_suffix(self):
        result = check_tool_versions(
            {"meson": "1.12.1", "ninja": "1.13.2"},
            {"meson": "1.12.1", "ninja": "1.13.2.git.kitware.jobserver-pipe-1"},
        )
        self.assertEqual(result["ninja"]["version"], "1.13.2")
        self.assertEqual(result["ninja"]["reported_version"], "1.13.2.git.kitware.jobserver-pipe-1")
        with self.assertRaises(ValueError):
            check_tool_versions(
                {"meson": "1.12.1", "ninja": "1.14.0"}, {"meson": "1.12.1", "ninja": "1.14.0"}
            )

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_generated_patch_reproduces_edit_and_refuses_unrelated_mutation(self):
        base, edited = self.root / "base", self.root / "edited"
        for d in (base, edited):
            (d / "plugins").mkdir(parents=True)
        (base / "plugins/api.c").write_text("/* base */\nint old;\n")
        (edited / "plugins/api.c").write_text("/* base */\nint old, added;\n")
        (edited / "plugins/poc-clock-observer.c").write_text("int adapter;\n")
        patch = self.root / "observer.patch"
        result = generate_clock_patch(base, edited, patch)
        self.assertEqual(result["paths"], ["plugins/api.c", "plugins/poc-clock-observer.c"])
        p = subprocess.run(
            ["patch", "-p1", "--batch", "-i", str(patch)], cwd=base, capture_output=True, timeout=5
        )
        self.assertEqual(p.returncode, 0, p.stderr)
        for name in result["paths"]:
            self.assertEqual((base / name).read_bytes(), (edited / name).read_bytes())
        with self.assertRaises(FileExistsError):
            generate_clock_patch(base, edited, patch)
        (edited / "forbidden.c").write_text("int unexpected;\n")
        with self.assertRaises(ValueError):
            generate_clock_patch(base, edited, self.root / "invalid.patch")

    def test_real_patch_exports_symbols_and_contains_identical_core(self):
        source = self.root / "source"
        # Only existing paths touched by 0004 need the pinned base contents.
        base = ROOT / ".tools/qemu-time-control/qemu-9.2.0"
        for name in (
            "plugins/api.c",
            "plugins/meson.build",
            "include/qemu/qemu-plugin.h",
            "hw/intc/riscv_aclint.c",
        ):
            dest = source / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(base / name, dest)
        p = subprocess.run(
            [
                "patch",
                "-p1",
                "--batch",
                "-i",
                str(ROOT / "tools/qemu/0004-clock-anchor-observer.patch"),
            ],
            cwd=source,
            capture_output=True,
            timeout=10,
        )
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        verify_overlays(ROOT, source)
        probe = self.root / "no-plugin.c"
        probe.write_text(
            '#include "sysemu/poc-clock-observer.h"\n'
            "int main(void) { poc_clock_epoch(0, 2); return 0; }\n"
        )
        native = subprocess.run(
            [
                "cc",
                "-std=c11",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-I" + str(source / "include"),
                str(probe),
                "-o",
                str(self.root / "no-plugin"),
            ],
            capture_output=True,
            timeout=10,
        )
        self.assertEqual(native.returncode, 0, native.stderr)
        probe.write_text(
            '#include <ctype.h>\n#include "poc-clock-state.h"\n'
            "int main(void) { return tolower('A') != 'a'; }\n"
        )
        native = subprocess.run(
            [
                "cc",
                "-std=c11",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-DPOC_CLOCK_IN_QEMU",
                "-I" + str(source / "include"),
                "-I" + str(source / "plugins"),
                str(probe),
                str(source / "plugins/poc-clock-state.c"),
                "-o",
                str(self.root / "core-in-qemu"),
            ],
            capture_output=True,
            timeout=10,
        )
        self.assertEqual(native.returncode, 0, native.stderr)
        command = [
            sys.executable,
            str(ROOT / "references/qemu-clock-anchor/scripts/qemu-plugin-symbols.py"),
            str(source / "include/qemu/qemu-plugin.h"),
        ]
        exports = subprocess.check_output(command, text=True, timeout=5)
        for name in EXPORTS:
            self.assertIn("  " + name + ";", exports)
        core = source / "plugins/poc-clock-state.c"
        core.write_bytes(core.read_bytes() + b"/* changed */\n")
        with self.assertRaises(ValueError):
            verify_overlays(ROOT, source)

    def test_build_preflight_existing_destination_bad_archive_and_missing_patch(self):
        script = ROOT / "tools/qemu/build-clock-anchor-probe.sh"
        existing = self.root / "existing"
        existing.mkdir()
        bad = self.root / "bad.tar.xz"
        bad.write_bytes(b"not the pinned archive")
        for dest, archive, jobs in (
            (existing, bad, "2"),
            (self.root / "bad-hash", bad, "2"),
            (self.root / "jobs", bad, "8"),
        ):
            p = subprocess.run(
                [str(script), str(dest), str(archive), jobs], capture_output=True, timeout=5
            )
            self.assertNotEqual(p.returncode, 0)
            self.assertNotIn(b"pip install", p.stdout + p.stderr)
        fake = self.root / "repo"
        tool = fake / "tools/qemu"
        tool.mkdir(parents=True)
        shutil.copy2(script, tool / script.name)
        p = subprocess.run(
            [str(tool / script.name), str(self.root / "missing"), str(bad), "2"],
            capture_output=True,
            timeout=5,
        )
        self.assertNotEqual(p.returncode, 0)
        self.assertIn(b"Missing patch", p.stderr)
