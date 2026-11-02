"""Independent causal failures must carry specific machine-readable reasons."""

import copy
import csv
import gzip
import tempfile
import tracemalloc
import unittest
from pathlib import Path

from psf_lab.clock_anchor_evidence import scan_evidence
from psf_lab.clock_anchor_wire import ClockEvidenceError, iter_access_rows, iter_clock_records
from tests.fixtures.clock_anchor import record, write_wire
from tests.fixtures.clock_anchor_semantic import marker_fixture, semantic_fixture


class ClockScanTests(unittest.TestCase):
    def test_plain_and_gzip_produce_identical_causal_summary(self):
        f = semantic_fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            clock = root / "clock.jsonl"
            raw = root / "accesses.csv"
            write_wire(clock, f.records)
            with raw.open("w", newline="") as stream:
                columns = [k for k in f.accesses[0] if k != "index"]
                writer = csv.DictWriter(stream, fieldnames=columns)
                writer.writeheader()
                writer.writerows(
                    {k: v for k, v in row.items() if k != "index"} for row in f.accesses
                )
            # Wire column order is fixed; fixture dictionaries put operation before costs.
            self.assertEqual(
                raw.read_text().splitlines()[0],
                "pc,address,size,operation,l1i,l1d,l2,ram_read,ram_write",
            )
            expected = scan_evidence(iter_clock_records(clock), iter_access_rows(raw), f.expected)
            for path in (clock, raw):
                path.with_suffix(path.suffix + ".gz").write_bytes(gzip.compress(path.read_bytes()))
            actual = scan_evidence(
                iter_clock_records(root / "clock.jsonl.gz"),
                iter_access_rows(root / "accesses.csv.gz"),
                f.expected,
            )
            self.assertEqual(actual, expected)

    def test_fifo_and_end_then_applied(self):
        f = semantic_fixture()
        result = scan_evidence(iter(f.records), iter(f.accesses), f.expected)
        self.assertEqual(result["pending"], "0")
        self.assertEqual(result["requests"], "3")
        self.assertEqual(result["injected_ns"], "12")
        self.assertEqual(result["max_queue_cursor_distance"], "2")
        self.assertEqual(result["raw_rows"], "3")

    def test_individual_causal_corruptions_fail_with_specific_codes(self):
        f = semantic_fixture()
        for index, changes, code in (
            (2, dict(request_id="0"), "request_order"),
            (3, dict(request_id="1"), "request_order"),
            (3, dict(delta_ns="5"), "request_cost"),
            (3, dict(request_event_index="0"), "request_row"),
            (6, dict(request_id="2"), "apply_order"),
            (6, dict(requested_target_ns="1003"), "apply_target"),
            (7, dict(raw_cursor="2"), "cursor_order"),
            (9, dict(pending="1"), "footer_counts"),
            (0, dict(elf_sha256="f" * 64), "identity"),
        ):
            bad = copy.deepcopy(f.records)
            bad[index].update(changes)
            with (
                self.subTest(code=code, changes=changes),
                self.assertRaises(ClockEvidenceError) as c,
            ):
                scan_evidence(iter(bad), iter(f.accesses), f.expected)
            self.assertEqual(c.exception.code, code)
        with self.assertRaises(ClockEvidenceError) as c:
            scan_evidence(iter(f.records[:-1]), iter(f.accesses), f.expected)
        self.assertEqual(c.exception.code, "missing_footer")
        with self.assertRaises(ClockEvidenceError) as c:
            scan_evidence(iter(f.records), iter(f.accesses), f.expected, pending_limit=2)
        self.assertEqual(c.exception.code, "pending_limit")

    def test_native_formula_pairing_frequency_and_epoch(self):
        f = marker_fixture()
        good = scan_evidence(iter(f.records), iter(f.accesses), f.expected)
        self.assertEqual(len(good["markers"]), 5)
        for index, changes, code in (
            (3, dict(mtime64="109"), "native_formula"),
            (3, dict(value32="109"), "native_word"),
            (4, dict(address=str(0x0200BFFC)), "io_pair"),
            (3, dict(timebase_hz="1000000"), "frequency_unavailable"),
            (5, dict(marker_phase="2"), "marker_order"),
        ):
            bad = copy.deepcopy(f.records)
            bad[index].update(changes)
            with self.subTest(code=code), self.assertRaises(ClockEvidenceError) as c:
                scan_evidence(bad, f.accesses, f.expected)
            self.assertEqual(c.exception.code, code)

    def test_raw_extra_or_short_and_footer_after_data_rejected(self):
        f = semantic_fixture()
        for raw, records in (
            (f.accesses[:-1], f.records),
            (f.accesses + [f.accesses[-1]], f.records),
            (f.accesses, f.records + [f.records[-1]]),
        ):
            with self.assertRaises(ClockEvidenceError):
                scan_evidence(records, raw, f.expected)

    def test_epoch_change_is_not_silently_rebased(self):
        f = marker_fixture()
        f.records[3] = record(
            "epoch_change", 3, 2, "device_epoch", reason="reset", old_value=None, new_value=None
        )
        with self.assertRaises(ClockEvidenceError) as caught:
            scan_evidence(f.records, f.accesses, f.expected)
        self.assertEqual(caught.exception.code, "epoch_change")

    def test_marker_pc_must_match_actual_next_instruction_and_pinned_hook(self):
        f = marker_fixture()
        f.records[5]["pc"] = str(int(f.records[5]["pc"]) + 2)
        with self.assertRaises(ClockEvidenceError) as caught:
            scan_evidence(f.records, f.accesses, f.expected)
        self.assertEqual(caught.exception.code, "marker_instruction")
        f = marker_fixture()
        f.expected["marker_pcs"] = {"enter_pc": 1, "sampled_pc": 2, "leave_pc": 3}
        with self.assertRaises(ClockEvidenceError) as caught:
            scan_evidence(f.records, f.accesses, f.expected)
        self.assertEqual(caught.exception.code, "marker_pc")

    def test_consumed_rows_do_not_accumulate_in_memory(self):
        fixture = semantic_fixture()

        def peak(count):
            expected = dict(fixture.expected, raw_rows=count)

            def records():
                yield fixture.records[0]
                yield record("capture_begin", 1, 0, "before_guest_instruction")
                for i in range(count):
                    yield record(
                        "cost_request",
                        2 + i * 2,
                        i + 1,
                        "instruction_before",
                        request_id=str(i + 1),
                        request_event_index=str(i),
                        delta_ns="2",
                        request_clock_ns=None,
                        pc="2147483648",
                    )
                    yield record(
                        "cost_applied",
                        3 + i * 2,
                        i + 1,
                        "cpu_async_outside_exec",
                        request_id=str(i + 1),
                        before_ns=str(i * 2),
                        requested_target_ns=str(i * 2 + 2),
                        advance_return_ns=str(i * 2 + 2),
                        after_ns=str(i * 2 + 2),
                    )
                yield record("capture_end", 2 + count * 2, count, "before_guest_instruction")
                yield record(
                    "footer",
                    3 + count * 2,
                    count,
                    "finished",
                    complete=True,
                    raw_rows=str(count),
                    requests=str(count),
                    applied=str(count),
                    pending="0",
                    device_io="0",
                    plugin_io="0",
                    record_count=str(4 + count * 2),
                )

            raw = (dict(fixture.accesses[0], index=i) for i in range(count))
            tracemalloc.start()
            try:
                result = scan_evidence(records(), raw, expected)
                memory = tracemalloc.get_traced_memory()[1]
            finally:
                tracemalloc.stop()
            self.assertEqual(result["max_pending"], "1")
            return memory

        small, large = peak(1000), peak(12000)
        self.assertLess(large, small + 250000)
        self.assertLess(large, 1000000)
