import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.unit.test_binary import FIXTURE


class DecodeCLITests(unittest.TestCase):
    def test_decode_writes_json(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "trace.json"
            result = subprocess.run(
                [sys.executable, "-m", "psf_lab", "decode", str(FIXTURE), "--output", str(output)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(json.loads(output.read_text())["events"]), 309)

    def test_invalid_input_does_not_write_success(self):
        with tempfile.TemporaryDirectory() as temp:
            bad = Path(temp) / "bad.psf"
            bad.write_bytes(b"bad")
            output = Path(temp) / "trace.json"
            result = subprocess.run(
                [sys.executable, "-m", "psf_lab", "decode", str(bad), "--output", str(output)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 2)
            self.assertFalse(output.exists())
