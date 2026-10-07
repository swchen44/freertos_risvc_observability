import importlib.util
import unittest


def event(seq, index, kind, task=None, cause=None, phase="before", depth=0):
    return dict(
        schema="context-event-v1",
        seq=seq,
        event_index=index,
        phase=phase,
        pc=100 + 4 * index,
        kind=kind,
        task_id=task,
        cause=cause,
        depth=depth,
        evidence="fixture",
    )


def fixture():
    return [
        event(0, 0, "begin", task=1),
        event(1, 2, "trap_enter", cause=0x80000007, depth=1),
        event(2, 3, "selected_task", task=2, depth=1),
        event(3, 4, "mret_pending", task=2, phase="after", depth=1),
        event(4, 5, "return_commit", task=2),
        event(5, 7, "trap_enter", cause=11, depth=1),
        event(6, 8, "selected_task", task=1, depth=1),
        event(7, 8, "mret_pending", task=1, phase="after", depth=1),
        event(8, 9, "return_commit", task=1),
        event(9, 10, "end"),
    ]


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("psf_lab.execution_context"))
        from psf_lab.execution_context import context_intervals, validate_context_anchors

        self.intervals = context_intervals
        self.anchors = validate_context_anchors

    def test_hand_computed_intervals(self):
        result = self.intervals(fixture(), raw_events=10, task_ids={1, 2})
        self.assertEqual(result["quality"], "exact")
        self.assertEqual(
            [(r["start"], r["end"], r["context"]) for r in result["intervals"]],
            [
                (0, 2, "task:1"),
                (2, 5, "irq:7"),
                (5, 7, "task:2"),
                (7, 9, "scheduler_transition"),
                (9, 10, "task:1"),
            ],
        )

    def test_immediate_retrap_does_not_charge_zero_length_task(self):
        rows = fixture()
        rows[5]["event_index"] = 5
        result = self.intervals(rows, raw_events=10, task_ids={1, 2})
        self.assertEqual(
            [(r["start"], r["end"], r["context"]) for r in result["intervals"]],
            [(0, 2, "task:1"), (2, 5, "irq:7"), (5, 9, "scheduler_transition"), (9, 10, "task:1")],
        )

    def test_corrupted_sequence_and_bounds_rejected(self):
        for index, key, value in [
            (1, "seq", 0),
            (1, "event_index", 11),
            (1, "event_index", -1),
            (1, "depth", False),
            (0, "task_id", 99),
            (9, "phase", "after"),
            (4, "event_index", 4),
            (3, "kind", "return_commit"),
        ]:
            rows = fixture()
            rows[index][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.intervals(rows, raw_events=10, task_ids={1, 2})

    def test_missing_boundaries_and_open_trap_rejected(self):
        for rows in (fixture()[1:], fixture()[:-1], fixture()[:3] + [event(3, 10, "end", depth=1)]):
            with self.assertRaises(ValueError):
                self.intervals(rows, raw_events=10, task_ids={1, 2})

    def test_nested_fixture_and_real_rejection(self):
        rows = [
            event(0, 0, "begin", task=1),
            event(1, 1, "trap_enter", cause=0x80000007, depth=1),
            event(2, 2, "trap_enter", cause=0x80000007, depth=2),
            event(3, 3, "mret_pending", task=1, phase="after", depth=2),
            event(4, 4, "return_commit", task=1, depth=1),
            event(5, 5, "mret_pending", task=1, phase="after", depth=1),
            event(6, 6, "return_commit", task=1),
            event(7, 8, "end"),
        ]
        with self.assertRaises(ValueError):
            self.intervals(rows, raw_events=8, task_ids={1})
        result = self.intervals(rows, raw_events=8, task_ids={1}, allow_nested=True)
        self.assertEqual(result["intervals"][-1]["context"], "task:1")
        self.assertEqual(sum(r["end"] - r["start"] for r in result["intervals"]), 8)

    def test_anchor_requires_raw_instruction_and_elf_opcode(self):
        events = [event(0, 0, "begin", task=1), event(1, 1, "end")]
        config = dict(
            capture_begin_pc=100,
            capture_end_pc=104,
            evidence=[dict(pc=100, opcode=0x13), dict(pc=104, opcode=0x13)],
        )
        self.anchors(events, [dict(pc=100, operation="I")], config)
        for rows in ([dict(pc=102, operation="I")], [dict(pc=100, operation="R")]):
            with self.assertRaises(ValueError):
                self.anchors(events, rows, config)
        with self.assertRaises(ValueError):
            self.anchors(events, [dict(pc=100, operation="I")], dict(config, evidence=[]))
