import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from psf_lab import event_window as m
from psf_lab.hotspot_events import iter_hotspot_events
from tests.unit.test_hotspot_report import profile, rows_for


class ManifestCacheTests(unittest.TestCase):
    def test_content_cache_revalidates_and_cannot_be_poisoned(self):
        m._parsed_manifest.cache_clear()
        self.addCleanup(m._parsed_manifest.cache_clear)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rid = "A02-baseline-b1-1-1"
            folder = root / m.BASE / rid
            data = m.write_event_chunks(
                iter_hotspot_events(rows_for([(100, 100, 4, "I")]), [], profile(), contexts=None),
                folder,
            )
            data["identity"] = {"run_id": rid}
            raw = m.canonical(data)
            (folder / "manifest.json").write_bytes(raw)

            def catalog(payload):
                (folder.parent / "catalog.json").write_bytes(
                    m.canonical(
                        {
                            "schema": "event-window-catalog-v1",
                            "runs": [{"run_id": rid, "workload": "A02", "sha256": m.sha(payload)}],
                        }
                    )
                )

            catalog(raw)
            with patch.object(
                m, "validate_event_manifest", wraps=m.validate_event_manifest
            ) as validate:
                first = m.load_event_manifest(root, rid)
                first["contexts"][0] = "poisoned"
                self.assertNotEqual(m.load_event_manifest(root, rid)["contexts"][0], "poisoned")
                m.load_event_chunk(root, rid, "000000")
                self.assertEqual(validate.call_count, 1)
            changed = raw.replace(b"unknown", b"changed")
            self.assertEqual(len(raw), len(changed))
            (folder / "manifest.json").write_bytes(changed)
            with self.assertRaises(ValueError):
                m.load_event_manifest(root, rid)
            catalog(changed)
            self.assertEqual(m.load_event_manifest(root, rid)["contexts"], ["changed"])
            bad = json.loads(changed)
            bad["contexts"] = "changed"
            broken = m.canonical(bad)
            (folder / "manifest.json").write_bytes(broken)
            catalog(broken)
            with self.assertRaises(ValueError):
                m.load_event_chunk(root, rid, "000000")
