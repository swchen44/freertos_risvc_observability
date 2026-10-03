import csv
import io
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from psf_lab.server import create_app
from tests.unit.test_store import FIXTURE


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.client = TestClient(create_app(self.root), base_url="http://127.0.0.1")

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def upload(self):
        r = self.client.post("/api/traces", files={"file": ("demo.psf", FIXTURE)})
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()["trace_id"]

    def test_upload_query_view_and_all_csv(self):
        id_ = self.upload()
        base = f"/api/traces/{id_}"
        self.assertEqual(self.client.get(base).status_code, 200)
        r = self.client.post(
            base + "/events", json={"filters": {}, "sort": [], "offset": 0, "limit": 20}
        )
        self.assertEqual(r.json()["total"], 309)
        self.assertEqual(len(r.json()["rows"]), 20)
        view = self.client.post(base + "/view", json={"filters": {}})
        self.assertEqual(view.status_code, 200)
        self.assertIn("task_share", view.json()["metrics"])
        csv_ = self.client.post(
            base + "/export", json={"filters": {}, "sort": [], "kind": "events"}
        )
        self.assertEqual(len(list(csv.DictReader(io.StringIO(csv_.text)))), 309)
        self.assertEqual(
            self.client.post(
                base + "/export", json={"filters": {}, "sort": [], "kind": "metrics"}
            ).status_code,
            200,
        )

    def test_bad_inputs_and_host(self):
        self.assertEqual(
            self.client.post("/api/traces", files={"file": ("empty", b"")}).status_code, 422
        )
        self.assertEqual(self.client.get("/api/traces/unknown").status_code, 404)
        self.assertEqual(
            self.client.get("/api/traces", headers={"host": "evil.example"}).status_code, 400
        )
        id_ = self.upload()
        for payload in [
            {"filters": {"x": 1}},
            {"limit": None},
            {"offset": -1},
            {"sort": [{"field": "bad", "direction": "asc"}]},
        ]:
            self.assertEqual(
                self.client.post(f"/api/traces/{id_}/events", json=payload).status_code, 422
            )

    def test_resource_limits_and_recovery(self):
        with TestClient(
            create_app(self.root, max_bytes=8000, max_traces=1), base_url="http://127.0.0.1"
        ) as client:
            self.assertEqual(
                client.post("/api/traces", files={"file": ("large", bytes(8001))}).status_code, 413
            )
            self.assertEqual(
                client.post("/api/traces", files={"file": ("a", FIXTURE)}).status_code, 201
            )
            self.assertEqual(
                client.post("/api/traces", files={"file": ("b", FIXTURE)}).status_code, 413
            )
        with TestClient(create_app(self.root), base_url="http://127.0.0.1") as client:
            self.assertEqual(len(client.get("/api/traces").json()), 1)

    def test_partial_warning_and_run_comparisons(self):
        r = self.client.post("/api/traces", files={"file": ("partial", FIXTURE[:-1])})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["quality"]["status"], "partial")
        runs = self.client.get("/api/runs")
        self.assertEqual(runs.status_code, 200)
        pair = []
        for case in ["logger_bad", "logger_fixed"]:
            pair.append(next(r["run_id"] for r in runs.json() if r["case_id"] == case))
        r = self.client.post("/api/comparisons", json={"pair_id": "logger", "run_ids": pair})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["verdict"], "pass")
        self.assertEqual(
            self.client.post(
                "/api/comparisons", json={"pair_id": "logger", "run_ids": ["../secret", "bad"]}
            ).status_code,
            404,
        )

    def test_concurrent_uploads_obey_quota(self):
        from concurrent.futures import ThreadPoolExecutor

        with TestClient(create_app(self.root, max_traces=1), base_url="http://127.0.0.1") as client:

            def upload(_):
                return client.post("/api/traces", files={"file": ("a", FIXTURE)}).status_code

            with ThreadPoolExecutor(max_workers=2) as pool:
                self.assertEqual(sorted(pool.map(upload, range(2))), [201, 413])

    def test_zero_frequency_and_missing_run(self):
        from tests.fixtures.binary import stream

        r = self.client.post("/api/traces", files={"file": ("zero.psf", stream(frequency=0))})
        self.assertEqual(r.status_code, 201)
        id_ = r.json()["trace_id"]
        view = self.client.post(f"/api/traces/{id_}/view", json={})
        self.assertIsNone(view.json()["metrics"]["window_seconds"])
        self.assertEqual(self.client.get("/api/runs/unknown/psf").status_code, 404)

    def test_large_http_body_rejected_before_parse(self):
        with TestClient(
            create_app(self.root, max_bytes=100), base_url="http://127.0.0.1"
        ) as client:
            r = client.post(
                "/api/traces",
                content=bytes(66000),
                headers={"content-type": "application/octet-stream"},
            )
            self.assertEqual(r.status_code, 413)
            self.assertNotIn(str(self.root), r.text)
