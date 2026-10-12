import copy
import importlib
import unittest

from psf_lab.memory_timing import from_profile
from tests.unit.test_cost_attribution import owner


def profile():
    return dict(
        schema="memory-timing-profile-v1",
        name="toy",
        assumptions="hand calculation",
        write_policy="write-through-write-allocate",
        caches={
            k: dict(size=128, line=64, ways=1, lookup_cycles=1 if k != "l2" else 8)
            for k in ("l1i", "l1d", "l2")
        },
        regions=[
            dict(
                name="ram",
                start=0,
                end=4096,
                cacheable=True,
                read_latency_cycles=10,
                write_latency_cycles=10,
                bus_bytes_per_cycle=8,
            )
        ],
    )


def rows_for(accesses):
    model = from_profile(profile())
    return [
        dict(
            pc=pc,
            address=a,
            size=s,
            operation=op,
            **{k: v for k, v in model.access(a, s, op).items() if k != "total"},
        )
        for pc, a, s, op in accesses
    ]


class HotspotReportTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(
            importlib.util.find_spec("psf_lab.hotspot_report"), "missing hotspot implementation"
        )
        self.module = importlib.import_module("psf_lab.hotspot_report")
        self.identity = dict(
            run_id="toy", workload="A02", variant="baseline", family="b1", mode=1, repeat=1
        )

    def build(self, rows, contexts=None):
        return self.module.build_hotspot_report(
            rows, [owner(0, 512)], profile(), identity=self.identity, contexts=contexts
        )

    def test_same_function_context_is_joint_not_marginal(self):
        rows = rows_for([(100, 100, 4, "I")] * 2)
        r = self.build(
            rows, [dict(start=0, end=1, context="task:A"), dict(start=1, end=2, context="irq:7")]
        )
        self.assertEqual(r["totals"]["instructions"], 2)
        self.assertEqual(r["totals"]["memory_cycles"], 28)
        self.assertEqual(sorted(f["memory_cycles"] for f in r["facts"]), [1, 27])
        self.assertEqual([f["instructions"] for f in r["facts"]], [1, 1])
        self.assertEqual(self.build(rows)["facts"][0]["context"], "unknown")

    def test_write_hit_and_cross_line(self):
        r = self.build(rows_for([(100, 0, 4, "R"), (100, 0, 4, "W"), (100, 62, 4, "R")]))
        self.assertEqual(
            r["totals"]["cache"]["l1d"],
            dict(accesses=4, misses=2, compulsory=2, conflict=0, capacity=0),
        )
        self.assertEqual(r["totals"]["cache"]["l2"]["accesses"], 3)
        self.assertEqual(r["totals"]["cost_cycles"]["ram_write"], 11)

    def test_three_c_and_unresolved(self):
        for blocks, want in [([0, 2, 0], (2, 1, 0)), ([0, 1, 2, 0], (3, 0, 1))]:
            r = self.build(rows_for([(999, b * 64, 4, "R") for b in blocks]))
            c = r["totals"]["cache"]["l1d"]
            self.assertEqual(tuple(c[k] for k in ("compulsory", "conflict", "capacity")), want)
            self.assertEqual(r["facts"][0]["role"], "unresolved")

    def test_reject_bad_costs_and_coverage(self):
        rows = rows_for([(100, 100, 4, "I")])
        for val in (True, -1, "-1", "1.5", 1.5, 28):
            with self.subTest(val=val), self.assertRaises(ValueError):
                self.build([dict(rows[0], l1i=val)])
        for intervals in (
            [dict(start=1, end=2, context="x")],
            [dict(start=0, end=2, context="x")],
            [],
        ):
            with self.assertRaises(ValueError):
                self.build(rows, intervals)
        with self.assertRaises(ValueError):
            self.build([])
        r = self.build(rows)
        r["facts"][0]["memory_cycles"] += 1
        with self.assertRaises(ValueError):
            self.module.validate_hotspot_report(r)

    def test_decimal_rows_and_noncacheable(self):
        rows = rows_for([(100, 100, 4, "I")])
        self.assertEqual(
            self.build([{k: str(v) for k, v in rows[0].items()}])["totals"]["memory_cycles"], 27
        )
        p = copy.deepcopy(profile())
        p["regions"][0]["cacheable"] = False
        costs = from_profile(p).access(100, 4, "R")
        costs.pop("total")
        r = self.module.build_hotspot_report(
            [dict(pc=100, address=100, size=4, operation="R", **costs)],
            [],
            p,
            identity=self.identity,
            contexts=None,
        )
        self.assertEqual(r["totals"]["cache"]["l2"]["accesses"], 0)
        self.assertEqual(r["totals"]["memory_cycles"], 11)
