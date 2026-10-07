"""Strict raw-event boundary semantics for independently observed contexts."""

from psf_lab.cost_attribution import _integer

KINDS = {"begin", "trap_enter", "selected_task", "mret_pending", "return_commit", "end", "fault"}


def context_intervals(
    events: list[dict], *, raw_events: int, task_ids: set[int], allow_nested: bool = False
) -> dict:
    _integer(raw_events)
    for task in task_ids:
        _integer(task)
    if not events or events[0]["kind"] != "begin" or events[-1]["kind"] != "end":
        raise ValueError("Missing begin/end")
    current, stack, pending, selected = "unknown", [], None, None
    intervals, last, quality = [], 0, "exact"
    for seq, event in enumerate(events):
        if (
            event.get("schema") != "context-event-v1"
            or _integer(event["seq"]) != seq
            or event["kind"] not in KINDS
            or event["phase"] not in ("before", "after")
            or not event.get("evidence")
        ):
            raise ValueError("Invalid context event")
        index, depth = _integer(event["event_index"]), _integer(event["depth"])
        _integer(event["pc"])
        for key in ("task_id", "cause"):
            if event[key] is not None:
                _integer(event[key])
        if event["task_id"] is not None and event["task_id"] not in task_ids:
            raise ValueError("Unknown task ID")
        boundary = index + (event["phase"] == "after")
        if (
            index > raw_events
            or (event["phase"] == "after" and index == raw_events)
            or boundary < last
        ):
            raise ValueError("Context boundary out of order or bounds")
        if boundary > last:
            if intervals and intervals[-1]["context"] == current and intervals[-1]["end"] == last:
                intervals[-1]["end"] = boundary
            else:
                intervals.append(
                    dict(
                        start=last,
                        end=boundary,
                        context=current,
                        reason="missing_context" if current == "unknown" else None,
                    )
                )
        kind = event["kind"]
        if kind == "begin":
            if seq != 0 or boundary != 0 or event["phase"] != "before" or event["task_id"] is None:
                raise ValueError("Invalid initial task")
            current = f"task:{event['task_id']}"
        elif kind == "trap_enter":
            if pending is not None or (stack and not allow_nested) or event["phase"] != "before":
                raise ValueError("Unsupported nested trap or uncommitted return")
            stack.append((current, selected))
            selected = None
            cause = event["cause"]
            current = (
                "irq:7"
                if cause == 0x80000007
                else "scheduler_transition"
                if cause == 11
                else "unknown"
            )
            if current == "unknown":
                quality = "unknown_cause"
        elif kind == "selected_task":
            if not stack or pending is not None or event["task_id"] is None:
                raise ValueError("Task selection outside active trap")
            selected = event["task_id"]
        elif kind == "mret_pending":
            if (
                not stack
                or pending is not None
                or event["phase"] != "after"
                or event["task_id"] is None
            ):
                raise ValueError("Unmatched mret")
            if selected is not None and selected != event["task_id"]:
                raise ValueError("Selected task/return mismatch")
            pending = event["task_id"]
        elif kind == "return_commit":
            if (
                pending is None
                or not stack
                or event["phase"] != "before"
                or event["task_id"] != pending
            ):
                raise ValueError("Return without matching mret")
            saved, outer_selected = stack.pop()
            current = saved if stack else f"task:{pending}"
            selected = outer_selected
            pending = None
        elif kind == "end":
            if (
                seq != len(events) - 1
                or index != raw_events
                or event["phase"] != "before"
                or stack
                or pending
            ):
                raise ValueError("Incomplete context capture")
        else:
            raise ValueError("Context observer fault")
        if depth != len(stack):
            raise ValueError("Context depth mismatch")
        last = boundary
    return dict(intervals=intervals, quality=quality, transitions=len(events))


def validate_context_anchors(events: list[dict], rows, boundaries: dict) -> None:
    """Verify sidecar PCs against actual I rows and ELF-derived instruction evidence."""
    requested = {event["event_index"] for event in events if event["kind"] != "end"}
    observed = {}
    count = 0
    for count, row in enumerate(rows, 1):
        if count - 1 in requested:
            observed[count - 1] = row
    opcodes = {entry["pc"]: entry["opcode"] for entry in boundaries["evidence"]}
    keys = {
        "begin": "capture_begin_pc",
        "end": "capture_end_pc",
        "trap_enter": "trap_entry_pc",
        "selected_task": "selected_task_pc",
    }
    for event in events:
        pc = event["pc"]
        kind = event["kind"]
        if pc not in opcodes:
            raise ValueError("Missing ELF opcode evidence")
        if kind in keys and pc != boundaries[keys[kind]]:
            raise ValueError("Boundary PC mismatch")
        if kind == "mret_pending" and (
            pc not in boundaries["mret_pcs"] or opcodes[pc] != 0x30200073
        ):
            raise ValueError("Invalid mret opcode")
        if kind == "end":
            if event["event_index"] != count or event["phase"] != "before":
                raise ValueError("Invalid end anchor")
            continue
        row = observed.get(event["event_index"])
        if row is None or row["operation"] != "I" or int(row["pc"]) != pc:
            raise ValueError("Raw context anchor mismatch")
