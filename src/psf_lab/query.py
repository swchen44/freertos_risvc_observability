"""Shared half-open filters and bounded views; scheduling denominator stays intact."""

from functools import cmp_to_key

from psf_lab.analysis import metrics_for

FILTER_KEYS = {
    "start_ticks",
    "end_ticks",
    "task_ids",
    "object_ids",
    "channels",
    "event_ids",
    "search",
}
SORT_KEYS = {"ticks", "kind", "object_id", "sequence", "offset"}


def validate_filters(filters):
    if not isinstance(filters, dict) or set(filters) - FILTER_KEYS:
        raise ValueError("Invalid filters")
    for key in ["start_ticks", "end_ticks"]:
        if key in filters and (
            not isinstance(filters[key], str)
            or not filters[key].isdigit()
            or len(filters[key]) > 40
        ):
            raise ValueError("Ticks must be unsigned decimal strings")
    if all(k in filters for k in ["start_ticks", "end_ticks"]) and int(
        filters["start_ticks"]
    ) >= int(filters["end_ticks"]):
        raise ValueError("Time window must have start < end")
    for key in ["task_ids", "object_ids", "channels", "event_ids"]:
        if key not in filters:
            continue
        value = filters[key]
        expected = int if key == "event_ids" else str
        if (
            not isinstance(value, list)
            or len(value) > 512
            or any(type(v) is not expected for v in value)
        ):
            raise ValueError("Invalid selection list")
    if not isinstance(filters.get("search", ""), str) or len(filters.get("search", "")) > 256:
        raise ValueError("Search exceeds 256 characters")


def query_events(trace, filters, sort, *, offset=0, limit=200):
    validate_filters(filters)
    if (
        type(offset) is not int
        or offset < 0
        or (limit is not None and (type(limit) is not int or not 1 <= limit <= 2000))
    ):
        raise ValueError("Invalid page bounds")
    if not isinstance(sort, list) or len(sort) > 5:
        raise ValueError("Invalid sort")
    for item in sort:
        if (
            not isinstance(item, dict)
            or set(item) != {"field", "direction"}
            or item["field"] not in SORT_KEYS
            or item["direction"] not in ("asc", "desc")
        ):
            raise ValueError("Invalid sort")
    names = {o["object_id"]: o.get("name", "") for o in trace.get("objects", [])}
    selections = {
        k: set(filters.get(k, [])) for k in ["task_ids", "object_ids", "channels", "event_ids"]
    }
    search = filters.get("search", "").casefold()
    start = int(filters["start_ticks"]) if "start_ticks" in filters else None
    end = int(filters["end_ticks"]) if "end_ticks" in filters else None

    def matches(e):
        ticks = int(e["ticks"]) if e.get("ticks") is not None else None
        if start is not None and (ticks is None or ticks < start):
            return False
        if end is not None and (ticks is None or ticks >= end):
            return False
        for key, value in [
            ("task_ids", e.get("actor_id")),
            ("object_ids", e.get("object_id")),
            ("channels", e["fields"].get("channel")),
            ("event_ids", e.get("id")),
        ]:
            if selections[key] and value not in selections[key]:
                return False
        return (
            not search
            or search
            in " ".join(
                [
                    names.get(e.get("actor_id"), "") or "",
                    names.get(e.get("object_id"), "") or "",
                    e["fields"].get("message", "") or "",
                ]
            ).casefold()
        )

    rows = [e for e in trace["events"] if matches(e)]

    def compare(a, b):
        for spec in [*sort, {"field": "offset", "direction": "asc"}]:
            key = spec["field"]
            x, y = a.get(key), b.get(key)
            if x is None or y is None:
                if x is not y:
                    return 1 if x is None else -1
                continue
            if key == "ticks":
                x, y = int(x), int(y)
            if x != y:
                return ((x > y) - (x < y)) * (1 if spec["direction"] == "asc" else -1)
        return 0

    rows.sort(key=cmp_to_key(compare))
    return {"total": len(rows), "rows": rows[offset : None if limit is None else offset + limit]}


def query_view(trace, analysis, filters):
    validate_filters(filters)
    base = analysis["metrics"]
    start = int(filters.get("start_ticks", base["start_ticks"]))
    end = int(filters.get("end_ticks", base["end_ticks"]))
    if end < start:
        raise ValueError("Window is outside the trace")
    intervals = analysis["intervals"]
    frequency = int(trace["clock"]["frequency_hz"])
    metrics = metrics_for(intervals, start, end, frequency)
    selected = set(filters.get("task_ids", []))
    visible = []
    for i in intervals:
        if i["end_ticks"] is None or (selected and i["object_id"] not in selected):
            continue
        left, right = max(start, int(i["start_ticks"])), min(end, int(i["end_ticks"]))
        if right > left:
            visible.append({**i, "start_ticks": str(left), "end_ticks": str(right)})
    raw_count = len(visible)
    aggregation = {"mode": "intervals", "raw_intervals": raw_count, "max_marks": 2000}
    if raw_count > 2000:
        lanes = {i["object_id"] for i in visible}
        if len(lanes) > 2000:
            visible = []
            aggregation["mode"] = "too_many_lanes"
        else:
            bins = max(1, min(500, 2000 // len(lanes)))
            step = max(1, (end - start + bins - 1) // bins)
            groups = {}
            for i in visible:
                slot = min(bins - 1, (int(i["start_ticks"]) - start) // step)
                key = (i["object_id"], slot)
                if key not in groups:
                    groups[key] = {
                        "object_id": key[0],
                        "start_ticks": str(start + slot * step),
                        "end_ticks": str(min(end, start + (slot + 1) * step)),
                        "state": "density",
                        "quality": ["aggregated_by_start"],
                        "count": 0,
                    }
                groups[key]["count"] += 1
            visible = list(groups.values())
            aggregation.update(mode="density_by_interval_start", bin_ticks=str(step))
    requests = [
        r
        for r in analysis["requests"]
        if int(r["start_ticks"]) < end and (r["end_ticks"] is None or int(r["end_ticks"]) > start)
    ]
    if selected:
        requests = [r for r in requests if r.get("worker_id") in selected]
    trend = []
    if end > start:
        step = max(1, (end - start + 39) // 40)
        for left in range(start, end, step):
            trend.append(metrics_for(intervals, left, min(left + step, end), frequency))
    values = [int(r["response_ticks"]) for r in requests if r["response_ticks"] is not None]
    stats = {
        "samples": len(values),
        "min_ticks": str(min(values)) if values else None,
        "mean_ticks": sum(values) / len(values) if values else None,
        "max_ticks": str(max(values)) if values else None,
    }
    events = query_events(trace, filters, [], limit=None)["rows"]
    signals = [
        {"ticks": e["ticks"], "value": e["fields"]["counter"], "event_id": e["event_id"]}
        for e in events
        if "counter" in e["fields"]
    ]
    return dict(
        intervals=visible,
        metrics=metrics,
        trend=trend,
        requests=requests[:2000],
        request_total=len(requests),
        request_stats=stats,
        signals=signals[:2000],
        signal_total=len(signals),
        quality=analysis["quality"],
        aggregation=aggregation,
        event_total=len(events),
        untimed_events=sum(e.get("ticks") is None for e in trace["events"]),
        filter_scope=(
            "time: all views; task: lanes/requests; "
            "object/channel/type/search: events/signals; "
            "metrics denominator: full schedule"
        ),
    )
