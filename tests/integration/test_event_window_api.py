import copy
import gzip
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from psf_lab.event_window import BASE, canonical, encode_chunk, sha, write_event_chunks
from psf_lab.hotspot_events import iter_hotspot_events
from psf_lab.server import create_app
from tests.unit.test_cost_attribution import owner
from tests.unit.test_hotspot_report import profile, rows_for


class EventApiTests(unittest.TestCase):
    def test_fixed_routes_corruption_and_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rid = "A02-baseline-b1-1-1"
            folder = root / BASE / rid
            m = write_event_chunks(
                iter_hotspot_events(
                    rows_for([(100, 100, 4, "I")]), [owner(0, 512)], profile(), contexts=None
                ),
                folder,
            )
            m["identity"] = {"run_id": rid}
            raw = canonical(m)
            (folder / "manifest.json").write_bytes(raw)
            (folder.parent / "catalog.json").write_text(
                json.dumps(
                    {
                        "schema": "event-window-catalog-v1",
                        "runs": [{"run_id": rid, "workload": "A02", "sha256": sha(raw)}],
                    }
                )
            )
            with (
                patch("psf_lab.server.ROOT", root),
                TestClient(create_app(store=root / "store"), base_url="http://127.0.0.1") as c,
            ):
                self.assertEqual(c.get("/api/event-windows").status_code, 200)
                self.assertEqual(c.get("/api/event-windows/" + rid).status_code, 200)
                r = c.get("/api/event-windows/" + rid + "/chunks/000000")
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.content, (folder / "000000.json.gz").read_bytes())
                self.assertEqual(c.get("/api/event-windows/unknown").status_code, 404)
                download = c.get(f"/api/event-windows/{rid}/events.csv?start=0&end=1")
                self.assertEqual(download.status_code, 200)
                self.assertEqual(
                    download.headers["content-disposition"],
                    f'attachment; filename="{rid}-events.csv"',
                )
                self.assertIn(b'"index","pc"', download.content)
                self.assertEqual(
                    c.get(f"/api/event-windows/{rid}/events.csv?start=-1").status_code, 400
                )
                self.assertEqual(c.get("/api/event-windows/unknown/events.csv").status_code, 404)
                self.assertEqual(c.get("/api/event-windows/%2e%2e%2fsecret").status_code, 404)
                original = r.content
                malformed_chunk = json.loads(gzip.decompress(original))
                malformed_chunk["rows"][0][4] = "Q"
                encoded = encode_chunk(malformed_chunk)
                changed = copy.deepcopy(m)
                changed["chunks"][0].update(encoded["metadata"])
                altered_raw = canonical(changed)
                (folder / "000000.json.gz").write_bytes(encoded["gzip"])
                (folder / "manifest.json").write_bytes(altered_raw)
                catalog_path = folder.parent / "catalog.json"
                catalog = json.loads(catalog_path.read_text())
                catalog["runs"][0]["sha256"] = sha(altered_raw)
                catalog_path.write_bytes(canonical(catalog))
                self.assertEqual(
                    c.get("/api/event-windows/" + rid + "/chunks/000000").status_code, 503
                )
                self.assertEqual(c.get(f"/api/event-windows/{rid}/events.csv").status_code, 503)
                (folder / "manifest.json").write_bytes(raw)
                catalog["runs"][0]["sha256"] = sha(raw)
                catalog_path.write_bytes(canonical(catalog))
                (folder / "000000.json.gz").write_bytes(b"broken")
                self.assertEqual(
                    c.get("/api/event-windows/" + rid + "/chunks/000000").status_code, 503
                )
                malformed = dict(m)
                malformed.pop("identity")
                malformed_raw = canonical(malformed)
                (folder / "manifest.json").write_bytes(malformed_raw)
                (folder.parent / "catalog.json").write_bytes(
                    canonical(
                        {
                            "schema": "event-window-catalog-v1",
                            "runs": [
                                {"run_id": rid, "workload": "A02", "sha256": sha(malformed_raw)}
                            ],
                        }
                    )
                )
                self.assertEqual(c.get("/api/event-windows/" + rid).status_code, 503)
                (folder / "manifest.json").write_bytes(b"[]")
                self.assertEqual(c.get("/api/event-windows/" + rid).status_code, 503)
