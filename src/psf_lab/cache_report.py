"""Verified cache sidecar dataset and self-contained HTML export."""

import csv
import hashlib
import json
from pathlib import Path

from psf_lab.cache_model import Geometry, replay
from psf_lab.offline import embed_json

ROOT = Path(__file__).resolve().parents[2]


def load_comparison(directory):
    rows = []
    model_hash = hashlib.sha256((ROOT / 'src/psf_lab/cache_model.py').read_bytes()).hexdigest()
    expected = {f'{variant}-{n}' for variant in ('cache_row', 'cache_column')
                for n in (1, 2, 3)}
    found = {p.name for p in directory.glob('cache_*-[123]')}
    if found != expected:
        raise ValueError('expected row/column captures, repeats 1..3')
    for run in sorted(directory.glob('cache_*-[123]')):
        manifest = json.loads((run / 'manifest.json').read_text())
        for name in ['trace.psf', 'oracle.json', 'accesses.csv', 'firmware.elf']:
            actual = hashlib.sha256((run / name).read_bytes()).hexdigest()
            if manifest['files'].get(name) != actual:
                raise ValueError(f'cache evidence hash mismatch: {run.name}/{name}')
        oracle = json.loads((run / 'oracle.json').read_text())
        variant, repeat = run.name.rsplit('-', 1)
        if (manifest.get('variant') != variant or manifest.get('repeat') != int(repeat)
                or oracle.get('case_id') != variant):
            raise ValueError('cache case identity mismatch')
        if (not oracle['complete'] or oracle['received_ids'] != [8394752]
                or oracle['sent_ids'] != [8394752]):
            raise ValueError('cache oracle mismatch')
        with (run / 'accesses.csv').open() as stream:
            events = [(int(e['address']), int(e['size']), e['operation'])
                      for e in csv.DictReader(stream)]
        region = manifest['region']
        if (len(events) != 16384 or sum(e[2] == 'R' for e in events) != 8192
                or sum(e[2] == 'W' for e in events) != 8192
                or any(size != 4 or not region['data_start'] <= address
                       < region['data_start'] + region['data_size']
                       for address, size, _ in events)):
            raise ValueError('capture count/range mismatch')
        for size in [1024, 4096, 16384]:
            result = replay(events, Geometry(size, 64, 4), Geometry(32768, 64, 4))
            rows.append({**result, 'run': run.name, 'checksum': 8394752,
                         'psf_sha256': manifest['files']['trace.psf'],
                         'source_sha256': manifest['files']['accesses.csv'],
                         'model_sha256': model_hash,
                         'function': 'cache_work', 'object': 'cache_matrix',
                         'region': manifest['region']})
    if len(rows) != 18:
        raise ValueError('expected six captures with three geometries each')
    return {'schema': 'cache-dashboard-v1', 'rows': rows,
            'scope': 'data-only matrix region; L2 excludes instruction traffic',
            'time_alignment': 'whole workload region only; no per-event PSF timestamp',
            'source': 'QEMU guest physical access replay; not hardware PMU'}


def render_offline(data, template, js, css):
    html = template.replace('<script id="cache-data"></script>',
                            '<script id="cache-data" type="application/json">'
                            + embed_json(data) + '</script>')
    html = html.replace('<script src="/assets/cache.js"></script>',
                        '<script>' + js.replace('</script', '<\\/script') + '</script>')
    html = html.replace('<link rel="stylesheet" href="/assets/cache.css">',
                        '<style>' + css.replace('</style', '<\\/style') + '</style>')
    policy = ("default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
              "img-src data: blob:; connect-src 'none'; font-src data:; base-uri 'none'")
    return html.replace('<title>', '<meta http-equiv="Content-Security-Policy" content="'
                        + policy + '"><title>')


def export_cache(directory, output):
    assets = ROOT / 'web/dist/assets'
    html = render_offline(load_comparison(directory), (ROOT / 'web/cache.html').read_text(),
                          (assets / 'cache.js').read_text(), (assets / 'cache.css').read_text())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html)
