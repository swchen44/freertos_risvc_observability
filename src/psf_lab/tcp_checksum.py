"""Byte-order-explicit Internet checksum oracle; not the benchmark algorithm."""


def internet_checksum(data: bytes) -> int:
    """Return the complemented one's-complement sum in network numeric order."""
    if len(data) % 2:
        data += b"\0"
    total = sum(int.from_bytes(data[i : i + 2], "big") for i in range(0, len(data), 2))
    while total >> 16:
        total = (total & 0xFFFF) + (total >> 16)
    return (~total) & 0xFFFF
