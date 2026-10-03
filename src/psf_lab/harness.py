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
    elif case["case_id"] in ("logger_bad", "logger_fixed"):
        ids = list(range(case["parameters"]["requests"]))
        expect("oracle_requests", ids, [r["request_id"] for r in oracle.get("requests", [])])
        origin = int(trace["clock"]["origin_ticks"])
        for phase in ["START", "WORKER_BEGIN", "WORKER_END", "LOGGER_BEGIN", "LOGGER_END"]:
            observed = [e for e in markers if e["fields"].get("phase") == phase]
            independent = [p for p in oracle.get("phases", []) if p["phase"] == phase]
            expect("psf_" + phase, ids, [e["fields"]["request_id"] for e in observed])
            expect("oracle_" + phase, ids, [p["request_id"] for p in independent])
            if len(observed) == len(independent):
                for e, p in zip(observed, independent, strict=True):
                    delta = (int(e["timestamp_raw"]) - int(p["mtime"])) % (1 << 32)
                    expect(phase + "_timestamp_" + str(p["request_id"]), True, delta <= 1000)
        del origin
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


def compare_cases(pair_id: str, runs: list[dict]) -> dict:
    assertions, issues = [], []

    def expect(name, expected, actual):
        assertions.append(
            dict(name=name, expected=expected, actual=actual, passed=expected == actual)
        )

    pairs = {
        "logger": ("logger_bad", "logger_fixed"),
        "priority": ("inversion", "inheritance"),
        "locks": ("deadlock_abba", "ordered_locks"),
    }
    if pair_id not in pairs or len(runs) != 2:
        return dict(pair_id=pair_id, verdict="fail", assertions=[], issues=["invalid_pair"])
    by_id = {r["case"]["case_id"]: r for r in runs}
    if set(by_id) != set(pairs[pair_id]):
        return dict(pair_id=pair_id, verdict="fail", assertions=[], issues=["invalid_pair_members"])
    a, b = (by_id[k] for k in pairs[pair_id])
    for key in ["source_commit", "mtime_hz", "time_model"]:
        expect("same_" + key, a["manifest"].get(key), b["manifest"].get(key))
    for r in runs:
        expect(r["case"]["case_id"] + "_passed", "pass", r["manifest"]["status"])
        expect(r["case"]["case_id"] + "_loss", [], r["trace"]["quality"]["issues"])
    if pair_id == "logger":
        params = {"requests": 8, "worker_ticks": 2, "logger_ticks": 8}
        for r in runs:
            if r["case"]["parameters"] != params or [
                q["request_id"] for q in r["oracle"]["requests"]
            ] != list(range(8)):
                issues.append("workload_mismatch")
            for phase in ["WORKER_END", "LOGGER_END"]:
                ids = [p["request_id"] for p in r["oracle"]["phases"] if p["phase"] == phase]
                if ids != list(range(8)):
                    issues.append("workload_mismatch")
        if not issues:
            for x, y in zip(a["oracle"]["requests"], b["oracle"]["requests"], strict=True):
                delta = (int(x["end_mtime"]) - int(x["start_mtime"])) - (
                    int(y["end_mtime"]) - int(y["start_mtime"])
                )
                expect("response_improves_" + str(x["request_id"]), True, delta >= 40000)
    else:
        issues.append("unsupported_pair")
    return dict(
        pair_id=pair_id,
        verdict="pass" if not issues and all(x["passed"] for x in assertions) else "fail",
        assertions=assertions,
        issues=issues,
    )
