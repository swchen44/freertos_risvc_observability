import importlib
import json
import tempfile
import unittest
from pathlib import Path

from psf_lab.hotspot_dashboard import build_workload_bundle
from psf_lab.runner import digest
from tests.unit.test_hotspot_dashboard import report


class HotspotExportTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("psf_lab.hotspot_export"))
        self.m = importlib.import_module("psf_lab.hotspot_export")

    def test_inline_escape_and_existing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            d = root / "artifacts/verification/hotspot"
            d.mkdir(parents=True)
            data = build_workload_bundle([report(), report("pbuf")])
            # Untrusted source names remain text in a valid report.
            for r in data["reports"]:
                for owner in r["owners"].values():
                    owner["function"] = "</script><script>alert(1)</script>"
            data = build_workload_bundle(data["reports"])
            (d / "A02.json").write_text(json.dumps(data))
            (d / "catalog.json").write_text(
                json.dumps(
                    {
                        "schema": "hotspot-catalog-v1",
                        "workloads": [
                            {"id": "A02", "path": "A02.json", "sha256": digest(d / "A02.json")}
                        ],
                    }
                )
            )
            (root / "web/dist/assets").mkdir(parents=True)
            (root / "web/hotspot.html").write_text(
                '<title>x</title><link rel="stylesheet" href="/assets/hotspot.css">'
                '<script id="hotspot-data"></script>'
                '<script src="/assets/hotspot.js"></script>'
            )
            (root / "web/dist/assets/hotspot.js").write_text("window.loaded=true;")
            (root / "web/dist/assets/hotspot.css").write_text("body{color:black}")
            output = root / "result.html"
            self.m.export_hotspot_html(root, "A02", output)
            html = output.read_text()
            self.assertNotIn("</script><script>alert", html)
            self.assertIn("connect-src 'none'", html)
            self.assertNotIn('src="/assets/', html)
            with self.assertRaises(ValueError):
                self.m.export_hotspot_html(root, "A02", output)
            (d / "A02.json").write_text("{}")
            with self.assertRaises(ValueError):
                self.m.export_hotspot_html(root, "A02", root / "bad.html")
