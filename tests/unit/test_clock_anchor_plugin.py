"""Compile and run the real plugin helper with controlled public register inputs."""

import hashlib
import json
import shlex
import subprocess
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = """version=1
observer=1
injection=1
marker_mode=1
run_id=native-plugin-O
configuration=O
qemu_sha256=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
elf_sha256=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
profile_sha256=cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
plugin_sha256=dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd
sidecar=unused.jsonl
enter_pc=2147483664
sampled_pc=2147483680
leave_pc=2147483696
"""


class ClockAnchorPluginTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = ROOT / "runs/local/c2b-plugin-native" / uuid.uuid4().hex
        cls.out.mkdir(parents=True)
        cls.binary = cls.out / "plugin-helper"
        flags = shlex.split(
            subprocess.check_output(["pkg-config", "--cflags", "--libs", "glib-2.0"], text=True)
        )
        cmd = [
            "cc",
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-I" + str(ROOT / "references/qemu-time-control/include/qemu"),
            "-I" + str(ROOT / "tools/tcp"),
            str(ROOT / "tests/native/clock_anchor_plugin.c"),
            str(ROOT / "tools/tcp/clock_anchor.c"),
            "-o",
            str(cls.binary),
            *flags,
        ]
        p = subprocess.run(cmd, capture_output=True, timeout=20)
        cls.save("compile", cmd, p)
        if p.returncode:
            raise AssertionError(p.stderr.decode(errors="replace"))

    @classmethod
    def save(cls, label, cmd, p):
        (cls.out / (label + ".stdout")).write_bytes(p.stdout)
        (cls.out / (label + ".stderr")).write_bytes(p.stderr)
        sources = [
            ROOT / n
            for n in (
                "tests/native/clock_anchor_plugin.c",
                "tools/tcp/clock_anchor.c",
                "tools/tcp/clock_anchor.h",
                "tools/qemu/poc-clock-anchor-api.h",
            )
        ]
        (cls.out / (label + ".json")).write_text(
            json.dumps(
                dict(
                    command=cmd,
                    exit=p.returncode,
                    sources={
                        str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest()
                        for f in sources
                        if f.is_file()
                    },
                ),
                indent=2,
            )
            + "\n"
        )

    def execute(self, label, config=CONFIG, fault=0):
        path = self.out / (label + ".config")
        path.write_text(config)
        cmd = [str(self.binary), str(path), str(fault)]
        p = subprocess.run(cmd, capture_output=True, timeout=5)
        self.save(label, cmd, p)
        return p, [json.loads(s) for s in p.stdout.splitlines()]

    def test_register_payload_cursor_and_post_end_mmio(self):
        p, rows = self.execute("normal")
        self.assertEqual(p.returncode, 0, p.stderr)
        samples = [r for r in rows if r.get("kind") == 6]
        self.assertEqual(len(samples), 5)
        self.assertEqual(samples[0]["sample"], "8589934590")
        self.assertEqual(samples[0]["cursor"], 2)
        self.assertEqual([r["seq"] for r in samples], [1, 2, 3, 4, 5])
        io = [r for r in rows if r.get("kind") == 9]
        self.assertEqual([(r["cursor"], r["address"]) for r in io], [(16, 33603576)])
        self.assertEqual(rows[-1]["finished"], 16)
        self.assertTrue(rows[1]["needs_registers"])

    def test_observer_off_does_not_enumerate_or_read_new_registers(self):
        config = CONFIG.replace("observer=1", "observer=0").replace(
            "configuration=O", "configuration=C"
        )
        config = config.replace("sidecar=unused.jsonl", "sidecar=-")
        p, rows = self.execute("observer-off", config)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertTrue(rows[0]["path_null"])
        self.assertFalse(rows[1]["needs_registers"])
        self.assertEqual(rows[-1]["register_lists"], 0)
        self.assertEqual(rows[-1]["register_reads"], 0)
        self.assertFalse(any(r.get("kind") in (5, 6, 7) for r in rows))
        self.assertEqual(sum(r.get("kind") == 2 for r in rows), 16)

    def test_missing_duplicate_short_registers_phase_jump_api_and_row_failure(self):
        for fault in range(1, 7):
            with self.subTest(fault=fault):
                p, _ = self.execute("fault-" + str(fault), fault=fault)
                self.assertNotEqual(p.returncode, 0)

    def test_unknown_duplicate_missing_and_noncanonical_config_rejected(self):
        configs = [
            CONFIG + "extra=1\n",
            CONFIG + "version=1\n",
            CONFIG.replace("marker_mode=1\n", ""),
            CONFIG.replace("observer=1", "observer=01"),
            CONFIG.replace("2147483664", "2147483665"),
            CONFIG.replace("run_id=native-plugin-O", 'run_id=bad"id'),
        ]
        for i, config in enumerate(configs):
            with self.subTest(case=i):
                p, rows = self.execute("config-" + str(i), config)
                self.assertNotEqual(p.returncode, 0)
                self.assertFalse(any(r.get("configured") for r in rows))
