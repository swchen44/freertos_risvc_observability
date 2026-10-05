"""Reproducible curl integration and agent-browser UI acceptance for T4."""

import csv
import json
import os
import subprocess
import unittest
from pathlib import Path

from psf_lab.timing_dashboard import load_dashboard

ROOT = Path(__file__).resolve().parents[2]
MODE = os.environ.get("TIMING_MODE", "server")
OUT = ROOT / "artifacts/verification/small-cache-dashboard" / MODE
SHOTS = ROOT / "artifacts/screenshots/timing"
SESSION = "timing-accept-" + MODE
BASE = "http://127.0.0.1:8016"
LOG = []


def ab(*args):
    if args[0] in {"click", "select", "download"}:
        ab(
            "eval",
            f'document.querySelector({json.dumps(args[1])}).scrollIntoView({{block:"center"}})',
        )
    command = ["agent-browser", "--session", SESSION, *args]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
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


class TimingAcceptance(unittest.TestCase):
    def test_workflow(self):
        OUT.mkdir(parents=True, exist_ok=True)
        SHOTS.mkdir(parents=True, exist_ok=True)
        if MODE == "server":
            receipts = []
            for route in ("api/timing", "timing.html", "assets/timing.js", "assets/timing.css"):
                response = subprocess.run(
                    ["curl", "--fail", "--silent", "--show-error", BASE + "/" + route],
                    capture_output=True,
                    timeout=20,
                )
                self.assertEqual(response.returncode, 0, response.stderr)
                receipts.append(
                    {"route": route, "exit": response.returncode, "bytes": len(response.stdout)}
                )
                if route == "api/timing":
                    self.assertEqual(json.loads(response.stdout), load_dashboard(ROOT))
            (OUT / "curl.json").write_text(json.dumps(receipts, indent=2) + "\n")
        else:
            response = subprocess.run(
                ["curl", "--silent", "--max-time", "2", BASE], capture_output=True
            )
            self.assertNotEqual(response.returncode, 0, "Stop the server before offline acceptance")
        try:
            ab("open", "about:blank")
            ab("set", "viewport", "1600", "1050")
            if MODE == "offline":
                ab("set", "offline", "on")
                ab("network", "route", "http://*", "--abort")
                ab("network", "route", "https://*", "--abort")
                url = (ROOT / "artifacts/offline/small-cache-comparison.html").as_uri()
            else:
                url = BASE + "/timing.html"
            ab("open", url)
            ab("wait", "--fn", "window.timingReady === true")
            ab("snapshot", "-i")
            self.assertEqual(evaluate('document.querySelectorAll(".chart svg").length'), 4)
            self.assertIn("4 筆", evaluate('document.querySelector("#status").textContent'))
            shot("01-overview")
            ab("select", "#group", "T3c-chain")
            ab("wait", "--text", "T3c-chain · 2 筆")
            ab("select", "#level", "l2")
            ab("wait", "--text", "L2 miss 歸因")
            ab("eval", 'document.querySelector("#miss").scrollIntoView({block:"center"})')
            ab("find", "first", '#miss svg path[fill="#326c89"]', "hover")
            ab("wait", "--text", "750 / 34904")
            shot("02-hover")
            ab("click", '.tabulator-col[tabulator-field="guest_ns"]')
            ab("download", "#csv", str(OUT / "sorted.csv"))
            with (OUT / "sorted.csv").open(encoding="utf-8-sig") as stream:
                rows = list(csv.DictReader(stream))
            values = [int(row["guest_ns"]) for row in rows]
            self.assertEqual(sorted(values), [2468700, 2489000])
            dom_values = evaluate(
                'Array.from(document.querySelectorAll(".tabulator-row '
                '.tabulator-cell[tabulator-field=guest_ns]")).map(e=>Number(e.textContent))'
            )
            self.assertEqual(values, dom_values)
            self.assertIn(values, [sorted(values), sorted(values, reverse=True)])
            shot("02-chain-sorted")
            ab("select", "#candidate", "fragmented-pbuf")
            ab("wait", "--text", "T3c-chain · 1 筆")
            ab("click", '.tabulator-row .tabulator-cell[tabulator-field="label"]')
            ab("click", "summary")
            self.assertIn(
                "2136 / 2136", evaluate('document.querySelector("#detail-summary").textContent')
            )
            ab("download", "#csv", str(OUT / "filtered.csv"))
            with (OUT / "filtered.csv").open(encoding="utf-8-sig") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["baseline"], "fragmented-baseline")
            self.assertAlmostEqual(float(rows[0]["improvement_pct"]), 100 * 20300 / 2489000)
            shot("03-filtered-evidence")
            ab("select", "#group", "T3c-linear")
            ab("wait", "--text", "T3c-linear · 2 筆")
            self.assertEqual(evaluate('document.querySelector("#candidate").value'), "all")
            ab("set", "viewport", "390", "844")
            self.assertTrue(evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
            shot("04-mobile")
            errors = json.loads(ab("errors", "--json"))["data"].get("errors", [])
            self.assertEqual(errors, [])
            network = evaluate('performance.getEntriesByType("resource").map(e=>e.name)')
            if MODE == "offline":
                self.assertFalse(any(url.startswith(("http:", "https:")) for url in network))
            (OUT / "assertions.json").write_text(
                json.dumps(
                    {
                        "passed": True,
                        "mode": MODE,
                        "svg_charts": 4,
                        "filtered_csv_rows": 1,
                        "sorted_values": values,
                        "offline_network_blocked": MODE == "offline",
                        "resources": network,
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
