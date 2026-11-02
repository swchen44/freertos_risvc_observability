"""Strict, bounded readers for C2b evidence; no clock alignment is inferred here."""

import csv
import gzip
import json
import re
import zlib
from collections.abc import Iterator
from pathlib import Path


class ClockEvidenceError(ValueError):
    """Malformed or inconsistent evidence, identified by a stable machine code."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class ClockUnavailable(ClockEvidenceError):
    """A clock domain cannot support this version's conversion."""


def decimal(value: str, *, bits: int | None = None) -> int:
    if not isinstance(value, str) or not re.fullmatch(r"0|[1-9][0-9]{0,39}", value):
        raise ClockEvidenceError("decimal")
    n = int(value)
    if bits is not None:
        if type(bits) is not int or not 1 <= bits <= 128 or n >= 1 << bits:
            raise ClockEvidenceError("integer_range")
    return n


def mtime_quantum(t: int, offset: int, hz: int) -> tuple[int, int]:
    for value in (t, offset):
        if type(value) is not int or not 0 <= value < 1 << 64:
            raise ClockEvidenceError("counter_range")
    if type(hz) is not int or not 0 <= hz < 1 << 32:
        raise ClockEvidenceError("frequency_range")
    if hz != 10_000_000:
        raise ClockUnavailable("frequency_unavailable")
    lower = ((t - offset) % (1 << 64)) * 100
    if lower >= 1 << 63:
        raise ClockEvidenceError("clock_range")
    return lower, min(lower + 100, 1 << 63)


_COMMON = {"schema", "run_id", "record_seq", "kind", "cpu", "raw_cursor", "phase"}
_SHA_FIELDS = {f"{name}_sha256" for name in ("qemu", "elf", "profile", "plugin")}
_DOMAINS = {"virtual": "qemu_virtual_ns", "mtime": "aclint_mtime64", "psf": "mtime_low32"}
_HEADER = {
    "abi_version",
    "configuration",
    "injection_enabled",
    "observer_enabled",
    "marker_mode",
    "expected_frequency_hz",
    "clock_domains",
} | _SHA_FIELDS
_FIELDS = {
    "header": _HEADER,
    "capture_begin": set(),
    "capture_end": set(),
    "cost_request": {"request_id", "request_event_index", "delta_ns", "request_clock_ns", "pc"},
    "cost_applied": {
        "request_id",
        "before_ns",
        "requested_target_ns",
        "advance_return_ns",
        "after_ns",
    },
    "marker_enter": {"marker_seq", "marker_phase", "sample64", "pc"},
    "marker_sampled": {"marker_seq", "marker_phase", "sample64", "pc"},
    "marker_leave": {"marker_seq", "marker_phase", "sample64", "pc"},
    "mtime_read": {
        "source",
        "native_io_seq",
        "address",
        "size",
        "pc",
        "virtual_ns",
        "timebase_hz",
        "time_delta",
        "mtime64",
        "value32",
    },
    "mtimecmp_write": {"source", "native_io_seq", "address", "size", "pc", "value32"},
    "epoch_change": {"reason", "old_value", "new_value"},
    "footer": {
        "complete",
        "raw_rows",
        "requests",
        "applied",
        "pending",
        "device_io",
        "plugin_io",
        "record_count",
    },
}
_PHASES = {
    "header": {"configured"},
    "footer": {"finished"},
    "capture_begin": {"before_guest_instruction"},
    "capture_end": {"before_guest_instruction"},
    "cost_request": {"instruction_before", "memory_after_success"},
    "cost_applied": {"cpu_async_outside_exec"},
    "marker_enter": {"hook_before_guest_instruction"},
    "marker_sampled": {"hook_before_guest_instruction"},
    "marker_leave": {"hook_before_guest_instruction"},
    "mtime_read": {"device_mmio", "memory_after_success"},
    "mtimecmp_write": {"device_mmio", "memory_after_success"},
    "epoch_change": {"device_epoch"},
}
_WIDTHS = {
    "pc": 32,
    "address": 32,
    "size": 32,
    "marker_seq": 32,
    "marker_phase": 32,
    "sample64": 64,
    "before_ns": 63,
    "requested_target_ns": 63,
    "advance_return_ns": 63,
    "after_ns": 63,
    "virtual_ns": 63,
    "timebase_hz": 32,
    "time_delta": 64,
    "mtime64": 64,
    "value32": 32,
    "delta_ns": 63,
}


def _validate_record(row: dict) -> None:
    if not isinstance(row, dict) or not isinstance(row.get("kind"), str):
        raise ClockEvidenceError("record_object")
    kind = row["kind"]
    if kind not in _FIELDS or set(row) != _COMMON | _FIELDS[kind]:
        raise ClockEvidenceError("record_keys")
    if row["schema"] != "clock-anchor-record-v1" or row["cpu"] != "0":
        raise ClockEvidenceError("schema_or_cpu")
    if not isinstance(row["run_id"], str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", row["run_id"]
    ):
        raise ClockEvidenceError("run_id")
    if not isinstance(row["phase"], str) or row["phase"] not in _PHASES[kind]:
        raise ClockEvidenceError("record_phase")
    decimal(row["record_seq"], bits=64)
    decimal(row["raw_cursor"], bits=64)
    if kind == "header":
        if (
            row["abi_version"] != "1"
            or row["marker_mode"] not in ("0", "1")
            or row["configuration"] not in ("L", "C", "O", "M")
            or row["expected_frequency_hz"] != "10000000"
            or row["clock_domains"] != _DOMAINS
        ):
            raise ClockEvidenceError("header_contract")
        for field in ("injection_enabled", "observer_enabled"):
            if type(row[field]) is not bool:
                raise ClockEvidenceError("flag_type")
        for field in _SHA_FIELDS:
            if not isinstance(row[field], str) or not re.fullmatch(r"[0-9a-f]{64}", row[field]):
                raise ClockEvidenceError("sha256")
        return
    if kind == "epoch_change":
        if row["reason"] not in ("mtime_write", "reset", "device_changed", "frequency_changed"):
            raise ClockEvidenceError("epoch_reason")
        for field in ("old_value", "new_value"):
            if row[field] is not None:
                decimal(row[field], bits=64)
        return
    if kind == "footer" and type(row["complete"]) is not bool:
        raise ClockEvidenceError("flag_type")
    nulls = set()
    if kind == "cost_request":
        nulls.add("request_clock_ns")
    if kind in ("marker_enter", "marker_leave"):
        nulls.add("sample64")
    if kind in ("mtime_read", "mtimecmp_write"):
        source = row["source"]
        if source not in ("device", "plugin") or row["size"] != "4":
            raise ClockEvidenceError("mmio_contract")
        expected_phase = "device_mmio" if source == "device" else "memory_after_success"
        if row["phase"] != expected_phase:
            raise ClockEvidenceError("mmio_phase")
        if source == "plugin":
            nulls |= {"virtual_ns", "timebase_hz", "time_delta", "mtime64", "value32"} & set(row)
    for field in nulls:
        if row[field] is not None:
            raise ClockEvidenceError("sample_must_be_null")
    for field in _FIELDS[kind] - nulls - {"source", "complete"}:
        decimal(row[field], bits=_WIDTHS.get(field, 64))
    if kind == "cost_request" and decimal(row["delta_ns"]) == 0:
        raise ClockEvidenceError("zero_delta")


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ClockEvidenceError("duplicate_key")
        result[key] = value
    return result


def _constant(value):
    raise ClockEvidenceError("nonfinite_json")


def _json_number(value):
    # Reject before Python's integer conversion limit. Wire counters are strings.
    raise ClockEvidenceError("json_numeric_literal")


def iter_clock_records(path: Path, *, max_line_bytes: int = 16384) -> Iterator[dict]:
    """Validate each line lazily; lifecycle/completeness belongs to the scanner."""
    if type(max_line_bytes) is not int or not 1 <= max_line_bytes <= 16384:
        raise ClockEvidenceError("line_limit")
    opener = gzip.open if path.suffix == ".gz" else open
    try:
        with opener(path, "rb") as stream:
            while line := stream.readline(max_line_bytes + 1):
                if len(line) > max_line_bytes or not line.endswith(b"\n") or line.endswith(b"\r\n"):
                    raise ClockEvidenceError("line_boundary")
                row = json.loads(
                    line.decode("utf-8"),
                    object_pairs_hook=_pairs,
                    parse_constant=_constant,
                    parse_int=_json_number,
                    parse_float=_json_number,
                )
                _validate_record(row)
                yield row
    except (OSError, EOFError, zlib.error) as e:
        raise ClockEvidenceError("wire_io") from e
    except (UnicodeError, json.JSONDecodeError, RecursionError) as e:
        raise ClockEvidenceError("wire_json") from e


def iter_access_rows(path: Path) -> Iterator[dict]:
    """Read the unchanged nine-column access format; numeric fields become ints."""
    fields = ["pc", "address", "size", "operation", "l1i", "l1d", "l2", "ram_read", "ram_write"]
    opener = gzip.open if path.suffix == ".gz" else open
    try:
        with opener(path, "rt", encoding="ascii", newline="") as stream:
            reader = csv.DictReader(stream, strict=True)
            if reader.fieldnames != fields:
                raise ClockEvidenceError("raw_columns")
            for index, row in enumerate(reader):
                if set(row) != set(fields) or any(v is None for v in row.values()):
                    raise ClockEvidenceError("raw_columns")
                op = row["operation"]
                if op not in ("I", "R", "W"):
                    raise ClockEvidenceError("raw_operation")
                values = {
                    k: decimal(row[k], bits=32 if k in fields[:3] else 64)
                    for k in fields
                    if k != "operation"
                }
                if not values["size"] or (
                    op == "I"
                    and (values["size"] not in (2, 4) or values["pc"] != values["address"])
                ):
                    raise ClockEvidenceError("raw_size_or_pc")
                yield dict(index=index, operation=op, **values)
    except (OSError, EOFError, zlib.error, UnicodeError, csv.Error) as e:
        raise ClockEvidenceError("raw_io") from e
