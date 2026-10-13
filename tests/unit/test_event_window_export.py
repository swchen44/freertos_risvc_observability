import importlib
import tempfile
import unittest
from pathlib import Path

from psf_lab.event_window import BASE, canonical, sha, write_event_chunks
from psf_lab.hotspot_events import iter_hotspot_events
from tests.unit.test_hotspot_report import profile, rows_for


class EventExportTests(unittest.TestCase):
    def test_inline_escape_hashes_and_existing_output(self):
        self.assertIsNotNone(importlib.util.find_spec("psf_lab.event_window_export"))
        module = importlib.import_module("psf_lab.event_window_export")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rid = "A02-baseline-b1-1-1"
            folder = root / BASE / rid
            m = write_event_chunks(
                iter_hotspot_events(rows_for([(100, 100, 4, "I")]), [], profile(), contexts=None),
                folder,
            )
            m.update(identity={"run_id": rid}, note="</script><script>alert(1)</script>\u2028")
            raw = canonical(m)
            (folder / "manifest.json").write_bytes(raw)
            (folder.parent / "catalog.json").write_bytes(
                canonical(
                    {
                        "schema": "event-window-catalog-v1",
                        "runs": [{"run_id": rid, "workload": "A02", "sha256": sha(raw)}],
                    }
                )
            )
            (root / "web/dist/assets").mkdir(parents=True)
            (root / "web/event-window.html").write_text(
                '<title>test</title><link rel="stylesheet" href="/assets/event-window.css">'
                '<script id="event-window-data"></script>'
                '<script src="/assets/event-window.js"></script>'
            )
            (root / "web/dist/assets/event-window.js").write_text("/* fixture */")
            (root / "web/dist/assets/event-window.css").write_text("body{}")
            target = root / "out.html"
            receipt = module.export_event_window_html(root, "A02", target)
            text = target.read_text()
            self.assertNotIn("<script>alert", text)
            self.assertIn('"chunk_pool"', text)
            self.assertIn('"manifest_gzip"', text)
            self.assertIn("connect-src 'none'", text)
            self.assertIn("worker-src blob:", text)
            self.assertEqual(receipt["output_sha256"], sha(target.read_bytes()))
            with self.assertRaises(ValueError):
                module.export_event_window_html(root, "A02", target)
            (folder / "000000.json.gz").write_bytes(b"broken")
            with self.assertRaises(ValueError):
                module.export_event_window_html(root, "A02", root / "bad.html")
