"""Read-only link/image validation for current docs, plus baseline manifest hashes."""

import json
from pathlib import Path
from urllib.parse import unquote, urlsplit

from markdown_it import MarkdownIt

from psf_lab.provenance import verify_sources


def verify_docs(root: Path) -> dict:
    root = root.resolve()
    parser = MarkdownIt()
    paths = [
        root / "README.md",
        *sorted((root / "docs").rglob("*.md")),
        *sorted((root / "web").glob("*.md")),
    ]
    broken = []
    checked = 0
    for path in paths:
        if not path.is_file():
            broken.append({"file": str(path.relative_to(root)), "target": "(missing document)"})
            continue
        for token in parser.parse(path.read_text()):
            for child in token.children or []:
                target = (
                    child.attrGet("href")
                    if child.type == "link_open"
                    else (child.attrGet("src") if child.type == "image" else None)
                )
                if not target or target.startswith("#"):
                    continue
                url = urlsplit(target)
                if url.scheme or url.netloc:
                    continue
                checked += 1
                dest = (path.parent / unquote(url.path)).resolve()
                if not dest.is_relative_to(root) or not dest.exists():
                    broken.append({"file": str(path.relative_to(root)), "target": target})
    manifest = json.loads((root / "references/manifest.json").read_text())
    baseline = verify_sources(root, manifest)
    return {
        "ok": not broken and baseline["ok"],
        "documents": len(paths),
        "links_checked": checked,
        "broken_links": broken,
        "baseline_files": len(manifest["files"]),
        "baseline": baseline,
    }
