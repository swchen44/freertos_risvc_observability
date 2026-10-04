import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from psf_lab.cache_report import load_comparison, render_offline
from psf_lab.server import create_app

ROOT = Path(__file__).resolve().parents[2]


class CacheReportTests(unittest.TestCase):
    def test_verified_dataset(self):
        data = load_comparison(ROOT / 'runs/cache-relative-v3')
        self.assertEqual(len(data['rows']), 18)
        self.assertTrue(all(len(row['psf_sha256']) == 64 for row in data['rows']))

    def test_script_escape(self):
        html = render_offline({'rows': [], 'label': '</script><script>alert(1)</script>'},
                              '<head><title>Cache</title></head>'
                              '<script id="cache-data"></script>', '', '')
        self.assertNotIn('</script><script>alert', html)
        self.assertIn('connect-src', html)

    def test_cache_api(self):
        with tempfile.TemporaryDirectory() as directory:
            with TestClient(create_app(Path(directory)), base_url='http://localhost') as client:
                response = client.get('/api/cache')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(response.json()['rows']), 18)

    def test_tampered_accesses_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'suite'
            shutil.copytree(ROOT / 'runs/cache-relative-v3', root)
            (root / 'cache_row-1/accesses.csv').write_text('address,size,operation\n0,4,R\n')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                load_comparison(root)

    def test_swapped_case_directories_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'suite'
            shutil.copytree(ROOT / 'runs/cache-relative-v3', root)
            (root / 'cache_row-1').rename(root / 'temporary')
            (root / 'cache_column-1').rename(root / 'cache_row-1')
            (root / 'temporary').rename(root / 'cache_column-1')
            with self.assertRaisesRegex(ValueError, 'identity mismatch'):
                load_comparison(root)

    def test_actual_model_hash_attached(self):
        expected = hashlib.sha256((ROOT / 'src/psf_lab/cache_model.py').read_bytes()).hexdigest()
        result = load_comparison(ROOT / 'runs/cache-relative-v3')
        self.assertTrue(all(row['model_sha256'] == expected for row in result['rows']))
