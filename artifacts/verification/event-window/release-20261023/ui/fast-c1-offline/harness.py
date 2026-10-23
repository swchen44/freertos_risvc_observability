"""curl integration and real agent-browser acceptance for C1 Web/offline."""

import argparse
import csv
import json
import shutil
import subprocess
import threading
import time
from pathlib import Path

from verify_event_window_dashboard import process_table, session_name

from psf_lab.hotspot_dashboard import load_hotspot_workload

ROOT = Path(__file__).resolve().parents[2]


def verify(mode, output, html=None, executable=None):
    output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(__file__, output / "harness.py")
    downloads = output / "downloads"
    downloads.mkdir()
    started = False
    owned = set()
    done = threading.Event()
    shots = output / "screenshots"
    shots.mkdir()
    log = []
    session = session_name("c1-accept-" + mode)

    def ab(*args):
        nonlocal started
        prefix = ["agent-browser", "--session", session]
        if not started and args[0] == "open":
            prefix += ["--download-path", str(downloads.resolve())]
            if executable:
                prefix += [
                    "--executable-path",
                    str(executable),
                    "--args",
                    "--disable-gpu,--disable-software-rasterizer,--renderer-process-limit=1",
                ]
            started = True
        p = subprocess.run(
            [*prefix, *args],
            text=True,
            capture_output=True,
            timeout=60,
        )
        log.append(dict(args=args, exit=p.returncode, stdout=p.stdout, stderr=p.stderr))
        (output / "commands.json").write_text(json.dumps(log, ensure_ascii=False, indent=2) + "\n")
        if p.returncode:
            raise RuntimeError(p.stderr)
        return p.stdout

    def ev(code):
        return json.loads(ab("eval", "--json", code))["data"]["result"]

    def wait():
        ab("wait", "--fn", "window.hotspotReady === true")

    def shot(name):
        ab("screenshot", "--full", str(shots / (name + ".png")))

    def scroll(selector):
        ev(f'document.querySelector({json.dumps(selector)}).scrollIntoView({{block:"center"}})')

    def choose(selector, value):
        scroll(selector)
        ab("select", selector, value)
        wait()

    def click(selector):
        scroll(selector)
        ab("click", selector)

    def download_csv(name):
        click("#csv")
        path = downloads / "hotspots.csv"
        deadline = time.monotonic() + 30
        while not path.exists() and time.monotonic() < deadline:
            time.sleep(0.1)
        assert path.is_file(), "CSV download missing"
        path.rename(output / name)

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

    receipt = {"passed": False, "mode": mode, "browser_session": session}
    monitor_thread = threading.Thread(target=monitor)
    monitor_thread.start()
    try:
        if mode == "server":
            routes = [
                ("api/hotspots", 200),
                ("api/hotspots/A02", 200),
                ("api/hotspots/unknown", 404),
                ("hotspot.html", 200),
                ("assets/hotspot.js", 200),
                ("assets/hotspot.css", 200),
            ]
            checks = []
            for route, status in routes:
                p = subprocess.run(
                    [
                        "curl",
                        "--silent",
                        "--show-error",
                        "--max-time",
                        "30",
                        "-o",
                        str(output / "curl-body.tmp"),
                        "-w",
                        "%{http_code}",
                        "http://127.0.0.1:8016/" + route,
                    ],
                    capture_output=True,
                    text=True,
                )
                assert p.returncode == 0 and p.stdout == str(status), (
                    route,
                    p.returncode,
                    p.stdout,
                )
                checks.append(
                    dict(
                        route=route, status=status, bytes=(output / "curl-body.tmp").stat().st_size
                    )
                )
            (output / "curl-body.tmp").unlink()
            (output / "curl.json").write_text(json.dumps(checks, indent=2) + "\n")
        else:
            p = subprocess.run(
                ["curl", "--silent", "--max-time", "2", "http://127.0.0.1:8016"],
                capture_output=True,
            )
            assert p.returncode != 0, "Stop Python server for offline acceptance"
        ab("open", "about:blank")
        ab("set", "viewport", "1600", "1050")
        if mode == "offline":
            ab("set", "offline", "on")
            ab("network", "route", "http://**", "--abort")
            ab("network", "route", "https://**", "--abort")
        start = time.monotonic()
        ab(
            "open",
            "http://127.0.0.1:8016/hotspot.html" if mode == "server" else html.resolve().as_uri(),
        )
        wait()
        receipt["load_wall_seconds"] = time.monotonic() - start
        assert ev('document.querySelectorAll(".hotspot-chart svg").length') == 4
        assert ev('document.querySelector("#quality").textContent') == "unknown"
        ab("snapshot", "-i")
        shot("01-overview")
        scroll("#rank-chart")
        ab("hover", '#rank-chart svg path[fill="#326c89"]')
        shot("02-hover")
        choose("#family", "b2")
        assert ev('document.querySelector("#quality").textContent') == "exact"
        data = load_hotspot_workload(ROOT, "A02")
        run = next(
            r
            for r in data["reports"]
            if r["identity"]["variant"] == "pbuf"
            and r["identity"]["family"] == "b2"
            and r["identity"]["mode"] == 1
            and r["identity"]["repeat"] == 1
        )
        ctx = next(k for k, v in run["context_labels"].items() if v["label"] == "tcp_session")
        choose("#context", ctx)
        scroll("#function-query")
        ab("fill", "#function-query", "tcp_")
        wait()
        expected = {}
        for f in run["facts"]:
            if (
                f["context"] == ctx
                and "tcp_" in run["owners"][f["function_id"]]["function"].lower()
            ):
                expected[f["function_id"]] = expected.get(f["function_id"], 0) + f["memory_cycles"]
        assert expected
        click('.tabulator-col[tabulator-field="value"]')
        shot("03-context-filter")
        scroll("#csv")
        download_csv("filtered.csv")
        with (output / "filtered.csv").open(encoding="utf-8-sig") as stream:
            rows = list(csv.DictReader(stream))
        assert len(rows) == len(expected), (len(rows), len(expected))
        assert {r["id"]: int(r["value"]) for r in rows} == expected
        values = [int(r["value"]) for r in rows]
        assert values in (sorted(values), sorted(values, reverse=True))
        assert all(int(r["run_denominator"]) == run["totals"]["memory_cycles"] for r in rows)
        choose("#top-n", "20")
        scroll("#csv")
        download_csv("top20.csv")
        with (output / "top20.csv").open(encoding="utf-8-sig") as stream:
            top = list(csv.DictReader(stream))
        assert {r["id"]: r["value"] for r in rows} == {r["id"]: r["value"] for r in top}
        click('#functions-table .tabulator-row .tabulator-cell[tabulator-field="name"]')
        assert ev('document.querySelectorAll("#pc-table .tabulator-row").length') > 0
        assert (
            ev('document.querySelectorAll("#pc-table .tabulator-col[tabulator-field]").length') == 3
        ), "PC table must not imply cross-binary pairing"
        click('#pc-table .tabulator-row .tabulator-cell[tabulator-field="pc_hex"]')
        assert "elf_sha256" in ev('document.querySelector("#source-evidence").textContent')
        shot("04-pc-source")
        scroll('#functions-table .tabulator-col[tabulator-field="name"]')
        rect = ev(
            "(()=>{const e=document.querySelector("
            '"#functions-table .tabulator-col[tabulator-field=name]")'
            ",r=e.getBoundingClientRect();return {x:r.right-2,y:r.top+r.height/2,width:r.width}})()"
        )
        ab("mouse", "move", str(int(rect["x"])), str(int(rect["y"])))
        ab("mouse", "down", "left")
        ab("mouse", "move", str(int(rect["x"] + 45)), str(int(rect["y"])))
        ab("mouse", "up", "left")
        width = ev(
            "document.querySelector("
            '"#functions-table .tabulator-col[tabulator-field=name]")'
            ".getBoundingClientRect().width"
        )
        assert width > rect["width"] + 10, (width, rect)
        receipt["column_resize"] = {"before": rect["width"], "after": width}
        before_order = ev(
            "Array.from(document.querySelectorAll("
            '"#functions-table .tabulator-col[tabulator-field]"))'
            '.map(e=>e.getAttribute("tabulator-field"))'
        )
        source = ev(
            "(()=>{const r=document.querySelector("
            '"#functions-table .tabulator-col[tabulator-field=name]").getBoundingClientRect();'
            "return {x:r.left+40,y:r.top+r.height/2}})()"
        )
        ab("mouse", "move", str(int(source["x"])), str(int(source["y"])))
        ab("mouse", "down", "left")
        # Tabulator starts column movement only after its hold timer fires.
        ab("wait", "--fn", 'Boolean(document.querySelector(".tabulator-moving"))')
        target = ev(
            "(()=>{const r=document.querySelector("
            '"#functions-table .tabulator-col[tabulator-field=value]").getBoundingClientRect();'
            "return {x:r.right-15,y:r.top+r.height/2}})()"
        )
        ab("mouse", "move", str(int(target["x"])), str(int(target["y"])))
        ab("mouse", "up", "left")
        after_order = ev(
            "Array.from(document.querySelectorAll("
            '"#functions-table .tabulator-col[tabulator-field]"))'
            '.map(e=>e.getAttribute("tabulator-field"))'
        )
        assert before_order != after_order, "Column reorder did not change DOM order"
        receipt["column_order"] = {"before": before_order, "after": after_order}

        choose("#metric", "misses")
        choose("#cache-level", "l2")
        shot("05-misses")
        scroll("#function-query")
        ab("fill", "#function-query", "no_such_function_0123")
        wait()
        assert "0 個函式" in ev('document.querySelector("#hotspot-status").textContent')
        assert ev('document.querySelectorAll("#pc-table .tabulator-row").length') == 0, (
            "Stale PC rows after empty filter"
        )
        choose("#family", "b1")
        assert ev('document.querySelector("#context").value') == "all"
        if mode == "server":
            choose("#workload", "A08")
            assert "A08" in ev('document.querySelector("#hotspot-status").textContent')
        ab("set", "viewport", "390", "844")
        assert ev("document.documentElement.scrollWidth <= innerWidth")
        shot("06-mobile")
        resources = ev('performance.getEntriesByType("resource").map(r=>r.name)')
        if mode == "offline":
            assert not any(r.startswith(("http:", "https:")) for r in resources)
        errors = json.loads(ab("errors", "--json"))["data"]["errors"]
        assert errors == [], errors
        receipt.update(
            passed=True, filtered_csv_rows=len(rows), resources=resources, errors=errors, svg=4
        )
    except Exception as error:
        receipt["failure"] = str(error)
        if started:
            try:
                receipt["failure_status"] = ev(
                    'document.querySelector("#hotspot-status")?.textContent'
                )
                receipt["failure_errors"] = json.loads(ab("errors", "--json"))["data"]["errors"]
            except Exception as probe_error:
                receipt["failure_probe_error"] = str(probe_error)
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
        time.sleep(0.5)
        remaining = process_table()
        receipt["owned_pids"] = sorted(owned)
        receipt["remaining_browser_pids"] = sorted(pid for pid in owned if pid in remaining)
        receipt["passed"] = bool(
            receipt.get("passed")
            and owned
            and receipt.get("close_exit") == 0
            and not receipt["remaining_browser_pids"]
        )
        (output / "assertions.json").write_text(json.dumps(receipt, indent=2) + "\n")
    assert receipt["passed"], receipt
    return receipt


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode", choices=["server", "offline"], required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--html", type=Path)
    p.add_argument("--browser-executable", type=Path)
    args = p.parse_args()
    print(json.dumps(verify(args.mode, args.output, args.html, args.browser_executable)))
