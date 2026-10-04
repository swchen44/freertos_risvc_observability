"""Split I/D L1 and unified non-inclusive L2 locality model; no cycle estimates."""

from psf_lab.cache_model import Geometry, _Cache


def replay_split(events, l1i=None, l1d=None, l2=None):
    geometries = (
        l1i or Geometry(16384, 64, 4),
        l1d or Geometry(16384, 64, 4),
        l2 or Geometry(65536, 64, 4),
    )
    if len({g.line for g in geometries}) != 1:
        raise ValueError("cache line sizes must match")
    instruction, data, shared = [_Cache(g) for g in geometries]
    counts = {"I": 0, "R": 0, "W": 0}
    for address, size, operation in events:
        if (
            type(address) is not int
            or type(size) is not int
            or address < 0
            or size <= 0
            or size > 4096
            or address + size > 2**64
            or operation not in counts
        ):
            raise ValueError("invalid access")
        counts[operation] += 1
        cache = instruction if operation == "I" else data
        rw = "R" if operation == "I" else operation
        line = cache.geometry.line
        for block in range(address // line, (address + size - 1) // line + 1):
            start = max(address, block * line)
            length = min(address + size, (block + 1) * line) - start
            if not cache.access(start, rw, length):
                shared.access(block * line, rw)
    result = shared.result()
    result.pop("spatial")
    return {
        "schema": "tcp-split-cache-v1",
        "initial_state": "cold-per-TX-phase",
        "policy": "LRU, write-allocate tags, non-inclusive; no dirty/writeback timing",
        "cycles": None,
        "events": counts,
        "l1i": instruction.result(),
        "l1d": data.result(),
        "l2": result,
    }
