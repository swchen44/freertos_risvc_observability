"""CSV uses the same query as the table, without a page limit."""

import csv
import io
import json

from psf_lab.query import query_events, query_view


def export_csv(trace, analysis, filters, sort, *, kind="events"):
    output = io.StringIO(newline="")
    common = {
        "source_sha256": trace["source"]["sha256"],
        "schema_version": trace["schema_version"],
        "time_unit": "recorder_ticks",
    }
    if kind == "events":
        fields = [
            *common,
            "event_id",
            "offset",
            "ticks",
            "kind",
            "actor_id",
            "object_id",
            "quality",
            "message",
            "spreadsheet_escaped",
        ]
        rows = [
            {
                **common,
                **{
                    k: e.get(k)
                    for k in ["event_id", "offset", "ticks", "kind", "actor_id", "object_id"]
                },
                "quality": json.dumps(e["quality"], ensure_ascii=False),
                "message": e["fields"].get("message", ""),
            }
            for e in query_events(trace, filters, sort, limit=None)["rows"]
        ]
    elif kind == "metrics":
        metrics = query_view(trace, analysis, filters)["metrics"]
        fields = [
            *common,
            "start_ticks",
            "end_ticks",
            "window_ticks",
            "known_ticks",
            "unknown_ticks",
            "task_id",
            "running_ticks",
            "fraction",
            "spreadsheet_escaped",
        ]
        rows = [
            {
                **common,
                **{
                    k: metrics[k]
                    for k in [
                        "start_ticks",
                        "end_ticks",
                        "window_ticks",
                        "known_ticks",
                        "unknown_ticks",
                    ]
                },
                "task_id": k,
                **v,
            }
            for k, v in (
                list(metrics["task_share"].items())
                or [(None, {"running_ticks": None, "fraction": None})]
            )
        ]
    else:
        raise ValueError("Unsupported CSV kind")
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        escaped = False
        for key, value in row.items():
            if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")):
                row[key] = "'" + value
                escaped = True
        row["spreadsheet_escaped"] = "true" if escaped else "false"
        writer.writerow(row)
    return output.getvalue()
