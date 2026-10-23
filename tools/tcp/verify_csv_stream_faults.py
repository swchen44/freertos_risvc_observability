"""Exercise normal and truncated CSV downloads over real loopback HTTP."""

import argparse
import csv
import hashlib
import io
import json
import socket
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch

import uvicorn

from psf_lab import event_window as events
from psf_lab.hotspot_events import iter_hotspot_events
from psf_lab.server import create_app
from tests.unit.test_cost_attribution import owner
from tests.unit.test_hotspot_report import profile, rows_for


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    receipt = dict(passed=False, synthetic_fixture=True, cases=[])
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        rid = "A02-baseline-b1-1-1"
        folder = root / events.BASE / rid
        m = events.write_event_chunks(
            iter_hotspot_events(
                rows_for([(100, 100, 4, "I")] * 1025), [owner(0, 512)], profile(), contexts=None
            ),
            folder,
        )
        m["identity"] = dict(run_id=rid)
        raw = events.canonical(m)
        (folder / "manifest.json").write_bytes(raw)
        (folder.parent / "catalog.json").write_bytes(
            events.canonical(
                dict(
                    schema="event-window-catalog-v1",
                    runs=[dict(run_id=rid, workload="A02", sha256=events.sha(raw))],
                )
            )
        )
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        with patch("psf_lab.server.ROOT", root):
            server = uvicorn.Server(
                uvicorn.Config(create_app(store=root / "store"), log_level="error")
            )
            thread = threading.Thread(target=lambda: server.run(sockets=[listener]))
            thread.start()
            try:
                deadline = time.monotonic() + 10
                while not server.started and time.monotonic() < deadline:
                    time.sleep(0.01)
                assert server.started

                def request(name):
                    body = a.output / (name + ".body")
                    headers = a.output / (name + ".headers")
                    command = [
                        "curl",
                        "--silent",
                        "--show-error",
                        "--noproxy",
                        "127.0.0.1",
                        "--max-time",
                        "10",
                        "--dump-header",
                        str(headers),
                        "--output",
                        str(body),
                        "--write-out",
                        "%{http_code}",
                        f"http://127.0.0.1:{port}/api/event-windows/{rid}/events.csv",
                    ]
                    result = subprocess.run(command, capture_output=True, text=True)
                    data = body.read_bytes() if body.exists() else b""
                    case = dict(
                        name=name,
                        exit=result.returncode,
                        status=result.stdout,
                        stderr=result.stderr,
                        bytes=len(data),
                        sha256=hashlib.sha256(data).hexdigest(),
                    )
                    receipt["cases"].append(case)
                    return case, data

                case, data = request("valid")
                rows = list(csv.DictReader(io.StringIO(data.decode())))
                assert case["exit"] == 0 and case["status"] == "200" and len(rows) == 1025
                (folder / "000001.json.gz").write_bytes(b"broken")
                case, data = request("late-corruption")
                assert case["status"] == "200" and case["exit"] in (18, 56) and len(data) > 0
                rows = list(csv.DictReader(io.StringIO(data.decode())))
                assert 0 < len(rows) < 1025
                (folder / "000000.json.gz").write_bytes(b"broken")
                case, data = request("first-corruption")
                assert (
                    case["exit"] == 0
                    and case["status"] == "503"
                    and json.loads(data)["error"] == "Invalid event evidence"
                )
                receipt["passed"] = True
            finally:
                server.should_exit = True
                thread.join(timeout=10)
                listener.close()
                receipt["server_stopped"] = not thread.is_alive()
                receipt["passed"] = bool(receipt["passed"] and receipt["server_stopped"])
                (a.output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    assert receipt["passed"]
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
