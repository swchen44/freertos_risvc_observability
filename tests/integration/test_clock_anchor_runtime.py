"""Opt-in real TCP sidecar validation and retained corruption/rejection probes."""

import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys
import unittest
import uuid
from pathlib import Path

from psf_lab.clock_anchor_capture import RunSpec, _run_qemu, capture_one
from psf_lab.clock_anchor_evidence import verify_clock_capture
from psf_lab.clock_anchor_wire import ClockEvidenceError
from psf_lab.runner import QEMU_FLAGS, digest, write_json
from tests.integration.clock_anchor_support import load_runtime_config


@unittest.skipUnless(os.environ.get("C2B_REQUIRE_QEMU") == "1", "C2b runtime not-performed; opt in")
class ClockAnchorRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config = load_runtime_config()
        cls.root = Path(config["root"])
        cls.tools = json.loads(Path(config["tools_manifest"]).read_text())
        cls.output = Path(config["output_parent"]) / ("causal-" + uuid.uuid4().hex)
        cls.output.mkdir(parents=True)
        cls.captured_run = cls.output / "observed"
        cls.capture = capture_one(
            cls.root,
            RunSpec("baseline", "O", 1),
            cls.tools,
            cls.tools["candidates"]["baseline"],
            cls.captured_run,
        )

    def test_real_tcp_o_has_five_verified_bounds(self):
        self.assertEqual(self.capture["status"], "captured-unvalidated")
        # QEMU keeps one vcpu_init callback per plugin/event; context must survive.
        log = (self.captured_run / "qemu.log").read_text()
        self.assertIn("context_capabilities registers=", log)
        self.assertIn("mcause_matches=1", log)
        result = verify_clock_capture(self.captured_run, self.capture["expected"])
        write_json(self.output / "validation.json", result)
        self.assertEqual(result["application_status"], "passed")
        self.assertEqual(result["evidence_status"], "valid")
        self.assertEqual(result["alignment_status"], "verified-bounds")
        self.assertEqual(len(result["anchors"]), 5)
        self.assertGreater(int(result["unknown_rows"]), 0)
        self.assertEqual(result["scan"]["pending"], "0")
        self.assertEqual(result["context"]["quality"], "exact")

    def test_sidecar_missing_footer_duplicate_request_and_hash_mismatch(self):
        for fault, code in (
            ("footer", "missing_footer"),
            ("duplicate", "request_order"),
            ("hash", "file_hash"),
        ):
            run = self.output / fault
            shutil.copytree(self.captured_run, run)
            path = run / "clock.jsonl.gz"
            # Streaming edit; retain all originals and each deliberately bad copy.
            changed = run / "changed.gz"
            sha = hashlib.sha256()
            size = 0
            count = 0
            with gzip.open(path, "rb") as src, gzip.open(changed, "wb") as dst:
                for line in src:
                    row = json.loads(line)
                    if fault == "footer" and row["kind"] == "footer":
                        continue
                    if row["kind"] == "cost_request":
                        count += 1
                        if count == 2 and fault in ("duplicate", "hash"):
                            row["request_id"] = "1"
                            line = (json.dumps(row) + "\n").encode()
                    dst.write(line)
                    sha.update(line)
                    size += len(line)
            changed.replace(path)
            captured = json.loads((run / "capture.json").read_text())
            if fault != "hash":
                captured["files"][path.name].update(sha256=digest(path), bytes=path.stat().st_size)
                captured["streams"]["clock.jsonl"].update(
                    content_sha256=sha.hexdigest(), content_bytes=size
                )
                write_json(run / "capture.json", captured)
            with self.subTest(fault=fault), self.assertRaises(ClockEvidenceError) as caught:
                verify_clock_capture(run, captured["expected"])
            self.assertEqual(caught.exception.code, code)

    def test_new_qemu_bad_cmdline_and_abi_smp_rejections(self):
        out = self.output / "bad-cmdline"
        out.mkdir()
        flags = QEMU_FLAGS.copy()
        flags[flags.index("-semihosting-config") + 1] += ",arg=c2b-markers=2"
        result = _run_qemu(
            [self.tools["clock_qemu"]["path"], *flags, "-kernel", self.tools["probe_elf"]["path"]],
            out,
        )
        write_json(out / "result.json", result)
        self.assertFalse(result["timed_out"])
        self.assertNotEqual(result["exit_code"], 0)
        abi_out = self.output / "abi-rejections"
        command = [
            sys.executable,
            str(self.root / "tests/integration/clock_anchor_abi.py"),
            "--help",
        ]
        # Real ABI CLI below; help is not counted as runtime evidence.
        help_result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        self.assertEqual(help_result.returncode, 0)
        command = command[:-1] + [
            "--build-manifest",
            self.tools["qemu_build_manifest"]["path"],
            "--guest-config",
            os.environ["C2B_RUNTIME_CONFIG"],
            "--output",
            str(abi_out),
        ]
        with (self.output / "abi-runtime.log").open("wb") as log:
            result = subprocess.run(
                command, cwd=self.root, stdout=log, stderr=subprocess.STDOUT, timeout=180
            )
        write_json(
            self.output / "abi-command.json", dict(command=command, exit_code=result.returncode)
        )
        self.assertEqual(result.returncode, 0)
