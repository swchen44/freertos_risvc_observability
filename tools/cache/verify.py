"""Actual curl integration and agent-browser E2E; CACHE_MODE=server|offline."""

import csv
import json
import os
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODE = os.environ.get('CACHE_MODE', 'server')
OUT = ROOT / 'artifacts/verification/cache-replay' / MODE
SHOTS = ROOT / 'artifacts/screenshots/cache'
SESSION = 'cache-accept-' + MODE
LOG = []


def ab(*args):
    if args[0] in {'click', 'select', 'download'}:
        selector = json.dumps(args[1])
        ab('eval', f'document.querySelector({selector}).scrollIntoView({{block:"center"}})')
    command = ['agent-browser', '--session', SESSION, *args]
    result = subprocess.run(command, capture_output=True, text=True, timeout=40)
    LOG.append({'command': command, 'exit': result.returncode,
                'stdout': result.stdout, 'stderr': result.stderr})
    (OUT / 'commands.json').write_text(json.dumps(LOG, ensure_ascii=False, indent=2) + '\n')
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout)
    return result.stdout


def evaluate(code):
    return json.loads(ab('eval', '--json', code))['data']['result']


def shot(name):
    ab('screenshot', '--full', str(SHOTS / f'{MODE}-{name}.png'))


class CacheAcceptance(unittest.TestCase):
    def test_cache_workflow(self):
        OUT.mkdir(parents=True, exist_ok=True)
        SHOTS.mkdir(parents=True, exist_ok=True)
        if MODE == 'server':
            response = subprocess.run(['curl', '--fail', '--silent', '--show-error',
                                       'http://127.0.0.1:8765/api/cache'], capture_output=True,
                                      text=True, timeout=20)
            self.assertEqual(response.returncode, 0, response.stderr)
            data = json.loads(response.stdout)
            self.assertEqual(len(data['rows']), 18)
            for row in data['rows']:
                expected = 256 if row['l1']['geometry']['size'] == 16384 else (
                    512 if 'row' in row['run'] else 8192)
                self.assertEqual(row['l1']['misses'], expected)
                self.assertEqual(row['l2']['misses'], 256)
            (OUT / 'curl-api.json').write_text(response.stdout)
        else:
            result = subprocess.run(['curl', '--silent', '--max-time', '2',
                                     'http://127.0.0.1:8765/api/cache'], capture_output=True)
            self.assertNotEqual(result.returncode, 0, 'stop server before offline acceptance')
        try:
            ab('open', 'about:blank')
            ab('set', 'viewport', '1600', '1050')
            if MODE == 'offline':
                ab('set', 'offline', 'on')
                ab('network', 'route', 'http://*', '--abort')
                ab('network', 'route', 'https://*', '--abort')
                url = (ROOT / 'artifacts/offline/cache-comparison.html').as_uri()
            else:
                url = 'http://127.0.0.1:8765/cache.html'
            ab('open', url)
            ab('wait', '--text', '目前 6 筆')
            self.assertEqual(evaluate('document.querySelectorAll(".chart svg").length'), 2)
            shot('01-overview')
            ab('select', '#size', '16384')
            ab('wait', '--fn', 'document.querySelector("#size").value==="16384"')
            shot('02-capacity')
            ab('select', '#size', '4096')
            ab('select', '#variant', 'cache_column')
            ab('select', '#repeat', '1')
            ab('wait', '--text', '目前 1 筆')
            ab('click', '.tabulator-row .tabulator-cell[tabulator-field="run"]')
            self.assertIn('psf_sha256', evaluate('document.querySelector("#evidence").textContent'))
            shot('03-filter-evidence')
            ab('download', '#csv', str(OUT / 'filtered.csv'))
            with (OUT / 'filtered.csv').open(encoding='utf-8-sig') as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['run'], 'cache_column-1')
            self.assertEqual(rows[0]['misses'], '8192')
            self.assertEqual(rows[0]['used'], '6.25')
            ab('select', '#variant', 'all')
            ab('select', '#repeat', 'all')
            ab('wait', '--text', '目前 6 筆')
            ab('click', '.tabulator-col[tabulator-field="misses"]')
            ab('download', '#csv', str(OUT / 'sorted.csv'))
            with (OUT / 'sorted.csv').open(encoding='utf-8-sig') as stream:
                values = [int(row['misses']) for row in csv.DictReader(stream)]
            self.assertEqual(values, sorted(values))
            shot('04-sort')
            errors = json.loads(ab('errors', '--json'))
            self.assertEqual(errors['data'].get('errors', []), [])
        finally:
            ab('close')


if __name__ == '__main__':
    unittest.main()
