"""Exact observer controls, marker effects and auditable C2b pilot reports."""

import csv
import json
import os
import re
import shutil
import subprocess
from dataclasses import asdict
from decimal import Decimal, localcontext
from pathlib import Path

from psf_lab.clock_anchor_capture import RunSpec, _validate_tools, pilot_matrix
from psf_lab.clock_anchor_evidence import verify_clock_capture
from psf_lab.clock_anchor_wire import decimal
from psf_lab.runner import digest, write_json

ROOT = Path(__file__).resolve().parents[2]
IDENTITY = ("candidate", "elf_sha256", "injection_enabled", "profile_sha256")
EXACT = (
    "packet_sha256",
    "oracle",
    "session",
    "tcp",
    "raw_stream_sha256",
    "audit",
    "model_cycles",
    "raw_rows",
    "psf_sha256",
    "psf_bytes",
    "marker_bytes",
    "measurement",
    "switches",
    "context_stream_sha256",
    "context",
)
RESOURCES = (
    "request_bytes",
    "acked_bytes",
    "retained_bytes",
    "peak_retained_bytes",
    "peer_closed",
    "active_pcbs",
    "timewait_pcbs",
    "resources_before",
    "resources_after",
)


def _pair(first, second):
    if any(
        k not in first
        or k not in second
        or type(first[k]) is not type(second[k])
        or first[k] != second[k]
        for k in IDENTITY
    ):
        raise ValueError("Comparison candidate/ELF/injection/profile mismatch")


def _valid(row):
    return row.get("evidence_status") == "valid" and row.get("application_status") == "passed"


def compare_transparent(reference: dict, observed: dict) -> dict:
    _pair(reference, observed)
    pair = (reference["configuration"], observed["configuration"])
    if pair not in (("L", "C"), ("C", "O")) or any(
        r.get("marker_mode") != 1 for r in (reference, observed)
    ):
        raise ValueError("Transparency requires L/C or C/O with markers enabled")
    differences = [
        k for k in EXACT if k not in reference or k not in observed or reference[k] != observed[k]
    ]
    if not all(_valid(r) for r in (reference, observed)):
        differences.append("validation_status")
    return dict(
        kind="transparency",
        reference=reference["run_id"],
        observed=observed["run_id"],
        passed=not differences,
        mismatches=differences,
        alignment_verified=observed.get("alignment_status") == "verified-bounds",
        host_readings=[
            {k: r.get(k) for k in ("run_id", "host_wall_seconds", "host_child_cpu_seconds")}
            for r in (reference, observed)
        ],
    )


def _metrics(row):
    measurement = row["measurement"]
    elapsed = measurement["after"] - measurement["before"]
    if elapsed < 0:
        raise ValueError("Nonmonotonic guest measurement")
    result = dict(
        model_cycles=decimal(row["model_cycles"]),
        guest_elapsed_ns=elapsed * 100,
        guest_elapsed_ticks=elapsed,
        scheduler_ticks=measurement["ticks"],
        raw_rows=decimal(row["raw_rows"]),
        psf_bytes=decimal(row["psf_bytes"]),
        marker_bytes=decimal(row["marker_bytes"]),
        task_switches=len(row["switches"]),
    )
    result.update({"raw_" + op: row["audit"]["operations"][op] for op in "IRW"})
    result.update({"memory_" + k: v for k, v in row["audit"]["costs"].items()})
    return result


def _percent(numerator, denominator):
    if denominator == 0:
        return None
    with localcontext() as context:
        context.prec = 100
        return format(Decimal(numerator) * 100 / Decimal(denominator), ".6f")


def _context_rows(row):
    totals = {}
    for span in row["context"]["intervals"]:
        key = span["context"]
        totals[key] = totals.get(key, 0) + span["end"] - span["start"]
    return {k: str(v) for k, v in totals.items()}


def bound_statistics(rows):
    samples = dict(
        sdk_quantum_ns=[], hook_bracket_rows=[], candidate_cursor_span=[], sample_to_sdk_ticks=[]
    )
    for row in rows:
        for a in row["anchors"]:
            samples["sdk_quantum_ns"].append(int(a["upper_ns"]) - int(a["lower_ns"]))
            samples["hook_bracket_rows"].append(int(a["bracket_end"]) - int(a["bracket_start"]))
            samples["candidate_cursor_span"].append(int(a["cursor_max"]) - int(a["cursor_min"]))
            samples["sample_to_sdk_ticks"].append(int(a["sample_to_sdk_ticks"]))
    result = dict(resolution_assessment="unrated", anchors=str(len(samples["sdk_quantum_ns"])))
    for key, values in samples.items():
        if not values:
            result[key] = None
            continue
        ordered = sorted(values)
        n = len(ordered)
        median = (Decimal(ordered[(n - 1) // 2]) + Decimal(ordered[n // 2])) / 2
        result[key] = dict(min=str(ordered[0]), median=str(median), max=str(ordered[-1]))
    return result


def compare_marker_effect(on: dict, off: dict) -> dict:
    _pair(on, off)
    if (
        (on["configuration"], off["configuration"]) != ("O", "M")
        or (on["marker_mode"], off["marker_mode"]) != (1, 0)
        or any(on.get(k) != off.get(k) for k in ("qemu_sha256", "plugin_sha256"))
    ):
        raise ValueError("Marker effect requires same QEMU/plugin O-on versus M-off")
    mismatches = [
        k for k in ("packet_sha256", "tcp") if k not in on or k not in off or on[k] != off[k]
    ]
    for key in RESOURCES:
        if (
            any(key not in r.get("session", {}) for r in (on, off))
            or on["session"][key] != off["session"][key]
        ):
            mismatches.append("session." + key)
    for key in (
        "case_id",
        "complete",
        "outcome",
        "transport_ok",
        "mtime_hz",
        "tick_hz",
        "sent_ids",
        "received_ids",
    ):
        if (
            any(key not in r.get("oracle", {}) for r in (on, off))
            or on["oracle"][key] != off["oracle"][key]
        ):
            mismatches.append("oracle." + key)
    if not all(_valid(r) and r.get("oracle", {}).get("complete") is True for r in (on, off)):
        mismatches.append("validation_status")
    result = dict(
        kind="marker-effect",
        on=on["run_id"],
        off=off["run_id"],
        passed=not mismatches,
        mismatches=mismatches,
        denominator_configuration="M",
        resolution_assessment="unrated",
        context_rows_on=_context_rows(on),
        context_rows_off=_context_rows(off),
        host_readings=[
            {k: r.get(k) for k in ("run_id", "host_wall_seconds", "host_child_cpu_seconds")}
            for r in (on, off)
        ],
    )
    on_metrics, off_metrics = _metrics(on), _metrics(off)
    if on_metrics.keys() != off_metrics.keys():
        raise ValueError("Metric set mismatch")
    for key, value in on_metrics.items():
        denominator = off_metrics[key]
        delta = value - denominator
        result.update(
            {
                key + "_delta": str(delta),
                key + "_denominator": str(denominator),
                key + "_percent": _percent(delta, denominator),
                key + "_percent_reason": "zero-denominator" if denominator == 0 else None,
            }
        )
    return result


def write_csv_rows(path, rows, *, numeric_fields=frozenset(), columns=None):
    """Keep exact decimal strings and quote/escape only nonnumeric spreadsheet cells."""
    rows = list(rows)
    fields = list(columns or dict.fromkeys(k for row in rows for k in row)) or ["run_id"]
    fields = [k for k in fields if k != "spreadsheet_escaped"] + ["spreadsheet_escaped"]
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=fields, quoting=csv.QUOTE_ALL, lineterminator="\r\n"
        )
        writer.writeheader()
        for row in rows:
            cells, escaped = {}, False
            for key in fields[:-1]:
                value = row.get(key)
                if isinstance(value, (list, dict, bool)):
                    value = json.dumps(value, separators=(",", ":"), ensure_ascii=False)
                text = "" if value is None else str(value)
                if key in numeric_fields and text:
                    if not re.fullmatch(r"-?(0|[1-9][0-9]*)(\.[0-9]+)?", text):
                        raise ValueError("Invalid generated numeric cell: " + key)
                elif text.startswith(("=", "+", "-", "@", "\t", "\r")):
                    text = "'" + text
                    escaped = True
                cells[key] = text
            writer.writerow(cells | dict(spreadsheet_escaped="true" if escaped else "false"))


def expected_identity(spec, tools):
    legacy = spec.configuration == "L"
    return dict(
        run_id=spec.run_id,
        candidate=spec.candidate,
        configuration=spec.configuration,
        injection_enabled=bool(spec.injection),
        observer_enabled=spec.observer_enabled,
        marker_mode=spec.marker_mode,
        expected_frequency_hz=10000000,
        qemu_sha256=tools["legacy_qemu" if legacy else "clock_qemu"]["sha256"],
        elf_sha256=tools["candidates"][spec.candidate]["elf"]["sha256"],
        profile_sha256=tools["profile"]["sha256"],
        plugin_sha256=tools["plugins"]["legacy" if legacy else "new"]["sha256"],
        profile_path=tools["profile"]["path"],
        raw_rows=None,
    )


def group_comparisons(summaries):
    groups = {}
    for row in summaries:
        key = (row["candidate"], row["injection_enabled"])
        group = groups.setdefault(key, {})
        if row["configuration"] in group:
            raise ValueError("Duplicate configuration")
        group[row["configuration"]] = row
    result = []
    for (candidate, injection), group in groups.items():
        comparisons = []
        if set(group) == set("LCOM"):
            comparisons = [
                compare_transparent(group[a], group[b]) for a, b in (("L", "C"), ("C", "O"))
            ]
            comparisons.append(compare_marker_effect(group["O"], group["M"]))
        result.append(
            dict(
                candidate=candidate,
                injection=int(injection),
                comparisons=comparisons,
                passed=bool(comparisons)
                and all(c["passed"] for c in comparisons)
                and group["O"]["alignment_status"] == "verified-bounds"
                and len(group["O"]["anchors"]) == 5,
            )
        )
    return result


def _section_sizes(text):
    return {
        m[1]: int(m[2])
        for line in text.splitlines()
        if (m := re.fullmatch(r"(\.[\w.]+)\s+([0-9]+)\s+[0-9]+", line.strip()))
    }


def _code_sizes(tools, output):
    result = {}
    for name, candidate in tools.get("candidates", {}).items():
        folder = output / "code-size" / name
        folder.mkdir(parents=True)
        metadata = Path(candidate["boundaries_file"]["path"]).parent
        source_files = {}
        for file in ("size.txt", "readelf.txt", "nm.txt", "objdump.txt"):
            src = metadata / file
            if digest(src) != candidate["boundaries"]["metadata_files"][file]:
                raise ValueError("Code-size metadata changed")
            shutil.copy2(src, folder / file)
            source_files[file] = digest(src)
        shutil.copy2(candidate["map"]["path"], folder / "firmware.map")
        new_sizes = _section_sizes((folder / "size.txt").read_text())
        reference = ROOT / f"runs/tcp-context-v1/probe/A02-{name}/enabled-1-1"
        old_manifest = json.loads((reference / "manifest.json").read_text())
        old_elf = reference / "firmware.elf"
        if digest(old_elf) != old_manifest["files"]["firmware.elf"]:
            raise ValueError("Reference code-size ELF changed")
        tool = candidate["boundaries"]["tools"]["size"]
        if digest(Path(tool["path"])) != tool["sha256"]:
            raise ValueError("Code-size tool changed")
        command = [tool["path"], "-A", str(old_elf)]
        p = subprocess.run(command, capture_output=True, timeout=30, check=True)
        (folder / "reference-size.txt").write_bytes(p.stdout)
        write_json(
            folder / "reference-command.json",
            dict(command=command, elf_sha256=digest(old_elf), tool=tool),
        )
        old_sizes = _section_sizes(p.stdout.decode())
        result[name] = dict(
            new_elf_sha256=candidate["elf"]["sha256"],
            old_elf_sha256=digest(old_elf),
            new_sections={k: str(v) for k, v in new_sizes.items()},
            reference_sections={k: str(v) for k, v in old_sizes.items()},
            whole_build_delta={
                k: str(new_sizes.get(k, 0) - old_sizes.get(k, 0))
                for k in sorted(new_sizes.keys() | old_sizes.keys())
            },
            metadata_sha256=source_files,
            map_sha256=candidate["map"]["sha256"],
            scope="entire helper/init/layout build change; not isolated SDK size",
        )
    return result


def _markdown(report, runset, output):
    lines = [
        "# C2b clock-anchor pilot 報告",
        "",
        f"狀態：**{report['status']}**；有效 runs：{len(report['runs'])}／16。",
        "解析度評估：unrated。此處為相對模擬模型，"
        "時間區間不代表逐事件 timestamp 或產品 SDK CPU loading。",
        "",
        "```mermaid",
        "flowchart LR",
        " A[同一 candidate ELF] --> B[L/C/O/M sequential captures]",
        " B --> C[獨立 cache replay與FIFO/MMIO驗證]",
        " C --> D[PSF markers與native MTIME join]",
        " D --> E[Bounds / unknown / 完全一致對照]",
        " E --> F[JSON / CSV / Markdown]",
        "```",
        "",
        "```mermaid",
        "sequenceDiagram",
        " participant G as Guest",
        " participant Q as QEMU",
        " participant P as SDK PSF",
        " G->>Q: enter hook / raw cursor",
        " G->>Q: 原生 MTIME read",
        " G->>Q: sampled hook / app sample",
        " G->>P: SDK event timestamp與payload",
        " G->>Q: leave hook",
        " Note over G,P: IRQ與async applied可穿插；不將hook當retirement",
        "```",
        "",
        "| Run | Config | Injection | Rows | Model cycles | Unknown rows | "
        "Unknown % | Alignment | 證據 |",
        "|---|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in report["runs"]:
        path = os.path.relpath(runset / row["run_id"] / "capture.json", output)
        unknown = _percent(int(row["unknown_rows"]), int(row["raw_rows"]))
        lines.append(
            f"| {row['run_id']} | {row['configuration']} | {int(row['injection_enabled'])} | "
            f"{row['raw_rows']} | {row['model_cycles']} | {row['unknown_rows']} | {unknown} | "
            f"{row['alignment_status']} | [capture]({path}) |"
        )
    lines += [
        "",
        "## 對照結果",
        "",
        "| Candidate | Injection | 類型 | 結果 | 差異 |",
        "|---|---:|---|---|---|",
    ]
    for group in report["comparisons"]:
        for check in group["comparisons"]:
            lines.append(
                f"| {group['candidate']} | {group['injection']} | {check['kind']} | "
                f"{check['passed']} | {', '.join(check['mismatches'])} |"
            )
    lines += [
        "",
        "## Marker 效應：O 減 M，以 M 為分母",
        "",
        "| Candidate | Injection | Model cycles 差 | Model % | "
        "Guest ns 差 | Guest % | PSF bytes 差 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for group in report["comparisons"]:
        for check in group["comparisons"]:
            if check["kind"] == "marker-effect":
                lines.append(
                    f"| {group['candidate']} | {group['injection']} | "
                    f"{check['model_cycles_delta']} | {check['model_cycles_percent']} | "
                    f"{check['guest_elapsed_ns_delta']} | {check['guest_elapsed_ns_percent']} | "
                    f"{check['psf_bytes_delta']} |"
                )
    lines += ["", "## Bounds 分布", "", "| 項目 | 最小 | 中位數 | 最大 |", "|---|---:|---:|---:|"]
    for key, value in report["bound_statistics"].items():
        if isinstance(value, dict):
            lines.append(f"| {key} | {value['min']} | {value['median']} | {value['max']} |")
    lines += [
        "",
        "## Code size：整個 build 的差值",
        "",
        "| Candidate | .text 新／舊／差值 bytes | .rodata 差值 | .bss 差值 |",
        "|---|---|---:|---:|",
    ]
    for candidate, size in report.get("code_size", {}).items():
        old, new, delta = (
            size[k] for k in ("reference_sections", "new_sections", "whole_build_delta")
        )
        lines.append(
            f"| {candidate} | {new.get('.text')} / {old.get('.text')} / "
            f"{delta.get('.text')} | {delta.get('.rodata')} | {delta.get('.bss')} |"
        )
    lines += [
        "",
        "## 判讀與限制",
        "",
        "L/C與C/O逐項核對完整packet順序／bytes、oracle、資源、raw成本、PSF原bytes與guest計時；任何差異都不正規化。",
        "O/M差值以M為分母，分母0為null；負差值保留。"
        "host wall與child CPU僅列本次原始值，不推算穩定overhead百分比。",
        "anchors.csv列原PSF offset、sample、量化bounds、候選數與context；"
        "prefix／suffix及缺證據維持unknown，不插值。",
        "context是raw rows的歸屬，不是CPU時間百分比。marker bracket可含IRQ／其他task，"
        "exclusive CPU成本維持unavailable。",
        "request沒有安全clock，因此不提供request→applied ns latency。queue欄位僅表示cursor距離。",
        "code-size保存size -A、sections、symbols、反組譯與map。"
        "新舊ELF差值包括helper／init／layout；O/M共用ELF，不能用它量SDK編譯開關大小。",
        "本輪每組只有一份配對，未驗證重複穩定性、實機PMU、產品SDK開銷、UART或Dashboard。",
        "",
        "比較與原始host讀值見summary.json及comparisons.csv；所有檔案SHA見inventory.json。",
    ]
    if report["errors"]:
        lines += ["", "## 未完成或失敗", ""] + ["- " + str(e) for e in report["errors"]]
    return "\n".join(lines) + "\n"


def write_pilot_report(runset: Path, output: Path) -> dict:
    runset, output = runset.resolve(), output.absolute()
    if output.is_symlink():
        raise ValueError("Symlink report output")
    output.mkdir(parents=True, exist_ok=False)
    state = json.loads((runset / "runset.json").read_text())
    if state["schema"] != "clock-anchor-runset-v1":
        raise ValueError("Runset schema")
    matrix = pilot_matrix()
    errors, summaries = [], []
    if state["requested_runs"] != [asdict(s) for s in matrix]:
        errors.append("requested matrix differs from fixed16")
    if state["runs"]:
        _validate_tools(ROOT, state["tools"])
    for index, entry in enumerate(state["runs"]):
        try:
            spec = RunSpec(**entry["spec"])
            if (
                index >= 16
                or spec != matrix[index]
                or entry["path"] != spec.run_id
                or entry["run_id"] != spec.run_id
            ):
                raise ValueError("Run identity/order differs from fixed matrix")
            run = (runset / entry["path"]).resolve()
            if not run.is_relative_to(runset) or run.is_symlink():
                raise ValueError("Run path escaped")
            capture_path = run / "capture.json"
            if digest(capture_path) != entry["capture_sha256"]:
                raise ValueError("Capture receipt changed")
            capture = json.loads(capture_path.read_text())
            if (
                capture["capture_source_commit"] != state["source_commit"]
                or capture["tools"] != state["tools"]
            ):
                raise ValueError("Runset source/tools mismatch")
            summaries.append(verify_clock_capture(run, expected_identity(spec, state["tools"])))
        except (ValueError, KeyError, OSError) as e:
            errors.append(dict(run_id=entry.get("run_id"), error=str(e)))
    checks = group_comparisons(summaries)
    if len(summaries) != 16:
        errors.append("pilot incomplete: requires exact16 verified runs")
    passed = (
        len(summaries) == 16
        and len(checks) == 4
        and all(c["passed"] for c in checks)
        and not errors
    )
    report = dict(
        schema="clock-anchor-pilot-report-v1",
        status="complete" if passed else "partial",
        runs=summaries,
        comparisons=checks,
        errors=errors,
        resolution_assessment="unrated",
        runset_sha256=digest(runset / "runset.json"),
        capture_source_commit=state["source_commit"],
        analysis_source_commit=subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        analysis_source_clean=not subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=ROOT, text=True
        ),
        bound_statistics=bound_statistics(summaries),
    )
    try:
        report["code_size"] = _code_sizes(state["tools"], output)
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as e:
        report["errors"].append(dict(code_size=str(e)))
        report["status"] = "partial"
    write_json(output / "summary.json", report)
    anchors = []
    for row in summaries:
        for anchor in row["anchors"]:
            anchors.append(
                dict(
                    run_id=row["run_id"],
                    **anchor,
                    quantum_width_ns=str(int(anchor["upper_ns"]) - int(anchor["lower_ns"])),
                    hook_bracket_rows=str(
                        int(anchor["bracket_end"]) - int(anchor["bracket_start"])
                    ),
                    unknown_rows=row["unknown_rows"],
                    unknown_percent=_percent(int(row["unknown_rows"]), int(row["raw_rows"])),
                    max_queue_cursor_distance=row["scan"]["max_queue_cursor_distance"],
                )
            )
    numeric = {
        k
        for row in anchors
        for k in row
        if k
        not in (
            "run_id",
            "contexts",
            "contexts_enter_sampled",
            "contexts_sampled_leave",
            "preempted",
            "exclusive_cpu_status",
        )
    }
    write_csv_rows(output / "anchors.csv", anchors, numeric_fields=numeric)
    comparisons = [
        dict(candidate=g["candidate"], injection=str(g["injection"]), **c)
        for g in checks
        for c in g["comparisons"]
    ]
    numeric = {
        k for row in comparisons for k in row if k.endswith(("_delta", "_denominator", "_percent"))
    } | {"injection"}
    write_csv_rows(output / "comparisons.csv", comparisons, numeric_fields=numeric)
    (output / "report.md").write_text(_markdown(report, runset, output), encoding="utf-8")
    write_json(
        output / "inventory.json",
        {
            p.relative_to(output).as_posix(): dict(bytes=p.stat().st_size, sha256=digest(p))
            for p in sorted(output.rglob("*"))
            if p.is_file()
        },
    )
    return report
