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
