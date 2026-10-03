import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from psf_lab.parser.semantic import parse_trace

ROOT = Path(__file__).resolve().parents[2]
QEMU_FLAGS = [
    "-machine",
    "virt",
    "-cpu",
    "rv32",
    "-smp",
    "1",
    "-m",
    "128M",
    "-bios",
    "none",
    "-display",
    "none",
    "-monitor",
    "none",
    "-serial",
    "file:console.log",
    "-accel",
    "tcg,thread=single",
    "-icount",
    "shift=0,align=off,sleep=off",
    "-semihosting-config",
    "enable=on,target=native",
]


def capture(case):
    elf = ROOT / "build" / case / "firmware.elf"
    if not elf.exists():
        raise AssertionError(f"Missing built firmware: {case}")
    with tempfile.TemporaryDirectory() as directory:
        command = ["qemu-system-riscv32", *QEMU_FLAGS, "-kernel", str(elf)]
        subprocess.run(command, cwd=directory, timeout=30, check=True, capture_output=True)
        run = Path(directory)
        trace = parse_trace((run / "trace.psf").read_bytes())
        oracle = json.loads((run / "oracle.json").read_text())
        return trace, oracle


class ClockCaptureTests(unittest.TestCase):
    def test_clock_probe_and_irq_restore(self):
        trace, oracle = capture("clock_probe")
        self.assertEqual(trace["clock"]["frequency_hz"], "10000000")
        self.assertEqual(oracle["delta_ticks"], 100)
        self.assertLessEqual(abs(int(oracle["delta_mtime"]) - 1000000), 20000)
        self.assertTrue(oracle["irq_restore_ok"])
        self.assertTrue(oracle["complete"])
        self.assertTrue(oracle["transport_ok"])

    def test_real_queue_capture(self):
        trace, oracle = capture("queue_baseline")
        self.assertEqual(trace["platform"]["name"], "FreeRTOS")
        self.assertEqual(oracle["sent_ids"], list(range(16)))
        self.assertEqual(oracle["received_ids"], list(range(16)))
        self.assertTrue(oracle["complete"])
        self.assertTrue(oracle["transport_ok"])
        for phase in ["SEND", "RECEIVE"]:
            events = [
                e["fields"]["message_id"]
                for e in trace["events"]
                if e["fields"].get("phase") == phase
            ]
            self.assertEqual(events, list(range(16)))
        self.assertTrue(any(e["fields"].get("phase") == "COMPLETE" for e in trace["events"]))
        self.assertTrue(any(e["kind"] == "queue_send" for e in trace["events"]))
        self.assertTrue(any(e["kind"] == "queue_receive" for e in trace["events"]))
