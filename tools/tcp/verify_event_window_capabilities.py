"""Real browser checks for unavailable Worker/DecompressionStream, using exact built assets."""

import argparse
import hashlib
import json
import shutil
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from verify_event_window_dashboard import ROOT, process_table


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--browser-executable", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(__file__, args.output / "harness.py")
    template = (ROOT / "web/event-window.html").read_text()
    resources = {
        f"/assets/event-window.{ext}": (ROOT / f"web/dist/assets/event-window.{ext}").read_bytes()
        for ext in ["js", "css"]
    }
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            if self.path in ["/Worker.html", "/DecompressionStream.html"]:
                missing = self.path[1:-5]
                body = template.replace(
                    "</head>", f"<script>globalThis.{missing}=undefined;</script></head>"
                ).encode()
                content_type = "text/html; charset=utf-8"
            elif self.path in resources:
                body = resources[self.path]
                content_type = "text/javascript" if self.path.endswith(".js") else "text/css"
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    session = "c2a-capabilities"
    commands, owned, cases = [], set(), []
    started = False
    done = threading.Event()
    receipt = dict(
        passed=False,
        injected_fixture=True,
        cases=cases,
        assets={k: hashlib.sha256(v).hexdigest() for k, v in resources.items()},
    )

    def ab(*command):
        nonlocal started
        prefix = ["agent-browser", "--session", session]
        if not started and command[0] == "open":
            prefix += [
                "--executable-path",
                str(args.browser_executable),
                "--args",
                "--disable-gpu,--disable-software-rasterizer,--renderer-process-limit=1,--js-flags=--max-old-space-size=64",
            ]
            started = True
        result = subprocess.run(prefix + list(command), capture_output=True, text=True, timeout=50)
        commands.append(
            dict(args=command, exit=result.returncode, stdout=result.stdout, stderr=result.stderr)
        )
        (args.output / "commands.json").write_text(json.dumps(commands, indent=2) + "\n")
        if result.returncode:
            raise RuntimeError(result.stderr or result.stdout)
        return result.stdout

    def ev(code):
        return json.loads(ab("eval", "--json", code))["data"]["result"]

    def monitor():
        while not done.is_set():
            rows = process_table()
            try:
                daemon = int((Path.home() / ".agent-browser" / f"{session}.pid").read_text())
            except (OSError, ValueError):
                daemon = -1
            descendants = {daemon}
            for _ in range(10):
                descendants.update(pid for pid, row in rows.items() if row[0] in descendants)
            owned.update(
                pid for pid in descendants if pid in rows and "chrome" in rows[pid][2].lower()
            )
            done.wait(0.2)

    monitor_thread = threading.Thread(target=monitor)
    monitor_thread.start()
    try:
        for capability in ["Worker", "DecompressionStream"]:
            ab("open", f"http://127.0.0.1:{server.server_port}/{capability}.html")
            ab("set", "viewport", "1600", "1050")
            ab(
                "wait",
                "--fn",
                "document.querySelector('#status').textContent.includes('瀏覽器需支援')",
            )
            state = ev("""({ready:window.eventWindowReady,result:window.eventWindowResult,
                status:document.querySelector('#status').textContent,
                rows:document.querySelectorAll(
                    '#function-table .tabulator-row,#event-table .tabulator-row').length,
                paths:document.querySelectorAll(
                    '#event-chart svg path,#rank-chart svg path,#cost-chart svg path').length})""")
            assert state["ready"] is False and state["result"] is None
            assert state["rows"] == 0 and state["paths"] == 0
            cases.append(dict(missing=capability, **state))
            ab("screenshot", str(args.output / f"no-{capability}.png"))
        assert not any(path.startswith("/api/") for path in requests)
        receipt["checks_passed"] = True
    except Exception as error:
        receipt["failure"] = str(error)
        raise
    finally:
        try:
            if started:
                ab("close")
            receipt["close_exit"] = 0
        except Exception as error:
            receipt.update(close_exit=1, close_error=str(error))
        done.set()
        monitor_thread.join()
        server.shutdown()
        server.server_close()
        thread.join()
        time.sleep(0.5)
        remaining = process_table()
        receipt["owned_pids"] = sorted(owned)
        receipt["remaining_browser_pids"] = sorted(pid for pid in owned if pid in remaining)
        receipt["requests"] = requests
        receipt["passed"] = bool(
            receipt.get("checks_passed")
            and owned
            and receipt.get("close_exit") == 0
            and not receipt["remaining_browser_pids"]
        )
        (args.output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    assert receipt["passed"], receipt
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
