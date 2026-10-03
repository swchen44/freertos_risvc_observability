"""Hand-packed PSF v14 fixture; independent of production decoder."""

import struct


def event(event_id=0x25, sequence=5, timestamp=100, words=(0x1234,), width=4):
    return struct.pack("<HHI", (len(words) << 12) | event_id, sequence, timestamp) + (
        struct.pack("<" + ("I" if width == 4 else "Q") * len(words), *words)
    )


def stream(*events, width=4, frequency=1000, entry_count=0, symbol_size=28, states=3):
    header = struct.pack(
        "<IHHIIIHBB8s",
        0x50534600,
        14,
        0x1AA1 if width == 4 else 0x1FF1,
        0 if width == 4 else 8,
        0x301,
        0,
        0,
        2 if width == 4 else 0,
        1,
        b"FreeRTOS" if width == 4 else b"my_krnl\0",
    )
    word = "I" if width == 4 else "Q"
    timestamp = struct.pack("<II" + word + "IIII", 1, 0, frequency, 0, 1000, 0, 0)
    table = struct.pack("<" + word * 3, entry_count, symbol_size, states)
    return header + timestamp + table + b"".join(events)
