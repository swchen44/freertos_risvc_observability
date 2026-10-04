"""Loopback-only, bounded local PSF analysis service."""

import asyncio
import json
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException

from psf_lab.cache_report import load_comparison
from psf_lab.export import export_csv
from psf_lab.harness import compare_cases
from psf_lab.parser.errors import ParseError
from psf_lab.query import query_events, query_view
from psf_lab.runner import CASE_IDS, check_run, digest, load_run
from psf_lab.store import StoreError, create_trace, list_traces, load_trace, trace_path

ROOT = Path(__file__).resolve().parents[2]


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filters: dict = Field(default_factory=dict)
    sort: list = Field(default_factory=list)
    offset: StrictInt = Field(default=0, ge=0)
    limit: StrictInt = Field(default=200, ge=1, le=2000)


class ViewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filters: dict = Field(default_factory=dict)


class ExportRequest(ViewRequest):
    sort: list = Field(default_factory=list)
    kind: str = "events"


class CompareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pair_id: str
    run_ids: list[str] = Field(min_length=2, max_length=2)


def error_response(code, message, status, offset=None):
    return JSONResponse(
        {"error": {"code": code, "message": message, "offset": offset}}, status_code=status
    )


class BodyLimit:
    def __init__(self, app, max_bytes):
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in ("POST", "PUT"):
            return await self.app(scope, receive, send)
        chunks = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            size += len(message.get("body", b""))
            if size > self.max_bytes:
                return await error_response("too_large", "Request body exceeds limit", 413)(
                    scope, receive, send
                )
            chunks.append(message.get("body", b""))
            if not message.get("more_body", False):
                break
        sent = False

        async def bounded_receive():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return await receive()

        await self.app(scope, bounded_receive, send)


def create_app(
    store: Path, *, max_bytes=16 * 1024 * 1024, max_traces=20, run_root: Path | None = None
) -> FastAPI:
    app = FastAPI(title="PSF Lab local API", docs_url=None, redoc_url=None)
    app.add_middleware(BodyLimit, max_bytes=max_bytes + 65536)
    gate = asyncio.Semaphore(1)
    store = store.resolve()
    runs = run_root or ROOT / "runs"

    @app.middleware("http")
    async def local_only(request, call_next):
        host = request.url.hostname
        origin = request.headers.get("origin")
        if host not in ("localhost", "127.0.0.1", "::1") or (
            origin and urlsplit(origin).hostname not in ("localhost", "127.0.0.1", "::1")
        ):
            return error_response("invalid_host", "Local requests only", 400)
        return await call_next(request)

    @app.exception_handler(ParseError)
    async def parse_error(request, error):
        return error_response(error.code, error.message, 422, error.offset)

    @app.exception_handler(StoreError)
    async def store_error(request, error):
        return error_response(error.code, str(error), error.status)

    @app.exception_handler(ValueError)
    async def value_error(request, error):
        return error_response("invalid_input", str(error), 422)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        return error_response("invalid_request", "Invalid request fields", 422)

    @app.exception_handler(HTTPException)
    async def http_error(request, error):
        return error_response("http_error", "Request not available", error.status_code)

    @app.exception_handler(OSError)
    async def io_error(request, error):
        return error_response("storage_error", "Local data unavailable", 500)

    @lru_cache(maxsize=2)
    def data(id_):
        return load_trace(store, id_)

    @app.get("/api/cache")
    def cache_comparison():
        return load_comparison(ROOT / "runs/cache-relative-v3")

    @app.get("/api/traces")
    def traces():
        return list_traces(store)

    @app.post("/api/traces", status_code=201)
    async def upload(file: UploadFile):
        try:
            async with gate:
                value = bytearray()
                while chunk := await file.read(65536):
                    if len(value) + len(chunk) > max_bytes:
                        raise StoreError("too_large", "PSF exceeds configured byte limit", 413)
                    value.extend(chunk)
                return await run_in_threadpool(
                    create_trace,
                    store,
                    bytes(value),
                    source_name=file.filename or "trace.psf",
                    max_traces=max_traces,
                    max_bytes=max_bytes,
                )
        finally:
            await file.close()

    @app.get("/api/traces/{id_}")
    def metadata(id_: str):
        return json.loads((trace_path(store, id_) / "metadata.json").read_text())

    @app.post("/api/traces/{id_}/events")
    def events(id_: str, query: QueryRequest):
        trace, _ = data(id_)
        return query_events(
            trace, query.filters, query.sort, offset=query.offset, limit=query.limit
        )

    @app.post("/api/traces/{id_}/view")
    def view(id_: str, query: ViewRequest):
        trace, analysis = data(id_)
        return query_view(trace, analysis, query.filters)

    @app.post("/api/traces/{id_}/export")
    def export(id_: str, query: ExportRequest):
        trace, analysis = data(id_)
        result = export_csv(trace, analysis, query.filters, query.sort, kind=query.kind)
        return Response(
            result,
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": 'attachment; filename="psf-'
                + ("metrics" if query.kind == "metrics" else "events")
                + '.csv"'
            },
        )

    @lru_cache(maxsize=1)
    def registry():
        found = {}
        paths = sorted(runs.glob("*/manifest.json")) + sorted(runs.glob("suite-*/*/manifest.json"))
        for p in paths:
            if p.parent.parent.name == "local":
                continue
            try:
                m = json.loads(p.read_text())
                if m["case_id"] not in CASE_IDS or m["status"] != "pass" or m["exit_code"] != 0:
                    continue
                if check_run(p.parent)["verdict"] != "pass":
                    continue
                if any(
                    item.get("missing") or digest(p.parent / name) != item["sha256"]
                    for name, item in m["files"].items()
                ):
                    continue
                found[p.parent.name] = {
                    "path": p.parent,
                    "manifest_sha256": digest(p),
                    "summary": {
                        "run_id": p.parent.name,
                        "case_id": m["case_id"],
                        "quality": m["quality"],
                        "source_commit": m["source_commit"],
                        "outcome": json.loads((p.parent / "oracle.json").read_text())["outcome"],
                        "event_count": m["event_count"],
                    },
                }
            except (ValueError, KeyError, OSError):
                continue
        return found

    def verified_run(id_):
        item = registry().get(id_)
        if not item:
            raise StoreError("not_found", "Unknown verified run")
        if (
            digest(item["path"] / "manifest.json") != item["manifest_sha256"]
            or check_run(item["path"])["verdict"] != "pass"
        ):
            raise StoreError("changed_run", "Run evidence changed", 422)
        return item["path"]

    @app.get("/api/runs")
    def run_list():
        return [v["summary"] for v in registry().values()]

    @app.get("/api/runs/{id_}/psf")
    def run_psf(id_: str):
        return FileResponse(
            verified_run(id_) / "trace.psf",
            media_type="application/octet-stream",
            filename=id_ + ".psf",
        )

    @app.post("/api/comparisons")
    def compare(query: CompareRequest):
        values = [load_run(verified_run(id_)) for id_ in query.run_ids]
        result = compare_cases(query.pair_id, values)
        result["runs"] = [
            {
                "run_id": id_,
                "case": v["case"],
                "analysis": v["analysis"],
                "oracle": v["oracle"],
                "manifest": {
                    k: v["manifest"][k] for k in ["source_commit", "time_model", "mtime_hz"]
                },
            }
            for id_, v in zip(query.run_ids, values, strict=True)
        ]
        return result

    dist = ROOT / "web/dist"
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=dist, html=True), name="dashboard")
    return app
