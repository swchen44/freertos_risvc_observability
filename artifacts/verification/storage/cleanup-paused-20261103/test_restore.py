"""Small real restore fixtures for the cleanup handoff command."""

import gzip
import hashlib
import importlib.util
import json
import os
import tarfile
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "cleanup_restore", Path(__file__).with_name("restore.py")
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RestoreTests(unittest.TestCase):
    def fixture(self, root, *, traversal=False):
        source = root / "input/qemu-9.2.0"
        source.mkdir(parents=True)
        (source / "main.c").write_bytes(b"original source\0\xff")
        (source / "main.c").chmod(0o755)
        (source / "unused-link").symlink_to("/opt/X11/include")
        archive = root / "source.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(source, arcname="qemu-9.2.0")
            if traversal:
                tar.add(source / "main.c", arcname="../escaped")
        body = archive.read_bytes()
        parts = []
        for i, start in enumerate(range(0, len(body), 71)):
            path = root / f"part{i:03d}"
            chunk = body[start : start + 71]
            path.write_bytes(chunk)
            parts.append(
                dict(path=path.name, bytes=len(chunk), sha256=hashlib.sha256(chunk).hexdigest())
            )
        # Expected content/mode/link metadata are hand specified.
        expected = [
            dict(
                path="main.c",
                kind="file",
                mode=0o755,
                bytes=17,
                sha256=hashlib.sha256(b"original source\0\xff").hexdigest(),
            ),
            dict(path="unused-link", kind="symlink", mode=0o755, target="/opt/X11/include"),
        ]
        # macOS symlink lstat mode is 755; use host's lstat permission representation.
        expected[1]["mode"] = (source / "unused-link").lstat().st_mode & 0o7777
        inventory = root / "inventory.json.gz"
        inventory.write_bytes(gzip.compress(json.dumps(expected).encode()))
        return dict(
            parts=parts,
            archive_sha256=hashlib.sha256(body).hexdigest(),
            inventory=inventory.name,
            inventory_sha256=hashlib.sha256(inventory.read_bytes()).hexdigest(),
        )

    def test_roundtrip_and_existing_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            entry = self.fixture(root)
            out = root / "restored"
            self.assertEqual(module.restore(entry, root, out)["status"], "restored-verified")
            self.assertEqual((out / "qemu-9.2.0/main.c").read_bytes(), b"original source\0\xff")
            self.assertEqual(os.readlink(out / "qemu-9.2.0/unused-link"), "/opt/X11/include")
            with self.assertRaises(FileExistsError):
                module.restore(entry, root, out)

    def test_bad_or_missing_part_refuses_before_creating_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            entry = self.fixture(root)
            first = root / entry["parts"][0]["path"]
            first.write_bytes(b"corrupt")
            with self.assertRaises(ValueError):
                module.restore(entry, root, root / "bad")
            self.assertFalse((root / "bad").exists())
            first.unlink()
            with self.assertRaises(FileNotFoundError):
                module.restore(entry, root, root / "missing")

    def test_traversal_is_rejected_before_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            entry = self.fixture(root, traversal=True)
            with self.assertRaises(ValueError):
                module.restore(entry, root, root / "bad")
            self.assertFalse((root / "escaped").exists())


if __name__ == "__main__":
    unittest.main()
