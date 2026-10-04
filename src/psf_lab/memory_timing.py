"""Serialized memory-service estimates, with no CPU or QEMU clock feedback.

All levels use LRU, write-through and write-allocate. Stores synchronously
reach RAM even on L1 hits. A missing L2 line is read before a partial store.
This explicit simple policy is not a claim about the product's cache policy.
"""

from dataclasses import asdict, dataclass

from psf_lab.cache_model import Geometry, _Cache

COSTS = ("l1i", "l1d", "l2", "ram_read", "ram_write")


def nonnegative(value):
    return type(value) is int and value >= 0


@dataclass(frozen=True)
class Region:
    name: str
    start: int
    end: int
    cacheable: bool
    read_latency_cycles: int
    write_latency_cycles: int
    bus_bytes_per_cycle: int

    def __post_init__(self):
        if (
            not isinstance(self.name, str)
            or not self.name
            or not nonnegative(self.start)
            or not nonnegative(self.end)
            or not self.start < self.end <= 2**64
            or type(self.cacheable) is not bool
            or not nonnegative(self.read_latency_cycles)
            or not nonnegative(self.write_latency_cycles)
            or type(self.bus_bytes_per_cycle) is not int
            or self.bus_bytes_per_cycle <= 0
        ):
            raise ValueError("Invalid memory region")

    def service(self, size, write=False):
        latency = self.write_latency_cycles if write else self.read_latency_cycles
        return latency + (size + self.bus_bytes_per_cycle - 1) // self.bus_bytes_per_cycle


class MemoryTiming:
    def __init__(
        self, *, regions, l1i=None, l1d=None, l2=None, l1i_cycles=1, l1d_cycles=1, l2_cycles=8
    ):
        geometries = (
            l1i or Geometry(16384, 64, 4),
            l1d or Geometry(16384, 64, 4),
            l2 or Geometry(65536, 64, 4),
        )
        if len({g.line for g in geometries}) != 1:
            raise ValueError("Cache line sizes must match")
        self.line = geometries[0].line
        self.regions = sorted(regions, key=lambda r: r.start)
        if not self.regions or len({r.name for r in self.regions}) != len(self.regions):
            raise ValueError("Memory regions must be nonempty with unique names")
        previous_end = 0
        for region in self.regions:
            if region.start % self.line or region.end % self.line or region.start < previous_end:
                raise ValueError("Regions must be line-aligned and nonoverlapping")
            previous_end = region.end
        if any(not nonnegative(v) for v in (l1i_cycles, l1d_cycles, l2_cycles)):
            raise ValueError("Lookup latencies must be nonnegative integer cycles")
        self.lookup = dict(l1i=l1i_cycles, l1d=l1d_cycles, l2=l2_cycles)
        self.caches = dict(zip(("l1i", "l1d", "l2"), map(_Cache, geometries), strict=True))
        self.costs = dict.fromkeys(COSTS, 0)
        self.transactions = dict(ram_read=0, ram_write=0)
        self.operations = dict(I=0, R=0, W=0)
        self.region_costs = {r.name: dict(ram_read=0, ram_write=0) for r in self.regions}

    def access(self, address, size, operation):
        if (
            not nonnegative(address)
            or type(size) is not int
            or not 0 < size <= 4096
            or address + size > 2**64
            or operation not in ("I", "R", "W")
        ):
            raise ValueError("Invalid memory access")
        # Preflight the entire access; a gap must not partially mutate replay state.
        pieces = []
        for block in range(address // self.line, (address + size - 1) // self.line + 1):
            start = max(address, block * self.line)
            end = min(address + size, (block + 1) * self.line)
            region = next((r for r in self.regions if r.start <= start and end <= r.end), None)
            if region is None:
                raise ValueError("Unmapped memory access")
            pieces.append((start, end - start, region))
        costs = dict.fromkeys(COSTS, 0)
        self.operations[operation] += 1

        def ram(region, length, write=False):
            key = "ram_write" if write else "ram_read"
            cycles = region.service(length, write)
            costs[key] += cycles
            self.region_costs[region.name][key] += cycles
            self.transactions[key] += 1

        for start, length, region in pieces:
            if not region.cacheable:
                ram(region, length, operation == "W")
                continue
            level = "l1i" if operation == "I" else "l1d"
            rw = "W" if operation == "W" else "R"
            costs[level] += self.lookup[level]
            hit = self.caches[level].access(start, rw)
            if not hit or operation == "W":
                costs["l2"] += self.lookup["l2"]
                if not self.caches["l2"].access(start, rw):
                    ram(region, self.line)
            if operation == "W":
                ram(region, length, True)
        for key in COSTS:
            self.costs[key] += costs[key]
        return dict(costs, total=sum(costs.values()))

    def result(self):
        levels = {}
        for name, cache in self.caches.items():
            levels[name] = cache.result()
            levels[name].pop("spatial")
        return dict(
            schema="memory-service-v1",
            estimated_memory_service_cycles=sum(self.costs.values()),
            cpu_cycles=None,
            guest_time_changed=False,
            policy="serial LRU; non-inclusive; write-through + write-allocate at both levels",
            initial_state="cold; continuous input trace",
            cost_cycles=dict(self.costs),
            operations=dict(self.operations),
            regions=[asdict(r) for r in self.regions],
            lookup_cycles=dict(self.lookup),
            region_cost_cycles={name: dict(costs) for name, costs in self.region_costs.items()},
            ram_read_transactions=self.transactions["ram_read"],
            ram_write_transactions=self.transactions["ram_write"],
            **levels,
        )


def from_profile(profile):
    required = {"schema", "name", "assumptions", "write_policy", "caches", "regions"}
    if (
        set(profile) != required
        or profile["schema"] != "memory-timing-profile-v1"
        or profile["write_policy"] != "write-through-write-allocate"
        or not isinstance(profile["name"], str)
        or not profile["name"]
        or not isinstance(profile["assumptions"], str)
        or not profile["assumptions"]
        or set(profile["caches"]) != {"l1i", "l1d", "l2"}
    ):
        raise ValueError("Unsupported or incomplete timing profile")
    kwargs = {}
    for name, fields in profile["caches"].items():
        if set(fields) != {"size", "line", "ways", "lookup_cycles"}:
            raise ValueError("Incomplete cache configuration")
        kwargs[name] = Geometry(fields["size"], fields["line"], fields["ways"])
        kwargs[name + "_cycles"] = fields["lookup_cycles"]
    kwargs["regions"] = [Region(**r) for r in profile["regions"]]
    return MemoryTiming(**kwargs)
