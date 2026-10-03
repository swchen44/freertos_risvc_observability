"""Export one PSF as a self-contained, network-independent interactive report."""

import hashlib
import json
import tempfile
from functools import lru_cache
from pathlib import Path

from psf_lab.store import create_trace, load_trace

ROOT = Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def casefold_map():
    return {chr(i): chr(i).casefold() for i in range(0x110000) if chr(i).casefold() != chr(i)}


def embed_json(data):
    return (
        json.dumps(data, ensure_ascii=True, allow_nan=False, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace("&", "\\u0026")
    )


def export_html(input_path: Path, output_path: Path) -> dict:
    if input_path.resolve() == output_path.resolve():
        raise ValueError("HTML output must not overwrite input PSF")
    if input_path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError("PSF exceeds 16 MiB limit")
    assets = ROOT / "web/dist/assets"
    if not (assets / "app.js").is_file() or not (assets / "app.css").is_file():
        raise ValueError(
            "Build web assets first: npm --prefix web ci && npm --prefix web run build"
        )
    with tempfile.TemporaryDirectory() as d:
        store = Path(d)
        metadata = create_trace(store, input_path.read_bytes(), source_name=input_path.name)
        trace, analysis = load_trace(store, metadata["trace_id"])
    metadata["trace_id"] = trace["source"]["sha256"][:32]
    payload = {
        "version": 1,
        "trace": trace,
        "analysis": analysis,
        "metadata": metadata,
        "casefold": casefold_map(),
    }
    js = (assets / "app.js").read_text().replace("</script", "<\\/script")
    css = (assets / "app.css").read_text().replace("</style", "<\\/style")
    html = (ROOT / "web/index.html").read_text()
    html = html.replace(
        '<link rel="stylesheet" href="/assets/app.css" />', "<style>" + css + "</style>"
    )
    html = html.replace(
        '<script type="module" src="/assets/app.js"></script>',
        '<script id="psf-offline-data" type="application/json">'
        + embed_json(payload)
        + "</script><script>"
        + js
        + "</script>",
    )
    policy = (
        "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
        "img-src data: blob:; connect-src 'none'; font-src data:; "
        "base-uri 'none'; form-action 'none'"
    )
    html = html.replace(
        "<title>",
        f'<meta http-equiv="Content-Security-Policy" content="{policy}" /><title>離線 · ',
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=output_path.parent, mode="w", encoding="utf-8", delete=False
    ) as f:
        temporary = Path(f.name)
        try:
            f.write(html)
            f.close()
            temporary.replace(output_path)
        finally:
            temporary.unlink(missing_ok=True)
    return {
        "source_sha256": trace["source"]["sha256"],
        "event_count": len(trace["events"]),
        "schema_version": trace["schema_version"],
        "html_bytes": output_path.stat().st_size,
        "html_sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
        "issues": trace["quality"]["issues"],
    }
