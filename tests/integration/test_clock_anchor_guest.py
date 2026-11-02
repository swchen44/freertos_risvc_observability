"""Same-ELF marker modes and malformed command lines on the pinned QEMU."""

import json
import os
import unittest

from psf_lab.parser.semantic import parse_trace
from tests.integration.clock_anchor_support import capture_probe, load_runtime_config


@unittest.skipUnless(os.environ.get("C2B_REQUIRE_QEMU") == "1", "C2b runtime not-performed; opt in")
class ClockAnchorGuestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_runtime_config()

    def test_same_elf_modes_and_real_psf(self):
        hashes = []
        for mode in (0, 1):
            run = capture_probe(self.config, f"c2b-markers={mode}", f"mode-{mode}")
            self.assertFalse(run["timed_out"])
            self.assertEqual(run["exit"], 0)
            out = run["output"]
            oracle = json.loads((out / "oracle.json").read_text())
            self.assertTrue(oracle["complete"])
            self.assertEqual(oracle["clock_marker_mode"], mode)
            self.assertEqual(oracle["clock_marker_count"], 5 if mode else 0)
            trace = parse_trace((out / "trace.psf").read_bytes())
            events = [e for e in trace["events"] if e["fields"].get("channel") == "C2B"]
            self.assertEqual(len(events), 5 if mode else 0)
            for i, e in enumerate(events, 1):
                self.assertEqual(e["fields"]["format"], "C2Bv1|%u|%u|%u|%u")
                self.assertEqual(e["fields"]["arguments"][:2], [str(i), str(i)])
                self.assertEqual(e["quality"], [])
            hashes.append(run["elf_sha256"])
        self.assertEqual(hashes[0], hashes[1])

    def test_missing_long_invalid_and_extra_argument_fail_before_capture(self):
        for label, arg in (
            ("missing", None),
            ("long", "c2b-markers=1" + "x" * 64),
            ("invalid", "c2b-markers=2"),
            ("extra", "c2b-markers=1,arg=extra"),
        ):
            with self.subTest(label=label):
                run = capture_probe(self.config, arg, label)
                self.assertFalse(run["timed_out"])
                self.assertNotEqual(run["exit"], 0)
                self.assertFalse((run["output"] / "oracle.json").exists())
                self.assertIn(
                    "C2b invalid marker mode", (run["output"] / "console.log").read_text()
                )
