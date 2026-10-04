#!/bin/sh
# Isolated research build. Does not install or replace system QEMU.
set -eu
repo=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 NEW_DEST_DIRECTORY" >&2
    exit 2
fi
mkdir "$1"
dest=$(CDPATH= cd -- "$1" && pwd)
uv venv "$dest/venv"
uv pip install --python "$dest/venv/bin/python" meson==1.12.1 ninja==1.13.2
curl -fL --max-time 600 https://download.qemu.org/qemu-9.2.0.tar.xz -o "$dest/qemu-9.2.0.tar.xz"
"$dest/venv/bin/python" - "$dest/qemu-9.2.0.tar.xz" <<'PY'
import hashlib
import sys
from pathlib import Path
expected = "f859f0bc65e1f533d040bbe8c92bcfecee5af2c921a6687c652fb44d089bd894"
actual = hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest()
if actual != expected:
    raise SystemExit("QEMU source archive SHA-256 mismatch")
print("Source archive verified:", actual)
PY
tar -xJf "$dest/qemu-9.2.0.tar.xz" -C "$dest"
mkdir "$dest/build"
cd "$dest/build"
"$dest/qemu-9.2.0/configure" \
    --target-list=riscv32-softmmu --without-default-features \
    --enable-system --enable-tcg --enable-plugins --enable-fdt=internal \
    --disable-docs --disable-werror \
    --python="$dest/venv/bin/python" --ninja="$dest/venv/bin/ninja" \
    > "$dest/configure.log" 2>&1
"$dest/venv/bin/ninja" -j4 qemu-system-riscv32 > "$dest/baseline-build.log" 2>&1
cp qemu-system-riscv32 "$dest/qemu-system-riscv32-baseline"
patch -d "$dest/qemu-9.2.0" -p1 < "$repo/tools/qemu/0001-experimental-icount-setter.patch"
"$dest/venv/bin/ninja" -j4 qemu-system-riscv32 > "$dest/setter-build.log" 2>&1
cp qemu-system-riscv32 "$dest/qemu-system-riscv32-setter"
patch -d "$dest/qemu-9.2.0" -p1 < "$repo/tools/qemu/0002-clock-advance-without-pending-timer.patch"
"$dest/venv/bin/ninja" -j4 qemu-system-riscv32 > "$dest/clock-build.log" 2>&1
cp qemu-system-riscv32 "$dest/qemu-system-riscv32-clock"
"$dest/venv/bin/python" - "$dest" <<'PY'
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path
root = Path(sys.argv[1])
files = [root / ("qemu-system-riscv32-" + suffix)
         for suffix in ("baseline", "setter", "clock")]
result = {"host": platform.platform(), "binaries": {
    p.name: {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
             "version": subprocess.check_output([str(p), "--version"], text=True)}
    for p in files}}
(root / "binaries.json").write_text(json.dumps(result, indent=2) + "\n")
PY
printf 'Built isolated research binaries in %s\n' "$dest"
