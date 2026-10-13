"""Stream self-cost events with continuous cache state and exact source validation."""

import hashlib
import json

from psf_lab.cache_model import _Cache
from psf_lab.cost_attribution import COST_KEYS, METRICS, _number, normalize_ranges, resolve_pc
from psf_lab.memory_timing import from_profile
from psf_lab.tcp_hotspots import MissClassifier

LEVELS = ("l1i", "l1d", "l2")
COUNTERS = ("accesses", "misses", "compulsory", "conflict", "capacity")


def empty_counts():
    return {
        **dict.fromkeys(METRICS, 0),
        "cost_cycles": dict.fromkeys(COST_KEYS, 0),
        "cache": {level: dict.fromkeys(COUNTERS, 0) for level in LEVELS},
    }


def add_counts(target, source):
    for key in METRICS:
        target[key] += source[key]
    for key in COST_KEYS:
        target["cost_cycles"][key] += source["cost_cycles"][key]
    for level in LEVELS:
        for key in COUNTERS:
            target["cache"][level][key] += source["cache"][level][key]


def iter_hotspot_events(rows, ranges: list[dict], profile: dict, *, contexts):
    if contexts is not None:
        end = 0
        for interval in contexts:
            if (
                _number(interval["start"]) != end
                or _number(interval["end"]) <= end
                or not isinstance(interval["context"], str)
                or not interval["context"]
            ):
                raise ValueError("Invalid context coverage")
            end = interval["end"]
    ranges = normalize_ranges(ranges)
    model = from_profile(profile)
    current = None

    class ObservedCache(_Cache):
        def __init__(self, geometry, level):
            super().__init__(geometry)
            self.level = level
            self.classifier = MissClassifier(geometry.size // geometry.line)

        def access(self, address, operation, byte_count=None):
            hit = super().access(address, operation, byte_count)
            kind = self.classifier.observe(address // self.geometry.line, hit)
            counts = current["cache"][self.level]
            counts["accesses"] += 1
            if kind:
                counts["misses"] += 1
                counts[kind] += 1
            return hit

    model.caches = {k: ObservedCache(c.geometry, k) for k, c in model.caches.items()}
    owners, pc_cache = {}, {}
    count = interval_index = 0
    for row in rows:
        pc, address, size = (_number(row[k]) for k in ("pc", "address", "size"))
        if row["operation"] == "I" and (pc != address or size not in (2, 4)):
            raise ValueError("Invalid instruction mapping")
        if pc not in pc_cache:
            owner = resolve_pc(ranges, pc)
            owner_key = {
                k: owner.get(k) for k in ("start", "end", "object", "function", "role", "source")
            }
            if owner["start"] is None:
                owner_key["pc"] = pc
            fid = hashlib.sha256(json.dumps(owner_key, sort_keys=True).encode()).hexdigest()
            owners[fid] = owner
            pc_cache[pc] = (fid, owner["role"])
        fid, role = pc_cache[pc]
        context = "unknown"
        if contexts is not None:
            while interval_index < len(contexts) and count >= contexts[interval_index]["end"]:
                interval_index += 1
            if interval_index == len(contexts):
                raise ValueError("Context ends before stream")
            context = contexts[interval_index]["context"]
        current = dict(
            index=count,
            pc=pc,
            address=address,
            size=size,
            operation=row["operation"],
            context=context,
            role=role,
            function_id=fid,
            owner=owners[fid],
            **empty_counts(),
        )
        expected = model.access(address, size, row["operation"])
        if any(_number(row[k]) != expected[k] for k in COST_KEYS):
            raise ValueError(f"Native/Python costs disagree at event {count}")
        current["instructions"] += int(row["operation"] == "I")
        current["memory_cycles"] += expected["total"]
        current["model_service_ns"] += 2 * expected["total"]
        current["accounted_model_ns"] += 2 * expected["total"] + int(row["operation"] == "I")
        for key in COST_KEYS:
            current["cost_cycles"][key] += expected[key]
        count += 1
        yield current
    if not count or (contexts is not None and (contexts[-1]["end"] if contexts else 0) != count):
        raise ValueError("Empty stream or incomplete coverage")
