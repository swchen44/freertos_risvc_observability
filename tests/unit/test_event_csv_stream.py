import csv
import io
import tempfile
import unittest
from pathlib import Path

from psf_lab import event_window as m
from psf_lab.hotspot_events import iter_hotspot_events
from tests.unit.test_cost_attribution import owner
from tests.unit.test_hotspot_report import profile, rows_for


class EventCsvStreamTests(unittest.TestCase):
    def test_verified_stream_filters_exact_rows_and_rejects_invalid_range(self):
        self.assertTrue(hasattr(m, "event_csv_stream"), "Need bounded CSV streaming API")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rid = "A02-baseline-b1-1-1"
            folder = root / m.BASE / rid
            manifest = m.write_event_chunks(
                iter_hotspot_events(
                    rows_for([(100, 100, 4, "I")] * 1025), [owner(0, 512)], profile(), contexts=None
                ),
                folder,
            )
            manifest["identity"] = dict(run_id=rid)
            manifest["owners"][0]["function"] = '=臺灣\n"quoted"'

            def install():
                raw = m.canonical(manifest)
                (folder / "manifest.json").write_bytes(raw)
                (folder.parent / "catalog.json").write_bytes(
                    m.canonical(
                        dict(
                            schema="event-window-catalog-v1",
                            runs=[dict(run_id=rid, workload="A02", sha256=m.sha(raw))],
                        )
                    )
                )

            install()
            data = b"".join(m.event_csv_stream(root, rid, "1023", "1025", function_query="臺灣"))
            rows = list(csv.DictReader(io.StringIO(data.decode())))
            self.assertEqual([r["index"] for r in rows], ["1023", "1024"])
            self.assertEqual(rows[0]["function"], '\'=臺灣\n"quoted"')
            self.assertTrue(data.endswith(b"\r\n"))
            empty = b"".join(m.event_csv_stream(root, rid, "1", "1"))
            self.assertEqual(list(csv.DictReader(io.StringIO(empty.decode()))), [])
            self.assertEqual(
                list(
                    csv.DictReader(
                        io.StringIO(
                            b"".join(
                                m.event_csv_stream(root, rid, "0", "1025", context="absent")
                            ).decode()
                        )
                    )
                ),
                [],
            )
            with self.assertRaises(m.InvalidEventQuery):
                m.event_csv_stream(root, rid, "-1", "2")
            with self.assertRaises(m.InvalidEventQuery):
                m.event_csv_stream(root, rid, "0", "1026")
            pieces = list(m.event_csv_stream(root, rid, "0", "1025"))
            self.assertGreater(len(pieces), 2)
            self.assertLessEqual(max(map(len, pieces)), 256 * 1024)
            self.assertEqual(
                len(list(csv.DictReader(io.StringIO(b"".join(pieces).decode())))), 1025
            )
            late = folder / "000001.json.gz"
            late.write_bytes(b"broken")
            stream = m.event_csv_stream(root, rid, "0", "1025")
            with self.assertRaises(ValueError):
                list(stream)
            (folder / "000000.json.gz").write_bytes(b"broken")
            with self.assertRaises(ValueError):
                m.event_csv_stream(root, rid, "0", "2")

    def test_stream_preserves_big_integer_and_empty_function_label(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rid = "A02-baseline-b1-1-1"
            item = next(
                iter_hotspot_events(
                    rows_for([(100, 100, 4, "I")]), [owner(0, 512)], profile(), contexts=None
                )
            )
            item["cost_cycles"]["l1i"] = 9007199254740993
            item["memory_cycles"] = sum(item["cost_cycles"].values())
            item["model_service_ns"] = 2 * item["memory_cycles"]
            item["accounted_model_ns"] = item["model_service_ns"] + item["instructions"]
            manifest = m.write_event_chunks([item], root / m.BASE / rid)
            manifest["identity"] = dict(run_id=rid)
            manifest["owners"][0]["function"] = ""
            raw = m.canonical(manifest)
            (root / m.BASE / rid / "manifest.json").write_bytes(raw)
            (root / m.BASE / "catalog.json").write_bytes(
                m.canonical(
                    dict(
                        schema="event-window-catalog-v1",
                        runs=[dict(run_id=rid, workload="A02", sha256=m.sha(raw))],
                    )
                )
            )
            rows = list(
                csv.DictReader(io.StringIO(b"".join(m.event_csv_stream(root, rid)).decode()))
            )
            self.assertEqual(rows[0]["l1i"], "9007199254740993")
            self.assertEqual(rows[0]["function"], "")
