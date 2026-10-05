import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.tcp import run_workload_matrix as batch


class BatchTests(unittest.TestCase):
    def test_unignored_sibling_logs_are_rejected_before_creation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with (
                patch.object(batch, "ROOT", root),
                patch("sys.argv", ["batch", "--output", str(root / "runs/new")]),
                patch.object(batch.subprocess, "check_output", return_value=b""),
                patch.object(batch.subprocess, "run") as run,
            ):
                run.return_value.returncode = 0

                def status(*args, **kwargs):
                    from types import SimpleNamespace

                    return SimpleNamespace(returncode=int("-logs" in args[0][-1]))

                run.side_effect = status
                with self.assertRaises(SystemExit):
                    batch.main()
            self.assertFalse((root / "runs/new-logs").exists())
