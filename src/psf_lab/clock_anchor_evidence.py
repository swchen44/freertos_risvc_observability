"""Independent bounded causal validation and native MTIME / SDK-PSF joins."""

import gzip
import hashlib
import json
from collections import deque
from pathlib import Path

from psf_lab.clock_anchor_wire import (
    ClockEvidenceError,
    ClockUnavailable,
    _validate_record,
    decimal,
    iter_access_rows,
    iter_clock_records,
    mtime_quantum,
)

COSTS = ("l1i", "l1d", "l2", "ram_read", "ram_write")
ROOT = Path(__file__).resolve().parents[2]


def _require(condition, code):
    if not condition:
        raise ClockEvidenceError(code)


def scan_evidence(records, accesses, expected: dict, *, pending_limit=65536) -> dict:
    """Pass1 keeps only bounded queues and five marker brackets, never raw rows."""
    _require(type(pending_limit) is int and 0 < pending_limit <= 65536, "pending_limit")
    rows = expected["raw_rows"]
    _require(type(rows) is int and 0 <= rows <= 3000000, "raw_limit")
    raw = iter(accesses)
    cursor = sequence = requests = applied = device = plugin = 0
    total = max_pending = max_distance = injected = 0
    last_row = None
    pending = deque()
    pending_io = None
    stage = "configured"
    marker_stage = 0
    markers = []
    current = None
    last_clock = -1
    offset = None
    header_seen = footer_seen = False

    def advance(target):
        nonlocal cursor, last_row, total
        _require(cursor <= target <= rows, "cursor_order")
        while cursor < target:
            last_row = next(raw, None)
            _require(last_row is not None and last_row["index"] == cursor, "raw_count")
            total += sum(last_row[k] for k in COSTS)
            cursor += 1

    def clock(ns):
        nonlocal last_clock
        _require(ns >= last_clock, "clock_order")
        last_clock = ns

    for row in records:
        _validate_record(row)
        _require(not footer_seen, "after_footer")
        _require(decimal(row["record_seq"]) == sequence, "record_order")
        sequence += 1
        _require(row["run_id"] == expected["run_id"], "identity")
        kind = row["kind"]
        advance(decimal(row["raw_cursor"]))
        if kind == "header":
            _require(not header_seen and sequence == 1 and cursor == 0, "header_order")
            for key in (
                "configuration",
                "injection_enabled",
                "observer_enabled",
                "qemu_sha256",
                "elf_sha256",
                "profile_sha256",
                "plugin_sha256",
            ):
                _require(row[key] == expected[key], "identity")
            _require(
                int(row["marker_mode"]) == expected["marker_mode"]
                and int(row["expected_frequency_hz"]) == expected["expected_frequency_hz"],
                "identity",
            )
            _require(row["observer_enabled"], "observer_disabled_sidecar")
            header_seen = True
            continue
        _require(header_seen, "missing_header")
        if kind == "capture_begin":
            _require(stage == "configured" and cursor == 0, "begin_order")
            stage = "active"
        elif kind == "capture_end":
            _require(stage == "active" and cursor == rows, "end_order")
            stage = "draining"
        elif kind == "cost_request":
            _require(stage == "active" and expected["injection_enabled"], "request_state")
            _require(decimal(row["request_id"]) == requests + 1, "request_order")
            _require(
                cursor == requests + 1
                and decimal(row["request_event_index"]) == cursor - 1
                and last_row is not None
                and int(row["pc"]) == last_row["pc"],
                "request_row",
            )
            phase = "instruction_before" if last_row["operation"] == "I" else "memory_after_success"
            delta = sum(last_row[k] for k in COSTS) * 2
            _require(row["phase"] == phase and int(row["delta_ns"]) == delta, "request_cost")
            _require(len(pending) < pending_limit, "pending_limit")
            pending.append((requests + 1, cursor, delta))
            requests += 1
            injected += delta
            max_pending = max(max_pending, len(pending))
        elif kind == "cost_applied":
            _require(
                stage in ("active", "draining")
                and pending
                and int(row["request_id"]) == pending[0][0],
                "apply_order",
            )
            _, requested_cursor, delta = pending.popleft()
            _require(cursor >= requested_cursor, "apply_cursor")
            before, target, returned, after = (
                int(row[k])
                for k in ("before_ns", "requested_target_ns", "advance_return_ns", "after_ns")
            )
            _require(
                before + delta < 1 << 63 and target == returned == after == before + delta,
                "apply_target",
            )
            clock(before)
            clock(after)
            max_distance = max(max_distance, cursor - requested_cursor)
            applied += 1
        elif kind.startswith("marker_"):
            _require(stage == "active" and expected["marker_mode"] == 1, "marker_state")
            names = ("marker_enter", "marker_sampled", "marker_leave")
            seq = len(markers) + 1
            _require(
                seq <= 5
                and kind == names[marker_stage]
                and int(row["marker_seq"]) == seq
                and int(row["marker_phase"]) == seq,
                "marker_order",
            )
            if marker_stage == 0:
                current = dict(marker_seq=str(seq), marker_phase=str(seq))
            current[names[marker_stage]] = dict(row)
            if marker_stage == 2:
                markers.append(current)
                current = None
            marker_stage = (marker_stage + 1) % 3
        elif kind in ("mtime_read", "mtimecmp_write"):
            _require(stage in ("active", "draining"), "io_state")
            address = int(row["address"])
            if row["source"] == "device":
                _require(pending_io is None and int(row["native_io_seq"]) == device + 1, "io_order")
                if kind == "mtime_read":
                    _require(address in (0x0200BFF8, 0x0200BFFC), "io_address")
                    hz = int(row["timebase_hz"])
                    if hz != expected["expected_frequency_hz"]:
                        raise ClockUnavailable("frequency_unavailable")
                    ns, tick, delta = (int(row[k]) for k in ("virtual_ns", "mtime64", "time_delta"))
                    clock(ns)
                    _require((ns * hz // 1000000000 + delta) % (1 << 64) == tick, "native_formula")
                    word = (tick >> (32 if address == 0x0200BFFC else 0)) & 0xFFFFFFFF
                    _require(word == int(row["value32"]), "native_word")
                    _require(offset is None or offset == delta, "epoch_change")
                    offset = delta
                else:
                    _require(address in (0x02004000, 0x02004004), "io_address")
                pending_io = row
                device += 1
            else:
                _require(
                    pending_io is not None
                    and all(
                        row[k] == pending_io[k]
                        for k in ("kind", "native_io_seq", "address", "size", "pc", "raw_cursor")
                    ),
                    "io_pair",
                )
                plugin += 1
                pending_io = None
        elif kind == "epoch_change":
            raise ClockEvidenceError("epoch_change")
        elif kind == "footer":
            _require(stage == "draining" and pending_io is None and not pending, "incomplete")
            counts = dict(
                raw_rows=rows,
                requests=requests,
                applied=applied,
                pending=0,
                device_io=device,
                plugin_io=plugin,
                record_count=sequence,
            )
            _require(
                row["complete"] and all(int(row[k]) == v for k, v in counts.items()),
                "footer_counts",
            )
            _require(requests == (rows if expected["injection_enabled"] else 0), "request_count")
            _require(
                len(markers) == (5 if expected["marker_mode"] else 0) and not marker_stage,
                "marker_count",
            )
            footer_seen = True
        else:
            raise ClockEvidenceError("record_kind")
    _require(footer_seen, "missing_footer")
    _require(next(raw, None) is None, "raw_count")
    return dict(
        raw_rows=str(rows),
        requests=str(requests),
        applied=str(applied),
        pending="0",
        model_cycles=str(total),
        injected_ns=str(injected),
        markers=markers,
        device_io=str(device),
        plugin_io=str(plugin),
        record_count=str(sequence),
        max_pending=str(max_pending),
        max_queue_cursor_distance=str(max_distance),
        time_delta=None if offset is None else str(offset),
        epoch_id="0",
        marker_mode=expected["marker_mode"],
    )


def extract_psf_markers(trace: dict) -> list[dict]:
    _require(trace["clock"]["frequency_hz"] == "10000000", "psf_frequency")
    _require(
        not trace["quality"]["issues"]
        and all(not e["quality"] and e["kind"] != "unknown" for e in trace["events"]),
        "psf_quality",
    )
    result = []
    for event in trace["events"]:
        if event["fields"].get("channel") != "C2B":
            continue
        fields = event["fields"]
        _require(
            fields.get("format") == "C2Bv1|%u|%u|%u|%u" and len(fields.get("arguments", [])) == 4,
            "psf_marker_format",
        )
        seq, phase, low, high = (decimal(v, bits=32) for v in fields["arguments"])
        _require(seq == phase == len(result) + 1 and seq <= 5, "psf_marker_order")
        result.append(
            dict(
                marker_seq=str(seq),
                marker_phase=str(phase),
                sample64=str((high << 32) | low),
                timestamp_raw=str(event["timestamp_raw"]),
                psf_offset=str(event["offset"]),
                psf_ticks=event["ticks"],
            )
        )
    _require(len(result) in (0, 5), "psf_marker_count")
    return result


def join_anchor_bounds(records, scan: dict, psf: dict) -> dict:
    """Pass2 aggregates only matching low-register reads inside each hook bracket."""
    psf_markers = extract_psf_markers(psf)
    if not scan["marker_mode"]:
        _require(not psf_markers, "marker_mode")
        return dict(
            alignment_status="unavailable",
            reason="markers-off",
            anchors=[],
            intervals=[],
            covered_rows="0",
            unknown_rows=scan["raw_rows"],
        )
    _require(len(psf_markers) == len(scan["markers"]) == 5, "marker_count")
    aggregates = [
        [
            dict(
                count=0,
                tick=None,
                cursor_min=None,
                cursor_max=None,
                ns_min=None,
                ns_max=None,
                offset=None,
                ambiguous=False,
            )
            for _ in range(2)
        ]
        for _ in range(5)
    ]
    for marker, psf_marker in zip(scan["markers"], psf_markers, strict=True):
        _require(marker["marker_sampled"]["sample64"] == psf_marker["sample64"], "marker_payload")
    for row in records:
        if (
            row["kind"] != "mtime_read"
            or row["source"] != "device"
            or int(row["address"]) != 0x0200BFF8
        ):
            continue
        seq, tick = int(row["record_seq"]), int(row["mtime64"])
        for i, marker in enumerate(scan["markers"]):
            enter, sampled, leave = (
                int(marker[k]["record_seq"])
                for k in ("marker_enter", "marker_sampled", "marker_leave")
            )
            which = 0 if enter < seq < sampled else 1 if sampled < seq < leave else None
            if which is None:
                continue
            expected_tick = int(
                psf_markers[i]["sample64"] if which == 0 else psf_markers[i]["timestamp_raw"]
            )
            if (tick if which == 0 else tick & 0xFFFFFFFF) != expected_tick:
                continue
            a = aggregates[i][which]
            cursor, ns = int(row["raw_cursor"]), int(row["virtual_ns"])
            a["count"] += 1
            a["ambiguous"] |= a["tick"] is not None and a["tick"] != tick
            a["tick"] = tick
            a["offset"] = int(row["time_delta"])
            for prefix, value in (("cursor", cursor), ("ns", ns)):
                for suffix, fn in (("min", min), ("max", max)):
                    key = prefix + "_" + suffix
                    a[key] = value if a[key] is None else fn(a[key], value)
    anchors = []
    for i, (app, sdk) in enumerate(aggregates):
        _require(app["count"] > 0, "app_sample_unavailable")
        _require(sdk["count"] > 0, "sdk_sample_unavailable")
        _require(not app["ambiguous"] and not sdk["ambiguous"], "ambiguous_full_counter")
        low, high = mtime_quantum(sdk["tick"], sdk["offset"], 10000000)
        _require(low <= sdk["ns_min"] <= sdk["ns_max"] < high, "quantum_formula")
        _require(sdk["tick"] >= app["tick"], "anchor_clock_order")
        anchors.append(
            dict(
                **psf_markers[i],
                epoch_id=scan["epoch_id"],
                sdk_mtime64=str(sdk["tick"]),
                lower_ns=str(low),
                upper_ns=str(high),
                cursor_min=str(sdk["cursor_min"]),
                cursor_max=str(sdk["cursor_max"]),
                sdk_candidates=str(sdk["count"]),
                app_candidates=str(app["count"]),
                sample_to_sdk_ticks=str(sdk["tick"] - app["tick"]),
                bracket_start=scan["markers"][i]["marker_enter"]["raw_cursor"],
                bracket_end=scan["markers"][i]["marker_leave"]["raw_cursor"],
                exclusive_cpu_status="unavailable",
            )
        )
    intervals = []
    for previous, following in zip(anchors, anchors[1:], strict=False):
        _require(int(previous["lower_ns"]) <= int(following["lower_ns"]), "anchor_clock_order")
        _require(
            int(following["sdk_mtime64"]) - int(previous["sdk_mtime64"])
            == int(following["psf_ticks"]) - int(previous["psf_ticks"]),
            "psf_clock_relation",
        )
        start, end = int(previous["cursor_max"]), int(following["cursor_min"])
        if start < end:
            intervals.append(
                dict(
                    start=str(start),
                    end=str(end),
                    lower_ns=previous["lower_ns"],
                    upper_ns=following["upper_ns"],
                    quality="between_observations",
                )
            )
    covered = sum(int(i["end"]) - int(i["start"]) for i in intervals)
    return dict(
        alignment_status="verified-bounds",
        anchors=anchors,
        intervals=intervals,
        covered_rows=str(covered),
        unknown_rows=str(int(scan["raw_rows"]) - covered),
    )


def _content_identity(path):
    opener = gzip.open if path.suffix == ".gz" else open
    sha = hashlib.sha256()
    size = 0
    with opener(path, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
            size += len(chunk)
    return dict(sha256=sha.hexdigest(), bytes=size)


def verify_clock_capture(run: Path, expected: dict) -> dict:
    """Real-file boundary: validate pinned tools, replay costs, then scan twice."""
    from psf_lab.clock_anchor_capture import PROFILE, _validate_tools
    from psf_lab.execution_context import context_intervals, validate_context_anchors
    from psf_lab.live_cache import audit_accesses
    from psf_lab.live_cache_irq import validate_irq_trace
    from psf_lab.parser.semantic import parse_trace
    from psf_lab.runner import digest
    from psf_lab.tcp_packets import decode_packet
    from psf_lab.tcp_session import validate_request_pbufs, validate_session

    run = run.resolve()
    capture = json.loads((run / "capture.json").read_text())
    _require(
        capture["schema"] == "clock-anchor-capture-v1"
        and capture["status"] == "captured-unvalidated"
        and capture["expected"] == expected,
        "capture_identity",
    )
    tools = capture["tools"]
    _validate_tools(ROOT, tools)
    profile_path = Path(expected["profile_path"])
    _require(
        digest(profile_path) == expected["profile_sha256"] == digest(ROOT / PROFILE),
        "profile_identity",
    )
    _require(tools["profile"]["sha256"] == expected["profile_sha256"], "profile_identity")
    for name, identity in capture["files"].items():
        path = (run / name).resolve()
        _require(
            Path(name).name == name
            and path.is_relative_to(run)
            and path.is_file()
            and path.stat().st_size == identity["bytes"]
            and digest(path) == identity["sha256"],
            "file_hash",
        )
    _require(digest(run / "firmware.elf") == expected["elf_sha256"], "elf_identity")
    candidate = tools["candidates"][expected["candidate"]]
    _require(
        candidate["elf"]["sha256"] == expected["elf_sha256"]
        and digest(run / "firmware.map") == candidate["map"]["sha256"]
        and digest(run / "symbols.txt") == candidate["symbols"]["sha256"],
        "elf_identity",
    )
    paths = {}
    for name, stream in capture["streams"].items():
        _require(Path(stream["path"]).name == stream["path"], "stream_path")
        path = run / stream["path"]
        _require(stream["path"] in capture["files"], "stream_identity")
        _require(
            _content_identity(path)
            == dict(sha256=stream["content_sha256"], bytes=stream["content_bytes"]),
            "stream_hash",
        )
        paths[name] = path
    raw = paths["accesses.csv"]
    audit = audit_accesses(raw, profile=json.loads(profile_path.read_text()))
    wanted = dict(expected, raw_rows=audit["events"])
    trace = parse_trace((run / "trace.psf").read_bytes())
    measurement = json.loads((run / "live-cache.json").read_text())
    session = json.loads((run / "session.json").read_text())
    oracle = json.loads((run / "oracle.json").read_text())
    _require(
        oracle["complete"] is True
        and oracle["transport_ok"] is True
        and oracle["outcome"] == "normal"
        and oracle["clock_marker_mode"] == expected["marker_mode"]
        and oracle["clock_marker_count"] == (5 if expected["marker_mode"] else 0),
        "oracle",
    )
    packets = []
    for index, item in enumerate(session["packets"]):
        name = f"packet-{index}.bin"
        _require(item["file"] == name and name in capture["files"], "packet_identity")
        packets.append(dict(decode_packet((run / name).read_bytes()), direction=item["direction"]))
    tcp = validate_session(packets, session, workload=tools["workload"])
    validate_request_pbufs(session, "matrix", workload=tools["workload"])
    switches = validate_irq_trace(trace, measurement, scenario="tcp")
    psf_markers = extract_psf_markers(trace)
    _require(len(psf_markers) == (5 if expected["marker_mode"] else 0), "psf_marker_count")
    with gzip.open(paths["context.jsonl"], "rt") as f:
        context_events = [json.loads(line) for line in f]
    boundaries = candidate["boundaries"]["context"]
    validate_context_anchors(context_events, iter_access_rows(raw), boundaries)
    task_ids = {e["task_id"] for e in context_events if e["task_id"] is not None}
    context = context_intervals(context_events, raw_events=audit["events"], task_ids=task_ids)
    result = dict(
        schema="clock-anchor-validation-v1",
        **expected,
        evidence_status="valid",
        application_status="passed",
        alignment_status="unavailable",
        resolution_assessment="unrated",
        raw_rows=str(audit["events"]),
        model_cycles=str(audit["cycles"]),
        audit=audit,
        tcp=tcp,
        measurement=measurement,
        session=session,
        oracle=oracle,
        switches=switches,
        context=context,
        packet_sha256=[capture["files"][f"packet-{i}.bin"]["sha256"] for i in range(len(packets))],
        psf_sha256=digest(run / "trace.psf"),
        raw_stream_sha256=audit["stream_sha256"],
        context_stream_sha256=capture["streams"]["context.jsonl"]["content_sha256"],
        capture_source_commit=capture["capture_source_commit"],
        compiled_source_commit=capture["compiled_source_commit"],
        host_wall_seconds=capture["host_wall_seconds"],
        host_child_cpu_seconds=capture.get("host_child_cpu_seconds"),
        anchors=[],
        intervals=[],
        covered_rows="0",
        unknown_rows=str(audit["events"]),
    )
    if expected["observer_enabled"]:
        clock_path = paths["clock.jsonl"]
        before = _content_identity(clock_path)
        scan = scan_evidence(iter_clock_records(clock_path), iter_access_rows(raw), wanted)
        joined = join_anchor_bounds(iter_clock_records(clock_path), scan, trace)
        _require(
            before
            == _content_identity(clock_path)
            == dict(
                sha256=capture["streams"]["clock.jsonl"]["content_sha256"],
                bytes=capture["streams"]["clock.jsonl"]["content_bytes"],
            ),
            "scan_content_changed",
        )
        for anchor in joined["anchors"]:
            start, end = int(anchor["bracket_start"]), int(anchor["bracket_end"])
            spans = [i for i in context["intervals"] if i["start"] < end and i["end"] > start]
            anchor["contexts"] = sorted({i["context"] for i in spans})
            anchor["preempted"] = any(i["context"].startswith("irq:") for i in spans)
        result.update(scan=scan, **joined)
    else:
        _require("clock.jsonl" not in paths, "observer_disabled_sidecar")
    return result
