"""Validate packet/PSF/raw trace evidence and derive TCP comparison data."""

import bisect
import csv
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path

from psf_lab.parser.semantic import parse_trace
from psf_lab.tcp_cache import replay_split
from psf_lab.tcp_packets import decode_packet

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_files(run, manifest):
    for name, expected in manifest["files"].items():
        if Path(name).name != name or digest(run / name) != expected:
            raise ValueError("TCP evidence hash mismatch: " + name)


def analyze_run(run):
    manifest = json.loads((run / "manifest.json").read_text())
    verify_files(run, manifest)
    metrics = json.loads((run / "tcp.json").read_text())
    oracle = json.loads((run / "oracle.json").read_text())
    if (
        metrics["case"] != manifest["variant"]
        or oracle["case_id"] != manifest["variant"]
        or metrics["acked_bytes"] != 5840
        or metrics["retransmits"] != 1
        or metrics["packet_count"] != 6
        or not oracle["complete"]
        or oracle["sent_ids"] != [5840]
        or oracle["received_ids"] != [5840]
    ):
        raise ValueError("TCP completion oracle failed")
    packets = [decode_packet((run / f"packet-{n}.bin").read_bytes()) for n in range(6)]
    payload = bytes((i * 17 + 31) % 256 for i in range(1460))
    for packet in packets:
        if (
            packet["src"],
            packet["dst"],
            packet["ack"],
            packet["source_ip"],
            packet["destination_ip"],
        ) != (1234, 50000, 1001, [10, 0, 0, 1], [10, 0, 0, 2]):
            raise ValueError("Unexpected peer or ACK")
    if packets[0]["flags"] != 0x12 or packets[0]["payload"]:
        raise ValueError("SYN-ACK failed")
    base = (packets[0]["seq"] + 1) % 2**32
    for packet, offset in zip(packets[1:], (0, 1460, 2920, 2920, 4380), strict=True):
        if (
            packet["payload"] != payload
            or packet["seq"] != (base + offset) % 2**32
            or packet["flags"] & 0x17 != 0x10
        ):
            raise ValueError("TCP payload, sequence or retransmission mismatch")
    phases = metrics["phases"]
    if (
        [p["phase"] for p in phases] != list(range(5))
        or [p["kind"] for p in phases] != ["send", "send", "send", "retransmit", "send"]
        or any(type(p["instructions"]) is not int or p["instructions"] <= 0 for p in phases)
    ):
        raise ValueError("Unexpected measurement phases")
    psf = parse_trace((run / "trace.psf").read_bytes())
    markers = [(e["fields"].get("phase"), e["fields"].get("request_id")) for e in psf["events"]]
    for phase in range(5):
        for name in ("TCP_TX_BEGIN", "TCP_TX_END"):
            if markers.count((name, phase)) != 1:
                raise ValueError("PSF phase marker mismatch")
    symbols = []
    for line in (run / "symbols.txt").read_text().splitlines():
        fields = line.split()
        if len(fields) == 4 and fields[2] in ("T", "t"):
            symbols.append((int(fields[0], 16), int(fields[1], 16), fields[3]))
    symbols.sort()
    addresses = [s[0] for s in symbols]
    events = [[] for _ in range(5)]
    hotspots = [Counter() for _ in range(5)]
    previous = 0
    with gzip.open(run / "accesses.csv.gz", "rt") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != ["phase", "pc", "address", "size", "operation"]:
            raise ValueError("Unexpected trace schema")
        for record in reader:
            phase, pc, addr, size = (int(record[k]) for k in ("phase", "pc", "address", "size"))
            op = record["operation"]
            if phase not in range(5) or phase < previous or phase > previous + 1:
                raise ValueError("Invalid trace phase order")
            previous = phase
            if not (0x80000000 <= addr < addr + size <= 0x88000000):
                raise ValueError("Guest physical RAM bounds violated")
            if op == "I" and (addr != pc or size not in (2, 4)):
                raise ValueError("Instruction identity mapping violated")
            events[phase].append((addr, size, op))
            if op == "I":
                index = bisect.bisect_right(addresses, pc) - 1
                symbol = symbols[index] if index >= 0 else None
                name = symbol[2] if symbol and pc < symbol[0] + symbol[1] else "unresolved"
                hotspots[phase][name] += 1
    count = sum(map(len, events))
    if f"tcp_trace_complete={count},phases=5" not in (run / "qemu.log").read_text():
        raise ValueError("Trace completion receipt missing")
    models = [replay_split(event) for event in events]
    if any(not m["events"]["I"] or not m["events"]["R"] or not m["events"]["W"] for m in models):
        raise ValueError("Empty phase trace")
    rows = []
    for kind in ("send", "retransmit"):
        indexes = [i for i, p in enumerate(phases) if p["kind"] == kind]
        hot = Counter()
        for i in indexes:
            hot.update(hotspots[i])
        row = dict(
            run=run.name,
            variant=manifest["variant"],
            repeat=manifest["repeat"],
            kind=kind,
            bytes=1460 * len(indexes),
            phases=len(indexes),
            instructions=sum(phases[i]["instructions"] for i in indexes),
            text_bytes=manifest["text_bytes"],
            reads=sum(models[i]["events"]["R"] for i in indexes),
            writes=sum(models[i]["events"]["W"] for i in indexes),
            hotspots=[{"function": name, "instructions": n} for name, n in hot.most_common(12)],
            models=[models[i] for i in indexes],
            evidence={
                "manifest": f"{run.name}/manifest.json",
                "psf": f"{run.name}/trace.psf",
                "packets_validated": 6,
                "acked_bytes": 5840,
                "retransmits": 1,
                "cache_scope": "cold reset per isolated TX; no ACK cache state, no cycles",
            },
        )
        for level in ("l1i", "l1d", "l2"):
            row[level + "_misses"] = sum(models[i][level]["misses"] for i in indexes)
        rows.append(row)
    return rows


def load_transfer(directory):
    manifest = json.loads((directory / "manifest.json").read_text())
    expected = {
        f"{variant}-{repeat}"
        for variant in ("tcp_copy2", "tcp_copy3", "tcp_nocopy3")
        for repeat in (1, 2, 3)
    }
    if len(manifest["runs"]) != 9 or {r["name"] for r in manifest["runs"]} != expected:
        raise ValueError("Expected nine TCP runs")
    if digest(directory / "results.json") != manifest["results_sha256"]:
        raise ValueError("TCP results hash mismatch")
    for run in manifest["runs"]:
        if Path(run["name"]).name != run["name"]:
            raise ValueError("Invalid run name")
        path = directory / run["name"] / "manifest.json"
        if digest(path) != run["manifest_sha256"]:
            raise ValueError("TCP run manifest hash mismatch")
        verify_files(path.parent, json.loads(path.read_text()))
    data = json.loads((directory / "results.json").read_text())
    if data["schema"] != "tcp-dashboard-v1" or len(data["rows"]) != 18:
        raise ValueError("Unexpected TCP comparison dataset")
    return data


def export_transfer(directory, output):
    from psf_lab.cache_report import render_offline

    data = load_transfer(directory)
    html = render_offline(
        data,
        (ROOT / "web/tcp.html")
        .read_text()
        .replace("tcp-data", "cache-data")
        .replace("/assets/tcp.", "/assets/cache."),
        (ROOT / "web/dist/assets/tcp.js").read_text().replace("tcp-data", "cache-data"),
        (ROOT / "web/dist/assets/tcp.css").read_text(),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html)
