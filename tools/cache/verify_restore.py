"""Restore the source snapshot in a temporary directory and verify replay/rebuild."""

import argparse
import hashlib
import json
import os
import subprocess
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rebuild', action='store_true')
    parser.add_argument('--toolchain', type=Path,
                        default=ROOT / '.tools/xpack-riscv-none-elf-gcc-15.2.0-1/bin')
    args = parser.parse_args()
    archive = ROOT / 'artifacts/restore/cache-replay-source.tar.gz'
    out = ROOT / 'artifacts/verification/cache-replay'
    out.mkdir(parents=True, exist_ok=True)
    expected = json.loads(archive.with_name('cache-replay-source.json').read_text())
    archive_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
    if expected['sha256'] != archive_hash:
        raise ValueError('archive checksum mismatch')
    with tempfile.TemporaryDirectory(prefix='cache-restore-') as name:
        target = Path(name).resolve()
        with tarfile.open(archive) as stream:
            stream.extractall(target, filter='data')
        files = json.loads((target / 'RESTORE-SHA256.json').read_text())
        for path, digest in files.items():
            item = (target / path).resolve()
            if (not item.is_relative_to(target)
                    or hashlib.sha256(item.read_bytes()).hexdigest() != digest):
                raise ValueError('restored file checksum mismatch')
        env = dict(os.environ, PYTHONPATH=str(target / 'src'))
        commands = [
            ['python3', 'tools/cache/run.py', '--output', 'runs/cache-relative-v3',
             '--replay-only', '--export-html', 'artifacts/offline/rebuilt.html'],
            ['python3', '-m', 'unittest', 'discover', '-s', 'tests/unit',
             '-p', 'test_cache_model.py'],
        ]
        if args.rebuild:
            commands.append(['python3', 'tools/cache/run.py', '--toolchain',
                             str(args.toolchain.resolve()), '--output', 'runs/local/restored-new'])
        results = []
        for index, command in enumerate(commands):
            result = subprocess.run(command, cwd=target, env=env, capture_output=True,
                                    text=True, timeout=180)
            (out / f'restore-{index}.log').write_text(result.stdout + result.stderr)
            results.append({'command': command, 'exit': result.returncode})
            if result.returncode:
                raise RuntimeError(f'restore command {index} failed; see logs')
        comparison_matches = None
        if args.rebuild:
            a = json.loads((target / 'runs/local/restored-new/comparison.json').read_text())
            b = json.loads((ROOT / 'runs/cache-relative-v3/comparison.json').read_text())
            comparison_matches = ([(r['run'], r['l1'], r['l2']) for r in a]
                                  == [(r['run'], r['l1'], r['l2']) for r in b])
            if not comparison_matches:
                raise ValueError('restored captures differ')
        receipt = {'archive_sha256': archive_hash, 'files_verified': len(files),
                   'commands': results, 'same_host': True,
                   'comparison_matches': comparison_matches}
        (out / 'restore.json').write_text(json.dumps(receipt, indent=2) + '\n')
        print(json.dumps(receipt))


if __name__ == '__main__':
    main()
