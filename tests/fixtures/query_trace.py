def trace_250():
    return {
        "schema_version": 1,
        "source": {"sha256": "abc"},
        "clock": {"frequency_hz": "1000"},
        "objects": [{"object_id": "A", "name": "工作A"}, {"object_id": "B", "name": "工作B"}],
        "quality": {"issues": []},
        "events": [
            {
                "event_id": f"0:{i}",
                "offset": i,
                "ticks": str(i),
                "id": 80,
                "sequence": i,
                "kind": "user_event",
                "actor_id": "A" if i % 2 == 0 else "B",
                "object_id": "queue",
                "quality": [],
                "fields": {"channel": "POC", "message": '文字,"含引號"\n換行'},
            }
            for i in range(250)
        ],
    }
