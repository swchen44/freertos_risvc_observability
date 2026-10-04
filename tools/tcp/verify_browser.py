"""Real curl integration and agent-browser E2E; TCP_MODE=server|offline."""

import csv
import json
import os
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODE = os.environ.get("TCP_MODE", "server")
OUT = ROOT / "artifacts/verification/tcp-optimization" / MODE
SHOTS = ROOT / "artifacts/screenshots/tcp"
SESSION = "tcp-accept-" + MODE
LOG = []


def ab(*args):
    if args[0] in {"click", "select", "download"}:
        ab(
            "eval",
            f'document.querySelector({json.dumps(args[1])}).scrollIntoView({{block:"center"}})',
        )
    command = ["agent-browser", "--session", SESSION, *args]
    result = subprocess.run(command, capture_output=True, text=True, timeout=40)
    LOG.append(
        {
            "command": command,
            "exit": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    )
    (OUT / "commands.json").write_text(json.dumps(LOG, ensure_ascii=False, indent=2) + "\n")
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout)
    return result.stdout


def evaluate(code):
    return json.loads(ab("eval", "--json", code))["data"]["result"]


def shot(name):
    ab("screenshot", "--full", str(SHOTS / f"{MODE}-{name}.png"))


class TCPAcceptance(unittest.TestCase):
    def test_workflow(self):
        OUT.mkdir(parents=True, exist_ok=True)
        SHOTS.mkdir(parents=True, exist_ok=True)
        if MODE == "server":
            for route in ("api/tcp", "tcp.html", "assets/tcp.js", "assets/tcp.css"):
                response = subprocess.run(
                    [
                        "curl",
                        "--fail",
                        "--silent",
                        "--show-error",
                        "http://127.0.0.1:8765/" + route,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                self.assertEqual(response.returncode, 0, response.stderr)
                if route == "api/tcp":
                    data = json.loads(response.stdout)
                    self.assertEqual(len(data["rows"]), 18)
                    self.assertTrue(all(r["evidence"]["acked_bytes"] == 5840 for r in data["rows"]))
                    (OUT / "curl-api.json").write_text(response.stdout)
        else:
            result = subprocess.run(
                ["curl", "--silent", "--max-time", "2", "http://127.0.0.1:8765/api/tcp"],
                capture_output=True,
            )
            self.assertNotEqual(result.returncode, 0, "stop server before offline acceptance")
        try:
            ab("open", "about:blank")
            ab("set", "viewport", "1600", "1050")
            if MODE == "offline":
                ab("set", "offline", "on")
                ab("network", "route", "http://*", "--abort")
                ab("network", "route", "https://*", "--abort")
                url = (ROOT / "artifacts/offline/tcp-optimization.html").as_uri()
            else:
                url = "http://127.0.0.1:8765/tcp.html"
            ab("open", url)
            ab("wait", "--fn", "window.tcpReady === true")
            self.assertEqual(evaluate('document.querySelectorAll(".chart svg").length'), 3)
            shot("01-overview")
            ab("select", "#variant", "tcp_nocopy3")
            ab("wait", "--text", "目前 1 筆")
            ab("click", '.tabulator-row .tabulator-cell[tabulator-field="variant"]')
            ab("click", "summary")
            self.assertIn("5840", evaluate('document.querySelector("#evidence").textContent'))
            shot("02-zero-copy")
            ab("download", "#csv", str(OUT / "filtered.csv"))
            with (OUT / "filtered.csv").open(encoding="utf-8-sig") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["variant"], "tcp_nocopy3")
            self.assertEqual(rows[0]["instructions"], "13712")
            ab("select", "#variant", "all")
            ab("select", "#kind", "retransmit")
            ab("wait", "--text", "目前 3 筆")
            shot("03-retransmit")
            ab("click", '.tabulator-col[tabulator-field="instructions"]')
            ab("download", "#csv", str(OUT / "sorted.csv"))
            with (OUT / "sorted.csv").open(encoding="utf-8-sig") as f:
                values = [int(r["instructions"]) for r in csv.DictReader(f)]
            self.assertEqual(values, sorted(values))
            self.assertEqual(values, [3898, 3955, 6109])
            ab("select", "#repeat", "all")
            ab("select", "#kind", "all")
            ab("wait", "--text", "目前 18 筆")
            shot("04-all-results")
            errors = json.loads(ab("errors", "--json"))["data"].get("errors", [])
            self.assertEqual(errors, [])
            (OUT / "assertions.json").write_text(
                json.dumps(
                    {
                        "passed": True,
                        "mode": MODE,
                        "svg_charts": 3,
                        "filtered_csv_rows": 1,
                        "sorted_values": values,
                        "offline_network_blocked": MODE == "offline",
                        "errors": errors,
                    },
                    indent=2,
                )
                + "\n"
            )
        finally:
            ab("close")


if __name__ == "__main__":
    unittest.main(verbosity=2)
