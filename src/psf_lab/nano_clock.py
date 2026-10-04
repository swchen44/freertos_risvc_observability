"""Compare identical instruction workloads, using guest mtime rather than requests."""

DELAYS = (10, 20, 50, 100, 1000)


def compare_nano(control, active, control_receipts, active_receipts):
    if any(len(x) != 5 for x in (control, active, control_receipts, active_receipts)):
        raise ValueError("Incomplete nano matrix")
    rows = []
    for i, delay in enumerate(DELAYS):
        c, a, cr, ar = control[i], active[i], control_receipts[i], active_receipts[i]
        for p in (c, a):
            if p["id"] != i or p["delay_ns"] != delay or p["repeats"] != 1000:
                raise ValueError("Invalid phase")
            if p["ticks"] != 0:
                raise ValueError("Unexpected timer interference")
            if not 0 <= p["before"] <= p["after"]:
                raise ValueError("Guest clock reversed")
        for r in (cr, ar):
            if r["id"] != i or r["requests"] != 1000 or r["requested_ns"] != delay * 1000:
                raise ValueError("Incomplete or wrong request budget")
        if cr["insns"] != ar["insns"]:
            raise ValueError("Control and active instruction work differs")
        observed = ((a["after"] - a["before"]) - (c["after"] - c["before"])) * 100
        expected = delay * 1000
        rows.append(
            dict(
                delay_ns=delay,
                requests=1000,
                expected_extra_ns=expected,
                observed_extra_ns=observed,
                error_ns=observed - expected,
                delivery_ratio=observed / expected,
                reliable=abs(observed - expected) <= 200,
            )
        )
    return dict(
        all_delays_reliable=all(r["reliable"] for r in rows),
        rows=rows,
        tolerance_ns=200,
        boundary="Aggregate mtime evidence; clock mode is recorded in the capture manifest",
    )
