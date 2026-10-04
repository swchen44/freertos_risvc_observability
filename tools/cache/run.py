#!/usr/bin/env python3
"""Build/capture deterministic cache A/B; replay needs only Python stdlib + local source."""

import argparse
import csv
import hashlib
import json
import platform
import shlex
import shutil
import subprocess
from pathlib import Path

from psf_lab.cache_report import export_cache, load_comparison
from psf_lab.runner import QEMU_FLAGS

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def execute(command, directory, log):
    result = subprocess.run(command, cwd=directory, capture_output=True, timeout=120)
    log.write_bytes(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError(f'command failed ({result.returncode}); see {log}')
    return command


def read_events(path):
    with path.open() as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ['address', 'size', 'operation']:
            raise ValueError('unexpected access CSV columns')
        return [(int(row['address']), int(row['size']), row['operation']) for row in reader]


def analyze(directory):
    dataset = load_comparison(directory)
    summaries = dataset['rows']
    for run in sorted(directory.glob('cache_*-[123]')):
        rows = [r for r in summaries if r['run'] == run.name]
        (run / 'analysis.json').write_text(json.dumps(rows, indent=2) + '\n')
    (directory / 'comparison.json').write_text(json.dumps(summaries, indent=2) + '\n')
    receipt = {'model_sha256': digest(ROOT / 'src/psf_lab/cache_model.py'),
               'report_sha256': digest(ROOT / 'src/psf_lab/cache_report.py'),
               'comparison_sha256': digest(directory / 'comparison.json'),
               'row_count': len(summaries)}
    (directory / 'analysis-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return summaries


def capture(directory, toolchain, qemu):
    directory.mkdir(parents=True, exist_ok=False)
    plugin = directory / ('addresses.dylib' if platform.system() == 'Darwin' else 'addresses.so')
    link = ['-dynamiclib', '-undefined', 'dynamic_lookup'] if platform.system() == 'Darwin' else [
        '-shared', '-fPIC']
    build = ['cc', *link, '-O2', '-Wall', '-Wextra', '-Werror',
             '-I' + str(ROOT / 'third_party/qemu-cache'),
             str(ROOT / 'tools/cache/addresses.c'), '-o', str(plugin),
             *shlex.split(subprocess.check_output(
                 ['pkg-config', '--cflags', 'glib-2.0'], text=True))]
    execute(build, ROOT, directory / 'plugin-build.log')
    manifests = []
    for variant in ['cache_row', 'cache_column']:
        command = ['make', '-B', '-C', 'firmware', f'CASE={variant}',
                   f'TOOLCHAIN={toolchain}']
        execute(command, ROOT, directory / f'{variant}-build.log')
        elf = ROOT / 'build' / variant / 'firmware.elf'
        symbols = subprocess.check_output(
            [str(toolchain / 'riscv-none-elf-nm'), '-S', str(elf)], text=True)
        table = {parts[3]: (int(parts[0], 16), int(parts[1], 16))
                 for line in symbols.splitlines() if len(parts := line.split()) == 4}
        pc, pc_size = table['cache_work']
        data, data_size = table['cache_matrix']
        if data_size != 16384 or data % 64:
            raise ValueError('matrix size/alignment mismatch')
        for number in range(1, 4):
            run = directory / f'{variant}-{number}'
            run.mkdir()
            for name in ['firmware.elf', 'firmware.map']:
                shutil.copyfile(elf.parent / name, run / name)
            (run / 'symbols.txt').write_text(symbols)
            args = (f'{plugin},pc_start={pc:x},pc_end={pc+pc_size:x},'
                    f'data_start={data:x},data_end={data+data_size:x},out=accesses.csv')
            command = [qemu, *QEMU_FLAGS, '-kernel', str(run / 'firmware.elf'), '-plugin', args]
            execute(command, run, run / 'qemu.log')
            oracle = json.loads((run / 'oracle.json').read_text())
            if (not oracle['complete'] or oracle['sent_ids'] != [8394752]
                    or oracle['received_ids'] != [8394752]):
                raise ValueError('work checksum mismatch')
            events = read_events(run / 'accesses.csv')
            if (len(events) != 16384 or sum(e[2] == 'R' for e in events) != 8192
                    or any(not (data <= a < data+data_size) or size != 4
                           for a, size, _ in events)):
                raise ValueError('capture count/range mismatch')
            if 'cache_capture_complete=16384' not in (run / 'qemu.log').read_text():
                raise ValueError('capture completion marker missing')
            manifest = {'schema': 'cache-run-v1', 'variant': variant, 'repeat': number,
                        'command': command, 'checksum': 8394752,
                        'region': {'pc_start': pc, 'pc_size': pc_size,
                                   'data_start': data, 'data_size': data_size},
                        'files': {p.name: digest(p) for p in run.iterdir() if p.is_file()}}
            (run / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
            manifests.append(manifest)
    analyze(directory)
    sources = [ROOT / 'tools/cache/addresses.c', ROOT / 'tools/cache/run.py',
               ROOT / 'src/psf_lab/cache_model.py', ROOT / 'src/psf_lab/cache_report.py',
               ROOT / 'firmware/Makefile',
               *sorted((ROOT / 'firmware/app/cases').glob('cache*')),
               *sorted((ROOT / 'third_party/qemu-cache').glob('*'))]
    receipt = {'schema': 'cache-suite-v1', 'build_command': build,
               'qemu_version': subprocess.check_output([qemu, '--version'], text=True),
               'compiler': subprocess.check_output(['cc', '--version'], text=True),
               'plugin_sha256': digest(plugin), 'sources': {
                   str(p.relative_to(ROOT)): digest(p) for p in sources if p.is_file()},
               'captures': len(manifests), 'host': platform.platform()}
    (directory / 'suite.json').write_text(json.dumps(receipt, indent=2) + '\n')
    plugin.unlink()  # platform binary is reproducible from checked-in sources


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--replay-only', action='store_true')
    parser.add_argument('--export-html', type=Path)
    parser.add_argument('--toolchain', type=Path,
                        default=ROOT / '.tools/xpack-riscv-none-elf-gcc-15.2.0-1/bin')
    parser.add_argument('--qemu', default='qemu-system-riscv32')
    args = parser.parse_args()
    if args.replay_only:
        analyze(args.output.resolve())
    else:
        capture(args.output.resolve(), args.toolchain.resolve(), args.qemu)
    if args.export_html:
        export_cache(args.output.resolve(), args.export_html.resolve())


if __name__ == '__main__':
    main()
