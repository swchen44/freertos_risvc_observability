"""PC-attributed self memory-service cost; no call-tree or exclusive task-time claim."""

import bisect
from collections import Counter

from psf_lab.memory_timing import COSTS


def rank_self_costs(rows, symbols, *, stack_markers=None):
    symbols = sorted(symbols)
    starts = [s[0] for s in symbols]
    costs, instructions = Counter(), Counter()
    scopes, per_function = Counter(), {}
    active, windows = False, 0
    for row in rows:
        pc = int(row["pc"])
        if stack_markers and row["operation"] == "I":
            if pc == stack_markers[0]:
                if active:
                    raise ValueError("Nested stack window")
                active = True
                windows += 1
            if pc == stack_markers[1]:
                if not active:
                    raise ValueError("Unmatched stack window end")
                active = False
        index = bisect.bisect_right(starts, pc) - 1
        symbol = symbols[index] if index >= 0 else None
        name = symbol[2] if symbol and pc < symbol[0] + symbol[1] else "assembly/unresolved"
        value = sum(int(row[k]) for k in COSTS)
        costs[name] += value
        scope = "stack_window_including_preemption" if active else "harness_window"
        scopes[scope] += value
        per_function.setdefault(name, Counter())[scope] += value
        instructions[name] += row["operation"] == "I"
    if stack_markers and (active or not windows):
        raise ValueError("Incomplete stack windows")
    result = dict(
        total_cycles=sum(costs.values()),
        functions=[
            dict(name=name, cycles=value, instructions=instructions[name])
            for name, value in costs.most_common()
        ],
    )

    if stack_markers:
        result.update(windows=windows, scope_cycles=dict(scopes))
        for function in result["functions"]:
            function["scope_cycles"] = dict(per_function[function["name"]])
    return result


class MissClassifier:
    """3C comparison against same-capacity fully associative LRU, per level."""

    def __init__(self, lines):
        from collections import OrderedDict

        self.lines = lines
        self.seen = set()
        self.shadow = OrderedDict()

    def observe(self, block, hit):
        kind = None
        if not hit:
            kind = (
                "compulsory"
                if block not in self.seen
                else "conflict"
                if block in self.shadow
                else "capacity"
            )
        self.seen.add(block)
        self.shadow.pop(block, None)
        self.shadow[block] = None
        if len(self.shadow) > self.lines:
            self.shadow.popitem(last=False)
        return kind


def profile_misses(rows, profile, symbols, *, stack_markers=None, audit=True):
    """Replay actual per-line lookups, including L1 writes, attributed by instruction PC.

    Classifications describe this trace and model. L2 sees filtered lookups including
    write-through stores. Scope windows may include ISR/preemption. No call tree.
    """
    from collections import defaultdict

    from psf_lab.cache_model import _Cache
    from psf_lab.memory_timing import from_profile

    model = from_profile(profile)
    symbols = sorted(symbols)
    starts = [s[0] for s in symbols]
    context = {}
    functions = defaultdict(Counter)
    locations = defaultdict(Counter)
    scopes = defaultdict(Counter)
    totals = Counter()
    active, windows = False, 0

    class ObservedCache(_Cache):
        def __init__(self, geometry, level):
            super().__init__(geometry)
            self.level = level
            self.classifier = MissClassifier(geometry.size // geometry.line)

        def access(self, address, operation, byte_count=None):
            hit = super().access(address, operation, byte_count)
            kind = self.classifier.observe(address // self.geometry.line, hit)
            counts = {self.level + "_accesses": 1}
            if kind:
                counts.update({self.level + "_misses": 1, self.level + "_" + kind: 1})
            for target in (
                totals,
                functions[context["name"]],
                locations[context["pc"]],
                scopes[context["scope"]],
            ):
                target.update(counts)
            return hit

    model.caches = {k: ObservedCache(c.geometry, k) for k, c in model.caches.items()}
    events = 0
    for row in rows:
        pc = int(row["pc"])
        if stack_markers and row["operation"] == "I":
            if pc == stack_markers[0]:
                if active:
                    raise ValueError("Nested stack window")
                active = True
                windows += 1
            if pc == stack_markers[1]:
                if not active:
                    raise ValueError("Unmatched stack window end")
                active = False
        index = bisect.bisect_right(starts, pc) - 1
        symbol = symbols[index] if index >= 0 else None
        name = symbol[2] if symbol and pc < symbol[0] + symbol[1] else "assembly/unresolved"
        context.update(
            pc=pc,
            name=name,
            scope="stack_window_including_preemption" if active else "harness_window",
        )
        costs = model.access(int(row["address"]), int(row["size"]), row["operation"])
        if audit and any(costs[k] != int(row[k]) for k in COSTS):
            raise ValueError(f"Native/Python costs disagree at event {events}")
        delta = Counter(cycles=costs["total"], instructions=int(row["operation"] == "I"))
        totals.update(delta)
        functions[name].update(delta)
        locations[pc].update(delta)
        scopes[context["scope"]].update(delta)
        events += 1
    if stack_markers and (active or not windows):
        raise ValueError("Incomplete stack windows")
    if not events:
        raise ValueError("Empty access stream")
    return dict(
        schema="tcp-os-cache-profile-v1",
        events=events,
        windows=windows,
        totals=dict(totals),
        model=model.result(),
        scopes=dict(scopes),
        functions=[
            dict(name=k, **v)
            for k, v in sorted(functions.items(), key=lambda item: item[1]["cycles"], reverse=True)
        ],
        pcs=[dict(pc=k, **v) for k, v in sorted(locations.items())],
    )
