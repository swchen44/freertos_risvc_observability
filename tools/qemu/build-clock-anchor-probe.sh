#!/bin/sh
# Build only in a NEW directory. Preserve all source and partial build logs.
set -eu
repo=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
if [ "$#" -lt 1 ] || [ "$#" -gt 3 ]; then
    echo "Usage: $0 NEW_DEST [SOURCE_ARCHIVE] [JOBS=1|2]" >&2
    exit 2
fi
dest=$1
jobs=${3:-2}
case "$jobs" in 1|2) ;; *) echo "JOBS must be 1 or 2" >&2; exit 2 ;; esac
if [ -e "$dest" ] || [ -L "$dest" ]; then echo "Destination already exists" >&2; exit 2; fi
for name in 0001-experimental-icount-setter.patch \
    0002-clock-advance-without-pending-timer.patch \
    0003-experimental-relative-clock-cost.patch 0004-clock-anchor-observer.patch; do
    if [ ! -f "$repo/tools/qemu/$name" ]; then
        echo "Missing patch: $name" >&2
        exit 2
    fi
done
archive=${2:-$repo/.tools/qemu-time-control/qemu-9.2.0.tar.xz}
created=0
if [ ! -f "$archive" ]; then
    if [ "$#" -ge 2 ]; then echo "Missing supplied archive" >&2; exit 2; fi
    mkdir "$dest"
    created=1
    archive="$dest/qemu-9.2.0.tar.xz"
    curl -fL --max-time 600 https://download.qemu.org/qemu-9.2.0.tar.xz \
        -o "$archive" > "$dest/download.log" 2>&1
fi
python3 - "$archive" <<'PY'
import hashlib, sys
with open(sys.argv[1], 'rb') as stream:
    actual = hashlib.file_digest(stream, 'sha256').hexdigest()
if actual != 'f859f0bc65e1f533d040bbe8c92bcfecee5af2c921a6687c652fb44d089bd894':
    raise SystemExit('Source archive SHA-256 mismatch')
PY
if [ "$created" -eq 0 ]; then mkdir "$dest"; fi
dest=$(CDPATH= cd -- "$dest" && pwd)
archive=$(python3 - "$archive" <<'PY'
import pathlib, sys
print(pathlib.Path(sys.argv[1]).resolve())
PY
)
tar -xJf "$archive" -C "$dest" > "$dest/extract.log" 2>&1
source="$dest/qemu-9.2.0"
for name in 0001-experimental-icount-setter.patch \
    0002-clock-advance-without-pending-timer.patch \
    0003-experimental-relative-clock-cost.patch 0004-clock-anchor-observer.patch; do
    patch -d "$source" -p1 --batch < "$repo/tools/qemu/$name" >> "$dest/patch.log" 2>&1
done
python3 "$repo/tools/qemu/make_clock_anchor_patch.py" --verify-overlays "$source" \
    > "$dest/overlay-check.json"
uv venv --python "$repo/.venv/bin/python" "$dest/venv" > "$dest/venv.log" 2>&1
uv pip install --python "$dest/venv/bin/python" meson==1.12.1 ninja==1.13.2 \
    > "$dest/tool-install.log" 2>&1
NINJA="$dest/venv/bin/ninja"
export NINJA
mkdir "$dest/build"
cd "$dest/build"
"$source/configure" --target-list=riscv32-softmmu --without-default-features \
    --enable-system --enable-tcg --enable-plugins --enable-fdt=internal \
    --disable-docs --disable-werror \
    --python="$dest/venv/bin/python" --ninja="$dest/venv/bin/ninja" \
    > "$dest/configure.log" 2>&1
"$dest/venv/bin/ninja" "-j$jobs" qemu-system-riscv32 > "$dest/build.log" 2>&1
cp qemu-system-riscv32 "$dest/qemu-system-riscv32-clock-anchor"
"$repo/.venv/bin/python" - "$repo" "$dest" "$archive" "$jobs" <<'PY'
import hashlib, json, platform, shutil, subprocess, sys
from pathlib import Path
repo, dest, archive = map(Path, sys.argv[1:4]); jobs = int(sys.argv[4])
def sha(p):
    with p.open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()
def identity(p): return dict(path=str(p.resolve()), sha256=sha(p))
def version(cmd): return subprocess.check_output(cmd, text=True).strip()
source=dest/'qemu-9.2.0'; binary=dest/'qemu-system-riscv32-clock-anchor'
patches=sorted((repo/'tools/qemu').glob('000[1-4]-*.patch'))
cc=Path(shutil.which('cc')).resolve()
manifest=dict(schema='c2b-qemu-build-v1', source_commit=version(['git','-C',str(repo),'rev-parse','HEAD']),
    host=dict(system=platform.system(),machine=platform.machine(),platform=platform.platform()),
    source_archive=identity(archive), source=str(source), jobs=jobs,
    patches={str(p.relative_to(repo)):sha(p) for p in patches},
    overlays=json.loads((dest/'overlay-check.json').read_text()),
    binary=identity(binary), header=identity(source/'include/qemu/qemu-plugin.h'),
    abi_header=identity(source/'include/qemu/poc-clock-anchor-api.h'),
    compiler=dict(**identity(cc),version=version([str(cc),'--version'])),
    meson=dict(**identity(dest/'venv/bin/meson'),version=version([str(dest/'venv/bin/meson'),'--version'])),
    ninja=dict(**identity(dest/'venv/bin/ninja'),version=version([str(dest/'venv/bin/ninja'),'--version'])),
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
PY
