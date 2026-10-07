import copy
import importlib.util
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


class ContextCaptureTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("psf_lab.context_capture"))
        from psf_lab.context_capture import compare_context_capture, run_context_case

        self.compare = compare_context_capture
        self.run = run_context_case
        self.reference = dict(
            candidate="A02-baseline",
            mode=1,
            elf_sha256="a" * 64,
            raw_stream_sha256="b" * 64,
            packets=[dict(sha256="c" * 64, direction="rx")],
            psf=dict(
                objects=[dict(id=1, name="task")], switches=[[1, 10]], markers=[["BEGIN", 0, 1]]
            ),
            measurement=dict(
                case="tcp_request_response",
                before=1,
                after=10,
                before_tick=0,
                ticks=2,
                work=11680,
                woke=1,
                observer_tick=2,
                observer_mtime=5,
            ),
        )

    def test_parity_requires_all_observations(self):
        self.assertTrue(self.compare(self.reference, copy.deepcopy(self.reference))["passed"])
        for field, value in [
            ("raw_stream_sha256", "d" * 64),
            ("packets", []),
            ("elf_sha256", "e" * 64),
            ("mode", 0),
            ("candidate", "A08-baseline"),
        ]:
            observed = copy.deepcopy(self.reference)
            observed[field] = value
            result = self.compare(self.reference, observed)
            self.assertFalse(result["passed"])
            self.assertIn(field, result["mismatches"])
        for key in ("objects", "switches", "markers"):
            observed = copy.deepcopy(self.reference)
            observed["psf"][key] = []
            self.assertFalse(self.compare(self.reference, observed)["passed"])
        observed = copy.deepcopy(self.reference)
        observed["measurement"]["after"] = 11
        self.assertFalse(self.compare(self.reference, observed)["passed"])
        del observed["raw_stream_sha256"]
        with self.assertRaises(ValueError):
            self.compare(self.reference, observed)

    def test_existing_or_source_output_rejected(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            for out in (source, root):
                with self.assertRaises(ValueError):
                    self.run(root, source, out, repeats=1, context_enabled=True)
