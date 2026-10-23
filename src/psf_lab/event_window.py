"""Hash-verified event chunks; raw order and cache state are never reconstructed by UI."""

import copy
import csv
import gzip
import hashlib
import io
import json
import re
import zlib
from functools import lru_cache
from pathlib import Path

from psf_lab.cost_attribution import COST_KEYS
from psf_lab.hotspot_events import COUNTERS, LEVELS, add_counts, empty_counts, iter_hotspot_events

CHUNK_ROWS = 1024
MAX_JSON = 2 * 1024 * 1024
_UINT_PATTERN = re.compile(r"0|[1-9][0-9]{0,39}")
COLUMNS = (
    ["index", "pc", "address", "size", "operation", "context_id", "owner_id"]
    + list(COST_KEYS)
    + [f"{level}.{key}" for level in LEVELS for key in COUNTERS]
)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def wire(value):
    if type(value) is int:
        return str(value)
    if isinstance(value, dict):
        return {k: wire(v) for k, v in value.items()}
    if isinstance(value, list):
        return [wire(v) for v in value]
    return value


def uint(value):
    if not isinstance(value, str) or not _UINT_PATTERN.fullmatch(value):
        raise ValueError("Expected canonical unsigned decimal string")
    return int(value)


def encode_chunk(data):
    raw = canonical(data)
    if len(raw) > MAX_JSON:
        raise ValueError("Chunk exceeds JSON byte limit")
    payload = gzip.compress(raw, mtime=0)
    return dict(
        gzip=payload,
        metadata=dict(
            gzip_sha256=sha(payload),
            json_sha256=sha(raw),
            compressed_bytes=str(len(payload)),
            uncompressed_bytes=str(len(raw)),
        ),
    )


def row_counts(row):
    n = [uint(x) if i != 4 else x for i, x in enumerate(row)]
    if n[4] not in ("I", "R", "W") or n[3] < 1:
        raise ValueError("Invalid access operation/size")
    if n[4] == "I" and (n[1] != n[2] or n[3] not in (2, 4)):
        raise ValueError("Invalid I mapping")
    counts = empty_counts()
    counts["instructions"] = int(n[4] == "I")
    counts["cost_cycles"] = dict(zip(COST_KEYS, n[7:12], strict=True))
    counts["memory_cycles"] = sum(n[7:12])
    counts["model_service_ns"] = 2 * counts["memory_cycles"]
    counts["accounted_model_ns"] = counts["model_service_ns"] + counts["instructions"]
    for i, level in enumerate(LEVELS):
        values = n[12 + 5 * i : 17 + 5 * i]
        if values[1] != sum(values[2:]) or values[1] > values[0]:
            raise ValueError("Invalid cache counters")
        counts["cache"][level] = dict(zip(COUNTERS, values, strict=True))
    return counts


def validate_event_manifest(manifest):
    try:
        if manifest["schema"] != "event-window-run-v1" or manifest["columns"] != COLUMNS:
            raise ValueError("Unsupported event schema")
        end = 0
        totals = empty_counts()
        if not isinstance(manifest["owners"], list) or not manifest["owners"]:
            raise ValueError("Missing owner dictionary")
        contexts = manifest["contexts"]
        if (
            not isinstance(contexts, list)
            or not contexts
            or any(not isinstance(c, str) or not c for c in contexts)
        ):
            raise ValueError("Invalid contexts")
        if len(set(contexts)) != len(contexts):
            raise ValueError("Duplicate contexts")
        ids = set()
        for owner in manifest["owners"]:
            if (
                not isinstance(owner, dict)
                or not isinstance(owner.get("function_id"), str)
                or not owner["function_id"]
                or not isinstance(owner.get("role"), str)
            ):
                raise ValueError("Invalid owner")
            if owner["function_id"] in ids:
                raise ValueError("Duplicate owner")
            ids.add(owner["function_id"])
            if owner.get("function") is not None and not isinstance(owner["function"], str):
                raise ValueError("Invalid function label")
        if not isinstance(manifest["chunks"], list):
            raise ValueError("Invalid chunk directory")
        for index, chunk in enumerate(manifest["chunks"]):
            start, stop = uint(chunk["start"]), uint(chunk["end"])
            if chunk["id"] != f"{index:06d}" or start != end or not 0 < stop - start <= CHUNK_ROWS:
                raise ValueError("Chunk range discontinuity")
            if stop - start != uint(chunk["rows"]) or uint(chunk["uncompressed_bytes"]) > MAX_JSON:
                raise ValueError("Invalid chunk size")
            if not 0 < uint(chunk["compressed_bytes"]) <= MAX_JSON:
                raise ValueError("Invalid compressed byte count")
            for k in ("gzip_sha256", "json_sha256"):
                if not re.fullmatch(r"[0-9a-f]{64}", chunk[k]):
                    raise ValueError("Invalid chunk digest")
            ct = chunk["totals"]
            parsed = {k: uint(ct[k]) for k in empty_counts() if k not in ("cache", "cost_cycles")}
            parsed["cost_cycles"] = {k: uint(ct["cost_cycles"][k]) for k in COST_KEYS}
            parsed["cache"] = {
                level: {k: uint(ct["cache"][level][k]) for k in COUNTERS} for level in LEVELS
            }
            add_counts(totals, parsed)
            end = stop
        if not end or end != uint(manifest["events"]) or wire(totals) != manifest["totals"]:
            raise ValueError("Incomplete manifest or totals mismatch")
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError("Malformed event manifest") from exc


def decode_event_chunk(payload, descriptor, manifest):
    try:
        if (
            len(payload) != uint(descriptor["compressed_bytes"])
            or sha(payload) != descriptor["gzip_sha256"]
        ):
            raise ValueError("Compressed chunk mismatch")
        with gzip.GzipFile(fileobj=io.BytesIO(payload)) as stream:
            raw = stream.read(MAX_JSON + 1)
        if (
            len(raw) > MAX_JSON
            or len(raw) != uint(descriptor["uncompressed_bytes"])
            or sha(raw) != descriptor["json_sha256"]
        ):
            raise ValueError("Decoded chunk mismatch")
        data = json.loads(raw)
        if data["schema"] != "event-window-chunk-v1" or data["columns"] != COLUMNS:
            raise ValueError("Unsupported chunk schema")
        if any(data[k] != descriptor[k] for k in ("start", "end")) or len(data["rows"]) != uint(
            descriptor["rows"]
        ):
            raise ValueError("Chunk range mismatch")
        totals = empty_counts()
        for index, row in enumerate(data["rows"], uint(data["start"])):
            if len(row) != len(COLUMNS) or uint(row[0]) != index:
                raise ValueError("Row index/width mismatch")
            if uint(row[5]) >= len(manifest["contexts"]) or uint(row[6]) >= len(manifest["owners"]):
                raise ValueError("Unknown dictionary reference")
            add_counts(totals, row_counts(row))
        if wire(totals) != descriptor["totals"]:
            raise ValueError("Chunk totals disagree")
        return data
    except (KeyError, TypeError, IndexError, OSError, EOFError, zlib.error) as exc:
        raise ValueError("Malformed event chunk") from exc


def write_event_chunks(events, output: Path):
    if output.exists():
        raise ValueError("Output must be new")
    output.mkdir(parents=True, exist_ok=False)
    owners, owner_ids, contexts = [], {}, []
    chunks, rows = [], []
    total, subtotal = empty_counts(), empty_counts()
    facts = {}
    n = 0

    def flush():
        nonlocal rows, subtotal
        end = rows[-1][0]
        data = dict(
            schema="event-window-chunk-v1",
            start=rows[0][0],
            end=str(int(end) + 1),
            columns=COLUMNS,
            rows=rows,
        )
        encoded = encode_chunk(data)
        identifier = f"{len(chunks):06d}"
        descriptor = dict(
            id=identifier,
            start=data["start"],
            end=data["end"],
            rows=str(len(rows)),
            totals=wire(subtotal),
            **encoded["metadata"],
        )
        (output / (identifier + ".json.gz")).write_bytes(encoded["gzip"])
        chunks.append(descriptor)
        rows, subtotal = [], empty_counts()

    for e in events:
        if e["index"] != n:
            raise ValueError("Non-contiguous input events")
        fid = e["function_id"]
        if fid not in owner_ids:
            owner_ids[fid] = len(owners)
            owners.append(dict(function_id=fid, **e["owner"]))
        if e["context"] not in contexts:
            contexts.append(e["context"])
        values = [
            n,
            e["pc"],
            e["address"],
            e["size"],
            e["operation"],
            contexts.index(e["context"]),
            owner_ids[fid],
        ]
        values += [e["cost_cycles"][k] for k in COST_KEYS]
        values += [e["cache"][level][k] for level in LEVELS for k in COUNTERS]
        rows.append(wire(values))
        add_counts(total, e)
        add_counts(subtotal, e)
        key = (e["context"], e["role"], fid, e["pc"])
        fact = facts.setdefault(
            key, dict(context=key[0], role=key[1], function_id=fid, pc=e["pc"], **empty_counts())
        )
        add_counts(fact, e)
        n += 1
        if len(rows) == CHUNK_ROWS:
            flush()
    if rows:
        flush()
    manifest = dict(
        schema="event-window-run-v1",
        columns=COLUMNS,
        events=str(n),
        owners=owners,
        contexts=contexts,
        chunks=chunks,
        totals=wire(total),
    )
    validate_event_manifest(manifest)
    (output / "facts.json.gz").write_bytes(
        gzip.compress(canonical([facts[k] for k in sorted(facts)]), mtime=0)
    )
    (output / "manifest.json").write_bytes(canonical(manifest))
    return manifest


def build_event_run(root: Path, entry: dict, output: Path):
    from psf_lab.hotspot_evidence import load_hotspot_input
    from psf_lab.parser.semantic import parse_trace

    source = load_hotspot_input(root, entry)
    with gzip.open(source["raw_path"], "rt", newline="") as stream:
        events = iter_hotspot_events(
            csv.DictReader(stream), source["ranges"], source["profile"], contexts=source["contexts"]
        )
        manifest = write_event_chunks(events, output)
    old = root / "artifacts/verification/hotspot/formal" / entry["run_id"] / "report.json.gz"
    with gzip.open(old, "rt") as stream:
        saved = json.load(stream)
    with gzip.open(output / "facts.json.gz", "rt") as stream:
        facts = json.load(stream)
    if (
        facts != saved["facts"]
        or manifest["totals"] != wire(saved["totals"])
        or uint(manifest["events"]) != saved["events"]
    ):
        raise ValueError("C1 full fact parity failure")
    psf_path = source["raw_path"].parent / "trace.psf"
    trace = parse_trace(psf_path.read_bytes())
    manifest.update(
        identity=entry,
        profile=source["profile"],
        evidence=source["evidence"],
        context_quality=saved["context_quality"],
        source_lines=saved["source_lines"],
        psf=dict(
            clock=trace["clock"],
            events=trace["events"],
            quality=trace.get("quality"),
            sha256=sha(psf_path.read_bytes()),
        ),
        parity=dict(passed=True, c1_report_sha256=sha(old.read_bytes())),
    )
    (output / "manifest.json").write_bytes(canonical(manifest))
    return manifest


class UnknownEventRun(LookupError):
    """Requested identifier is absent from a structurally valid catalog."""


BASE = Path("artifacts/verification/event-window/formal")


@lru_cache(maxsize=1)
def _parsed_manifest(raw: bytes):
    # Only the last content-verified manifest is retained; callers cannot mutate it.
    manifest = json.loads(raw)
    validate_event_manifest(manifest)
    return manifest


def load_event_manifest(root: Path, run_id: str):
    return copy.deepcopy(_load_verified_manifest(root, run_id))


def _load_verified_manifest(root: Path, run_id: str):
    try:
        catalog = load_event_catalog(root)
        matches = [r for r in catalog["runs"] if r["run_id"] == run_id]
        if not matches:
            raise UnknownEventRun(run_id)
        if (
            not re.fullmatch(r"A0[1-8]-(baseline|pbuf)-b[12]-[01]-[1-3]", run_id)
            or len(matches) != 1
        ):
            raise ValueError("Invalid catalog identity")
        raw = (root / BASE / run_id / "manifest.json").read_bytes()
        if sha(raw) != matches[0]["sha256"]:
            raise ValueError("Manifest hash mismatch")
        manifest = _parsed_manifest(raw)
        if manifest["identity"]["run_id"] != run_id:
            raise ValueError("Identity mismatch")
        return manifest
    except (KeyError, OSError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid event catalog") from exc


def load_event_chunk(root: Path, run_id: str, chunk_id: str):
    manifest = _load_verified_manifest(root, run_id)
    matches = [c for c in manifest["chunks"] if c["id"] == chunk_id]
    if not matches:
        raise UnknownEventRun(chunk_id)
    payload = (root / BASE / run_id / (chunk_id + ".json.gz")).read_bytes()
    decode_event_chunk(payload, matches[0], manifest)
    return payload


def load_event_catalog(root: Path):
    try:
        catalog = json.loads((root / BASE / "catalog.json").read_bytes())
        if catalog["schema"] != "event-window-catalog-v1" or not catalog["runs"]:
            raise ValueError("Invalid catalog")
        seen = set()
        for record in catalog["runs"]:
            run_id = record["run_id"]
            if (
                not re.fullmatch(r"A0[1-8]-(baseline|pbuf)-b[12]-[01]-[1-3]", run_id)
                or run_id in seen
            ):
                raise ValueError("Invalid or duplicate run identity")
            if record["workload"] != run_id[:3] or not re.fullmatch(
                r"[a-f0-9]{64}", record["sha256"]
            ):
                raise ValueError("Invalid run digest")
            seen.add(run_id)
        return catalog
    except (KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        raise ValueError("Malformed catalog") from exc
