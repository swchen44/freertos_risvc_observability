"""Deterministic synthetic capacity measurements, never hardware performance claims."""

import hashlib
import json
import math
import platform
import resource
import statistics
import struct
import subprocess
import sys
import time
import tracemalloc
from pathlib import Path

from psf_lab.parser.semantic import parse_trace


def make_fixture(count: int) -> bytes:
    if type(count) is not int or not 1 <= count <= 200000:
        raise ValueError("event count must be an integer in 1..200000")
    header = struct.pack("<IHHIIIHBB8s", 0x50534600, 14, 0x1AA1, 0, 0x301, 0, 0, 2, 1, b"FreeRTOS")
    clock = struct.pack("<IIIIIII", 1, 0, 10000000, 0, 1000, 0, 0)
    table = struct.pack("<III", 0, 28, 3)
    # Fixed pattern, no random state: five tasks, a switch every 100 ticks.
    records = [
        struct.pack("<HHII", 0x1037, i % 65536, i * 100, 0x1000 + i % 5) for i in range(count)
    ]
    return header + clock + table + b"".join(records)


def summarize(values: list[float]) -> dict:
    if not values:
        return {"median_ms": None, "p95_ms": None}
    if any(not math.isfinite(v) or v < 0 for v in values):
        raise ValueError("durations must be finite and nonnegative")
    return {
        "median_ms": statistics.median(values),
        "p95_ms": sorted(values)[math.ceil(len(values) * 0.95) - 1],
    }


def _measure(path: Path) -> dict:
    data = path.read_bytes()
    count = len(parse_trace(data)["events"])  # one warmup, outside timings
    durations = []
    for _ in range(5):
        begin = time.perf_counter_ns()
        trace = parse_trace(data)
        durations.append((time.perf_counter_ns() - begin) / 1e6)
        del trace
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    tracemalloc.start()
    trace = parse_trace(data)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    del trace
    return {
        "event_count": count,
        "byte_length": len(data),
        "source_sha256": hashlib.sha256(data).hexdigest(),
        "parse_ms": durations,
        **summarize(durations),
        "peak_rss_raw": rss,
        "peak_rss_raw_unit": "bytes" if sys.platform == "darwin" else "KiB",
        "peak_rss_bytes": rss if sys.platform == "darwin" else rss * 1024,
        "tracemalloc_peak_bytes": peak,
    }


def benchmark(event_counts: list[int], output: Path) -> dict:
    if not event_counts:
        raise ValueError("at least one event count is required")
    fixtures = [(count, make_fixture(count)) for count in event_counts]
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for count, data in fixtures:
        path = output / f"synthetic-{count}.psf"
        path.write_bytes(data)
        worker = subprocess.run(
            [sys.executable, "-m", "psf_lab.benchmark", "--worker", str(path)],
            capture_output=True,
            text=True,
            check=True,
            timeout=180,
        )
        rows.append(json.loads(worker.stdout))
    report = {
        "kind": "synthetic_capacity_only",
        "generator": "five-task-switch-v1",
        "seed": "fixed pattern; no PRNG",
        "python": sys.version,
        "platform": platform.platform(),
        "warmup": 1,
        "repetitions": 5,
        "p95_method": "nearest rank",
        "rss_scope": (
            "fresh subprocess per count; high-water after warmup/timed parse; before tracemalloc"
        ),
        "tracemalloc_scope": "one separate parse; Python tracked allocations only",
        "results": rows,
    }
    (output / "parser.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "--worker":
        raise SystemExit("internal worker requires --worker FILE")
    print(json.dumps(_measure(Path(sys.argv[2])), allow_nan=False))
