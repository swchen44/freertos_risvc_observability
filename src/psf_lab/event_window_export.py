"""Export complete compressed workload data with local worker assets."""

import base64
import gzip
from pathlib import Path

from psf_lab.event_window import (
    BASE,
    decode_event_chunk,
    load_event_catalog,
    load_event_manifest,
    sha,
)
from psf_lab.offline import embed_json


def export_event_window_html(root: Path, workload: str, output: Path):
    if output.exists():
        raise ValueError("Output must be new")
    catalog = load_event_catalog(root)
    records = [r for r in catalog["runs"] if r["workload"] == workload]
    if not records:
        raise ValueError("Unknown workload")
    runs = {}
    chunk_pool = {}
    for record in records:
        rid = record["run_id"]
        m = load_event_manifest(root, rid)
        raw_manifest = (root / BASE / rid / "manifest.json").read_bytes()
        for c in m["chunks"]:
            payload = (root / BASE / rid / (c["id"] + ".json.gz")).read_bytes()
            decode_event_chunk(payload, c, m)
            chunk_pool[c["gzip_sha256"]] = base64.b64encode(payload).decode("ascii")
        runs[rid] = dict(
            manifest_gzip=base64.b64encode(gzip.compress(raw_manifest, mtime=0)).decode("ascii")
        )
    template = root / "web/event-window.html"
    js = root / "web/dist/assets/event-window.js"
    css = root / "web/dist/assets/event-window.css"
    html = template.read_text().replace(
        '<link rel="stylesheet" href="/assets/event-window.css" />',
        '<link rel="stylesheet" href="/assets/event-window.css">',
    )
    changes = {
        '<script id="event-window-data"></script>': (
            '<script id="event-window-data" type="application/json">'
        )
        + embed_json(
            dict(
                catalog=dict(schema=catalog["schema"], runs=records),
                runs=runs,
                chunk_pool=chunk_pool,
            )
        )
        + "</script>",
        '<script src="/assets/event-window.js"></script>': "<script>"
        + js.read_text().replace("</script", "<\\/script")
        + "</script>",
        '<link rel="stylesheet" href="/assets/event-window.css">': "<style>"
        + css.read_text().replace("</style", "<\\/style")
        + "</style>",
    }
    for anchor, value in changes.items():
        if html.count(anchor) != 1:
            raise ValueError("Missing or duplicate template anchor")
        html = html.replace(anchor, value)
    policy = (
        "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
        "worker-src blob:; img-src data: blob:; connect-src 'none'; "
        "font-src data:; base-uri 'none'"
    )
    html = html.replace(
        "<title>", '<meta http-equiv="Content-Security-Policy" content="' + policy + '"><title>', 1
    )
    if len(html.encode()) > 95 * 1024 * 1024:
        raise ValueError("HTML exceeds pilot capacity gate")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as f:
        f.write(html)
    return dict(
        workload=workload,
        runs=len(records),
        bytes=output.stat().st_size,
        output_sha256=sha(output.read_bytes()),
        assets={str(p.relative_to(root)): sha(p.read_bytes()) for p in [template, js, css]},
        source_catalog=records,
    )
