import copy
import json
import unittest
from pathlib import Path

from psf_lab.tcp_workload import load_workload
from psf_lab.timing_dashboard import validate_comparison

ROOT = Path(__file__).resolve().parents[2]


class MatrixDashboardTests(unittest.TestCase):
    def data(self):
        source = json.loads(
            (ROOT / "artifacts/verification/tcp-os-small-cache/results/comparison.json").read_text()
        )
        base = next(r for r in source["results"] if r["label"] == "baseline")
        rows = []
        for i in range(1, 9):
            for variant in ("baseline", "pbuf"):
                row = copy.deepcopy(base)
                row.update(
                    label=f"A{i:02}-{variant}",
                    workload_id=f"A{i:02}",
                    variant=variant,
                    workload=load_workload(ROOT / "cases/tcp/workload-matrix-v1.json", f"A{i:02}"),
                )
                rows.append(row)
        return dict(schema="tcp-workload-matrix-v1", passed=True, results=rows)

    def test_complete_matrix_accepted(self):
        validate_comparison(self.data(), "tcp-workload-matrix-v1")

    def test_wrong_workload_identity_rejected(self):
        d = self.data()
        d["results"][0]["workload"]["id"] = "A02"
        with self.assertRaises(ValueError):
            validate_comparison(d, "tcp-workload-matrix-v1")

    def test_missing_candidate_rejected(self):
        d = self.data()
        d["results"].pop()
        with self.assertRaises(ValueError):
            validate_comparison(d, "tcp-workload-matrix-v1")

    def test_same_id_different_workload_rejected(self):
        data = self.data()
        row = next(r for r in data["results"] if r["label"] == "A01-pbuf")
        row["workload"]["request_bytes"] = 65
        row["workload"]["request_segments"] = [65]
        with self.assertRaisesRegex(ValueError, "workload"):
            validate_comparison(data, "tcp-workload-matrix-v1")

    def test_missing_report_hash_rejected(self):
        from tempfile import TemporaryDirectory

        from psf_lab.timing_dashboard import load_dashboard

        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "cases/timing").mkdir(parents=True)
            (root / "cases/timing/dashboard-sources.json").write_text('{"files": {}}')
            with self.assertRaisesRegex(ValueError, "Missing required evidence hash"):
                load_dashboard(root)
