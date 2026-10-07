import copy
import importlib.util
import unittest
from pathlib import Path


class BatchTests(unittest.TestCase):
    def setUp(self):
        path = Path("tools/tcp/run_context_batch.py")
        self.assertTrue(path.exists())
        spec = importlib.util.spec_from_file_location("context_batch", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.validate = module.validate_context_batch
        self.module = module
        self.rows = [
            dict(
                candidate=c,
                mode=m,
                repeat=r,
                context_enabled=True,
                parity_passed=True,
                context_exact=True,
                run_manifest_sha256="a" * 64,
            )
            for c in ("A02-baseline", "A02-pbuf", "A08-baseline", "A08-pbuf")
            for m in (0, 1)
            for r in (1, 2, 3)
        ]

    def test_exact_formal_cartesian_set(self):
        self.validate(self.rows)
        for rows in (self.rows[:-1], self.rows + [self.rows[0]], self.rows[1:] + [self.rows[1]]):
            with self.assertRaises(ValueError):
                self.validate(rows)
        for key, value in [
            ("repeat", True),
            ("mode", True),
            ("context_enabled", False),
            ("parity_passed", False),
            ("context_exact", False),
            ("nested", True),
            ("run_manifest_sha256", "missing"),
        ]:
            rows = copy.deepcopy(self.rows)
            rows[0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.validate(rows)

    def test_empty_probe_runs_cannot_authorize_formal_capture(self):
        import hashlib
        import json
        from tempfile import TemporaryDirectory

        self.assertTrue(hasattr(self.module, "validate_probe_gate"))
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidates = []
            for name in ("A02-baseline", "A02-pbuf", "A08-baseline", "A08-pbuf"):
                folder = root / name
                folder.mkdir()
                path = folder / "manifest.json"
                path.write_text(json.dumps(dict(candidate=name, passed=True, runs=[])))
                candidates.append(
                    dict(
                        candidate=name,
                        manifest_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    )
                )
            (root / "probe-gate.json").write_text(
                json.dumps(
                    dict(schema="context-probe-gate-v1", passed=True, runs=8, candidates=candidates)
                )
            )
            with self.assertRaises(ValueError):
                self.module.validate_probe_gate(root)
        self.module.validate_probe_gate(Path("runs/tcp-context-v1/probe"))
