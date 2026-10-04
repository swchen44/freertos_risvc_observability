"""Run from the POC root to recheck T2g artifacts and write receipt.json."""

import csv
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path

from psf_lab.live_cache import audit_accesses, compare_guest
from psf_lab.live_cache_irq import compare_irq, validate_irq_trace
from psf_lab.parser.semantic import parse_trace
from psf_lab.tcp_packets import decode_packet
from psf_lab.tcp_session import validate_session

root = Path.cwd()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


summary = []
for name, scenario, expected_ticks in (
    ("live-tcp-irq-v2", "tcp", 2),
    ("live-tcp-irq-regression-memory", "memory", 3),
    ("live-tcp-irq-regression-masked", None, 0),
):
    directory = root / "runs" / name
    manifest = json.loads((directory / "manifest.json").read_text())
    results = json.loads((directory / "results.json").read_text())
    assert results["passed"] and results["repeatable"]
    assert sha(directory / "results.json") == manifest["results_sha256"]
    for path, expected_hash in manifest["sources"].items():
        assert sha(root / path) == expected_hash, path
    irq = scenario is not None
    packet_baseline = None
    entries = []
    for run in manifest["runs"]:
        path = directory / run["name"]
        assert sha(path / "manifest.json") == run["sha256"]
        run_manifest = json.loads((path / "manifest.json").read_text())
        result = run_manifest["result"]
        for filename, expected_hash in run_manifest["files"].items():
            assert sha(path / filename) == expected_hash, filename
        assert audit_accesses(path / "accesses.csv.gz") == result["audit"]
        entry = dict(run=run["name"], files_verified=len(run_manifest["files"]))
        if (path / "session.json").exists():
            metrics = json.loads((path / "session.json").read_text())
            packets = []
            packet_hashes = []
            for index, packet in enumerate(metrics["packets"]):
                assert packet["file"] == f"packet-{index}.bin"
                blob = (path / packet["file"]).read_bytes()
                packet_hashes.append(hashlib.sha256(blob).hexdigest())
                packets.append(dict(decode_packet(blob), direction=packet["direction"]))
            assert validate_session(packets, metrics) == result["tcp"]
            if packet_baseline is None:
                packet_baseline = packet_hashes
            assert packet_hashes == packet_baseline, "Packet bytes changed across timing modes"
            entry["tcp_packets_byte_identical_to_control"] = len(packet_hashes)
        if irq:
            trace = parse_trace((path / "trace.psf").read_bytes())
            assert (
                validate_irq_trace(trace, result["measurement"], scenario=scenario)
                == result["switches"]
            )
            symbols = {
                parts[-1]: int(parts[0], 16)
                for line in (path / "symbols.txt").read_text().splitlines()
                if len(parts := line.split()) in (3, 4)
            }
            expected = {
                "freertos_risc_v_trap_handler": expected_ticks + 1,
                "test_if_mtimer": expected_ticks,
                "xTaskIncrementTick": expected_ticks,
                "synchronous_exception": 1,
                "handle_exception": 1,
                "application_exception_handler": 0,
            }
            counts = Counter()
            pc_names = {symbols[key]: key for key in expected}
            with gzip.open(path / "accesses.csv.gz", "rt") as stream:
                for row in csv.DictReader(stream):
                    if row["operation"] == "I" and int(row["pc"]) in pc_names:
                        counts[pc_names[int(row["pc"])]] += 1
            for key, count in expected.items():
                assert counts[key] == (count if result["enabled"] else 0), (key, counts)
            entry["verified_trap_path_counts"] = {key: counts[key] for key in expected}
        entries.append(entry)
    for comparison in results["comparisons"]:
        control = next(
            r for r in results["runs"] if not r["enabled"] and r["repeat"] == comparison["repeat"]
        )
        active = next(
            r for r in results["runs"] if r["enabled"] and r["repeat"] == comparison["repeat"]
        )
        checked = (
            compare_irq(
                control["measurement"],
                active["measurement"],
                control["audit"],
                active["audit"],
                scenario=scenario,
            )
            if irq
            else compare_guest(control["measurement"], active["measurement"], active["audit"]["ns"])
        )
        assert checked == {k: v for k, v in comparison.items() if k not in ("accepted", "repeat")}
    summary.append(
        dict(
            name=name,
            manifest_sha256=sha(directory / "manifest.json"),
            sources_verified=len(manifest["sources"]),
            runs=entries,
        )
    )
receipt = root / "artifacts/verification/live-tcp-irq/receipt.json"
receipt.write_text(
    json.dumps(dict(verified=summary, review="self review; no independent reviewer"), indent=2)
    + "\n"
)
print("Verified 10 runs: hashes, costs, PSF switches, timer/ECALL paths and TCP packet bytes")
