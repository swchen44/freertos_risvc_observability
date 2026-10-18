"""Serial backend data-path diagnostic; not browser acceptance."""

import argparse
import hashlib
import importlib.util
import json
import platform
import time
from pathlib import Path

from psf_lab import event_window


def benchmark(root, run_id, output, engine=None):
    module = event_window
    if engine:
        spec = importlib.util.spec_from_file_location("baseline_event_window", engine)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    manifest = module.load_event_manifest(root, run_id)
    runs = []
    for _ in range(3):
        if hasattr(module, "_parse_event_manifest"):
            module._parse_event_manifest.cache_clear()
        start = time.perf_counter()
        digest = hashlib.sha256()
        for descriptor in manifest["chunks"]:
            digest.update(module.load_event_chunk(root, run_id, descriptor["id"]))
        runs.append(dict(seconds=time.perf_counter() - start, payloads_sha256=digest.hexdigest()))
    receipt = dict(
        scope="Python backend, full chunk validation; not browser acceptance",
        python=platform.python_version(),
        chunks=len(manifest["chunks"]),
        engine_sha256=hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest(),
        runs=runs,
    )
    with output.open("x") as stream:
        json.dump(receipt, stream, indent=2)
        stream.write("\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default="A02-baseline-b1-1-1")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--engine", type=Path)
    args = parser.parse_args()
    benchmark(Path(__file__).resolve().parents[2], args.run_id, args.output, args.engine)
