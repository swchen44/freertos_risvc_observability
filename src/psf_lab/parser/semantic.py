"""Decode selected platform semantics while keeping every original payload."""

import re
import struct

from .binary import parse_binary
from .errors import ParseError
from .schemas import desktop, freertos


def resolve_kind(platform_name: str, event_id: int) -> str:
    schema = {"my_krnl": desktop, "FreeRTOS": freertos}.get(platform_name)
    if schema is None:
        return "unknown"
    if schema.USER_BASE < event_id < schema.USER_BASE + 8:
        return "user_event"
    if schema.FIXED_BASE <= event_id < schema.FIXED_BASE + 8:
        return "user_event_fixed"
    return schema.KINDS.get(event_id, "unknown")


def _format_message(fmt, args, bits):
    """Only integer conversions and %% are interpreted; never execute a format string."""
    parts = []
    index = 0
    last = 0
    for match in re.finditer(r"%.", fmt):
        parts.append(fmt[last : match.start()])
        token = match.group()
        if token == "%%":
            parts.append("%")
        elif token in ("%u", "%d", "%x") and index < len(args):
            value = args[index]
            index += 1
            if token == "%d" and value >= 1 << (bits - 1):
                value -= 1 << bits
            parts.append(format(value, "x") if token == "%x" else str(value))
        else:
            return fmt, False
        last = match.end()
    parts.append(fmt[last:])
    return "".join(parts), index == len(args) and "%" not in fmt[last:]


def parse_trace(data: bytes, *, source_name: str = "memory.psf", strict: bool = True) -> dict:
    trace = parse_binary(data, source_name=source_name, strict=strict)
    platform = trace["platform"]
    key = (platform["platform_id"], platform["name"], platform["schema"], platform["word_bytes"])
    schema = {desktop.KEY: desktop, freertos.KEY: freertos}.get(key)
    if schema is None:
        raise ParseError("unsupported_schema", 6, repr(key))
    width = platform["word_bytes"]
    objects = []
    active = {}
    epochs = {}
    current = None
    issues = trace["quality"]["issues"]

    def issue(code, event):
        issues.append({"code": code, "offset": event["offset"]})
        event["quality"].append(code)

    def object_for(address, offset, kind="unknown"):
        address = hex(address) if isinstance(address, int) else address
        if address == "0x0":
            return None
        if address not in active:
            epoch = epochs.get(address, -1) + 1
            epochs[address] = epoch
            obj = {
                "object_id": f"{address}:{epoch}",
                "address": address,
                "epoch": epoch,
                "kind": kind,
                "name": address,
                "created_offset": None,
                "deleted_offset": None,
                "first_seen_offset": offset,
            }
            objects.append(obj)
            active[address] = obj
        obj = active[address]
        if kind != "unknown":
            obj["kind"] = kind
        return obj

    for entry in trace["raw_metadata"]["entries"]:
        obj = object_for(entry["address"], entry["offset"])
        if obj:
            obj["name"] = entry["name"]
    previous_sequence = None
    previous_timestamp = None
    elapsed = 0
    time_valid = trace["clock"]["type"] == 1
    trace["clock"]["assumptions"] = ["less_than_one_wrap_between_events"]
    for ev in trace["events"]:
        kind = resolve_kind(platform["name"], ev["id"])
        ev["kind"] = kind
        raw = bytes.fromhex(ev["payload_hex"])
        words = struct.unpack("<" + ("I" if width == 4 else "Q") * (len(raw) // width), raw)
        ev["fields"]["raw_words"] = [str(value) for value in words]
        if previous_sequence is not None and (ev["sequence"] - previous_sequence) % 65536 != 1:
            issue("sequence_gap", ev)
            current = None
        previous_sequence = ev["sequence"]
        timestamp = ev["timestamp_raw"]
        if previous_timestamp is None:
            trace["clock"]["origin_ticks"] = str(timestamp)
        elif time_valid:
            delta = (timestamp - previous_timestamp) % (1 << 32)
            if delta > 1 << 31:
                time_valid = False
                issue("ambiguous_timestamp", ev)
            else:
                elapsed += delta
        previous_timestamp = timestamp
        if time_valid:
            ev["ticks"] = str(elapsed)
        else:
            issue("unsupported_timer" if trace["clock"]["type"] != 1 else "uncertain_time", ev)
        if kind == "unknown":
            issue("unknown_event", ev)
            current = None
        if kind in ("isr_begin", "isr_resume"):
            current = None
            issue("isr_execution_not_reconstructed", ev)
        ev["actor_id"] = current
        if kind == "object_name":
            if len(raw) <= width:
                raise ParseError(
                    "invalid_parameters", ev["offset"], "name requires handle and text"
                )
            obj = object_for(words[0], ev["offset"])
            if obj:
                obj["name"] = raw[width:].split(b"\0", 1)[0].decode("utf-8", errors="replace")
                ev["object_id"] = obj["object_id"]
                ev["fields"]["name"] = obj["name"]
        elif kind.startswith(
            (
                "task_",
                "queue_",
                "mutex_",
                "semaphore_",
                "eventgroup_",
                "timer_",
                "streambuffer_",
                "messagebuffer_",
            )
        ):
            if kind in ("task_delay", "task_delay_until"):
                ev["object_id"] = current
                continue
            if not words or (kind == "task_create" and len(words) < 2):
                raise ParseError("invalid_parameters", ev["offset"], f"missing {kind} parameters")
            object_kind = kind.split("_", 1)[0]
            obj = object_for(words[0], ev["offset"], object_kind)
            if obj:
                ev["object_id"] = obj["object_id"]
                if kind.endswith("_create"):
                    obj["created_offset"] = ev["offset"]
                if kind in (
                    "task_create",
                    "task_priority",
                    "task_prio_inherit",
                    "task_prio_disinherit",
                ):
                    if len(words) >= 2:
                        ev["fields"]["priority"] = words[1]
                if kind == "task_switch":
                    current = obj["object_id"]
                    ev["actor_id"] = current
                if kind.endswith("_delete"):
                    obj["deleted_offset"] = ev["offset"]
                    active.pop(obj["address"])
                    if current == obj["object_id"]:
                        current = None
        elif kind == "trace_start" and words:
            # trcTask.c TRACE_HANDLE_NO_TASK is the reserved value 2.
            obj = object_for(words[0], ev["offset"], "task") if words[0] != 2 else None
            current = obj["object_id"] if obj else None
            ev["actor_id"] = current
        elif kind in ("user_event", "user_event_fixed"):
            if kind == "user_event":
                nwords = ev["id"] - schema.USER_BASE
                if len(raw) <= nwords * width:
                    raise ParseError("invalid_parameters", ev["offset"], "missing inline string")
                fmt = raw[nwords * width :].split(b"\0", 1)[0].decode("utf-8", errors="replace")
                args = words[1:nwords]
            else:
                nwords = 2 + ev["id"] - schema.FIXED_BASE
                if len(words) < nwords:
                    raise ParseError("invalid_parameters", ev["offset"], "missing fixed arguments")
                fmt_obj = active.get(hex(words[1]))
                fmt = fmt_obj["name"] if fmt_obj else None
                args = words[2:nwords]
            channel = object_for(words[0], ev["offset"], "channel")
            ev["object_id"] = channel["object_id"] if channel else None
            fields = ev["fields"]
            fields.update(
                channel=channel["name"] if channel else "unknown",
                format=fmt,
                arguments=[str(arg) for arg in args],
            )
            if fmt is None:
                issue("unresolved_string", ev)
                fields["message"] = "Unresolved string"
                continue
            message, supported = _format_message(fmt, args, width * 8)
            fields["message"] = message
            if not supported:
                issue("unsupported_format", ev)
            if fmt == "Counter: %d" and args:
                fields["counter"] = args[0]
            parts = message.split("|")
            if supported and len(parts) == 4 and parts[0] == "POC" and parts[3].isdigit():
                fields.update(
                    case_id=parts[1],
                    phase=parts[2],
                    message_id=int(parts[3]),
                    request_id=int(parts[3]),
                )
    trace["objects"] = objects
    if issues:
        trace["quality"]["status"] = "partial"
    return trace
