"""Catch false miss classification and attributing data addresses as instruction PCs."""

import unittest

from psf_lab import tcp_hotspots


class MissTests(unittest.TestCase):
    def test_compulsory_conflict_capacity(self):
        self.assertTrue(hasattr(tcp_hotspots, "MissClassifier"), "Classifier not implemented")
        c = tcp_hotspots.MissClassifier(2)
        self.assertEqual(c.observe(0, False), "compulsory")
        self.assertEqual(c.observe(2, False), "compulsory")
        self.assertEqual(c.observe(0, False), "conflict")
        self.assertIsNone(c.observe(0, True))
        self.assertEqual(c.observe(1, False), "compulsory")
        self.assertEqual(c.observe(2, False), "capacity")

    def test_hit_updates_shadow_recency(self):
        self.assertTrue(hasattr(tcp_hotspots, "MissClassifier"), "Classifier not implemented")
        c = tcp_hotspots.MissClassifier(2)
        for b in (0, 1):
            c.observe(b, False)
        c.observe(0, True)
        c.observe(2, False)
        self.assertEqual(c.observe(0, False), "conflict")

    def test_cross_line_write_misses_and_pc_attribution(self):
        import json
        from pathlib import Path

        profile = json.loads(
            (Path(__file__).resolve().parents[2] / "cases/timing/sysram-10-small.json").read_text()
        )
        rows = [dict(pc=0x80001000, address=0x8000003F, size=2, operation="W")] * 2
        result = tcp_hotspots.profile_misses(
            rows, profile, [(0x80001000, 4, "writer")], audit=False
        )
        self.assertEqual(result["totals"]["l1d_accesses"], 4)
        self.assertEqual(result["totals"]["l1d_misses"], 2)
        self.assertEqual(result["totals"]["l1d_compulsory"], 2)
        self.assertEqual(result["totals"]["l2_accesses"], 4)
        self.assertEqual(result["totals"]["cycles"], 116)
        self.assertEqual(result["functions"][0]["name"], "writer")

    def test_native_cost_mismatch_is_rejected(self):
        import json
        from pathlib import Path

        profile = json.loads(
            (Path(__file__).resolve().parents[2] / "cases/timing/sysram-10-small.json").read_text()
        )
        row = dict(
            pc=0x80000000,
            address=0x80000000,
            size=4,
            operation="I",
            l1i=1,
            l1d=0,
            l2=0,
            ram_read=0,
            ram_write=0,
        )
        with self.assertRaisesRegex(ValueError, "disagree"):
            tcp_hotspots.profile_misses([row], profile, [])

    def test_small_trace_audit_rejects_default_geometry(self):
        import csv
        import json
        import tempfile
        from pathlib import Path

        from psf_lab.live_cache import audit_accesses

        profile = json.loads(
            (Path(__file__).resolve().parents[2] / "cases/timing/sysram-10-small.json").read_text()
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "accesses.csv"
            with path.open("w", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(
                    [
                        "pc",
                        "address",
                        "size",
                        "operation",
                        "l1i",
                        "l1d",
                        "l2",
                        "ram_read",
                        "ram_write",
                    ]
                )
                for i in range(5):
                    writer.writerow([0x80001000, 0x80000000 + i * 2048, 4, "R", 0, 1, 8, 18, 0])
                writer.writerow([0x80001000, 0x80000000, 4, "R", 0, 1, 8, 0, 0])
            self.assertEqual(audit_accesses(path, profile=profile)["cycles"], 144)
            with self.assertRaisesRegex(ValueError, "disagree"):
                audit_accesses(path)
