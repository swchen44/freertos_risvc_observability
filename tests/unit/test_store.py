import tempfile
import unittest
from pathlib import Path

from psf_lab.store import StoreError, create_trace, list_traces, load_trace

FIXTURE = Path("fixtures/desktop/trace.psf").read_bytes()


class StoreTests(unittest.TestCase):
    def test_names_are_display_only_and_persist(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "store"
            a = create_trace(root, FIXTURE, source_name="../../escape.psf")
            b = create_trace(root, FIXTURE, source_name="escape.psf")
            self.assertNotEqual(a["trace_id"], b["trace_id"])
            self.assertEqual(a["source"]["name"], "escape.psf")
            self.assertEqual(len(list_traces(root)), 2)
            self.assertFalse((Path(d) / "escape.psf").exists())
            self.assertEqual(len(load_trace(root, a["trace_id"])[0]["events"]), 309)

    def test_failed_parse_leaves_no_committed_trace(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                create_trace(Path(d), b"bad", source_name="bad.psf")
            self.assertEqual(list(Path(d).iterdir()), [])

    def test_quota_and_unknown_ids(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            create_trace(root, FIXTURE, source_name="a", max_traces=1)
            with self.assertRaises(StoreError):
                create_trace(root, FIXTURE, source_name="b", max_traces=1)
            with self.assertRaises(StoreError):
                load_trace(root, "../../x")
