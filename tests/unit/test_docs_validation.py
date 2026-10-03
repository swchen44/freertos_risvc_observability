import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from psf_lab.docs_validation import verify_docs


class DocsValidationTests(unittest.TestCase):
    def test_markdown_links_images_and_immutable_baseline(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "docs").mkdir()
            (root / "references").mkdir()
            source = root / "references/source.txt"
            source.write_text("original")
            (root / "references/manifest.json").write_text(
                json.dumps(
                    {
                        "files": [
                            {
                                "path": "references/source.txt",
                                "sha256": hashlib.sha256(b"original").hexdigest(),
                            }
                        ]
                    }
                )
            )
            (root / "README.md").write_text(
                "[ok](docs/a.md)\n![broken](missing.png)\n`[code](ignored)`\n[web](https://example.com)"
            )
            (root / "docs/a.md").write_text("# A\n")
            result = verify_docs(root)
            self.assertFalse(result["ok"])
            self.assertEqual(len(result["broken_links"]), 1)
            self.assertEqual(source.read_text(), "original")
            (root / "missing.png").write_bytes(b"placeholder")
            self.assertTrue(verify_docs(root)["ok"])
            source.write_text("modified")
            self.assertFalse(verify_docs(root)["ok"])
            self.assertEqual(source.read_text(), "modified")
