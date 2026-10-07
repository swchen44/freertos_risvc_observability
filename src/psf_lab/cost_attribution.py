"""Provenance-based, exclusive code ownership and self-cost attribution."""

import re
from bisect import bisect_right

ROLES = {
    "recorder",
    "observer_entry",
    "lwip",
    "application_harness",
    "kernel_port",
    "runtime_library",
    "unresolved",
}


def _integer(value):
    if type(value) is not int or value < 0:
        raise ValueError("Expected nonnegative integer")
    return value


def _unknown(reason, evidence=()):
    return dict(
        start=None,
        end=None,
        role="unresolved",
        function="unresolved",
        aliases=[],
        object=None,
        source=None,
        evidence=list(evidence),
        reason=reason,
    )


def normalize_ranges(records: list[dict]) -> list[dict]:
    """Merge aliases only; preserve conflicting intervals for explicit resolution."""
    groups = {}
    for record in records:
        start, end = _integer(record["start"]), _integer(record["end"])
        if end <= start or record["role"] not in ROLES:
            raise ValueError("Invalid executable range or role")
        key = (start, end, record["role"], record.get("object"))
        row = groups.setdefault(key, {**record, "aliases": [], "evidence": []})
        aliases = [*record.get("aliases", [])]
        if record.get("function"):
            aliases.append(record["function"])
        row["aliases"] = sorted(set(row["aliases"] + aliases))
        row["evidence"] = sorted(set(row["evidence"] + record.get("evidence", [])))
        row["function"] = (
            row["aliases"][0] if row["aliases"] else f"unresolved@{row.get('object')}:{start}"
        )
    return sorted(
        groups.values(), key=lambda r: (r["start"], r["end"], r["role"], str(r.get("object")))
    )


def resolve_pc(ranges: list[dict], pc: int) -> dict:
    """Resolve a PC without silently selecting one of multiple overlapping owners."""
    _integer(pc)
    stop = bisect_right(ranges, pc, key=lambda row: row["start"])
    hits = [row for row in ranges[:stop] if pc < row["end"]]
    if not hits:
        return _unknown("no_executable_owner")
    if len(hits) != 1:
        return _unknown("overlap_conflict", sorted({e for r in hits for e in r["evidence"]}))
    return dict(hits[0])


def classify_owner(owner: dict, rules: dict) -> dict:
    """Classify verified source/object provenance; never infer a caller from a name."""
    if rules.get("schema") != "code-role-rules-v1" or rules.get("abi") != "rv32":
        raise ValueError("Unsupported role rules")
    source, obj = owner.get("source") or "", owner.get("object") or ""
    matches = []
    for rule in rules["rules"]:
        kind, value = rule["match_kind"], rule["value"]
        if rule["role"] not in ROLES:
            raise ValueError("Unknown role")
        if kind in ("source", "object", "function"):
            matched = owner.get(kind) == value
            if kind == "function":
                matched = matched and owner.get("definition_source", source) == rule.get("source")
        elif kind == "source-root":
            matched = source.startswith(value.rstrip("/") + "/")
        elif kind == "archive":
            archive = re.fullmatch(r"(?:.*/)?([^/()]+\.a)\(([^()]+)\)", obj)
            matched = bool(archive and archive[1] == value)
        else:
            raise ValueError("Unknown match kind")
        if matched:
            matches.append((0 if kind == "source-root" else 1, rule))
    if not matches:
        return dict(role="unresolved", reason="no_provenance_rule", rule_ids=[])
    priority = max(p for p, _ in matches)
    selected = [rule for p, rule in matches if p == priority]
    roles = {r["role"] for r in selected}
    return dict(
        role=next(iter(roles)) if len(roles) == 1 else "unresolved",
        reason=None if len(roles) == 1 else "rule_conflict",
        rule_ids=sorted(r["id"] for r in selected),
    )


COST_KEYS = ("l1i", "l1d", "l2", "ram_read", "ram_write")
METRICS = ("instructions", "memory_cycles", "model_service_ns", "accounted_model_ns")


def _number(value):
    if isinstance(value, str) and re.fullmatch("[0-9]+", value):
        value = int(value)
    return _integer(value)


def _empty():
    return dict.fromkeys(METRICS, 0) | {"cost_cycles": dict.fromkeys(COST_KEYS, 0)}


def _add(target, delta):
    for key in METRICS:
        target[key] += delta[key]
    for key in COST_KEYS:
        target["cost_cycles"][key] += delta["cost_cycles"][key]


def aggregate_costs(
    rows, ranges: list[dict], *, mode: int, contexts: list[dict] | None = None
) -> dict:
    """Attribute each raw row once in each dimension, keeping global denominators."""
    if type(mode) is not int or mode not in (0, 1):
        raise ValueError("Invalid timing mode")
    if contexts is not None:
        expected_start = 0
        for interval in contexts:
            if (
                _integer(interval["start"]) != expected_start
                or _integer(interval["end"]) <= interval["start"]
                or not isinstance(interval["context"], str)
            ):
                raise ValueError("Invalid context coverage")
            expected_start = interval["end"]
    interval_index = 0
    totals = _empty()
    groups = {name: {} for name in ("by_role", "by_function", "by_pc", "by_context", "matrix")}
    unresolved, cache, events = {}, {}, 0
    for row in rows:
        pc = _number(row["pc"])
        if row["operation"] not in ("I", "R", "W"):
            raise ValueError("Invalid operation")
        costs = {k: _number(row[k]) for k in COST_KEYS}
        cycles = sum(costs.values())
        instructions = int(row["operation"] == "I")
        delta = dict(
            instructions=instructions,
            cost_cycles=costs,
            memory_cycles=cycles,
            model_service_ns=2 * cycles,
            accounted_model_ns=2 * cycles + instructions,
        )
        if pc not in cache:
            cache[pc] = resolve_pc(ranges, pc)
        owner = cache[pc]
        role = owner["role"]
        function = f"{owner['object']}:{owner['start']}:{owner['end']}:{owner['function']}"
        if owner["start"] is None:
            function += f":pc={pc}"
        context = "unknown"
        if contexts is not None:
            while interval_index < len(contexts) and events >= contexts[interval_index]["end"]:
                interval_index += 1
            if interval_index == len(contexts):
                raise ValueError("Context coverage ends before raw stream")
            context = contexts[interval_index]["context"]
        keys = dict(
            by_role=role,
            by_function=function,
            by_pc=pc,
            by_context=context,
            matrix=context + "|" + role,
        )
        _add(totals, delta)
        for dimension, key in keys.items():
            group = groups[dimension].setdefault(key, _empty())
            _add(group, delta)
            if dimension in ("by_function", "by_pc"):
                group["owner"] = owner
            if dimension == "by_pc":
                group["pc"] = pc
        if role == "unresolved":
            _add(unresolved.setdefault(owner["reason"] or "unresolved", _empty()), delta)
        events += 1
    if contexts is not None and (contexts[-1]["end"] if contexts else 0) != events:
        raise ValueError("Context coverage exceeds raw stream")
    for groupset in groups.values():
        for metric in METRICS:
            if sum(r[metric] for r in groupset.values()) != totals[metric]:
                raise ValueError("Attribution conservation failure")
        for key in COST_KEYS:
            if sum(r["cost_cycles"][key] for r in groupset.values()) != totals["cost_cycles"][key]:
                raise ValueError("Cost component conservation failure")
    for record in [totals, *[r for g in groups.values() for r in g.values()], *unresolved.values()]:
        record["shares"] = {
            metric: dict(
                numerator=record[metric],
                denominator=totals[metric],
                percent=100 * record[metric] / totals[metric] if totals[metric] else None,
            )
            for metric in METRICS
        }
    return dict(
        schema="cost-attribution-v1",
        mode=mode,
        events=events,
        totals=totals,
        **groups,
        unresolved=unresolved,
        evidence={},
        context_quality="not_observed_in_A_trace" if contexts is None else "supplied_intervals",
        cost_semantics="injected_model" if mode else "shadow_model",
    )
