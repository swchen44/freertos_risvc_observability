"""Accept observed guest timing, never a plugin's request alone."""

DELAYS = (1000000, 2000000, 0, 3000000, 1000000)


def validate_edges(measurement, receipt, enabled):
    phases, requests = measurement["phases"], receipt["requests"]
    if type(enabled) is not bool or len(phases) != 5 or len(requests) != 5:
        raise ValueError("Invalid boundary matrix")
    last = 0
    deltas = []
    for i, (phase, request, delay) in enumerate(zip(phases, requests, DELAYS, strict=True)):
        for key in ("before_mtime", "after_mtime", "before_tick", "after_tick"):
            if type(phase[key]) is not int or phase[key] < 0:
                raise ValueError("Invalid guest counter")
        before, after = phase["before_mtime"], phase["after_mtime"]
        if phase["id"] != i or request["id"] != i or not last <= before <= after:
            raise ValueError("Guest clock is not monotonic")
        last = after
        delta = after - before
        if abs(delta - (delay // 100 if enabled else 0)) > 2000:
            raise ValueError(f"Incorrect elapsed time in phase {i}")
        if request["delay_ns"] != delay or request["applied"] is not enabled:
            raise ValueError("Incorrect plugin request")
        if not before * 100 <= request["anchor_ns"] <= after * 100:
            raise ValueError("Anchor not in guest measurement interval")
        target = 0 if i == 2 else request["anchor_ns"] + delay
        mode = request.get("mode", "absolute_target")
        if mode == "relative_cost":
            if request["target_ns"] is not None or request["anchor_target_ns"] != target:
                raise ValueError("Incorrect relative target metadata")
        elif mode != "absolute_target" or request["target_ns"] != target:
            raise ValueError("Incorrect absolute target")
        deltas.append(delta * 100)
    masked = phases[3]
    if masked["before_tick"] != masked["after_tick"]:
        raise ValueError("Timer tick delivered while IRQ masked")
    if measurement["masked_pending"] is not enabled:
        raise ValueError("Incorrect masked pending IRQ")
    if enabled:
        if measurement["restored_tick_delta"] < 3 or not measurement["observer_after_restore"]:
            raise ValueError("IRQ restore did not catch up or wake task")
        if phases[4]["after_tick"] <= phases[4]["before_tick"]:
            raise ValueError("Post-WFI injection did not advance tick")
    elif measurement["restored_tick_delta"] != 0 or measurement["observer_after_restore"]:
        raise ValueError("Control unexpectedly advanced scheduling")
    if (
        receipt["wfi_count"] < 1
        or requests[4]["wfi_before"] != 1
        or receipt["wfi_span_insns"] >= measurement["wfi_delta_mtime"] * 100
        or measurement["wfi_delta_mtime"] <= 0
        or measurement["wfi_tick_delta"] < 1
    ):
        raise ValueError("Missing WFI instruction/time-warp evidence")
    return dict(
        passed=True,
        enabled=enabled,
        phase_elapsed_ns=deltas,
        restored_ticks=measurement["restored_tick_delta"],
        wfi_elapsed_ns=measurement["wfi_delta_mtime"] * 100,
    )
