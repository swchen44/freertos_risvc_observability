"""Atomic local trace store; uploaded filenames never become filesystem paths."""

import json
import re
import shutil
import threading
import uuid
from pathlib import Path

from psf_lab.analysis import analyze
from psf_lab.parser.semantic import parse_trace
from psf_lab.runner import write_json

_LOCK = threading.Lock()


class StoreError(ValueError):
    def __init__(self, code, message, status=404):
        self.code, self.status = code, status
        super().__init__(message)


def trace_path(store: Path, trace_id: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{32}", trace_id):
        raise StoreError("not_found", "Unknown trace")
    path = store / trace_id
    if not path.is_dir() or path.is_symlink():
        raise StoreError("not_found", "Unknown trace")
    return path


def list_traces(store: Path) -> list:
    if not store.exists():
        return []
    results = []
    for path in sorted(store.iterdir()):
        if (
            re.fullmatch(r"[0-9a-f]{32}", path.name)
            and path.is_dir()
            and not path.is_symlink()
            and (path / "metadata.json").is_file()
        ):
            results.append(json.loads((path / "metadata.json").read_text()))
    return results


def load_trace(store: Path, trace_id: str) -> tuple[dict, dict]:
    p = trace_path(store, trace_id)
    return json.loads((p / "trace.json").read_text()), json.loads((p / "analysis.json").read_text())


def create_trace(
    store: Path, data: bytes, *, source_name: str, max_traces=20, max_bytes=16 * 1024 * 1024
) -> dict:
    if len(data) > max_bytes:
        raise StoreError("too_large", "PSF exceeds configured byte limit", 413)
    name = source_name.replace("\\", "/").split("/")[-1]
    name = "".join(c for c in name if ord(c) >= 32 and ord(c) != 127)[:200] or "trace.psf"
    with _LOCK:
        store.mkdir(parents=True, exist_ok=True)
        if len(list_traces(store)) >= max_traces:
            raise StoreError("quota", "Trace store is full", 413)
        trace = parse_trace(data, source_name=name, strict=False)
        analysis = analyze(trace)
        id_ = uuid.uuid4().hex
        temporary = store / (".pending-" + id_)
        temporary.mkdir()
        try:
            (temporary / "source.psf").write_bytes(data)
            write_json(temporary / "trace.json", trace)
            write_json(temporary / "analysis.json", analysis)
            metadata = {k: trace[k] for k in ["source", "platform", "clock", "objects", "quality"]}
            metadata.update(trace_id=id_, event_count=len(trace["events"]))
            write_json(temporary / "metadata.json", metadata)
            temporary.rename(store / id_)
        except BaseException:
            shutil.rmtree(temporary)
            raise
        return metadata
