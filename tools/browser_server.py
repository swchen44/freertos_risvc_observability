"""Isolated browser-test store, removed when this process exits normally."""

import tempfile
from pathlib import Path

import uvicorn

from psf_lab.server import create_app

with tempfile.TemporaryDirectory(prefix="psf-lab-browser-") as directory:
    uvicorn.run(create_app(Path(directory)), host="127.0.0.1", port=8766)
