"""Real localhost HTTP integration using curl; run with a disposable running server."""

import csv
import io
import json
import subprocess
import unittest
from pathlib import Path

from psf_lab.analysis import analyze
from psf_lab.export import export_csv
from psf_lab.parser.semantic import parse_trace
from psf_lab.query import query_events, query_view

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/verification/offline/http"
BASE = "http://127.0.0.1:8767"


def curl(name, path, *args):
    OUT.mkdir(parents=True, exist_ok=True)
    command = [
        "curl",
        "--silent",
        "--show-error",
        "--max-time",
        "60",
        "-D",
        str(OUT / (name + ".headers")),
        "-o",
        str(OUT / (name + ".body")),
        "-w",
        "%{http_code}",
        *args,
        BASE + path,
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    (OUT / (name + ".command.json")).write_text(
        json.dumps(
            {
                "command": command,
                "returncode": result.returncode,
                "stderr": result.stderr,
                "status": result.stdout,
            },
            indent=2,
        )
        + "\n"
    )
    if result.returncode:
        raise RuntimeError(result.stderr)
    return int(result.stdout), (OUT / (name + ".body")).read_text()


class CurlIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = next(
            (ROOT / "runs/suite-20261003T085652Z-2732b56355").glob("*-queue_baseline-*/trace.psf")
        )
        status, text = curl("upload", "/api/traces", "-F", f"file=@{cls.source}")
        assert status == 201, (status, text)
        cls.meta = json.loads(text)
        cls.id = cls.meta["trace_id"]
        cls.trace = parse_trace(cls.source.read_bytes(), source_name="trace.psf", strict=False)
        cls.analysis = analyze(cls.trace)

    def post(self, name, suffix, body):
        return curl(
            name,
            f"/api/traces/{self.id}/{suffix}",
            "-H",
            "Content-Type: application/json",
            "--data",
            json.dumps(body),
        )

    def test_metadata(self):
        status, text = curl("metadata", f"/api/traces/{self.id}")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(text)["source"]["sha256"], self.trace["source"]["sha256"])

    def test_filters_view_full_csv(self):
        filters = {"channels": ["POC"]}
        sort = [{"field": "ticks", "direction": "desc"}]
        status, text = self.post("events", "events", dict(filters=filters, sort=sort, limit=2))
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(text), query_events(self.trace, filters, sort, limit=2))
        status, text = self.post("view", "view", dict(filters=filters))
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(text), query_view(self.trace, self.analysis, filters))
        for kind in ["events", "metrics"]:
            status, text = self.post(
                kind + "-csv", "export", dict(filters=filters, sort=sort, kind=kind)
            )
            self.assertEqual(status, 200)
            rows = list(csv.DictReader(io.StringIO(text)))
            expected = list(
                csv.DictReader(
                    io.StringIO(export_csv(self.trace, self.analysis, filters, sort, kind=kind))
                )
            )
            self.assertEqual(rows, expected)
            if kind == "events":
                self.assertGreater(len(rows), 2)
            self.assertIn("text/csv", (OUT / (kind + "-csv.headers")).read_text().lower())

    def test_invalid_inputs(self):
        status, _ = curl("missing", "/api/traces/" + "0" * 32)
        self.assertEqual(status, 404)
        for name, body in [
            ("window", {"filters": {"start_ticks": "9", "end_ticks": "2"}}),
            ("sort", {"sort": [{"field": "oops", "direction": "asc"}]}),
        ]:
            status, text = self.post("invalid-" + name, "events", body)
            self.assertEqual(status, 422)
            self.assertIn("error", json.loads(text))
        status, text = curl("bad-psf", "/api/traces", "-F", f"file=@{ROOT / 'README.md'}")
        self.assertEqual(status, 422)
        self.assertIn("error", json.loads(text))

    def test_comparison(self):
        status, text = curl("runs", "/api/runs")
        self.assertEqual(status, 200)
        runs = json.loads(text)
        ids = [
            next(r["run_id"] for r in runs if r["case_id"] == c)
            for c in ["logger_bad", "logger_fixed"]
        ]
        status, text = curl(
            "comparison",
            "/api/comparisons",
            "-H",
            "Content-Type: application/json",
            "--data",
            json.dumps({"pair_id": "logger", "run_ids": ids}),
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(text)["verdict"], "pass")

    def test_web_assets(self):
        status, text = curl("index", "/")
        self.assertEqual(status, 200)
        self.assertIn("PSF Lab", text)
        status, _ = curl("javascript", "/assets/app.js")
        self.assertEqual(status, 200)
        # Do not commit a duplicate multi-megabyte build asset as a curl log.
        (OUT / "javascript.body").unlink()


if __name__ == "__main__":
    unittest.main(verbosity=2)
