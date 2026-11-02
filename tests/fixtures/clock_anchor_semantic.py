"""Synthetic causal fixtures, hand specified independently of the C producer."""

from dataclasses import dataclass

from tests.fixtures.clock_anchor import minimal_wire, psf_markers, record


@dataclass
class ClockFixture:
    records: list
    accesses: list
    expected: dict
    psf: bytes
    anchors: list


def _header(mode, injection, rows):
    h = minimal_wire()[0]
    h.update(configuration="O" if mode else "M", marker_mode=str(mode), injection_enabled=injection)
    expected = {
        k: h[k]
        for k in (
            "run_id",
            "configuration",
            "injection_enabled",
            "observer_enabled",
            "qemu_sha256",
            "elf_sha256",
            "profile_sha256",
            "plugin_sha256",
        )
    }
    expected.update(
        candidate="baseline", marker_mode=mode, raw_rows=rows, expected_frequency_hz=10000000
    )
    return h, expected


def _raw(index, op="I", cost=1):
    row = dict(
        index=index,
        pc=2147483648 + index * 4,
        address=2147483648 + index * 4,
        size=4,
        operation=op,
        l1i=0,
        l1d=0,
        l2=0,
        ram_read=0,
        ram_write=0,
    )
    row[{"I": "l1i", "R": "l1d", "W": "ram_write"}[op]] = cost
    return row


def _finish(records, cursor, requests, io):
    records.append(
        record(
            "footer",
            len(records),
            cursor,
            "finished",
            complete=True,
            raw_rows=str(cursor),
            requests=str(requests),
            applied=str(requests),
            pending="0",
            device_io=str(io),
            plugin_io=str(io),
            record_count=str(len(records) + 1),
        )
    )


def semantic_fixture():
    header, expected = _header(0, True, 3)
    raw = [_raw(0, "I", 1), _raw(1, "R", 2), _raw(2, "W", 3)]
    records = [header, record("capture_begin", 1, 0, "before_guest_instruction")]
    for i, row in enumerate(raw, 1):
        records.append(
            record(
                "cost_request",
                len(records),
                i,
                "instruction_before" if i == 1 else "memory_after_success",
                request_id=str(i),
                request_event_index=str(i - 1),
                delta_ns=str(i * 2),
                request_clock_ns=None,
                pc=str(row["pc"]),
            )
        )
    records.append(record("capture_end", 5, 3, "before_guest_instruction"))
    for i, before, after in ((1, 1000, 1002), (2, 1002, 1006), (3, 1006, 1012)):
        records.append(
            record(
                "cost_applied",
                len(records),
                3,
                "cpu_async_outside_exec",
                request_id=str(i),
                before_ns=str(before),
                requested_target_ns=str(after),
                advance_return_ns=str(after),
                after_ns=str(after),
            )
        )
    _finish(records, 3, 3, 0)
    return ClockFixture(records, raw, expected, b"", [])


def marker_fixture():
    header, expected = _header(1, False, 25)
    records = [header, record("capture_begin", 1, 0, "before_guest_instruction")]
    raw = [_raw(i) for i in range(25)]
    io = 0
    for seq in range(1, 6):
        start = (seq - 1) * 5

        def marker(kind, cursor, sample=None, seq=seq):
            records.append(
                record(
                    kind,
                    len(records),
                    cursor,
                    "hook_before_guest_instruction",
                    marker_seq=str(seq),
                    marker_phase=str(seq),
                    sample64=sample,
                    pc=str(raw[cursor]["pc"]),
                )
            )

        def read(cursor, tick, remainder):
            nonlocal io
            io += 1
            fields = dict(
                native_io_seq=str(io),
                address=str(0x0200BFF8),
                size="4",
                pc=str(raw[cursor - 1]["pc"]),
            )
            records.append(
                record(
                    "mtime_read",
                    len(records),
                    cursor,
                    "device_mmio",
                    source="device",
                    virtual_ns=str(tick * 100 + remainder),
                    timebase_hz="10000000",
                    time_delta="0",
                    mtime64=str(tick),
                    value32=str(tick),
                    **fields,
                )
            )
            records.append(
                record(
                    "mtime_read",
                    len(records),
                    cursor,
                    "memory_after_success",
                    source="plugin",
                    virtual_ns=None,
                    timebase_hz=None,
                    time_delta=None,
                    mtime64=None,
                    value32=None,
                    **fields,
                )
            )

        marker("marker_enter", start)
        read(start + 2, 100 + 10 * seq, 5)
        marker("marker_sampled", start + 2, str(100 + 10 * seq))
        read(start + 4, 101 + 10 * seq, 7)
        marker("marker_leave", start + 4)
    records.append(record("capture_end", len(records), 25, "before_guest_instruction"))
    _finish(records, 25, 0, 10)
    return ClockFixture(records, raw, expected, psf_markers(), [4, 9, 14, 19, 24])
