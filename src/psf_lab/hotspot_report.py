"""Joint self-cost and 3C attribution using the unchanged memory service model."""

from psf_lab.cost_attribution import METRICS
from psf_lab.hotspot_events import (
    add_counts as add_counts,
)
from psf_lab.hotspot_events import (
    empty_counts as empty_counts,
)
from psf_lab.hotspot_events import (
    iter_hotspot_events,
)


def validate_hotspot_report(report: dict) -> None:
    if report.get("schema") != "hotspot-report-v1" or not report["facts"]:
        raise ValueError("Invalid hotspot report")
    total = empty_counts()
    keys = set()
    for fact in report["facts"]:
        key = (fact["context"], fact["role"], fact["function_id"], fact["pc"])
        if key in keys or fact["function_id"] not in report["owners"]:
            raise ValueError("Duplicate or missing hotspot owner")
        keys.add(key)
        for value in [
            *(fact[k] for k in METRICS),
            *fact["cost_cycles"].values(),
            *(v for counters in fact["cache"].values() for v in counters.values()),
        ]:
            if type(value) is not int or value < 0:
                raise ValueError("Invalid hotspot counter")
        if (
            fact["memory_cycles"] != sum(fact["cost_cycles"].values())
            or fact["model_service_ns"] != 2 * fact["memory_cycles"]
            or fact["accounted_model_ns"] != fact["model_service_ns"] + fact["instructions"]
        ):
            raise ValueError("Cost conservation failure")
        for counts in fact["cache"].values():
            if (
                counts["misses"] != sum(counts[k] for k in ("compulsory", "conflict", "capacity"))
                or counts["misses"] > counts["accesses"]
            ):
                raise ValueError("Miss conservation failure")
        add_counts(total, fact)
    if total != report["totals"]:
        raise ValueError("Hotspot total conservation failure")


def build_hotspot_report(
    rows, ranges: list[dict], profile: dict, *, identity: dict, contexts: list[dict] | None
) -> dict:
    if type(identity.get("mode")) is not int or identity["mode"] not in (0, 1):
        raise ValueError("Invalid mode")
    for key in ("run_id", "workload", "variant", "family", "repeat"):
        if key not in identity:
            raise ValueError("Missing run identity")
    facts, owners = {}, {}
    count = 0
    for event in iter_hotspot_events(rows, ranges, profile, contexts=contexts):
        key = (event["context"], event["role"], event["function_id"], event["pc"])
        fact = facts.setdefault(
            key, dict(context=key[0], role=key[1], function_id=key[2], pc=key[3], **empty_counts())
        )
        add_counts(fact, event)
        owners[event["function_id"]] = event["owner"]
        count += 1
    totals = empty_counts()
    for fact in facts.values():
        add_counts(totals, fact)
    result = dict(
        schema="hotspot-report-v1",
        identity=dict(identity),
        profile=profile,
        events=count,
        facts=[facts[k] for k in sorted(facts)],
        owners=owners,
        totals=totals,
        evidence={},
        context_quality="supplied_intervals" if contexts is not None else "unknown",
        cost_semantics="injected_model" if identity["mode"] else "shadow_model",
    )
    validate_hotspot_report(result)
    return result
