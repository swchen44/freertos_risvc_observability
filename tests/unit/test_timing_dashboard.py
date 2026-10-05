import copy
import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from psf_lab.server import create_app
from psf_lab.timing_dashboard import export_dashboard, load_dashboard, validate_comparison

ROOT = Path(__file__).resolve().parents[2]


class TimingDashboardTests(unittest.TestCase):
    def test_real_groups_and_denominators(self):
        data = load_dashboard(ROOT)
        self.assertEqual(len(data["rows"]), 8)
        row = next(r for r in data["rows"] if r["label"] == "fragmented-pbuf")
        self.assertAlmostEqual(row["improvement_pct"], 100 * 20300 / 2489000)
        self.assertEqual(row["l1i_miss_pct"], 100 * 1662 / 332309)
        self.assertEqual(data["profile"]["caches"]["l2"]["size"], 32768)

    def test_tampered_input_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = ROOT / "cases/timing/dashboard-sources.json"
            for name in json.loads(manifest.read_text())["files"]:
                p = root / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes((ROOT / name).read_bytes())
            target = root / manifest.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(manifest.read_bytes())
            p = root / "cases/timing/sysram-10-small.json"
            p.write_text(p.read_text() + " ")
            with self.assertRaisesRegex(ValueError, "hash"):
                load_dashboard(root)

    def test_inconsistent_metrics_rejected(self):
        source = json.loads(
            (ROOT / "artifacts/verification/tcp-pbuf-holdout/results/comparison.json").read_text()
        )
        for key in ["cycles", "l1i_misses", "stack_cycles"]:
            with self.subTest(key=key):
                data = copy.deepcopy(source)
                data["results"][0][key] += 1
                with self.assertRaises(ValueError):
                    validate_comparison(data, source["schema"])
        for key, value in [("passed", False), ("schema", "other")]:
            data = copy.deepcopy(source)
            data[key] = value
            with self.assertRaises(ValueError):
                validate_comparison(data, source["schema"])

    def test_api_matches_export_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            with TestClient(create_app(Path(tmp)), base_url="http://localhost") as client:
                response = client.get("/api/timing")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), load_dashboard(ROOT))

    def test_missing_source_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(OSError):
                load_dashboard(Path(tmp))

    def test_offline_contains_same_data_and_no_external_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "comparison.html"
            export_dashboard(output)
            html = output.read_text()
            marker = '<script id="cache-data" type="application/json">'
            embedded = html.split(marker, 1)[1].split("</script>", 1)[0]
            self.assertEqual(json.loads(embedded), load_dashboard(ROOT))
            self.assertNotIn('src="/assets/', html)
            self.assertNotIn('href="/assets/', html)
            self.assertIn("connect-src 'none'", html)
