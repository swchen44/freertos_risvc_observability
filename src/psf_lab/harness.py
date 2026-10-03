"""Independent business assertions; expected values never come from decoding."""


def check_case(case: dict, trace: dict, oracle: dict) -> dict:
    assertions, issues = [], []

    def expect(name, expected, actual):
        assertions.append(
            dict(name=name, expected=expected, actual=actual, passed=actual == expected)
        )

    expect("case_id", case["case_id"], oracle.get("case_id"))
    expect("oracle_complete", True, oracle.get("complete"))
    expect("transport_ok", True, oracle.get("transport_ok"))
    if not oracle.get("complete"):
        issues.append("oracle_incomplete")
    if not oracle.get("transport_ok"):
        issues.append("transport_failure")
    expect("outcome", case["expected_outcome"], oracle.get("outcome"))
    expect("platform", "FreeRTOS", trace["platform"]["name"])
    expect("schema", "1.2.0", trace["platform"]["schema"])
    expect("word_bytes", 4, trace["platform"]["word_bytes"])
    expect("clock_hz", "10000000", trace["clock"]["frequency_hz"])
    expect("oracle_clock_hz", 10000000, oracle.get("mtime_hz"))
    expect("tick_hz", 1000, trace["clock"]["tick_hz"])
    expect("oracle_tick_hz", 1000, oracle.get("tick_hz"))
    expect("parse_issues", [], trace["quality"]["issues"])
    events = trace["events"]
    markers = [e for e in events if e["fields"].get("case_id") == case["case_id"]]
    expect("complete_markers", 1, sum(e["fields"].get("phase") == "COMPLETE" for e in markers))
    if case["case_id"] == "queue_baseline":
        ids = list(range(case["parameters"]["count"]))
        expect("oracle_sent_ids", ids, oracle.get("sent_ids"))
        expect("oracle_received_ids", ids, oracle.get("received_ids"))
        for phase in ["SEND", "RECEIVE"]:
            actual = [
                e["fields"].get("message_id") for e in markers if e["fields"].get("phase") == phase
            ]
            expect("psf_" + phase.lower(), ids, actual)
        queues = {e.get("object_id") for e in events if e["kind"] == "queue_create"}
        queues.discard(None)
        expect("queue_created", True, bool(queues))
        for kind in ["queue_send", "queue_receive"]:
            expect(
                kind + "_count",
                len(ids),
                sum(e["kind"] == kind and e.get("object_id") in queues for e in events),
            )
    elif case["case_id"] == "clock_probe":
        expect("clock_ticks", 100, oracle.get("delta_ticks"))
        expect(
            "clock_error_within_2_ticks",
            True,
            abs(int(oracle.get("delta_mtime", 0)) - 1000000) <= 20000,
        )
        expect("irq_restore", True, oracle.get("irq_restore_ok"))
    else:
        issues.append("unsupported_case")
    passed = all(a["passed"] for a in assertions) and not issues
    return dict(
        case_id=case["case_id"],
        verdict="pass" if passed else "fail",
        assertions=assertions,
        issues=issues,
    )
