import json
import tempfile
import unittest
from pathlib import Path

from psf_lab.benchmark import benchmark, make_fixture, summarize
from psf_lab.parser.semantic import parse_trace


class BenchmarkTests(unittest.TestCase):
    def test_fixed_binary_is_supported_and_deterministic(self):
        raw = make_fixture(1000)
        trace = parse_trace(raw)
        self.assertEqual(raw, make_fixture(1000))
        self.assertEqual(len(trace["events"]), 1000)
        self.assertEqual(trace["quality"]["issues"], [])

    def test_invalid_counts_and_empty_durations(self):
        for count in [0, -1, 200001, True, 1.5]:
            with self.subTest(count=count), self.assertRaises(ValueError):
                make_fixture(count)
        self.assertEqual(summarize([]), {"median_ms": None, "p95_ms": None})
        self.assertEqual(summarize([1, 2, 3, 4, 100]), {"median_ms": 3, "p95_ms": 100})
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                benchmark([], Path(d))

    def test_subprocess_measurements_finite_and_separated(self):
        with tempfile.TemporaryDirectory() as d:
            report = benchmark([20], Path(d))
            row = report["results"][0]
            self.assertEqual(len(row["parse_ms"]), 5)
            self.assertEqual(row["event_count"], 20)
            self.assertGreater(row["peak_rss_bytes"], 0)
            self.assertGreater(row["tracemalloc_peak_bytes"], 0)
            json.dumps(report, allow_nan=False)
