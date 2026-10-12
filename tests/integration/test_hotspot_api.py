import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from psf_lab.hotspot_dashboard import build_workload_bundle
from psf_lab.runner import digest
from psf_lab.server import create_app
from tests.unit.test_hotspot_dashboard import report


class HotspotApiTests(unittest.TestCase):
    def test_catalog_identity_and_tamper(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "artifacts/verification/hotspot"
            folder.mkdir(parents=True)
            (folder / "A02.json").write_text(
                json.dumps(build_workload_bundle([report(), report("pbuf")]))
            )
            (folder / "catalog.json").write_text(
                json.dumps(
                    {
                        "schema": "hotspot-catalog-v1",
                        "workloads": [
                            {"id": "A02", "path": "A02.json", "sha256": digest(folder / "A02.json")}
                        ],
                    }
                )
            )
            with patch("psf_lab.server.ROOT", root):
                with TestClient(
                    create_app(store=root / "store"), base_url="http://127.0.0.1"
                ) as client:
                    self.assertEqual(client.get("/api/hotspots").status_code, 200)
                    self.assertEqual(client.get("/api/hotspots/A02").status_code, 200)
                    self.assertEqual(client.get("/api/hotspots/unknown").status_code, 404)
                    self.assertEqual(client.get("/api/hotspots/%2e%2e%2fsecret").status_code, 404)
                    (folder / "A02.json").write_text("{}")
                    self.assertEqual(client.get("/api/hotspots/A02").status_code, 503)

    def test_malformed_hash_valid_bundle_is_503(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "artifacts/verification/hotspot"
            folder.mkdir(parents=True)
            with (
                patch("psf_lab.server.ROOT", root),
                TestClient(create_app(store=root / "store"), base_url="http://127.0.0.1") as client,
            ):
                for data in [
                    [],
                    {"schema": "hotspot-workload-v1"},
                    {"schema": "hotspot-workload-v1", "workload": "A02"},
                ]:
                    (folder / "A02.json").write_text(json.dumps(data))
                    (folder / "catalog.json").write_text(
                        json.dumps(
                            {
                                "schema": "hotspot-catalog-v1",
                                "workloads": [
                                    {
                                        "id": "A02",
                                        "path": "A02.json",
                                        "sha256": digest(folder / "A02.json"),
                                    }
                                ],
                            }
                        )
                    )
                    with self.subTest(data=data):
                        self.assertEqual(client.get("/api/hotspots/A02").status_code, 503)
