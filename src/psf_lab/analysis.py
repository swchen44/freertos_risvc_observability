"""Scheduling evidence, explicit unknown time and request response/execution."""


def metrics_for(intervals, start: int, end: int, frequency: int) -> dict:
    known = 0
    shares = {}
    for interval in intervals:
        if interval["end_ticks"] is None:
            continue
        duration = max(
            0, min(end, int(interval["end_ticks"])) - max(start, int(interval["start_ticks"]))
        )
        if interval["state"] == "running" and interval["object_id"]:
            known += duration
            key = interval["object_id"]
            shares[key] = shares.get(key, 0) + duration
    window = max(0, end - start)
    return {
        "start_ticks": str(start),
        "end_ticks": str(end),
        "window_ticks": str(window),
        "window_seconds": window / frequency if frequency else None,
        "known_ticks": str(known),
        "unknown_ticks": str(window - known),
        "task_share": {
            k: {"running_ticks": str(v), "fraction": v / window if window else None}
            for k, v in shares.items()
        },
    }


def analyze(trace: dict) -> dict:
    events = [e for e in trace["events"] if e.get("ticks") is not None]
    intervals, requests = [], []
    frequency = int(trace["clock"]["frequency_hz"])
    if not events:
        return dict(
            intervals=[],
            requests=[],
            metrics=metrics_for([], 0, 0, frequency),
            quality={"issues": ["no_timed_events"], "open_end": True},
        )
    # Only an explicit application COMPLETE marker proves the capture boundary.
    complete_index = next(
        (i for i, e in enumerate(events) if e["fields"].get("phase") == "COMPLETE"), None
    )
    if complete_index is not None:
        events = events[: complete_index + 1]
    start, end = int(events[0]["ticks"]), int(events[-1]["ticks"])
    actor = None
    for index, e in enumerate(events):
        quality = e.get("quality", [])
        if quality or e["kind"] in ("unknown", "isr_begin", "isr_resume"):
            actor = None
        if e["kind"] in ("task_switch", "trace_start"):
            actor = e.get("actor_id")
        if e["kind"] == "task_delete" and e.get("object_id") == actor:
            actor = None
        if index + 1 >= len(events):
            break
        following = events[index + 1]
        left, right = int(e["ticks"]), int(following["ticks"])
        if right <= left:
            continue
        gap = any(
            (q.get("code") if isinstance(q, dict) else q) == "sequence_gap"
            for q in following.get("quality", [])
        )
        owner = None if gap else actor
        state = "running" if owner else "unknown"
        if (
            intervals
            and intervals[-1]["object_id"] == owner
            and intervals[-1]["end_ticks"] == str(left)
            and intervals[-1]["state"] == state
        ):
            intervals[-1]["end_ticks"] = str(right)
        else:
            intervals.append(
                dict(
                    object_id=owner,
                    start_ticks=str(left),
                    end_ticks=str(right),
                    state=state,
                    quality=[] if owner else ["unobserved_execution"],
                )
            )
    if complete_index is None:
        intervals.append(
            dict(
                object_id=actor,
                start_ticks=str(end),
                end_ticks=None,
                state="running" if actor else "unknown",
                quality=["open_end"],
            )
        )
    pending = {}
    for e in events:
        f = e["fields"]
        phase = f.get("phase")
        key = (f.get("case_id"), f.get("request_id"))
        if phase == "START":
            r = dict(
                case_id=key[0],
                request_id=key[1],
                start_ticks=e["ticks"],
                end_ticks=None,
                response_ticks=None,
                response_seconds=None,
                execution_ticks=None,
                worker_id=None,
                quality=[],
            )
            if key in pending:
                r["quality"].append("duplicate_start")
            requests.append(r)
            pending[key] = r
        elif phase == "WORKER_BEGIN" and key in pending:
            pending[key]["worker_id"] = e.get("actor_id")
            pending[key]["worker_start_ticks"] = e["ticks"]
        elif phase == "WORKER_END" and key in pending:
            r = pending.pop(key)
            r["end_ticks"] = e["ticks"]
            duration = int(e["ticks"]) - int(r["start_ticks"])
            r["response_ticks"] = str(duration)
            r["response_seconds"] = duration / frequency if frequency else None
            worker_start = int(r.get("worker_start_ticks", r["start_ticks"]))
            overlaps = [
                i
                for i in intervals
                if i["end_ticks"] is not None
                and int(i["end_ticks"]) > worker_start
                and int(i["start_ticks"]) < int(e["ticks"])
            ]
            uncertain = not r["worker_id"] or any(i["state"] == "unknown" for i in overlaps)
            if uncertain:
                r["quality"].append("execution_unknown")
            else:
                r["execution_ticks"] = str(
                    sum(
                        max(
                            0,
                            min(int(e["ticks"]), int(i["end_ticks"]))
                            - max(worker_start, int(i["start_ticks"])),
                        )
                        for i in overlaps
                        if i["object_id"] == r["worker_id"]
                    )
                )
    for r in pending.values():
        r["quality"].append("incomplete_request")
    return dict(
        intervals=intervals,
        requests=requests,
        metrics=metrics_for(intervals, start, end, frequency),
        quality={"issues": list(trace["quality"]["issues"]), "open_end": complete_index is None},
    )
