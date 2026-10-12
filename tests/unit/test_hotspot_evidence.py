import importlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class HotspotEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("psf_lab.hotspot_evidence"))
        self.m = importlib.import_module("psf_lab.hotspot_evidence")

    def test_exact_catalog_and_unknown_workload(self):
        self.assertEqual(len(self.m.catalog_inputs(ROOT)), 40)
        self.assertEqual(len(self.m.catalog_inputs(ROOT, workload="A02")), 14)
        with self.assertRaises(ValueError):
            self.m.catalog_inputs(ROOT, workload="../A02")

    def test_batch_and_boundary_reject_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dest = root / "runs/tcp-context-v1/formal"
            dest.mkdir(parents=True)
            source = ROOT / "runs/tcp-context-v1/formal"
            shutil.copy2(source / "completion.json", dest / "completion.json")
            # Gate rejects incomplete batch before any expensive tooling.
            d = json.loads((dest / "completion.json").read_text())
            d["runs"].pop()
            (dest / "completion.json").write_text(json.dumps(d))
            with self.assertRaises(ValueError):
                self.m.catalog_inputs(root)

    def test_real_b1_loader_and_mutated_profile(self):
        entry = self.m.catalog_inputs(ROOT, workload="A02")[0]
        d = self.m.load_hotspot_input(ROOT, entry)
        self.assertTrue(d["raw_path"].is_file())
        self.assertEqual(d["identity"]["family"], "b1")
        self.assertIsNone(d["contexts"])
        self.assertTrue(d["evidence"]["elf_sha256"])
        with self.assertRaises(ValueError):
            self.m.load_hotspot_input(ROOT, dict(entry, mode=0))

    def test_formal_missing_required_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = ROOT / "runs/tcp-context-v1/formal"
            dest = root / "runs/tcp-context-v1/formal"
            shutil.copytree(src / "A02-baseline", dest / "A02-baseline")
            shutil.copy2(src / "completion.json", dest / "completion.json")
            path = dest / "A02-baseline/enabled-1-1/manifest.json"
            d = json.loads(path.read_text())
            del d["files"]["context-events.jsonl"]
            path.write_text(json.dumps(d))
            with self.assertRaises(ValueError):
                self.m.load_formal_context(root, "A02-baseline", 1, 1)

    def test_existing_output_rejected_before_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                self.m.analyze_hotspots(ROOT, Path(tmp), workload="A02")

    def test_boundary_and_missing_key_reject_with_valid_outer_digest(self):
        from psf_lab.runner import digest

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = ROOT / "runs/tcp-context-v1/formal"
            dest = root / "runs/tcp-context-v1/formal"
            shutil.copytree(source / "A02-baseline", dest / "A02-baseline")
            shutil.copy2(source / "completion.json", dest / "completion.json")
            run = dest / "A02-baseline/enabled-1-1"
            path = run / "manifest.json"
            original = path.read_text()
            receipt = json.loads((dest / "completion.json").read_text())
            record = next(
                r
                for r in receipt["runs"]
                if r["candidate"] == "A02-baseline" and r["mode"] == 1 and r["repeat"] == 1
            )
            data = json.loads(original)
            del data["files"]["context-events.jsonl"]
            path.write_text(json.dumps(data))
            record["run_manifest_sha256"] = digest(path)
            (dest / "completion.json").write_text(json.dumps(receipt))
            with self.assertRaisesRegex(ValueError, "Missing"):
                self.m.load_formal_context(root, "A02-baseline", 1, 1)
            path.write_text(original)
            record["run_manifest_sha256"] = digest(path)
            (dest / "completion.json").write_text(json.dumps(receipt))
            bp = dest / "A02-baseline/boundaries.json"
            bd = json.loads(bp.read_text())
            bd["elf_sha256"] = "0" * 64
            bp.write_text(json.dumps(bd))
            mp = dest / "A02-baseline/manifest.json"
            md = json.loads(mp.read_text())
            md["boundary_sha256"] = digest(bp)
            mp.write_text(json.dumps(md))
            with self.assertRaisesRegex(ValueError, "ELF mismatch"):
                self.m.load_formal_context(root, "A02-baseline", 1, 1)
