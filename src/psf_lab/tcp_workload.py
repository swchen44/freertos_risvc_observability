"""Bounded, versioned workload inputs independent of guest receipts."""

import copy
import json
import re


def validate_workload(value):
    if not isinstance(value, dict) or set(value) != {
        "id",
        "request_bytes",
        "request_segments",
        "rounds",
    }:
        raise ValueError("Invalid workload fields")
    if not isinstance(value["id"], str) or not re.fullmatch(
        r"[A-Za-z][A-Za-z0-9_-]{0,31}", value["id"]
    ):
        raise ValueError("Invalid workload id")
    length, parts = value["request_bytes"], value["request_segments"]
    if type(length) is not int or not 1 <= length <= 1460:
        raise ValueError("Request size must be 1..1460")
    if (
        not isinstance(parts, list)
        or not 1 <= len(parts) <= 8
        or any(type(n) is not int or n < 0 for n in parts)
        or parts[0] == 0
        or sum(parts) != length
    ):
        raise ValueError("Invalid request segments")
    if type(value["rounds"]) is not int or value["rounds"] != 2:
        raise ValueError("Expected two rounds")
    return copy.deepcopy(value)


def load_workload(path, case_id):
    data = json.loads(path.read_text())
    if set(data) != {"schema", "cases"} or data["schema"] != "tcp-workloads-v1":
        raise ValueError("Invalid registry schema")
    cases = [validate_workload(c) for c in data["cases"]]
    if len({c["id"] for c in cases}) != len(cases):
        raise ValueError("Duplicate workload id")
    for case in cases:
        if case["id"] == case_id:
            return case
    raise ValueError("Unknown workload id")
