"""Stage gates stop expansion before any new QEMU capture can be started."""

import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from psf_lab.clock_anchor_capture import run_pilot
from tests.unit.test_clock_anchor_analysis import analysis_identity


class PilotFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        (self.root / ".gitignore").write_text("runs/local/\n")
        self.output = self.root / "runs/local/smoke"
        self.tools = dict(
            candidates={c: dict(elf=dict(sha256="a" * 64)) for c in ("baseline", "pbuf")},
            legacy_qemu=dict(sha256="b" * 64),
            clock_qemu=dict(sha256="b" * 64),
            profile=dict(sha256="d" * 64, path="/fixture/profile"),
            plugins={p: dict(sha256="c" * 64) for p in ("legacy", "new")},
        )
        self.bad_alignment = False
        self.bad_packet = False

    def capture(self, root, spec, tools, elf, output):
        output.mkdir()
        (output / "trace.psf").write_bytes(b"hand-authored fixture")
        data = dict(
            status="captured-unvalidated",
            capture_source_commit="fixed",
            spec=dict(
                candidate=spec.candidate,
                configuration=spec.configuration,
                injection=spec.injection,
                repeat=1,
            ),
            expected=dict(configuration=spec.configuration),
            files={
                "trace.psf": dict(
                    bytes=21, sha256=hashlib.sha256(b"hand-authored fixture").hexdigest()
                )
            },
        )
        (output / "capture.json").write_text(json.dumps(data))
        return data

    def validate(self, run, expected):
        config = run.name.split("-")[1]
        result = analysis_identity(config)
        if config == "O":
            result["anchors"] = [dict(marker_seq=str(i)) for i in range(1, 6)]
        if self.bad_alignment and config == "O":
            result["alignment_status"] = "unavailable"
        if self.bad_packet and config == "M":
            result["packet_sha256"] = ["0" * 64]
        return result

    def controls(self):
        return (
            patch("psf_lab.clock_anchor_capture.require_clean_tree", return_value="fixed"),
            patch("psf_lab.clock_anchor_capture._validate_tools"),
            patch("psf_lab.clock_anchor_capture.capture_one", side_effect=self.capture),
            patch("psf_lab.clock_anchor_evidence.verify_clock_capture", side_effect=self.validate),
        )

    def test_full_revalidates_smoke_before_starting_any_new_capture(self):
        clean, tools, capture, validate = self.controls()
        with clean, tools, capture as owned, validate:
            result = run_pilot(self.root, self.output, self.tools, stage="smoke")
            self.assertTrue(result["smoke_passed"])
            owned.reset_mock()
            self.bad_alignment = True
            with self.assertRaisesRegex(ValueError, "Smoke"):
                run_pilot(self.root, self.output, self.tools, stage="full")
            owned.assert_not_called()

    def test_smoke_includes_marker_effect_application_gate(self):
        self.bad_packet = True
        clean, tools, capture, validate = self.controls()
        with clean, tools, capture, validate:
            result = run_pilot(self.root, self.output, self.tools, stage="smoke")
            self.assertFalse(result["smoke_passed"])
