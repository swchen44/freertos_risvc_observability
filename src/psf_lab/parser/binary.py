"""Bounded framing for the two selected little-endian streaming PSF v14 schemas."""

import hashlib
import struct

from .errors import ParseError

MAX_BYTES = 16 * 1024 * 1024
MAX_EVENTS = 200_000


def parse_binary(data: bytes, *, source_name: str = "memory.psf", strict: bool = True) -> dict:
    if len(data) > MAX_BYTES:
        raise ParseError("resource_limit", 0, "PSF exceeds 16 MiB")
    offset = 0

    def read(fmt, code):
        nonlocal offset
        size = struct.calcsize(fmt)
        if size > len(data) - offset:
            raise ParseError(code, offset, "record exceeds remaining input")
        values = struct.unpack_from(fmt, data, offset)
        offset += size
        return values

    fields = read("<IHHIIIHBB8s", "truncated_header")
    magic, version, platform, options, cores, tail, patch, minor, major, name = fields
    if data[:4] == b"PSF\0":
        raise ParseError("unsupported_endianness", 0, "only little endian is supported")
    if magic != 0x50534600:
        raise ParseError("invalid_magic", 0, "not a PSF stream")
    if version != 14:
        raise ParseError("unsupported_version", 4, str(version))
    if cores & 0xFF != 1:
        raise ParseError("unsupported_cores", 12, "only single-core traces are supported")
    if cores != 0x301:
        raise ParseError("unsupported_stream_mode", 12, "requires a single linear stream")
    width = 8 if options & 8 else 4
    word = "Q" if width == 8 else "I"
    timer, period, frequency, wraps, tick_hz, latest, tick_count = read(
        "<II" + word + "IIII", "truncated_timestamp_metadata"
    )
    count, symbol_size, states = read("<" + word * 3, "truncated_entry_header")
    if count > 65_536 or symbol_size > 4096 or states != 3:
        raise ParseError("invalid_entry_layout", offset - width * 3, "entry limits exceeded")
    entry_size = (1 + states) * width + 4 + symbol_size
    if count * entry_size > len(data) - offset:
        raise ParseError("truncated_entries", offset, "entries exceed remaining input")
    entries = []
    for _ in range(count):
        at = offset
        values = read("<" + word * (1 + states) + "I", "truncated_entries")
        symbol = data[offset : offset + symbol_size]
        offset += symbol_size
        entries.append(
            {
                "offset": at,
                "address": hex(values[0]),
                "states": [str(v) for v in values[1 : 1 + states]],
                "options": values[-1],
                "name": symbol.split(b"\0", 1)[0].decode("utf-8", errors="replace"),
                "symbol_hex": symbol.hex(),
            }
        )
    issues = []
    if frequency == 0:
        issues.append({"code": "invalid_frequency", "offset": 40})
    events = []
    while offset < len(data):
        at = offset
        if data[at : at + 6] == b"\0FSP\x0e\0":
            raise ParseError("multiple_sessions", at, "concatenated sessions are unsupported")
        if len(events) >= MAX_EVENTS:
            raise ParseError("resource_limit", at, "event count exceeds 200000")
        try:
            wire_id, sequence, timestamp = read("<HHI", "truncated_event_header")
            payload_size = (wire_id >> 12) * width
            if payload_size > len(data) - offset:
                raise ParseError("truncated_payload", at, "event payload exceeds input")
            payload = data[offset : offset + payload_size]
            offset += payload_size
        except ParseError as error:
            if strict:
                raise
            issues.append({"code": error.code, "offset": error.offset})
            break
        events.append(
            {
                "event_id": f"0:{at}",
                "offset": at,
                "id": wire_id & 0xFFF,
                "sequence": sequence,
                "core": 0,
                "timestamp_raw": timestamp,
                "ticks": None,
                "payload_hex": payload.hex(),
                "kind": "raw",
                "actor_id": None,
                "object_id": None,
                "fields": {},
                "quality": [],
            }
        )
    return {
        "schema_version": 1,
        "source": {
            "name": source_name,
            "sha256": hashlib.sha256(data).hexdigest(),
            "byte_length": len(data),
        },
        "platform": {
            "format_version": version,
            "platform_id": platform,
            "name": name.split(b"\0", 1)[0].decode("ascii", errors="replace"),
            "schema": f"{major}.{minor}.{patch}",
            "word_bytes": width,
            "endianness": "little",
            "core_count": 1,
        },
        "clock": {
            "frequency_hz": str(frequency),
            "tick_hz": tick_hz,
            "type": timer,
            "origin_ticks": None,
            "time_model": "unspecified",
        },
        "objects": [],
        "events": events,
        "quality": {
            "status": "partial" if issues else "valid",
            "issues": issues,
            "capture_complete": None,
        },
        "derived": {},
        "raw_metadata": {
            "entries": entries,
            "period": period,
            "wraparounds": wraps,
            "latest_timestamp": latest,
            "os_tick_count": tick_count,
            "options": options,
            "core_flags": cores,
            "tailchain_threshold": tail,
        },
    }
