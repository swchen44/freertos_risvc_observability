import copy
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from psf_lab.runner import digest
from psf_lab.tcp_workload_matrix import plugin_contract, require_keys


class MatrixIntegrityTests(unittest.TestCase):
    def test_hash_maps_cannot_omit_required_artifacts(self):
        for mapping in ({}, {"trace.psf": "sha"}):
            with self.assertRaisesRegex(ValueError, "Missing required"):
                require_keys(mapping, {"trace.psf", "firmware.elf"})
        require_keys({"trace.psf": "sha", "firmware.elf": "sha"}, {"trace.psf"})

    def test_plugin_tamper_and_output_path_rejected(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            runset = root / "A01-baseline"
            runset.mkdir()
            plugin = runset / "live_cache.dylib"
            plugin.write_bytes(b"plugin")
            manifest = dict(
                plugin_command=["cc", "-DPOC_SMALL_CACHE", "-o", str(plugin)],
                plugin_sha256=digest(plugin),
            )
            expected = plugin_contract(root, runset, manifest)
            self.assertEqual(expected[-1], "<plugin-output>")
            self.assertEqual(manifest["plugin_command"][-1], str(plugin))
            bad = copy.deepcopy(manifest)
            bad["plugin_command"][-1] = "/other/wrong/live_cache.dylib"
            with self.assertRaises(ValueError):
                plugin_contract(root, runset, bad)
            plugin.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                plugin_contract(root, runset, manifest)

    def test_wrong_workload_and_profile_are_rejected_before_replay(self):
        import json

        from psf_lab.tcp_workload_matrix import analyze_matrix

        repo = Path(__file__).resolve().parents[2]
        manifest = json.loads(
            (repo / "runs/tcp-workload-matrix-v1/A01-baseline/manifest.json").read_text()
        )
        for key, value in [
            ("workload", {}),
            ("cache_profile", "wrong.json"),
            ("checksum_opt", "O2"),
        ]:
            with self.subTest(key=key), TemporaryDirectory() as temp:
                root = Path(temp)
                (root / "cases/tcp").mkdir(parents=True)
                (root / "cases/timing").mkdir(parents=True)
                for name in [
                    "cases/tcp/workload-matrix-v1.json",
                    "cases/timing/sysram-10-small.json",
                ]:
                    (root / name).write_bytes((repo / name).read_bytes())
                runs = root / "runs"
                for i in range(1, 9):
                    for variant in ("baseline", "pbuf"):
                        (runs / f"A{i:02}-{variant}").mkdir(parents=True)
                changed = copy.deepcopy(manifest)
                changed[key] = value
                (runs / "A01-baseline/manifest.json").write_text(json.dumps(changed))
                with self.assertRaisesRegex(ValueError, "Workload or tool"):
                    analyze_matrix(root, runs, root / "output")

    def test_mixed_tool_environment_rejected(self):
        import json
        from unittest.mock import patch

        from psf_lab import tcp_workload_matrix as module

        repo = Path(__file__).resolve().parents[2]
        decode = json.loads
        profile = decode(
            (
                repo
                / "artifacts/verification/tcp-workload-matrix/results/A01-baseline-profile.json"
            ).read_text()
        )

        def changed(text, *args, **kwargs):
            value = decode(text, *args, **kwargs)
            if (
                isinstance(value, dict)
                and value.get("tcp_variant") == "pbuf"
                and "qemu_sha256" in value
            ):
                value["qemu_sha256"] = "different-tool"
            return value

        with (
            TemporaryDirectory() as temp,
            patch.object(module.json, "loads", side_effect=changed),
            patch.object(module, "profile_misses", return_value=profile),
            patch.object(
                module.subprocess, "check_output", return_value="text data bss\n41556 0 0\n"
            ),
        ):
            with self.assertRaisesRegex(ValueError, "Mixed tool environments"):
                module.analyze_matrix(
                    repo, repo / "runs/tcp-workload-matrix-v1", Path(temp) / "results"
                )
