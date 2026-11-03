"""Real byte/mode roundtrips, failed runs and hostile restore manifests."""

import json
import tempfile
import unittest
from pathlib import Path

from tools.tcp.package_clock_anchor import package_clock_anchor, verify_restore


class ClockPackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.runset = self.root / "runset"
        self.runset.mkdir()
        (self.runset / "runset.json").write_text(
            json.dumps(
                dict(
                    schema="clock-anchor-runset-v1",
                    runs=[dict(valid=False, error="intentional partial")],
                    tools={},
                )
            )
        )
        (self.runset / "partial").mkdir()
        (self.runset / "partial/trace.psf").write_bytes(bytes(range(256)) * 123)
        (self.runset / "partial/trace.psf").chmod(0o755)
        (self.runset / "partial/qemu.log").write_text("failed capture; retain me\n")

    def test_partial_binary_roundtrip_is_self_contained_and_bounded(self):
        output = self.root / "package"
        manifest = package_clock_anchor(self.runset, output, max_part_bytes=127)
        self.assertTrue(all(p["bytes"] <= 127 for f in manifest["files"] for p in f["parts"]))
        # Original run directory is unavailable during restore.
        self.runset.rename(self.root / "unavailable")
        result = verify_restore(output, self.root / "restored")
        self.assertEqual(result["status"], "restored-verified")
        trace = self.root / "restored/runset/partial/trace.psf"
        self.assertEqual(trace.read_bytes(), bytes(range(256)) * 123)
        self.assertEqual(trace.stat().st_mode & 0o777, 0o755)
        self.assertIn(
            "intentional partial", (self.root / "restored/runset/runset.json").read_text()
        )
        with self.assertRaises(FileExistsError):
            verify_restore(output, self.root / "restored")
        with self.assertRaises(FileExistsError):
            package_clock_anchor(self.root / "unavailable", output)

    def test_wrong_or_missing_parts_rejected(self):
        output = self.root / "package"
        manifest = package_clock_anchor(self.runset, output, max_part_bytes=127)
        part = output / manifest["files"][0]["parts"][0]["path"]
        original = part.read_bytes()
        part.write_bytes(b"corrupt")
        with self.assertRaises(ValueError):
            verify_restore(output, self.root / "corrupt")
        part.write_bytes(original)
        part.unlink()
        with self.assertRaises((ValueError, FileNotFoundError)):
            verify_restore(output, self.root / "missing")

    def test_traversal_absolute_and_symlink_restore_paths_rejected(self):
        output = self.root / "package"
        manifest = package_clock_anchor(self.runset, output)
        for path in ("../escape", "/tmp/escape", "runset/../../escape", "C:\\escape"):
            bad = json.loads(json.dumps(manifest))
            bad["files"][0]["path"] = path
            (output / "manifest.json").write_text(json.dumps(bad))
            with self.subTest(path=path), self.assertRaises(ValueError):
                verify_restore(output, self.root / "unsafe")
            self.assertFalse((self.root / "escape").exists())
        (output / "manifest.json").write_text(json.dumps(manifest))
        part = output / manifest["files"][0]["parts"][0]["path"]
        saved = self.root / "saved"
        part.rename(saved)
        part.symlink_to(saved)
        with self.assertRaises(ValueError):
            verify_restore(output, self.root / "linked")

    def test_symlink_input_and_unsupported_archive_codecs_refused(self):
        link = self.runset / "linked"
        link.symlink_to(self.runset / "runset.json")
        with self.assertRaises(ValueError):
            package_clock_anchor(self.runset, self.root / "bad-package")
        link.unlink()
        output = self.root / "package"
        manifest = package_clock_anchor(self.runset, output)
        for codec in ("tar", "zip"):
            bad = manifest | dict(codec=codec)
            (output / "manifest.json").write_text(json.dumps(bad))
            with self.assertRaises(ValueError):
                verify_restore(output, self.root / codec)

    def test_declared_size_limits_expansion_and_output_cannot_nest_input(self):
        with self.assertRaises(ValueError):
            package_clock_anchor(self.runset, self.runset / "package")
        for limit in (0, True, -1, 64 * 1024 * 1024 + 1):
            with self.assertRaises(ValueError):
                package_clock_anchor(self.runset, self.root / "bad", max_part_bytes=limit)
        output = self.root / "package"
        manifest = package_clock_anchor(self.runset, output)
        manifest["files"][0]["original_bytes"] = 0
        (output / "manifest.json").write_text(json.dumps(manifest))
        with self.assertRaises(ValueError):
            verify_restore(output, self.root / "bomb")
