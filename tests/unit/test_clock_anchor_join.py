"""Bounds are observations, never interpolated point timestamps."""

import copy
import unittest

from psf_lab.clock_anchor_evidence import extract_psf_markers, join_anchor_bounds, scan_evidence
from psf_lab.clock_anchor_wire import ClockEvidenceError
from psf_lab.parser.semantic import parse_trace
from tests.fixtures.clock_anchor import psf_markers
from tests.fixtures.clock_anchor_semantic import marker_fixture


class ClockJoinTests(unittest.TestCase):
    def test_five_bounds_prefix_suffix_and_no_point_timestamps(self):
        f = marker_fixture()
        scan = scan_evidence(f.records, f.accesses, f.expected)
        trace = parse_trace(f.psf)
        result = join_anchor_bounds(iter(f.records), scan, trace)
        self.assertEqual(result["alignment_status"], "verified-bounds")
        self.assertEqual([int(a["cursor_min"]) for a in result["anchors"]], f.anchors)
        self.assertEqual(
            (result["anchors"][0]["lower_ns"], result["anchors"][0]["upper_ns"]), ("11100", "11200")
        )
        self.assertEqual(result["unknown_rows"], "5")
        self.assertEqual(result["covered_rows"], "20")
        self.assertEqual(result["intervals"][0]["start"], "4")
        self.assertEqual(result["intervals"][-1]["end"], "24")
        self.assertTrue(all("timestamp" not in interval for interval in result["intervals"]))

    def test_psf_sequence_phase_payload_and_quality(self):
        f = marker_fixture()
        trace = parse_trace(f.psf)
        self.assertEqual(len(extract_psf_markers(trace)), 5)
        for mutate in ("gap", "unknown", "duplicate", "swap", "missing"):
            bad = copy.deepcopy(trace)
            marker = next(e for e in bad["events"] if e["fields"].get("channel") == "C2B")
            if mutate == "gap":
                marker["quality"] = ["sequence_gap"]
            elif mutate == "unknown":
                bad["events"][0]["kind"] = "unknown"
            elif mutate == "duplicate":
                marker["fields"]["arguments"][1] = "2"
            elif mutate == "swap":
                marker["fields"]["arguments"][2:] = ["0", "110"]
            else:
                bad["events"].remove(marker)
            with self.subTest(mutate=mutate), self.assertRaises(ClockEvidenceError):
                scan = scan_evidence(f.records, f.accesses, f.expected)
                join_anchor_bounds(f.records, scan, bad)

    def test_wrong_app_sample_does_not_join(self):
        f = marker_fixture()
        f.records[5]["sample64"] = "111"
        scan = scan_evidence(f.records, f.accesses, f.expected)
        with self.assertRaises(ClockEvidenceError) as c:
            join_anchor_bounds(f.records, scan, parse_trace(f.psf))
        self.assertEqual(c.exception.code, "marker_payload")

    def test_ts32_and_eventcount16_wrap_preserve_full_native_counter(self):
        f = marker_fixture()
        shift = (1 << 32) - 125
        for row in f.records:
            if row["kind"] == "mtime_read" and row["source"] == "device":
                row["mtime64"] = str(int(row["mtime64"]) + shift)
                row["value32"] = str(int(row["mtime64"]) & 0xFFFFFFFF)
                row["virtual_ns"] = str(int(row["virtual_ns"]) + shift * 100)
            elif row["kind"] == "marker_sampled":
                row["sample64"] = str(int(row["sample64"]) + shift)
        trace = parse_trace(psf_markers(base=(1 << 32) - 25, sequence_start=65532))
        scan = scan_evidence(f.records, f.accesses, f.expected)
        result = join_anchor_bounds(f.records, scan, trace)
        self.assertEqual(result["anchors"][0]["sdk_mtime64"], "4294967282")
        self.assertEqual(result["anchors"][2]["timestamp_raw"], "6")

    def test_uint64_offset_wrap_uses_modular_quantum(self):
        f = marker_fixture()
        for row in f.records:
            if row["kind"] == "mtime_read" and row["source"] == "device":
                row["time_delta"] = str((1 << 64) - 1)
                row["mtime64"] = str(int(row["mtime64"]) - 1)
                row["value32"] = str(int(row["value32"]) - 1)
            elif row["kind"] == "marker_sampled":
                row["sample64"] = str(int(row["sample64"]) - 1)
        scan = scan_evidence(f.records, f.accesses, f.expected)
        result = join_anchor_bounds(f.records, scan, parse_trace(psf_markers(base=99)))
        self.assertEqual(result["anchors"][0]["lower_ns"], "11100")

    def test_missing_or_nonunique_sdk_candidate_cannot_be_picked_arbitrarily(self):
        f = marker_fixture()
        scan = scan_evidence(f.records, f.accesses, f.expected)
        for ambiguous in (False, True):
            rows = copy.deepcopy(f.records)
            sdk = copy.deepcopy(rows[6])
            if ambiguous:
                sdk["mtime64"] = str(int(sdk["mtime64"]) + (1 << 32))
                sdk["virtual_ns"] = str(int(sdk["virtual_ns"]) + (1 << 32) * 100)
                rows.insert(7, sdk)
            else:
                rows[6]["mtime64"] = "112"
            with self.subTest(ambiguous=ambiguous), self.assertRaises(ClockEvidenceError) as c:
                join_anchor_bounds(rows, scan, parse_trace(f.psf))
            self.assertEqual(
                c.exception.code,
                "ambiguous_full_counter" if ambiguous else "sdk_sample_unavailable",
            )

    def test_same_tick_keeps_quantum_and_marker_off_consumes_second_pass(self):
        f = marker_fixture()
        trace = parse_trace(f.psf)
        for row in f.records:
            if row["kind"] == "mtime_read" and row["source"] == "device":
                row.update(mtime64="111", value32="111", virtual_ns="11107")
            elif row["kind"] == "marker_sampled":
                row["sample64"] = "111"
        for event in trace["events"]:
            if event["fields"].get("channel") == "C2B":
                event["fields"]["arguments"][2:] = ["111", "0"]
                event.update(timestamp_raw=111, ticks="12")
        scan = scan_evidence(f.records, f.accesses, f.expected)
        result = join_anchor_bounds(f.records, scan, trace)
        self.assertEqual(
            {(a["lower_ns"], a["upper_ns"]) for a in result["anchors"]}, {("11100", "11200")}
        )
        trace["events"] = [e for e in trace["events"] if e["fields"].get("channel") != "C2B"]
        consumed = []

        def stream():
            for r in f.records:
                consumed.append(1)
                yield r

        result = join_anchor_bounds(stream(), dict(scan, marker_mode=0), trace)
        self.assertEqual(len(consumed), len(f.records))
        self.assertEqual(result["intervals"], [])
        self.assertEqual(result["unknown_rows"], "25")
