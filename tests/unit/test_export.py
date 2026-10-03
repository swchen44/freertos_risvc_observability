import csv
import io
import unittest

from psf_lab.export import export_csv
from tests.fixtures.query_trace import trace_250


class ExportTests(unittest.TestCase):
    def test_all_filtered_rows_with_quoting(self):
        t = trace_250()
        rows = list(
            csv.DictReader(
                io.StringIO(
                    export_csv(
                        t,
                        {},
                        {"start_ticks": "10", "end_ticks": "240"},
                        [{"field": "ticks", "direction": "desc"}],
                    )
                )
            )
        )
        self.assertEqual(len(rows), 230)
        self.assertEqual(rows[0]["ticks"], "239")
        self.assertEqual(rows[0]["message"], '文字,"含引號"\n換行')

    def test_formula_protection_and_raw_unchanged(self):
        for text in ["=1+1", "+sum(A1)", "-formula", "@x", "\tfoo", "\rfoo"]:
            t = trace_250()
            t["events"] = t["events"][:1]
            t["events"][0]["fields"]["message"] = text
            row = next(csv.DictReader(io.StringIO(export_csv(t, {}, {}, []))))
            self.assertEqual(row["message"], "'" + text)
            self.assertEqual(row["spreadsheet_escaped"], "true")
            self.assertEqual(t["events"][0]["fields"]["message"], text)

    def test_empty_csv_still_has_header(self):
        t = trace_250()
        t["events"] = []
        self.assertIn("event_id", export_csv(t, {}, {}, []).splitlines()[0])
