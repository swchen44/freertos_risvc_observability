"""Reject plausible but incomplete or under-delivered cache timing captures."""

import gzip
import importlib.util
import tempfile
import unittest
from pathlib import Path


class LiveCacheReportTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(
            importlib.util.find_spec("psf_lab.live_cache"), "Live cache verifier not implemented"
        )
        from psf_lab.live_cache import audit_accesses, compare_guest

        self.audit = audit_accesses
        self.compare = compare_guest

    def test_event_costs_checked_against_python(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "access.csv"
            p.write_text(
                "pc,address,size,operation,l1i,l1d,l2,ram_read,ram_write\n"
                "2147483648,2147483648,4,I,1,0,8,18,0\n"
                "2147483648,2147483648,4,R,0,1,8,0,0\n"
            )
            result = self.audit(p)
            self.assertEqual((result["events"], result["cycles"], result["ns"]), (2, 36, 72))
            p.write_text(p.read_text().replace(",18,0", ",17,0"))
            with self.assertRaises(ValueError):
                self.audit(p)

    def test_archived_gzip_can_be_reaudited(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "access.csv"
            raw.write_text(
                "pc,address,size,operation,l1i,l1d,l2,ram_read,ram_write\n"
                "2147483648,2147483648,4,I,1,0,8,18,0\n"
            )
            packed = raw.with_suffix(".csv.gz")
            packed.write_bytes(gzip.compress(raw.read_bytes(), mtime=0))
            self.assertEqual(self.audit(raw), self.audit(packed))

    def test_nonidentity_instruction_mapping_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "access.csv"
            raw.write_text(
                "pc,address,size,operation,l1i,l1d,l2,ram_read,ram_write\n"
                "2147483652,2147483648,4,I,1,0,8,18,0\n"
            )
            with self.assertRaises(ValueError):
                self.audit(raw)

    def test_empty_capture_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "access.csv"
            p.write_text("pc,address,size,operation,l1i,l1d,l2,ram_read,ram_write\n")
            with self.assertRaises(ValueError):
                self.audit(p)

    def test_guest_delta_matches_accumulated_cost(self):
        c = dict(before=10, after=20, ticks=0, work=123)
        a = dict(before=10, after=30, ticks=0, work=123)
        self.assertEqual(self.compare(c, a, 1000)["extra_guest_ns"], 1000)
        with self.assertRaises(ValueError):
            self.compare(c, a, 2000)

    def test_different_work_timer_or_backward_time_rejected(self):
        c = dict(before=10, after=20, ticks=0, work=123)
        for changes in [dict(work=124), dict(ticks=1), dict(after=9)]:
            with self.assertRaises(ValueError):
                self.compare(c, dict(c, **changes), 0)
