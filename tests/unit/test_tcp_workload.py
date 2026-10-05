import copy
import json
import tempfile
import unittest
from pathlib import Path

from psf_lab.tcp_session import validate_request_pbufs, validate_session
from psf_lab.tcp_workload import load_workload, validate_workload
from tests.unit.test_tcp_session import fixture

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "cases/tcp/workload-matrix-v1.json"


class WorkloadTests(unittest.TestCase):
    def test_registry_and_no_mutation(self):
        cases = [load_workload(REGISTRY, f"A{i:02}") for i in range(1, 9)]
        self.assertEqual([c["request_bytes"] for c in cases], [64, 64, 63, 65, 256, 256, 64, 1460])
        before = copy.deepcopy(cases[1])
        result = validate_workload(cases[1])
        result["request_segments"][0] = 99
        self.assertEqual(cases[1], before)

    def test_invalid_values(self):
        case = dict(id="A02", request_bytes=64, request_segments=[13, 0, 51], rounds=2)
        for key, values in {
            "request_bytes": [0, -1, True, 64.0, 1461],
            "request_segments": [[0, 64], [13, 50], [True, 63], [-1, 65], [1] * 64],
            "rounds": [True, 1, 2.0],
            "id": ["", "../a"],
        }.items():
            for value in values:
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    validate_workload({**case, key: value})
        with self.assertRaises(ValueError):
            validate_workload({**case, "extra": 1})

    def test_duplicate_and_unknown_registry_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "registry.json"
            case = dict(id="A01", request_bytes=64, request_segments=[64], rounds=2)
            p.write_text(json.dumps({"schema": "tcp-workloads-v1", "cases": [case, case]}))
            with self.assertRaises(ValueError):
                load_workload(p, "A01")
        with self.assertRaises(ValueError):
            load_workload(REGISTRY, "missing")

    def test_receipt_is_observed_and_strict(self):
        w = load_workload(REGISTRY, "A02")
        m = {"request_pbufs": [{"lengths": [13, 0, 51], "totals": [64, 51, 51]} for _ in range(2)]}
        self.assertEqual(validate_request_pbufs(m, "matrix", workload=w)["nodes"], 6)
        for broken in [{}, {"request_pbufs": [{"lengths": [64], "totals": [64]}] * 2}]:
            with self.assertRaises(ValueError):
                validate_request_pbufs(broken, "matrix", workload=w)
        m["request_pbufs"][0]["totals"][0] = 64.0
        with self.assertRaises(ValueError):
            validate_request_pbufs(m, "matrix", workload=w)

    def test_variable_payload_independent_protocol_oracle(self):
        packets, metrics = fixture()
        w = load_workload(REGISTRY, "A04")
        # Transform hand-built transcript using protocol sequence positions, not production oracle.
        client = 1001
        for index, p in enumerate(packets):
            if index >= 3:
                if p["direction"] == "rx":
                    p["seq"] = client
                else:
                    p["ack"] = client
                if index in (3, 12):
                    round_id = (index - 3) // 9
                    p["payload"] = bytes((round_id + i) % 256 for i in range(65))
                    client += 65
                if index == 21:
                    client += 1
        metrics["request_bytes"] = 130
        self.assertEqual(validate_session(packets, metrics, workload=w)["request_bytes"], 130)
        for kind in ("payload", "ack", "length"):
            bad = copy.deepcopy(packets)
            if kind == "ack":
                bad[5]["ack"] += 1
            elif kind == "length":
                bad[3]["payload"] = bad[3]["payload"][:-1]
            else:
                bad[3]["payload"] = bytes(65)
            with self.assertRaises(ValueError):
                validate_session(bad, metrics, workload=w)

    def test_valid_standalone_request_ack_and_bad_ack(self):
        packets, metrics = fixture()
        w = load_workload(REGISTRY, "A01")
        ack = dict(direction="tx", seq=9001, ack=1065, flags=16, payload=b"")
        packets.insert(4, ack)
        self.assertEqual(validate_session(packets, metrics, workload=w)["packets"], 26)
        ack["ack"] += 1
        with self.assertRaises(ValueError):
            validate_session(packets, metrics, workload=w)
