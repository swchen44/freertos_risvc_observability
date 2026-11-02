"""Exact transparency, signed marker deltas and portable report encoding."""

import copy
import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from psf_lab.clock_anchor_analysis import (
    bound_statistics,
    compare_marker_effect,
    compare_transparent,
    group_comparisons,
    write_csv_rows,
    write_pilot_report,
)


def analysis_identity(config, *, cycles=100, elapsed_ns=1000):
    mode = 0 if config == "M" else 1
    return dict(
        configuration=config,
        candidate="baseline",
        elf_sha256="a" * 64,
        qemu_sha256="b" * 64,
        plugin_sha256="c" * 64,
        profile_sha256="d" * 64,
        injection_enabled=True,
        observer_enabled=config in ("O", "M"),
        marker_mode=mode,
        run_id="fixture-" + config,
        evidence_status="valid",
        application_status="passed",
        alignment_status="verified-bounds" if config == "O" else "unavailable",
        packet_sha256=["e" * 64, "f" * 64],
        psf_sha256="1" * 64,
        raw_stream_sha256="2" * 64,
        context_stream_sha256="3" * 64,
        model_cycles=str(cycles),
        raw_rows="20",
        psf_bytes="1000",
        marker_bytes=str(mode * 160),
        audit=dict(
            events=20,
            cycles=cycles,
            ns=cycles * 2,
            operations=dict(I=10, R=5, W=5),
            costs=dict(l1i=10, l1d=90, l2=0, ram_read=0, ram_write=0),
        ),
        measurement=dict(before=100, after=100 + elapsed_ns // 100, ticks=2, woke=1, work=11680),
        oracle=dict(
            case_id="tcp_request_response",
            complete=True,
            outcome="normal",
            transport_ok=True,
            mtime_hz=10000000,
            tick_hz=1000,
            sent_ids=[11680],
            received_ids=[11680],
            clock_marker_mode=mode,
            clock_marker_count=mode * 5,
        ),
        session=dict(
            acked_bytes=11680,
            request_bytes=128,
            retained_bytes=0,
            peak_retained_bytes=1460,
            active_pcbs=0,
            timewait_pcbs=0,
            peer_closed=True,
            resources_before=[0] * 6,
            resources_after=[0] * 6,
        ),
        tcp=dict(packets=25, unique_response_bytes=11680, request_bytes=128),
        switches=[],
        context=dict(quality="exact", intervals=[dict(start=0, end=20, context="task:1")]),
        host_wall_seconds=0.1,
        host_child_cpu_seconds=None,
        anchors=[],
        intervals=[],
        covered_rows="0",
        unknown_rows="20",
    )


class ClockAnalysisTests(unittest.TestCase):
    def test_bound_statistics_use_exact_median_and_do_not_rate_resolution(self):
        rows = [
            dict(
                anchors=[
                    dict(
                        lower_ns="100",
                        upper_ns="200",
                        bracket_start="0",
                        bracket_end="3",
                        cursor_min="2",
                        cursor_max="2",
                        sample_to_sdk_ticks="1",
                    ),
                    dict(
                        lower_ns="200",
                        upper_ns="300",
                        bracket_start="3",
                        bracket_end="9",
                        cursor_min="7",
                        cursor_max="8",
                        sample_to_sdk_ticks="5",
                    ),
                ]
            )
        ]
        result = bound_statistics(rows)
        self.assertEqual(result["hook_bracket_rows"], dict(min="3", median="4.5", max="6"))
        self.assertEqual(result["sdk_quantum_ns"], dict(min="100", median="100", max="100"))
        self.assertEqual(result["resolution_assessment"], "unrated")

    def test_group_cannot_claim_verified_bounds_without_five_anchors(self):
        rows = [analysis_identity(c) for c in "LCOM"]
        self.assertFalse(group_comparisons(rows)[0]["passed"])

    def test_report_keeps_all_sixteen_identities_and_csv_matches_json(self):
        from dataclasses import asdict

        from psf_lab.clock_anchor_capture import pilot_matrix
        from psf_lab.runner import digest

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runset = root / "runset"
            runset.mkdir()
            tools = dict(
                candidates={c: dict(elf=dict(sha256="a" * 64)) for c in ("baseline", "pbuf")},
                legacy_qemu=dict(sha256="b" * 64),
                clock_qemu=dict(sha256="b" * 64),
                profile=dict(sha256="d" * 64, path="/fixture/profile"),
                plugins={p: dict(sha256="c" * 64) for p in ("legacy", "new")},
            )
            specs = pilot_matrix()
            entries = []
            for spec in specs:
                run = runset / spec.run_id
                run.mkdir()
                (run / "capture.json").write_text(
                    json.dumps(dict(capture_source_commit="fixed", tools=tools))
                )
                entries.append(
                    dict(
                        spec=asdict(spec),
                        run_id=spec.run_id,
                        path=spec.run_id,
                        capture_sha256=digest(run / "capture.json"),
                    )
                )
            (runset / "runset.json").write_text(
                json.dumps(
                    dict(
                        schema="clock-anchor-runset-v1",
                        source_commit="fixed",
                        tools=tools,
                        requested_runs=[asdict(s) for s in specs],
                        runs=entries,
                    )
                )
            )

            def validate(run, expected):
                result = analysis_identity(expected["configuration"])
                result.update({k: v for k, v in expected.items() if k != "raw_rows"})
                if expected["configuration"] == "O":
                    result["scan"] = dict(max_queue_cursor_distance="2")
                    result["anchors"] = [
                        dict(
                            marker_seq=str(i),
                            lower_ns="10000",
                            upper_ns="10100",
                            bracket_start="0",
                            bracket_end="3",
                            sample64="100",
                            cursor_min="2",
                            cursor_max="2",
                            sample_to_sdk_ticks="1",
                            psf_offset=str(500 + i * 32),
                            exclusive_cpu_status="unavailable",
                        )
                        for i in range(1, 6)
                    ]
                return result

            with (
                patch("psf_lab.clock_anchor_analysis._validate_tools"),
                patch("psf_lab.clock_anchor_analysis.verify_clock_capture", side_effect=validate),
                patch("psf_lab.clock_anchor_analysis._code_sizes", return_value={}),
            ):
                report = write_pilot_report(runset, root / "report")
            self.assertEqual(report["status"], "complete")
            self.assertEqual(len({r["run_id"] for r in report["runs"]}), 16)
            self.assertEqual(len(report["comparisons"]), 4)
            with (root / "report/anchors.csv").open(newline="") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 20)
            self.assertEqual(
                {r["run_id"] for r in rows},
                {r["run_id"] for r in report["runs"] if r["configuration"] == "O"},
            )

    def test_transparency_and_marker_denominator_are_separate(self):
        control = analysis_identity("C")
        observed = analysis_identity("O")
        self.assertTrue(compare_transparent(control, observed)["passed"])
        observed["raw_stream_sha256"] = "f" * 64
        self.assertFalse(compare_transparent(control, observed)["passed"])
        effect = compare_marker_effect(
            analysis_identity("O", cycles=110, elapsed_ns=1200), analysis_identity("M")
        )
        self.assertEqual(effect["model_cycles_delta"], "10")
        self.assertEqual(effect["model_cycles_denominator"], "100")
        self.assertEqual(effect["model_cycles_percent"], "10.000000")
        self.assertEqual(effect["guest_elapsed_ns_delta"], "200")
        self.assertEqual(effect["guest_elapsed_ns_percent"], "20.000000")

    def test_no_timestamp_normalization_missing_artifact_or_cross_identity(self):
        reference = analysis_identity("L")
        observed = analysis_identity("C")
        for key, value in (
            ("psf_sha256", "9" * 64),
            ("oracle", {}),
            ("measurement", {}),
            ("packet_sha256", []),
            ("session", {}),
        ):
            with self.subTest(key=key):
                bad = copy.deepcopy(observed)
                bad[key] = value
                self.assertFalse(compare_transparent(reference, bad)["passed"])
        bad = copy.deepcopy(observed)
        del bad["psf_sha256"]
        self.assertFalse(compare_transparent(reference, bad)["passed"])
        for change in (
            dict(candidate="pbuf"),
            dict(elf_sha256="f" * 64),
            dict(injection_enabled=False),
        ):
            with self.assertRaises(ValueError):
                compare_transparent(reference, observed | change)
        with self.assertRaises(ValueError):
            compare_marker_effect(analysis_identity("M"), analysis_identity("O"))
        result = compare_transparent(
            analysis_identity("C"), analysis_identity("O") | dict(alignment_status="unavailable")
        )
        self.assertTrue(result["passed"])
        self.assertFalse(result["alignment_verified"])

    def test_negative_and_zero_denominators_and_packet_gate(self):
        effect = compare_marker_effect(analysis_identity("O", cycles=90), analysis_identity("M"))
        self.assertEqual(effect["model_cycles_delta"], "-10")
        self.assertEqual(effect["model_cycles_percent"], "-10.000000")
        effect = compare_marker_effect(analysis_identity("O"), analysis_identity("M", cycles=0))
        self.assertIsNone(effect["model_cycles_percent"])
        self.assertEqual(effect["model_cycles_percent_reason"], "zero-denominator")
        effect = compare_marker_effect(
            analysis_identity("O"), analysis_identity("M") | dict(packet_sha256=[])
        )
        self.assertFalse(effect["passed"])

    def test_marker_effect_compares_application_outcome_not_only_packet_bytes(self):
        on, off = analysis_identity("O"), analysis_identity("M")
        on["oracle"]["outcome"] = "failed"
        off["oracle"]["outcome"] = "normal"
        self.assertFalse(compare_marker_effect(on, off)["passed"])

    def test_csv_preserves_signed_numeric_precision_but_escapes_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.csv"
            rows = [
                dict(label="=SUM(A1:A2)", model_cycles_delta="-10", counter="18446744073709551615"),
                dict(label="@remote", model_cycles_delta="0", counter="0"),
            ]
            write_csv_rows(path, rows, numeric_fields={"model_cycles_delta", "counter"})
            data = path.read_bytes()
            self.assertIn(b'"-10"', data)
            self.assertIn(b"\r\n", data)
            self.assertNotIn(b"\n", data.replace(b"\r\n", b""))
            with path.open(newline="") as f:
                read = list(csv.DictReader(f))
            self.assertEqual(read[0]["label"], "'=SUM(A1:A2)")
            self.assertEqual(read[0]["model_cycles_delta"], "-10")
            self.assertEqual(read[0]["counter"], "18446744073709551615")
            self.assertEqual(read[0]["spreadsheet_escaped"], "true")

    def test_empty_partial_report_is_reviewable_and_cli_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runset = root / "runset"
            runset.mkdir()
            (runset / "runset.json").write_text(
                json.dumps(
                    dict(
                        schema="clock-anchor-runset-v1",
                        runs=[],
                        source_commit="a" * 40,
                        tools={},
                        requested_runs=[],
                    )
                )
            )
            result = write_pilot_report(runset, root / "report")
            self.assertEqual(result["status"], "partial")
            self.assertEqual(result["runs"], [])
            self.assertIn("mermaid", (root / "report/report.md").read_text())
            with self.assertRaises(FileExistsError):
                write_pilot_report(runset, root / "report")
            cli = Path(__file__).resolve().parents[2] / "tools/tcp/analyze_clock_anchor_pilot.py"
            p = subprocess.run(
                [sys.executable, str(cli), "--runset", str(runset), "--output", str(root / "cli")],
                capture_output=True,
                timeout=10,
            )
            self.assertEqual(p.returncode, 1)
            self.assertEqual(
                json.loads((root / "cli/summary.json").read_text())["status"], "partial"
            )
