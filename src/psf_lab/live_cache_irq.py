"""Acceptance for live memory service while timer IRQs and scheduling run."""


def validate_mmio(address, size, operation):
    allowed = size == 4 and (
        (operation == "R" and address in (0x0200BFF8, 0x0200BFFC))
        or (operation == "W" and address in (0x02004000, 0x02004004))
    )
    if not allowed:
        raise ValueError("Only CLINT mtime reads / mtimecmp writes may bypass RAM costing")


def compare_irq(control, active, control_audit, active_audit):
    for result in (control, active):
        if result["after"] < result["before"] or result["work"] != 210677760:
            raise ValueError("Guest clock or work checksum mismatch")
    if control["ticks"] != 0 or control["woke"] != 0:
        raise ValueError("Control unexpectedly reached observer deadline")
    if active["ticks"] < 2 or active["woke"] != 1:
        raise ValueError("Injected cost did not wake delayed observer")
    if not (
        active["before_tick"] + 2
        <= active["observer_tick"]
        <= active["before_tick"] + active["ticks"]
    ):
        raise ValueError("Observer tick is outside expected deadline/window")
    if not active["before"] <= active["observer_mtime"] <= active["after"]:
        raise ValueError("Observer timestamp outside capture")
    extra = ((active["after"] - active["before"]) - (control["after"] - control["before"])) * 100
    instruction_delta = active_audit["operations"]["I"] - control_audit["operations"]["I"]
    expected = active_audit["ns"] + instruction_delta
    if abs(extra - expected) > 200:
        raise ValueError(f"IRQ cost conservation failed: expected {expected}, observed {extra}")
    return dict(
        extra_guest_ns=extra,
        injected_service_ns=active_audit["ns"],
        extra_instruction_ns=instruction_delta,
        expected_extra_ns=expected,
        error_ns=extra - expected,
        tolerance_ns=200,
        active_ticks=active["ticks"],
        observer_tick=active["observer_tick"],
    )


def validate_irq_trace(trace, m):
    marks = [
        (e["fields"]["phase"], e["fields"].get("request_id"), e["timestamp_raw"])
        for e in trace["events"]
        if e["fields"].get("phase")
    ]
    expected = [("IRQ_CACHE_BEGIN", 0)]
    if m["woke"]:
        expected.append(("IRQ_OBSERVER", m["observer_tick"]))
    expected += [("IRQ_CACHE_END", 0), ("COMPLETE", 0)]
    if [(n, i) for n, i, _ in marks] != expected or not (
        marks[0][2] <= m["before"] <= m["after"] <= marks[-2][2]
    ):
        raise ValueError("IRQ PSF boundaries disagree")
    names = {o["object_id"]: o["name"] for o in trace["objects"]}
    switches = [
        dict(name=names.get(e["object_id"]), mtime=e["timestamp_raw"])
        for e in trace["events"]
        if e["kind"] == "task_switch" and marks[0][2] < e["timestamp_raw"] < marks[-2][2]
    ]
    observed = [x["name"] for x in switches]
    if m["woke"] and observed != ["cache_observer", "cache_worker"]:
        raise ValueError("Missing observer preemption / worker resumption")
    if not m["woke"] and observed:
        raise ValueError("Unexpected control preemption")
    if m["woke"] and not switches[0]["mtime"] <= m["observer_mtime"] <= switches[1]["mtime"]:
        raise ValueError("Observer clock outside PSF task interval")
    return switches
