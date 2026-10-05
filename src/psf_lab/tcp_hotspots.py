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
