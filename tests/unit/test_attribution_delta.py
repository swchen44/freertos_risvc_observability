import importlib.util
import unittest
from pathlib import Path


class DeltaTests(unittest.TestCase):
    def test_offsetting_components_remain_visible(self):
        spec = importlib.util.spec_from_file_location(
            "cost_batch", Path("tools/tcp/analyze_cost_attribution.py")
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertTrue(hasattr(module, "compare_cost_reports"))
        base = dict(
            instructions=1,
            memory_cycles=10,
            model_service_ns=20,
            accounted_model_ns=21,
            cost_cycles=dict(l1i=4, l1d=6, l2=0, ram_read=0, ram_write=0),
        )
        newer = dict(base, cost_cycles=dict(l1i=2, l1d=8, l2=0, ram_read=0, ram_write=0))

        def report(metric):
            return dict(
                totals=metric,
                measurement=dict(before=0, after=1),
                by_role={"lwip": metric},
                by_function={
                    "f": dict(
                        metric,
                        owner=dict(source="f.c", object="f.o", function="f", start=100, end=110),
                    )
                },
            )

        result = module.compare_cost_reports(report(base), report(newer))
        self.assertEqual(result["by_role"]["lwip"]["memory_cycles"], 0)
        self.assertEqual(
            result["by_role"]["lwip"]["cost_cycles"],
            dict(l1i=-2, l1d=2, l2=0, ram_read=0, ram_write=0),
        )
        self.assertEqual(next(iter(result["by_function"].values()))["cost_cycles"]["l1d"], 2)
