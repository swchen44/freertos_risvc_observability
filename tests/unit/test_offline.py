"""Single-file packaging and cross-language query behavior."""

import csv
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from psf_lab.analysis import analyze
from psf_lab.export import export_csv
from psf_lab.query import query_events, query_view
from tests.fixtures.query_trace import trace_250

ROOT = Path(__file__).resolve().parents[2]


class OfflineTests(unittest.TestCase):
    def test_export_self_contained_and_safe(self):
        from psf_lab.offline import export_html

        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "report.html"
            result = export_html(ROOT / "fixtures/desktop/trace.psf", target)
            html = target.read_text()
            self.assertGreater(result["event_count"], 0)
            self.assertIn("psf-offline-data", html)
            self.assertNotIn('src="/assets/', html)
            self.assertNotIn('href="/assets/', html)
            self.assertIn("connect-src", html)
            self.assertIn("離線", html)

    def test_reject_input_overwrite_and_bad_psf(self):
        from psf_lab.offline import export_html

        with tempfile.TemporaryDirectory() as d:
            source = Path(d) / "bad.psf"
            source.write_bytes(b"not psf")
            with self.assertRaises(ValueError):
                export_html(source, source)
            with self.assertRaises(ValueError):
                export_html(source, Path(d) / "bad.html")
            self.assertFalse((Path(d) / "bad.html").exists())
            self.assertEqual(source.read_bytes(), b"not psf")

    def test_script_terminator_payload_is_inert(self):
        from psf_lab.offline import embed_json

        text = embed_json({"message": "</script><img onerror=alert(1)>\u2028&"})
        self.assertNotIn("<", text)
        self.assertEqual(json.loads(text)["message"], "</script><img onerror=alert(1)>\u2028&")

    def test_query_and_csv_parity(self):
        trace = trace_250()
        for e in trace["events"]:
            e["ticks"] = str(2**54 + int(e["ticks"]))
        trace["events"][0]["fields"]["message"] = '=HYPERLINK("x")\nStraße Σς İ'
        trace["events"][1]["ticks"] = None
        trace["events"][2]["fields"]["counter"] = -1
        trace["events"][3]["quality"] = ["loss"]
        analysis = analyze(trace)
        start = 2**54
        cases = [
            {},
            {"search": "STRASSE"},
            {"search": "σ"},
            {"search": "i\u0307"},
            {"start_ticks": str(start + 20), "end_ticks": str(start + 80)},
            {"task_ids": ["A"]},
            {"event_ids": [80]},
            {"search": "does not exist"},
        ]
        requests = []
        for filters in cases:
            sort = [{"field": "ticks", "direction": "desc"}]
            requests.append({"filters": filters, "sort": sort})
        self.assert_parity(trace, analysis, requests)

    def assert_parity(self, trace, analysis, requests):
        payload = {"trace": trace, "analysis": analysis, "queries": requests}
        # Casefold mapping comes from Python's Unicode version, not JS locale rules.
        from psf_lab.offline import casefold_map

        payload["casefold"] = casefold_map()
        script = """import {queryEvents, queryView, exportCSV} from './web/src/offline-query.js';
let raw=''; for await (const c of process.stdin) raw+=c;
const p=JSON.parse(raw); console.log(JSON.stringify(p.queries.map(q=>({
 events:queryEvents(p.trace,q.filters,q.sort,0,2,p.casefold),
 view:queryView(p.trace,p.analysis,q.filters,p.casefold),
 csv:exportCSV(p.trace,p.analysis,q.filters,q.sort,'events',p.casefold),
 metrics:exportCSV(p.trace,p.analysis,q.filters,q.sort,'metrics',p.casefold)
}))));"""
        proc = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            cwd=ROOT,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for q, got in zip(requests, json.loads(proc.stdout), strict=True):
            with self.subTest(query=q):
                self.assertEqual(
                    got["events"], query_events(trace, q["filters"], q["sort"], limit=2)
                )
                self.assertEqual(got["view"], query_view(trace, analysis, q["filters"]))
                for key, kind in [("csv", "events"), ("metrics", "metrics")]:
                    expected = export_csv(trace, analysis, q["filters"], q["sort"], kind=kind)
                    actual_rows = list(csv.DictReader(io.StringIO(got[key])))
                    expected_rows = list(csv.DictReader(io.StringIO(expected)))
                    for rows in [actual_rows, expected_rows]:
                        for row in rows:
                            if row.get("fraction"):
                                row["fraction"] = float(row["fraction"])
                    self.assertEqual(actual_rows, expected_rows)

    def test_real_captures_parity(self):
        from psf_lab.parser.semantic import parse_trace

        suite = ROOT / "runs/suite-20261003T085652Z-2732b56355"
        for case in [
            "queue_baseline",
            "logger_bad",
            "logger_fixed",
            "inversion",
            "inheritance",
            "deadlock_abba",
            "ordered_locks",
        ]:
            psf = next(suite.glob("*-" + case + "-*/trace.psf"))
            trace = parse_trace(psf.read_bytes(), source_name=psf.name, strict=False)
            analysis = analyze(trace)
            start = int(analysis["metrics"]["start_ticks"])
            end = int(analysis["metrics"]["end_ticks"])
            with self.subTest(case=case):
                self.assert_parity(
                    trace,
                    analysis,
                    [
                        {"filters": {}, "sort": []},
                        {
                            "filters": {
                                "start_ticks": str(start + (end - start) // 4),
                                "end_ticks": str(start + (end - start) // 2),
                            },
                            "sort": [{"field": "kind", "direction": "desc"}],
                        },
                        {"filters": {"task_ids": [trace["objects"][0]["object_id"]]}, "sort": []},
                    ],
                )

    def test_density_and_truncation_parity(self):
        trace = trace_250()
        trace["events"] = [
            dict(
                trace["events"][0],
                event_id=f"0:{i}",
                offset=i,
                ticks=str(i),
                fields={"counter": -i},
            )
            for i in range(2105)
        ]
        analysis = {
            "intervals": [
                {
                    "object_id": "A",
                    "start_ticks": str(i),
                    "end_ticks": str(i + 1),
                    "state": "running",
                    "quality": [],
                }
                for i in range(2105)
            ],
            "requests": [],
            "metrics": {"start_ticks": "0", "end_ticks": "2105"},
            "quality": {},
        }
        self.assert_parity(trace, analysis, [{"filters": {}, "sort": []}])

    def test_empty_parity(self):
        trace = trace_250()
        trace["events"] = []
        self.assert_parity(trace, analyze(trace), [{"filters": {}, "sort": []}])
