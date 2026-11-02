import hashlib, json, os, platform, shutil, subprocess, sys
from pathlib import Path
repo, dest, archive = map(Path, sys.argv[1:4]); jobs = int(sys.argv[4])
sys.path.insert(0, str(repo))
from tools.qemu.make_clock_anchor_patch import check_tool_versions, verify_overlays
def sha(p):
    with p.open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()
def identity(p): return dict(path=str(p.resolve()), sha256=sha(p))
def version(cmd): return subprocess.check_output(cmd, text=True).strip()
source=dest/'qemu-9.2.0'; binary=dest/'qemu-system-riscv32-clock-anchor'
patches=sorted((repo/'tools/qemu').glob('000[1-4]-*.patch'))
cc=Path(shutil.which('cc')).resolve()
packages=json.loads(version([str(dest/'venv/bin/python'), '-c',
    'import json; from importlib.metadata import version; '
    'print(json.dumps({n:version(n) for n in ("meson","ninja")}))']))
tool_versions=check_tool_versions(packages, {
    n:version([str(dest/'venv/bin'/n),'--version']) for n in ('meson','ninja')})
manifest=dict(schema='c2b-qemu-build-v1', source_commit=os.environ['POC_CLOCK_COMPILE_COMMIT'],
    metadata_source_commit=version(['git','-C',str(repo),'rev-parse','HEAD']),
    host=dict(system=platform.system(),machine=platform.machine(),platform=platform.platform()),
    source_archive=identity(archive), source=str(source), jobs=jobs,
    patches={str(p.relative_to(repo)):sha(p) for p in patches},
    overlays=verify_overlays(repo,source),
    binary=identity(binary), header=identity(source/'include/qemu/qemu-plugin.h'),
    abi_header=identity(source/'include/qemu/poc-clock-anchor-api.h'),
    compiler=dict(**identity(cc),version=version([str(cc),'--version'])),
    meson=dict(**identity(dest/'venv/bin/meson'),**tool_versions['meson']),
    ninja=dict(**identity(dest/'venv/bin/ninja'),**tool_versions['ninja']),
    configure_command=[str(source/'configure'),'--target-list=riscv32-softmmu','--without-default-features',
       '--enable-system','--enable-tcg','--enable-plugins','--enable-fdt=internal','--disable-docs','--disable-werror',
       '--python='+str(dest/'venv/bin/python'),'--ninja='+str(dest/'venv/bin/ninja')],
    build_command=[str(dest/'venv/bin/ninja'),'-j'+str(jobs),'qemu-system-riscv32'])
if manifest['meson']['version']!='1.12.1' or manifest['ninja']['version']!='1.13.2':
    raise SystemExit('Build tool version mismatch')
exports=subprocess.check_output(['nm','-g',str(binary)],text=True)
(dest/'exports.txt').write_text(exports)
for name in ('qemu_plugin_poc_clock_configure','qemu_plugin_poc_clock_note',
             'qemu_plugin_poc_add_ns_tagged','qemu_plugin_poc_clock_finish'):
    if name not in exports: raise SystemExit('Missing binary export: '+name)
manifest['exports']=identity(dest/'exports.txt')
(dest/'build-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(dict(binary=manifest['binary'],build_manifest=str(dest/'build-manifest.json'))))
