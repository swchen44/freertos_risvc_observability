"""A failed API preflight must never create or inspect a browser session."""

import importlib.util
import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[2] / "tools/tcp/verify_event_window_dashboard.py"


class BrowserPreflightTests(unittest.TestCase):
    def test_connection_failure_never_launches_diagnostic_browser(self):
        spec = importlib.util.spec_from_file_location("browser_verify", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        calls = []

        def run(command, **kwargs):
            calls.append(command[0])
            if command[0] == "curl":
                time.sleep(0.05)
                return SimpleNamespace(returncode=7, stdout="000", stderr="connection refused")
            raise AssertionError("Browser command on failed preflight")

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "probe"
            with (
                patch.object(
                    module,
                    "acceptance_case",
                    return_value=dict(run_id="A02-baseline-b1-1-1", events=1, memory_cycles=1),
                ),
                patch.object(module, "process_table", return_value={}) as processes,
                patch.object(module.subprocess, "check_output", return_value="fixture-commit"),
                patch.object(module.subprocess, "run", side_effect=run),
                self.assertRaisesRegex(AssertionError, "api/event-windows"),
            ):
                module.verify("server", out)
            self.assertEqual(calls, ["curl"])
            processes.assert_not_called()
            receipt = json.loads((out / "receipt.json").read_text())
            self.assertFalse(receipt["browser_started"])
            self.assertEqual(receipt["sampled_peak_rss_kib"], 0)
            self.assertEqual(receipt["remaining_browser_pids"], [])
