def event(ticks, kind, actor=None, phase=None, request=0, quality=None):
    return {
        "ticks": str(ticks),
        "kind": kind,
        "actor_id": actor,
        "object_id": actor,
        "offset": ticks,
        "quality": quality or [],
        "fields": {"phase": phase, "request_id": request},
    }


def schedule_trace():
    return {
        "clock": {"frequency_hz": "1000"},
        "quality": {"issues": []},
        "events": [
            event(0, "task_switch", "A"),
            event(10, "task_switch", "B"),
            event(30, "user_event", "B", "COMPLETE"),
        ],
    }
