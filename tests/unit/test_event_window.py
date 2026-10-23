import copy
import gzip
import importlib
import json
import tempfile
import unittest
from pathlib import Path

from psf_lab.hotspot_events import iter_hotspot_events
from tests.unit.test_cost_attribution import owner
from tests.unit.test_hotspot_report import profile, rows_for


class EventWindowTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("psf_lab.event_window"))
        self.m = importlib.import_module("psf_lab.event_window")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.output = Path(self.tmp.name) / "run"

    def build(self):
        rows = rows_for([(100, 100, 4, "I")] * 1025)
        events = iter_hotspot_events(rows, [owner(0, 512)], profile(), contexts=None)
        return self.m.write_event_chunks(events, self.output)

    def test_full_chunks_and_warm_boundary(self):
        result = self.build()
        self.assertEqual(
            [(c["start"], c["end"]) for c in result["chunks"]], [("0", "1024"), ("1024", "1025")]
        )
        self.assertEqual(result["events"], "1025")
        chunk = result["chunks"][1]
        payload = (self.output / (chunk["id"] + ".json.gz")).read_bytes()
        data = self.m.decode_event_chunk(payload, chunk, result)
        self.assertEqual(data["rows"][0][0], "1024")
        self.assertEqual(data["rows"][0][7], "1")
        self.assertEqual(result["totals"]["instructions"], "1025")
        with self.assertRaises(ValueError):
            self.m.write_event_chunks([], self.output)

    def test_hash_valid_malformed_and_corruption_rejected(self):
        r = self.build()
        c = r["chunks"][0]
        blob = (self.output / (c["id"] + ".json.gz")).read_bytes()
        with self.assertRaises(ValueError):
            self.m.decode_event_chunk(blob + b"x", c, r)
        for change in ["op", "negative", "missing", "owner", "bool", "noncanonical"]:
            data = json.loads(gzip.decompress(blob))
            row = data["rows"][0]
            if change == "bool":
                row[7] = True
            if change == "noncanonical":
                row[7] = "01"
            if change == "op":
                row[4] = "Q"
            if change == "negative":
                row[7] = "-1"
            if change == "missing":
                row.pop()
            if change == "owner":
                row[6] = "999"
            encoded = self.m.encode_chunk(data)
            desc = dict(c, **encoded["metadata"])
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.m.decode_event_chunk(encoded["gzip"], desc, r)

    def test_manifest_rejects_gaps_and_duplicates(self):
        r = self.build()
        for chunks in [r["chunks"][:-1], r["chunks"] * 2]:
            bad = copy.deepcopy(r)
            bad["chunks"] = chunks
            with self.assertRaises(ValueError):
                self.m.validate_event_manifest(bad)

    def test_malformed_dictionary_and_deflate_are_value_errors(self):
        result = self.build()
        for key, bad in [
            ("contexts", "unknown"),
            ("contexts", [None]),
            ("owners", [None]),
            ("owners", [{}]),
        ]:
            altered = dict(result, **{key: bad})
            with self.subTest(key=key, bad=bad), self.assertRaises(ValueError):
                self.m.validate_event_manifest(altered)
        chunk = result["chunks"][0]
        data = bytearray((self.output / (chunk["id"] + ".json.gz")).read_bytes())
        data[10] = 0xFF
        desc = dict(chunk, gzip_sha256=self.m.sha(data))
        with self.assertRaises(ValueError):
            self.m.decode_event_chunk(bytes(data), desc, result)
