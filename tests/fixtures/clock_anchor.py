"""Hand-authored wire and PSF fixtures, independent of the clock observer."""

import json
import struct

from tests.fixtures.binary import event, stream


def record(kind, seq, cursor, phase, **fields):
    return dict(
        schema="clock-anchor-record-v1",
        run_id="fixture-O-1",
        record_seq=str(seq),
        kind=kind,
        cpu="0",
        raw_cursor=str(cursor),
        phase=phase,
        **fields,
    )


def minimal_wire():
    """Four syntactically valid lines; not a verified runtime capture."""
    return [
        record(
            "header",
            0,
            0,
            "configured",
            abi_version="1",
            configuration="O",
            injection_enabled=True,
            observer_enabled=True,
            marker_mode="1",
            expected_frequency_hz="10000000",
            qemu_sha256="a" * 64,
            elf_sha256="b" * 64,
            profile_sha256="c" * 64,
            plugin_sha256="d" * 64,
            clock_domains={
                "virtual": "qemu_virtual_ns",
                "mtime": "aclint_mtime64",
                "psf": "mtime_low32",
            },
        ),
        record("capture_begin", 1, 0, "before_guest_instruction"),
        record("capture_end", 2, 0, "before_guest_instruction"),
        record(
            "footer",
            3,
            0,
            "finished",
            complete=True,
            raw_rows="0",
            requests="0",
            applied="0",
            pending="0",
            device_io="0",
            plugin_io="0",
            record_count="4",
        ),
    ]


def write_wire(path, records):
    path.write_bytes(b"".join((json.dumps(r) + "\n").encode() for r in records))


def psf_markers(*, base=100, sequence_start=1):
    events = []
    for i, (handle, text) in enumerate(((4, "C2B"), (5, "C2Bv1|%u|%u|%u|%u"))):
        raw = struct.pack("<I", handle) + text.encode() + b"\0"
        raw += bytes(-len(raw) % 4)
        words = struct.unpack("<" + "I" * (len(raw) // 4), raw)
        events.append(event(3, (sequence_start + i) % 65536, (base - 1) % (1 << 32), words))
    for i in range(1, 6):
        sample = base + i * 10
        events.append(
            event(
                0x9C,
                (sequence_start + i + 1) % 65536,
                (sample + 1) % (1 << 32),
                (4, 5, i, i, sample % (1 << 32), sample >> 32),
            )
        )
    return stream(*events, frequency=10_000_000)
