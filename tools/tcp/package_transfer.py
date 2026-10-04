"""Archive the TCP transfer experiment and source dependencies for internal restore."""

import hashlib
import io
import json
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATHS = (
    "firmware",
    "src",
    "tools/tcp",
    "tools/toolchain-lock.json",
    "third_party/FreeRTOS/FreeRTOS/Source",
    "third_party/FreeRTOS/FreeRTOS/Demo/RISC-V_RV32_QEMU_VIRT_GCC",
    "references/baseline/percepio/TraceRecorder",
    "references/tcp/lwip",
    "runs/tcp-transfer-v2",
    "docs/research/TCP-IP與Cache最佳化案例.md",
    "docs/plans/09-tcp-optimization.md",
    "tests/unit/test_tcp_cache.py",
    "tests/unit/test_tcp_packets.py",
    "tests/unit/test_tcp_report.py",
    "tests/unit/test_tcp_checksum.py",
    "third_party/qemu-cache",
    "web/tcp.html",
    "web/src",
    "web/index.html",
    "web/cache.html",
    "web/THIRD_PARTY_NOTICES.md",
    "web/licenses",
    "web/build.mjs",
    "web/package.json",
    "web/package-lock.json",
    "web/dist",
    "artifacts/offline/tcp-optimization.html",
    "artifacts/screenshots/tcp",
    "docs/tcp-optimization.md",
    "requirements-runtime.lock",
    "requirements-dev.lock",
    "pyproject.toml",
)


def main():
    dest = ROOT / "artifacts/restore/tcp-transfer-source.tar.gz"
    dest.parent.mkdir(parents=True, exist_ok=True)
    hashes = {}
    with tarfile.open(dest, "w:gz") as archive:
        for relative in PATHS:
            path = ROOT / relative
            if not path.exists():
                raise FileNotFoundError(path)
            for item in sorted(path.rglob("*")) if path.is_dir() else [path]:
                if (
                    not item.is_file()
                    or item.is_symlink()
                    or any(p in (".git", "__pycache__") for p in item.parts)
                    or item.suffix == ".pyc"
                ):
                    continue
                name = str(item.relative_to(ROOT))
                blob = item.read_bytes()
                hashes[name] = hashlib.sha256(blob).hexdigest()
                info = tarfile.TarInfo(name)
                info.size, info.mode = len(blob), 0o644
                archive.addfile(info, io.BytesIO(blob))
        blob = (json.dumps(hashes, indent=2, ensure_ascii=False) + "\n").encode()
        info = tarfile.TarInfo("RESTORE-SHA256.json")
        info.size = len(blob)
        archive.addfile(info, io.BytesIO(blob))
    receipt = {
        "archive": dest.name,
        "sha256": hashlib.sha256(dest.read_bytes()).hexdigest(),
        "files": len(hashes),
        "bytes": dest.stat().st_size,
        "excluded": "Host executables, Python wheels, NIC/DMA/timing model",
    }
    dest.with_suffix("").with_suffix(".json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
