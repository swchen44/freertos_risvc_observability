import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from psf_lab.doctor import inspect_tools


class DoctorTests(unittest.TestCase):
    def test_missing_tool_fails_preflight(self):
        with patch.dict(os.environ, {"PATH": ""}):
            result = inspect_tools(("not-a-tool",))
        self.assertFalse(result["ok"])
        self.assertEqual(result["missing"], ["not-a-tool"])

    def test_real_executable_is_identified(self):
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / "fake-tool"
            binary.write_text("#!/bin/sh\nprintf 'test-tool 1.2\\n'\n")
            binary.chmod(0o755)
            with patch.dict(os.environ, {"PATH": directory}):
                result = inspect_tools(("fake-tool",))
            self.assertTrue(result["ok"])
            self.assertEqual(result["tools"]["fake-tool"]["version"], "test-tool 1.2")
            self.assertEqual(len(result["tools"]["fake-tool"]["sha256"]), 64)

    def test_version_command_failure_is_not_available(self):
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / "broken"
            binary.write_text("#!/bin/sh\nexit 7\n")
            binary.chmod(0o755)
            with patch.dict(os.environ, {"PATH": directory}):
                self.assertFalse(inspect_tools(("broken",))["ok"])
