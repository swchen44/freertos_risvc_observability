"""Acceptance checks for a fixed-jump virtual-time probe, not a cache simulator."""


def compare_probe(control, delayed, requested_ns):
    if type(requested_ns) is not int or not 0 < requested_ns <= 10_000_000:
        raise ValueError("Probe request must be 1..10000000 ns")
    for value in (control, delayed):
        if any(
            type(value.get(k)) is not int or value[k] < 0
            for k in ("delta_mtime", "immediate_mtime", "delta_ticks")
        ):
            raise ValueError("Invalid guest measurement")
        if type(value.get("observer_woke")) is not bool:
            raise ValueError("Invalid scheduler measurement")
    # QEMU virt mtime = 10 MHz, tick = 1000 Hz. Slack covers handler work,
    # not host duration, and is much smaller than the tested 1/5 ms jumps.
    additional = (delayed["delta_mtime"] - control["delta_mtime"]) * 100
    if abs(additional - requested_ns) > 200_000:
        raise ValueError("Injected time did not match guest clock")
    minimum_ticks = max(0, requested_ns // 1_000_000 - 1)
    if delayed["delta_ticks"] - control["delta_ticks"] < minimum_ticks:
        raise ValueError("Guest timer did not catch up")
    if control["observer_woke"] or (requested_ns >= 3_000_000 and not delayed["observer_woke"]):
        raise ValueError("Guest scheduler wakeup did not match delay")
    return dict(
        requested_ns=requested_ns,
        additional_guest_ns=additional,
        guest_clock_pass=True,
        scheduler_pass=True,
        tick_delta=delayed["delta_ticks"] - control["delta_ticks"],
        immediate_additional_ns=(delayed["immediate_mtime"] - control["immediate_mtime"]) * 100,
    )
