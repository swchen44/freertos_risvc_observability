"""Hook symbols must identify actual instructions in the same ELF evidence."""

import copy
import tempfile
import unittest
from pathlib import Path

from psf_lab.clock_anchor_boundaries import derive_boundaries
from tests.unit.test_context_boundaries import toy_elf


def marker_evidence(path, base=0x80000000):
    evidence = toy_elf(path, base)
    evidence["tool_outputs"]["nm"] += (
        f"\n{base + 12:08x} 00000004 T poc_clock_anchor_enter"
        f"\n{base + 20:08x} 00000004 T poc_clock_anchor_sampled"
        f"\n{base + 24:08x} 00000004 T poc_clock_anchor_leave"
    )
    return evidence


class ClockAnchorBoundaryTests(unittest.TestCase):
    def test_each_candidate_uses_own_marker_and_context_pcs(self):
        with tempfile.TemporaryDirectory() as tmp:
            for base in (0x80000000, 0x80001000):
                e = marker_evidence(Path(tmp) / "firmware.elf", base)
                result = derive_boundaries(e)
                self.assertEqual(
                    result["marker_pcs"],
                    dict(enter_pc=base + 12, sampled_pc=base + 20, leave_pc=base + 24),
                )
                self.assertEqual(result["context"]["capture_begin_pc"], base)
                self.assertEqual(result["context"]["mret_pcs"], [base + 48])

    def test_missing_duplicate_clone_mid_instruction_and_other_map_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "firmware.elf"
            valid = marker_evidence(path)
            for mutation in ("missing", "duplicate", "clone", "middle", "other-map"):
                e = copy.deepcopy(valid)
                nm = e["tool_outputs"]["nm"]
                if mutation == "missing":
                    nm = nm.replace("poc_clock_anchor_leave", "absent")
                elif mutation == "duplicate":
                    nm += "\n8000000c 00000004 T poc_clock_anchor_enter"
                elif mutation == "clone":
                    nm += "\n80000028 00000004 T poc_clock_anchor_enter.constprop.0"
                elif mutation == "middle":
                    nm = nm.replace("8000000c", "8000000e")
                else:
                    e["map_records"][0]["start"] += 0x1000
                    e["map_records"][0]["end"] += 0x1000
                e["tool_outputs"]["nm"] = nm
                with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                    derive_boundaries(e)
