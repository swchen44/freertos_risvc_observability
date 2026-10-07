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
                matched = matched and source == rule.get("source")
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
