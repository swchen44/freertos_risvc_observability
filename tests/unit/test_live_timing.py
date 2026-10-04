"""Native timing kernel must agree event-for-event with the Python oracle."""

import ctypes
import json
import random
import subprocess
import tempfile
import unittest
from pathlib import Path

from psf_lab.memory_timing import COSTS, from_profile

ROOT = Path(__file__).resolve().parents[2]


class LiveTimingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.source = ROOT / "tools/qemu/live_timing.c"
        if not cls.source.exists():
            return
        lib = Path(cls.temp.name) / "timing.so"
        subprocess.run(
            [
                "cc",
                "-shared",
                "-fPIC",
                "-O2",
                "-Wall",
                "-Wextra",
                "-Werror",
                str(cls.source),
                "-o",
                str(lib),
            ],
            check=True,
        )
        cls.lib = ctypes.CDLL(str(lib))
        cls.lib.timing_access.argtypes = [
            ctypes.c_uint64,
            ctypes.c_uint,
            ctypes.c_char,
            ctypes.POINTER(ctypes.c_uint64),
        ]
        cls.lib.timing_access.restype = ctypes.c_int

    def setUp(self):
        self.assertTrue(self.source.exists(), "Native timing kernel not implemented")
        self.lib.timing_reset()
        self.model = from_profile(json.loads((ROOT / "cases/timing/sysram-10.json").read_text()))

    def access(self, address, size, operation):
        costs = (ctypes.c_uint64 * 5)()
        status = self.lib.timing_access(address, size, operation.encode(), costs)
        return status, list(costs)

    def check_stream(self, stream):
        for address, size, operation in stream:
            status, costs = self.access(address, size, operation)
            self.assertEqual(status, 0)
            expected = self.model.access(address, size, operation)
            self.assertEqual(costs, [expected[k] for k in COSTS], (address, size, operation))

    def test_cold_warm_split_l1_and_write_through(self):
        self.check_stream([(0x80000000, 4, op) for op in ("R", "R", "I", "I", "W", "W")])

    def test_cross_line_and_lru_conflicts(self):
        stream = [(0x8000003F, 8, "W"), (0x8000003F, 8, "R")]
        stream += [(0x80000000 + i * 16384, 4, "R") for i in (0, 1, 2, 3, 0, 4, 1, 0)]
        self.check_stream(stream)

    def test_mixed_seeded_stream(self):
        rng = random.Random(500)
        self.check_stream(
            [
                (
                    0x80000000 + rng.randrange(0, 128 * 1024),
                    rng.choice((1, 2, 4, 8, 64, 128)),
                    rng.choice("IRW"),
                )
                for _ in range(5000)
            ]
        )

    def test_invalid_request_preserves_cache_state(self):
        for args in [
            (0x7FFFFFFF, 4, "R"),
            (0x87FFFFFF, 4, "W"),
            (0x80000000, 0, "I"),
            (0x80000000, 4097, "R"),
            (0x80000000, 4, "X"),
            (2**64 - 1, 4, "R"),
        ]:
            self.assertEqual(self.access(*args)[0], -1)
        self.check_stream([(0x80000000, 4, "R"), (0x87FFFFFC, 4, "W")])
