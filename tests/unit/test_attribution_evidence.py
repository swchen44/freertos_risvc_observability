import hashlib
import importlib.util
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("psf_lab.attribution_evidence"))
        from psf_lab.attribution_evidence import (
            build_role_ranges,
            parse_link_map,
            verify_file_hashes,
        )

        self.verify = verify_file_hashes
        self.parse = parse_link_map
        self.build = build_role_ranges
        self.rules = json.loads(Path("cases/timing/attribution-rules-v1.json").read_text())

    def test_hash_required_keys_mutation_and_traversal(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "firmware.elf").write_bytes(b"elf")
            hashes = {"firmware.elf": hashlib.sha256(b"elf").hexdigest()}
            self.verify(base, hashes, {"firmware.elf"})
            for bad in ({}, {**hashes, "../outside": "0" * 64}, {**hashes, "/outside": "0" * 64}):
                with self.assertRaises(ValueError):
                    self.verify(base, bad, {"firmware.elf"})
            (base / "firmware.elf").write_bytes(b"Elf")
            with self.assertRaises(ValueError):
                self.verify(base, hashes, {"firmware.elf"})

    def test_external_symlink_rejected(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "base").mkdir()
            (root / "outside").write_bytes(b"x")
            (root / "base/link").symlink_to(root / "outside")
            with self.assertRaises(ValueError):
                self.verify(root / "base", {"link": hashlib.sha256(b"x").hexdigest()}, {"link"})

    def test_map_skips_discarded_and_supports_wrapped_input(self):
        rows = self.parse("""Discarded input sections
 .text.bad 0x80000000 0x10 bad.o
Linker script and memory map
.text 0x80000000 0x40
 .text.f
                0x80000000 0x10 good.o
 .text.g 0x80000010 0x10 /tool/libc.a(memcpy.o)
 .data 0x80010000 0x10 good.o
""")
        self.assertEqual(
            [(r["start"], r["end"], r["object"]) for r in rows],
            [
                (0x80000000, 0x80000010, "good.o"),
                (0x80000010, 0x80000020, "/tool/libc.a(memcpy.o)"),
                (0x80010000, 0x80010010, "good.o"),
            ],
        )

    def fixture(self):
        return dict(
            executable_sections=[dict(start=100, end=140, name=".text")],
            map_records=[
                dict(start=100, end=120, section=".text", object="port.o", evidence="map:1"),
                dict(
                    start=120,
                    end=140,
                    section=".text.memcpy",
                    object="/tool/libc.a(memcpy.o)",
                    evidence="map:2",
                ),
            ],
            symbols=[
                dict(start=100, size=0, function="trap"),
                dict(start=120, size=20, function="memcpy"),
            ],
            object_sources={"port.o": "third_party/FreeRTOS/portASM.S"},
            debug={},
        )

    def test_no_size_assembly_and_runtime_provenance(self):
        rows = self.build(self.fixture(), self.rules)
        self.assertEqual(
            [(r["start"], r["end"], r["role"]) for r in rows],
            [(100, 120, "kernel_port"), (120, 140, "runtime_library")],
        )
        self.assertTrue(rows[0]["function"].startswith("unresolved@port.o:"))
        self.assertEqual(rows[1]["function"], "memcpy")

    def test_map_outside_executable_rejected(self):
        evidence = self.fixture()
        evidence["map_records"][0]["start"] = 200
        evidence["map_records"][0]["end"] = 220
        with self.assertRaises(ValueError):
            self.build(evidence, self.rules)

    def test_inline_origin_does_not_override_object(self):
        evidence = self.fixture()
        evidence["debug"] = {100: "references/tcp/lwip/inline.c"}
        rows = self.build(evidence, self.rules)
        self.assertEqual(rows[0]["role"], "kernel_port")

    def test_symbol_overrun_rejected(self):
        evidence = self.fixture()
        evidence["symbols"][1]["size"] = 30
        with self.assertRaises(ValueError):
            self.build(evidence, self.rules)

    def test_partial_symbols_do_not_become_aliases(self):
        from psf_lab.cost_attribution import resolve_pc

        evidence = self.fixture()
        evidence["symbols"] = [
            dict(start=100, size=15, function="f"),
            dict(start=110, size=10, function="g"),
        ]
        rows = self.build(evidence, self.rules)
        self.assertEqual(resolve_pc(rows, 112)["role"], "unresolved")
        self.assertEqual(resolve_pc(rows, 112)["reason"], "overlap_conflict")

    def test_git_pin_detects_map_replacement(self):
        import subprocess
        from psf_lab import attribution_evidence

        self.assertTrue(hasattr(attribution_evidence, "verify_git_files"))
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / "firmware.map").write_text("original map")
            subprocess.run(["git", "-C", str(root), "add", "firmware.map"], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(root),
                    "-c",
                    "user.name=Fixture",
                    "-c",
                    "user.email=fixture@example.invalid",
                    "commit",
                    "-qm",
                    "fixture",
                ],
                check=True,
            )
            sha = subprocess.check_output(
                ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
            ).strip()
            attribution_evidence.verify_git_files(root, sha, ["firmware.map"])
            (root / "firmware.map").write_text("replacement map")
            with self.assertRaises(ValueError):
                attribution_evidence.verify_git_files(root, sha, ["firmware.map"])
