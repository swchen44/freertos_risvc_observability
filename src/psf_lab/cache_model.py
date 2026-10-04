"""Deterministic data-only, write-allocate LRU tag replay; no timing feedback."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Geometry:
    size: int
    line: int
    ways: int

    def __post_init__(self):
        values = (self.size, self.line, self.ways)
        if any(type(v) is not int or v <= 0 or v & (v - 1) for v in values):
            raise ValueError('geometry values must be positive powers of two')
        if self.size < self.line * self.ways:
            raise ValueError('cache must contain at least one set')


class _Cache:
    def __init__(self, geometry):
        self.geometry = geometry
        self.sets = [[] for _ in range(geometry.size // geometry.line // geometry.ways)]
        self.used = {}
        self.evicted_used = 0
        self.evicted_fills = 0
        self.stats = dict.fromkeys(('accesses', 'misses', 'reads', 'writes',
                                   'read_misses', 'write_misses'), 0)

    def access(self, address, operation, byte_count=None):
        block = address // self.geometry.line
        entries = self.sets[block % len(self.sets)]
        hit = block in entries
        key = 'read' if operation == 'R' else 'write'
        self.stats['accesses'] += 1
        self.stats[key + 's'] += 1
        if hit:
            entries.remove(block)
        else:
            self.stats['misses'] += 1
            self.stats[key + '_misses'] += 1
            if len(entries) == self.geometry.ways:
                removed = entries.pop(0)
                self.evicted_used += self.used.pop(removed, 0).bit_count()
                self.evicted_fills += 1
        if byte_count is not None:
            offset = address % self.geometry.line
            self.used[block] = self.used.get(block, 0) | (((1 << byte_count) - 1) << offset)
        entries.append(block)
        return hit

    def result(self):
        count = self.stats['accesses']
        used = self.evicted_used + sum(mask.bit_count() for mask in self.used.values())
        filled = self.stats['misses'] * self.geometry.line
        spatial = {
            'observed_used_bytes': used, 'filled_bytes': filled,
            'evicted_unused_bytes': self.evicted_fills * self.geometry.line - self.evicted_used,
            'resident_unobserved_bytes': (self.stats['misses'] - self.evicted_fills)
            * self.geometry.line - sum(mask.bit_count() for mask in self.used.values()),
            'observed_utilization': used / filled if filled else None,
        }
        return {'geometry': asdict(self.geometry), **self.stats, 'spatial': spatial,
                'miss_rate': self.stats['misses'] / count if count else None}


def replay(events, l1_geometry, l2_geometry=None):
    """Consume (guest physical address, byte size, R/W) in capture order.

    L2 is queried only on L1 misses and contains DATA ONLY. Writes allocate
    tags. Dirty bits, writebacks, inclusion, instructions and cycles are absent.
    Each call starts cold. Rates count cache-line lookups, not CPU instructions.
    """
    if l2_geometry and l2_geometry.line != l1_geometry.line:
        raise ValueError('L1 and L2 line sizes must match')
    l1 = _Cache(l1_geometry)
    l2 = _Cache(l2_geometry) if l2_geometry else None
    count = 0
    for address, size, operation in events:
        if (type(address) is not int or type(size) is not int or address < 0
                or size <= 0 or size > 4096 or address + size > 2**64
                or operation not in ('R', 'W')):
            raise ValueError('invalid memory access')
        count += 1
        line = l1_geometry.line
        for block in range(address // line, (address + size - 1) // line + 1):
            start = max(address, block * line)
            length = min(address + size, (block + 1) * line) - start
            if not l1.access(start, operation, length) and l2:
                l2.access(block * line, operation)
    l2_result = l2.result() if l2 else None
    if l2_result:
        l2_result.pop('spatial')  # L2 fetch stream cannot measure all CPU byte uses.
    return {'schema': 'psf-lab-cache-replay-v1', 'scope': 'data-only-region',
            'initial_state': 'cold', 'replacement': 'LRU', 'write_policy': 'tag-allocate',
            'timing_feedback': False, 'memory_operations': count,
            'l1': l1.result(), 'l2': l2_result}
