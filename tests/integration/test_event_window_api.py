import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from psf_lab.event_window import BASE, canonical, sha, write_event_chunks
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
                self.assertEqual(c.get("/api/event-windows/%2e%2e%2fsecret").status_code, 404)
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
