"""Create a source/evidence snapshot with FreeRTOS dependencies, without Git metadata."""

import hashlib
import io
import json
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATHS = ['firmware', 'src', 'tools/cache', 'tools/toolchain-lock.json',
         'third_party/qemu-cache', 'third_party/FreeRTOS/FreeRTOS/Source',
         'third_party/FreeRTOS/FreeRTOS/Demo/RISC-V_RV32_QEMU_VIRT_GCC',
         'references/baseline/percepio/TraceRecorder', 'references/cache',
         'runs/cache-relative-v3', 'web/cache.html', 'web/src/cache.js', 'web/src/cache.css',
         'web/dist/assets/cache.js', 'web/dist/assets/cache.css',
         'artifacts/offline/cache-comparison.html', 'artifacts/screenshots/cache',
         'docs/cache-replay.md',
         'docs/research/Cache效率與PSF擴充.md', 'requirements-runtime.lock',
         'requirements-dev.lock', 'pyproject.toml', 'tests/unit/test_cache_model.py',
         'tests/unit/test_cache_report.py']


def main():
    files = {}
    for name in PATHS:
        path = ROOT / name
        if not path.exists():
            raise FileNotFoundError(path)
        for item in sorted(path.rglob('*')) if path.is_dir() else [path]:
            if (not item.is_file() or item.is_symlink()
                    or any(p in ('.git', '__pycache__') for p in item.parts)
                    or item.suffix == '.pyc'):
                continue
            files[str(item.relative_to(ROOT))] = item
    dest = ROOT / 'artifacts/restore/cache-replay-source.tar.gz'
    dest.parent.mkdir(parents=True, exist_ok=True)
    records = {}
    with tarfile.open(dest, 'w:gz') as archive:
        for name, path in sorted(files.items()):
            data = path.read_bytes()
            records[name] = hashlib.sha256(data).hexdigest()
            entry = tarfile.TarInfo(name)
            entry.size = len(data)
            entry.mode = 0o644
            entry.mtime = 0
            archive.addfile(entry, io.BytesIO(data))
        blob = (json.dumps(records, indent=2, ensure_ascii=False) + '\n').encode()
        entry = tarfile.TarInfo('RESTORE-SHA256.json')
        entry.size = len(blob)
        archive.addfile(entry, io.BytesIO(blob))
    receipt = {'archive': dest.name, 'sha256': hashlib.sha256(dest.read_bytes()).hexdigest(),
               'bytes': dest.stat().st_size, 'files': len(files),
               'includes': 'source, FreeRTOS/SDK source dependencies, captures, offline HTML',
               'external_tools': ['Python 3.13', 'QEMU 11.1.2 API 7',
                                  'RISC-V GCC 15.2', 'C compiler', 'pkg-config', 'GLib headers'],
               'excluded': 'host executables, Python wheels, cross-platform validation'}
    (dest.parent / 'cache-replay-source.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
