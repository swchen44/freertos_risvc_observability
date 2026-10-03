"""Reproduce final review findings with hand-packed PSF and independent expectations."""

import csv
import io
import struct
import unittest

from psf_lab.analysis import analyze
from psf_lab.export import export_csv
from psf_lab.parser.semantic import parse_trace
from psf_lab.query import query_view
from tests.fixtures.binary import event, stream


def counter_event(value, *, width=4, sequence=0):
    unsigned = value % (1 << (8 * width))
    raw = (4).to_bytes(width, "little") + unsigned.to_bytes(width, "little") + b"Counter: %d\0"
    raw += bytes(-len(raw) % width)
    payload = struct.unpack("<" + ("I" if width == 4 else "Q") * (len(raw) // width), raw)
    return event(0x92 if width == 4 else 0x52, sequence, sequence * 100, payload, width)


class ReviewRegressionTests(unittest.TestCase):
    def test_signed_counter_matches_formatted_value_in_both_schemas(self):
        for width in [4, 8]:
            for value in [-1, -(1 << (width * 8 - 1)), 0, 7]:
                with self.subTest(width=width, value=value):
                    trace = parse_trace(stream(counter_event(value, width=width), width=width))
                    fields = trace["events"][0]["fields"]
                    self.assertEqual(fields["message"], f"Counter: {value}")
                    self.assertEqual(fields["counter"], value)
                    self.assertEqual(fields["arguments"], [str(value % (1 << (width * 8)))])

    def test_unknown_and_zero_windows_survive_metrics_csv(self):
        trace = parse_trace(stream(event(0x31, 0, 0, (0,)), event(0x31, 1, 100, (1,))))
        for filters, expected in [({}, "100"), ({"start_ticks": "200", "end_ticks": "210"}, "10")]:
            rows = list(
                csv.DictReader(
                    io.StringIO(export_csv(trace, analyze(trace), filters, [], kind="metrics"))
                )
            )
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["unknown_ticks"], expected)
            self.assertEqual(rows[0]["known_ticks"], "0")
            self.assertEqual(rows[0]["task_id"], "")
            self.assertEqual(rows[0]["fraction"], "")
        empty = parse_trace(stream())
        rows = list(
            csv.DictReader(io.StringIO(export_csv(empty, analyze(empty), {}, [], kind="metrics")))
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["window_ticks"], "0")
        self.assertEqual(rows[0]["fraction"], "")

    def test_signal_display_limit_has_explicit_scope(self):
        trace = parse_trace(stream(*(counter_event(i, sequence=i) for i in range(2001))))
        view = query_view(trace, analyze(trace), {})
        self.assertEqual(view["signal_total"], 2001)
        self.assertEqual(len(view["signals"]), 2000)
        limits = view["display_limits"]["signals"]
        self.assertEqual(limits["shown"], 2000)
        self.assertEqual(limits["total"], 2001)
        self.assertTrue(limits["truncated"])
        self.assertEqual(limits["mode"], "first_n")
        self.assertEqual(limits["start_ticks"], "0")
        self.assertEqual(limits["end_ticks"], "199900")
        analysis = analyze(trace)
        analysis["requests"] = [
            {
                "request_id": i,
                "start_ticks": str(i * 100),
                "end_ticks": str(i * 100 + (9999 if i == 2000 else 10)),
                "response_ticks": "9999" if i == 2000 else "10",
                "execution_ticks": None,
            }
            for i in range(2001)
        ]
        other = query_view(trace, analysis, {"end_ticks": "300000"})
        self.assertEqual(other["display_limits"]["requests"]["shown"], 2000)
        self.assertTrue(other["display_limits"]["requests"]["truncated"])
        self.assertEqual(other["request_stats"]["max_ticks"], "9999")
