"""Audit fixed sysram-10 live costs using the independent Python replay model."""

import csv
import gzip
import hashlib

from psf_lab.cache_model import Geometry
from psf_lab.memory_timing import COSTS, MemoryTiming, Region


def audit_accesses(path):
    model = MemoryTiming(
        l1i=Geometry(16384, 64, 4),
        l1d=Geometry(16384, 64, 4),
        l2=Geometry(65536, 64, 4),
        l1i_cycles=1,
        l1d_cycles=1,
        l2_cycles=8,
        regions=[Region("system_ram", 0x80000000, 0x88000000, True, 10, 10, 8)],
    )
    count = 0
    operations = dict.fromkeys("IRW", 0)
    total = 0
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ["pc", "address", "size", "operation", *COSTS]:
            raise ValueError("Invalid live access columns")
        for row in reader:
            pc, address, size = (int(row[k]) for k in ("pc", "address", "size"))
            if not 0x80000000 <= pc < 0x88000000 or (
                row["operation"] == "I" and (pc != address or size not in (2, 4))
            ):
                raise ValueError("Invalid instruction identity mapping")
            expected = model.access(address, size, row["operation"])
            if any(int(row[k]) != expected[k] for k in COSTS):
                raise ValueError(f"Native/Python costs disagree at event {count}")
            total += expected["total"]
            operations[row["operation"]] += 1
            count += 1
    if not count:
        raise ValueError("Empty live trace")
    with opener(path, "rb") as stream:
        stream_hash = hashlib.file_digest(stream, "sha256").hexdigest()
    return dict(
        events=count,
        operations=operations,
        cycles=total,
        ns=total * 2,
        costs=model.result()["cost_cycles"],
        stream_sha256=stream_hash,
    )


def compare_guest(control, active, expected_ns):
    for result in (control, active):
        if result["after"] < result["before"] or result["ticks"] != 0:
            raise ValueError("Nonmonotonic clock or unexpected scheduler tick")
    if control["work"] != active["work"]:
        raise ValueError("Guest work changed")
    baseline = (control["after"] - control["before"]) * 100
    measured = (active["after"] - active["before"]) * 100
    extra = measured - baseline
    # Four 100 ns-quantized clock endpoints: difference error strictly <200 ns.
    if abs(extra - expected_ns) > 200:
        raise ValueError(f"Cost delivery mismatch: expected {expected_ns}, observed {extra}")
    return dict(
        control_ns=baseline,
        active_ns=measured,
        extra_guest_ns=extra,
        expected_extra_ns=expected_ns,
        error_ns=extra - expected_ns,
        tolerance_ns=200,
    )
