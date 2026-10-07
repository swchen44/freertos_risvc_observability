import importlib.util
import json
import unittest
from pathlib import Path


def owner(start=100, end=110, **kwargs):
    return dict(
        start=start,
        end=end,
        role=kwargs.get("role", "lwip"),
        function=kwargs.get("function", "f"),
        aliases=kwargs.get("aliases", ["f"]),
        object=kwargs.get("object", "ip.o"),
        source="ip.c",
        evidence=["map:20"],
        reason=None,
    )


class CostAttributionTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("psf_lab.cost_attribution"))
        from psf_lab.cost_attribution import classify_owner, normalize_ranges, resolve_pc

        self.normalize = normalize_ranges
        self.resolve = resolve_pc
        self.classify = classify_owner
        self.rules = json.loads(Path("cases/timing/attribution-rules-v1.json").read_text())

    def test_half_open_and_gap(self):
        ranges = self.normalize([owner()])
        self.assertEqual(self.resolve(ranges, 109)["role"], "lwip")
        self.assertEqual(self.resolve(ranges, 110)["role"], "unresolved")
        self.assertEqual(self.resolve(ranges, 99)["reason"], "no_executable_owner")

    def test_aliases_merge_once(self):
        ranges = self.normalize([owner(), owner(function="alias", aliases=["alias"])])
        self.assertEqual(len(ranges), 1)
        self.assertEqual(ranges[0]["aliases"], ["alias", "f"])

    def test_overlap_conflict_not_order_dependent(self):
        for records in ([owner(), owner(108, 120)], [owner(108, 120), owner()]):
            ranges = self.normalize(records)
            self.assertEqual(self.resolve(ranges, 109)["reason"], "overlap_conflict")
            self.assertEqual(self.resolve(ranges, 107)["role"], "lwip")
            self.assertEqual(self.resolve(ranges, 110)["role"], "lwip")
        for other in (owner(role="recorder"), owner(object="other.o")):
            self.assertEqual(
                self.resolve(self.normalize([owner(), other]), 100)["role"], "unresolved"
            )

    def test_invalid_addresses(self):
        for start, end in [(1, 1), (2, 1), (-1, 2), (True, 2), (1, False), ("1", 2)]:
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                self.normalize([owner(start, end)])
        for pc in (False, -1, "100"):
            with self.assertRaises(ValueError):
                self.resolve(self.normalize([owner()]), pc)

    def test_unknown_function_retains_object_identity(self):
        rows = self.normalize(
            [owner(function=None, aliases=[]), owner(120, 130, function=None, aliases=[])]
        )
        self.assertEqual(rows[0]["role"], "lwip")
        self.assertEqual(rows[0]["function"], "unresolved@ip.o:100")
        self.assertNotEqual(rows[0]["function"], rows[1]["function"])

    def test_provenance_rules_not_name_guess(self):
        fixtures = [
            ("firmware/port/trcStreamPort.c", "port.o", "write", "recorder"),
            (
                "firmware/cases/tcp_request_response.c",
                "session.o",
                "timing_observer",
                "observer_entry",
            ),
            ("firmware/other.c", "other.o", "timing_observer", "application_harness"),
            ("references/tcp/lwip/src/core/tcp.c", "tcp.o", "f", "lwip"),
            ("third_party/FreeRTOS/FreeRTOS/Source/tasks.c", "tasks.o", "f", "kernel_port"),
            (None, "/tool/lib/libg_nano.a(lib_a-memcpy.o)", "memcpy", "runtime_library"),
            (None, "libc.a", "memcpy", "unresolved"),
            (None, "unknown.o", "tcp_memcpy", "unresolved"),
        ]
        for source, obj, function, role in fixtures:
            with self.subTest(source=source, obj=obj):
                result = self.classify(
                    dict(source=source, object=obj, function=function), self.rules
                )
                self.assertEqual(result["role"], role)

    def test_conflicting_exact_rules_are_unresolved(self):
        rules = dict(
            schema="code-role-rules-v1",
            abi="rv32",
            rules=[
                dict(id="a", match_kind="source", value="x.c", role="recorder"),
                dict(id="b", match_kind="source", value="x.c", role="lwip"),
            ],
        )
        self.assertEqual(self.classify(dict(source="x.c"), rules)["role"], "unresolved")
