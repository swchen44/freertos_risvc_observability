import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path

from psf_lab.provenance import require_clean_tree, verify_sources


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git("init", "-q")
        (self.root / "source.c").write_text("original")
        self.git("add", ".")
        self.git(
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-qm",
            "baseline",
        )

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, text=True).strip()

    def test_clean_tree_returns_full_commit(self):
        self.assertEqual(require_clean_tree(self.root), self.git("rev-parse", "HEAD"))

    def test_untracked_source_is_rejected(self):
        (self.root / "new.c").write_text("uncommitted")
        with self.assertRaises(RuntimeError):
            require_clean_tree(self.root)

    def test_tracked_edit_is_rejected(self):
        (self.root / "source.c").write_text("changed")
        with self.assertRaises(RuntimeError):
            require_clean_tree(self.root)

    def test_hash_mismatch_or_missing_file_is_rejected(self):
        good = hashlib.sha256(b"original").hexdigest()
        self.assertTrue(
            verify_sources(self.root, {"files": [{"path": "source.c", "sha256": good}]})["ok"]
        )
        for name in ("source.c", "missing.c", "../outside"):
            with self.subTest(name=name):
                result = verify_sources(self.root, {"files": [{"path": name, "sha256": "0" * 64}]})
                self.assertFalse(result["ok"])
