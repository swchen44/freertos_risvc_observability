"""agent-browser E2E. Run server mode, stop server, then run offline mode."""

import csv
import hashlib
import io
import json
import os
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODE = os.environ.get("POC_MODE", "server")
SESSION = "poc-accept-" + MODE
OUT = ROOT / "artifacts/verification/offline/agent-browser" / MODE
IMAGES = ROOT / "artifacts/screenshots" / MODE
PSF = next((ROOT / "runs/suite-20261003T085652Z-2732b56355").glob("*-queue_baseline-*/trace.psf"))
LOG = []
SHOTS = []


def ab(*args):
    if args[0] in {"click", "hover", "fill", "select", "download"}:
        selector = json.dumps(args[1])
        ab("eval", f'document.querySelector({selector}).scrollIntoView({{block:"center"}})')
    command = ["agent-browser", "--session", SESSION, *args]
    p = subprocess.run(command, capture_output=True, text=True, timeout=35)
    LOG.append(
        {"command": command, "exit_code": p.returncode, "stdout": p.stdout, "stderr": p.stderr}
    )
    (OUT / "commands.json").write_text(json.dumps(LOG, ensure_ascii=False, indent=2) + "\n")
    if p.returncode:
        raise RuntimeError(p.stderr or p.stdout)
    return p.stdout


def evaluate(code):
    return json.loads(ab("eval", "--json", code))["data"]["result"]


def settled():
    ab(
        "wait",
        "--fn",
        "Number(document.body.dataset.renderRevision)>0 && "
        '!document.querySelector("#status").textContent.includes("正在")',
    )
    ab("snapshot", "-i")


def shot(name, description):
    dest = IMAGES / (name + ".png")
    if name == "08-quality":
        ab("eval", 'document.querySelector("#details").scrollIntoView({block:"start"})')
        ab("screenshot", str(dest))
    else:
        ab("screenshot", "--full", str(dest))
    SHOTS.append(
        {
            "file": str(dest.relative_to(ROOT)),
            "description": description,
            "sha256": hashlib.sha256(dest.read_bytes()).hexdigest(),
            "state": evaluate(
                '({window:document.querySelector("#window-label").textContent,search:document.querySelector("#search-filter").value,task:[...document.querySelector("#task-filter").selectedOptions].map(x=>x.value),rows:document.querySelector("#row-count").textContent})'
            ),
        }
    )


class BrowserAcceptance(unittest.TestCase):
    def test_full_flow(self):
        OUT.mkdir(parents=True, exist_ok=True)
        IMAGES.mkdir(parents=True, exist_ok=True)
        try:
            ab("open", "about:blank")
            ab("set", "viewport", "1600", "1000")
            if MODE == "offline":
                probe = subprocess.run(
                    ["curl", "--silent", "--max-time", "2", "http://127.0.0.1:8767/api/traces"],
                    capture_output=True,
                )
                self.assertNotEqual(
                    probe.returncode, 0, "Stop the test server before offline acceptance"
                )
                (OUT / "server-stopped.json").write_text(
                    json.dumps({"curl_exit_code": probe.returncode}) + "\n"
                )
                ab("set", "offline", "on")
                ab("network", "route", "http://*", "--abort")
                ab("network", "route", "https://*", "--abort")
                ab("open", (ROOT / "artifacts/local/offline-reports/queue_baseline.html").as_uri())
            else:
                ab("open", "http://127.0.0.1:8767")
                ab("snapshot", "-i")
                shot("01-start", "本機服務：選擇原始 PSF 或已儲存 trace")
                meta = json.loads(
                    (ROOT / "artifacts/verification/offline/http/upload.body").read_text()
                )
                ab("select", "#saved-traces", meta["trace_id"])
            settled()
            self.assertGreater(evaluate('document.querySelectorAll("#timeline svg").length'), 0)
            self.assertIn("281", evaluate('document.querySelector("#row-count").textContent'))
            if MODE == "offline":
                self.assertFalse(
                    evaluate('!!document.querySelector(".upload").getClientRects().length')
                )
                self.assertFalse(
                    evaluate(
                        '!!document.querySelector(".compare-controls").getClientRects().length'
                    )
                )
            shot("02-overview", "Queue trace：時間軸、CPU 分母與事件來源")
            initial = evaluate(
                '({coverage:document.querySelector("#coverage-label").textContent,shares:document.querySelector("#share-values").textContent})'
            )
            task = evaluate(
                '[...document.querySelector("#task-filter").options].find(x=>x.textContent==="consumer").value'
            )
            ab("select", "#task-filter", task)
            settled()
            ab("fill", "#start-filter", "500")
            ab("fill", "#end-filter", "50000")
            ab("click", "#apply-window")
            settled()
            self.assertIn(
                "[500, 50000)", evaluate('document.querySelector("#window-label").textContent')
            )
            shot("03-filter-window", "選 consumer 與時間窗；統計分母保留完整排程")
            ab("click", "#reset")
            settled()
            self.assertEqual(
                initial,
                evaluate(
                    '({coverage:document.querySelector("#coverage-label").textContent,shares:document.querySelector("#share-values").textContent})'
                ),
            )
            ab("click", "#brush")
            box = evaluate(
                '(() => {const r=document.querySelector("#timeline").getBoundingClientRect();'
                "return {x:r.x,y:r.y,w:r.width,h:r.height};})()"
            )
            ab(
                "mouse",
                "move",
                str(round(box["x"] + box["w"] * 0.3)),
                str(round(box["y"] + box["h"] * 0.3)),
            )
            ab("mouse", "down", "left")
            ab(
                "mouse",
                "move",
                str(round(box["x"] + box["w"] * 0.6)),
                str(round(box["y"] + box["h"] * 0.6)),
            )
            ab("mouse", "up", "left")
            settled()
            self.assertNotEqual(evaluate('document.querySelector("#start-filter").value'), "")
            shot("04-timeline-brush", "實際拖曳選取時間窗，事件與統計同步更新")
            ab("click", "#reset")
            settled()
            # Hover a real table cell then pin the details through a click.
            ab("hover", ".tabulator-row:nth-child(2) .tabulator-cell[tabulator-field=kind]")
            ab("click", ".tabulator-row:nth-child(2) .tabulator-cell[tabulator-field=kind]")
            shot("04-event-details", "滑過事件並點選固定原始欄位、offset 與品質")
            ab("click", '.tabulator-col[tabulator-field="ticks"]')
            settled()
            ab("wait", "--fn", 'document.querySelector("#sort-label").textContent.includes("↓")')
            self.assertIn("↓", evaluate('document.querySelector("#sort-label").textContent'))
            # Real mouse drag of a column resize handle.
            rect = evaluate(
                "(() => {const r=document.querySelector("
                '".tabulator-col + .tabulator-col-resize-handle").getBoundingClientRect();'
                "return {x:r.x+r.width/2,y:r.y+r.height/2};})()"
            )
            before = evaluate(
                'document.querySelector(".tabulator-col").getBoundingClientRect().width'
            )
            ab("mouse", "move", str(round(rect["x"])), str(round(rect["y"])))
            ab("mouse", "down", "left")
            ab("mouse", "move", str(round(rect["x"] + 45)), str(round(rect["y"])))
            ab("mouse", "up", "left")
            self.assertGreater(
                evaluate('document.querySelector(".tabulator-col").getBoundingClientRect().width'),
                before,
            )
            shot("05-sort-resize", "時間倒序與拖曳調整欄寬")
            ab("download", "#export-events", str(OUT / "events.csv"))
            rows = list(csv.DictReader(io.StringIO((OUT / "events.csv").read_text())))
            self.assertEqual(len(rows), 281)
            self.assertEqual(
                [int(r["ticks"]) for r in rows],
                sorted([int(r["ticks"]) for r in rows], reverse=True),
            )
            ab("download", "#export-metrics", str(OUT / "metrics.csv"))
            self.assertTrue(list(csv.DictReader(io.StringIO((OUT / "metrics.csv").read_text()))))
            shot("06-csv", "匯出所有 281 筆事件，不只目前 20 筆；CSV 另以檔案驗證")
            ab("fill", "#search-filter", "no-such-message")
            settled()
            self.assertIn("符合 0 筆", evaluate('document.querySelector("#row-count").textContent'))
            shot("07-empty-filter", "沒有符合事件時仍保留正確的排程分母")
            ab("click", "#reset")
            settled()
            ab("click", "#show-quality")
            shot("08-quality", "來源 SHA、時基、完整性限制與品質")
            if MODE == "server":
                ab("click", ' .tabulator-row .tabulator-cell[tabulator-field="kind"]')
                ab("click", "#compare-run")
                ab(
                    "wait",
                    "--fn",
                    'document.querySelector("#status").textContent.includes("案例比較：pass")',
                )
                shot("09-comparison", "Logger 干擾／改善，附獨立 oracle 結果")
            else:
                requests = ab("network", "requests")
                self.assertNotIn("http://", requests)
                self.assertNotIn("https://", requests)
                (OUT / "network.txt").write_text(requests)
            errors = ab("errors")
            self.assertFalse(errors.strip(), errors)
            (OUT / "assertions.json").write_text(
                json.dumps(
                    {
                        "passed": True,
                        "mode": MODE,
                        "initial": initial,
                        "csv_rows": len(rows),
                        "console_errors": errors,
                        "source_sha256": hashlib.sha256(PSF.read_bytes()).hexdigest(),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n"
            )
        finally:
            (OUT / "screenshots.json").write_text(
                json.dumps(
                    {
                        "mode": MODE,
                        "viewport": [1600, 1000],
                        "source_commit": subprocess.check_output(
                            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
                        ).strip(),
                        "shots": SHOTS,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n"
            )
            ab("close")


if __name__ == "__main__":
    unittest.main(verbosity=2)
