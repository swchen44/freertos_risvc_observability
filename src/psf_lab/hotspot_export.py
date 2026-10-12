"""Self-contained, network-independent C1 workload HTML export."""

from pathlib import Path

from psf_lab.hotspot_dashboard import load_hotspot_workload
from psf_lab.offline import embed_json
from psf_lab.runner import digest


def export_hotspot_html(root: Path, workload: str, output: Path) -> dict:
    if output.exists():
        raise ValueError("Output must be new")
    data = load_hotspot_workload(root, workload)
    template = root / "web/hotspot.html"
    js = root / "web/dist/assets/hotspot.js"
    css = root / "web/dist/assets/hotspot.css"
    html = template.read_text()
    replacements = {
        '<script id="hotspot-data"></script>': '<script id="hotspot-data" type="application/json">'
        + embed_json(data)
        + "</script>",
        '<script src="/assets/hotspot.js"></script>': "<script>"
        + js.read_text().replace("</script", "<\\/script")
        + "</script>",
        '<link rel="stylesheet" href="/assets/hotspot.css">': "<style>"
        + css.read_text().replace("</style", "<\\/style")
        + "</style>",
    }
    for old, new in replacements.items():
        if html.count(old) != 1:
            raise ValueError("Missing or duplicate template anchor")
        html = html.replace(old, new)
    policy = (
        "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
        "img-src data: blob:; connect-src 'none'; font-src data:; base-uri 'none'"
    )
    html = html.replace(
        "<title>", '<meta http-equiv="Content-Security-Policy" content="' + policy + '"><title>', 1
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as stream:
        stream.write(html)
    return dict(
        workload=workload,
        output_sha256=digest(output),
        bytes=output.stat().st_size,
        manifest_sha256=data.get("manifest_sha256"),
        assets={str(p.relative_to(root)): digest(p) for p in (template, js, css)},
    )
