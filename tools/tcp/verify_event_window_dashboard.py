"""Serial curl/agent-browser acceptance with session-owned RSS and guaranteed close."""

import argparse
import csv
import gzip
import hashlib
import io
import json
import shutil
import subprocess
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "artifacts/verification/event-window/formal"
RSS_LIMIT_MIB = 640  # User-approved revision, 2026-10-14.


def process_table():
    rows = {}
    for line in subprocess.check_output(
        ["ps", "-axo", "pid=,ppid=,rss=,comm="], text=True
    ).splitlines():
        fields = line.strip().split(None, 3)
        if len(fields) == 4:
            rows[int(fields[0])] = (int(fields[1]), int(fields[2]), Path(fields[3]).name)
    return rows


def oracle(run_id, start, end, context="", search=""):
    manifest = json.loads((BASE / run_id / "manifest.json").read_text())
    result = {
        "events": 0,
        "instructions": 0,
        "memory_cycles": 0,
        "l1i.misses": 0,
        "l1d.misses": 0,
        "l2.misses": 0,
    }
    for desc in manifest["chunks"]:
        if int(desc["end"]) <= start or int(desc["start"]) >= end:
            continue
        with gzip.open(BASE / run_id / (desc["id"] + ".json.gz"), "rt") as f:
            data = json.load(f)
        for row in data["rows"]:
            if not start <= int(row[0]) < end:
                continue
            ctx = manifest["contexts"][int(row[5])]
            name = manifest["owners"][int(row[6])].get("function") or "unresolved"
            if context and ctx != context or search and search.lower() not in name.lower():
                continue
            result["events"] += 1
            result["instructions"] += int(row[4] == "I")
            result["memory_cycles"] += sum(map(int, row[7:12]))
            for key, index in [("l1i.misses", 13), ("l1d.misses", 18), ("l2.misses", 23)]:
                result[key] += int(row[index])
    return result


def verify(
    mode,
    output,
    html=None,
    executable=None,
    capacity_only=False,
    force_failure=False,
    profile_csv=False,
):
    output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(__file__, output / "harness.py")
    shots = output / "screenshots"
    shots.mkdir()
    session = "c2a-verify"
    commands = []
    samples = []
    tracked = set()
    done = threading.Event()
    stage = "launch"
    receipt = {
        "passed": False,
        "scope": "capacity-only" if capacity_only else "full-interactions",
        "rss_limit_mib": RSS_LIMIT_MIB,
        "mode": mode,
        "diagnostic_csv": profile_csv,
        "sample_interval_seconds": 0.2,
        "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "offline_html_sha256": hashlib.sha256(html.read_bytes()).hexdigest() if html else None,
        "browser_executable": str(executable) if executable else "agent-browser default",
    }
    downloads = output / "downloads"
    downloads.mkdir()
    prefix = ["agent-browser", "--session", session, "--download-path", str(downloads.resolve())]
    if executable:
        prefix += [
            "--executable-path",
            str(executable),
            "--args",
            "--disable-gpu,--disable-software-rasterizer,--renderer-process-limit=1,"
            "--js-flags=--max-old-space-size=64",
        ]

    browser_started = False

    def ab(*args):
        nonlocal browser_started
        command = ["agent-browser", "--session", session]
        if not browser_started and args[0] == "open":
            command = prefix
            browser_started = True
        p = subprocess.run(command + list(args), capture_output=True, text=True, timeout=50)
        commands.append(dict(args=args, exit=p.returncode, stdout=p.stdout, stderr=p.stderr))
        (output / "commands.json").write_text(json.dumps(commands, indent=2) + "\n")
        if p.returncode:
            raise RuntimeError(p.stderr or p.stdout)
        return p.stdout

    def ev(code):
        return json.loads(ab("eval", "--json", code))["data"]["result"]

    def wait():
        ab("wait", "--fn", "window.eventWindowReady === true")

    def scroll(selector):
        ev(f'document.querySelector({json.dumps(selector)}).scrollIntoView({{block:"center"}})')

    def click(selector):
        scroll(selector)
        ab("click", selector)

    def fill(selector, value):
        scroll(selector)
        ab("fill", selector, str(value))

    def choose(selector, value):
        scroll(selector)
        ab("select", selector, value)
        wait()

    def shot(name):
        nonlocal stage
        stage = "screenshot:" + name
        ab("screenshot", str(shots / (name + ".png")))
        stage = "interaction"

    def monitor():
        while not done.is_set():
            rows = process_table()
            try:
                daemon = int(
                    (Path.home() / ".agent-browser" / f"{session}.pid").read_text().strip()
                )
            except (ValueError, OSError):
                daemon = -1
            descendants = {daemon}
            for _ in range(10):
                descendants.update(pid for pid, r in rows.items() if r[0] in descendants)
            tracked.update(
                pid
                for pid in descendants
                if pid in rows
                and ("chrome" in rows[pid][2].lower() or "chromium" in rows[pid][2].lower())
            )
            samples.append(
                dict(
                    seconds=time.monotonic(),
                    wall_ms=time.time() * 1000,
                    stage=stage,
                    rss_kib=sum(rows[p][1] for p in tracked if p in rows),
                    pids=sorted(p for p in tracked if p in rows),
                )
            )
            done.wait(0.2)

    monitor_thread = threading.Thread(target=monitor)
    monitor_thread.start()
    try:
        if mode == "server":
            curls = []
            for route, want in [
                ("api/event-windows", 200),
                ("api/event-windows/A02-baseline-b1-1-1", 200),
                ("api/event-windows/A02-baseline-b1-1-1/chunks/000000", 200),
                ("api/event-windows/unknown", 404),
                ("event-window.html", 200),
                ("assets/event-window.js", 200),
                ("assets/event-window.css", 200),
            ]:
                target = output / "curl.tmp"
                p = subprocess.run(
                    [
                        "curl",
                        "--silent",
                        "--show-error",
                        "--max-time",
                        "30",
                        "-o",
                        str(target),
                        "-w",
                        "%{http_code}",
                        "http://127.0.0.1:8017/" + route,
                    ],
                    capture_output=True,
                    text=True,
                )
                assert p.returncode == 0 and p.stdout == str(want), (route, p.returncode, p.stdout)
                body = target.read_bytes()
                curls.append(
                    dict(
                        route=route,
                        status=want,
                        bytes=len(body),
                        sha256=hashlib.sha256(body).hexdigest(),
                    )
                )
            target.unlink()
            (output / "curl.json").write_text(json.dumps(curls, indent=2) + "\n")
            url = "http://127.0.0.1:8017/event-window.html"
        else:
            assert html and html.is_file()
            p = subprocess.run(
                ["curl", "--silent", "--max-time", "2", "http://127.0.0.1:8017/"],
                capture_output=True,
            )
            assert p.returncode != 0, "Python server must be stopped for offline acceptance"
            url = html.resolve().as_uri()
        start = time.monotonic()
        ab("open", "about:blank")
        if mode == "offline":
            ab("set", "offline", "on")
            ab("network", "route", "http://**", "--abort")
            ab("network", "route", "https://**", "--abort")
        ab("set", "viewport", "1600", "1050")
        ab("open", url)
        wait()
        receipt["ready_seconds"] = time.monotonic() - start
        receipt["browser"] = ev("navigator.userAgent")
        receipt["heap_initial"] = ev("performance.memory?.usedJSHeapSize ?? null")
        r = ev("window.eventWindowResult")
        assert r["event_count"] == "430324"
        assert r["totals"]["memory_cycles"] == "1088094"
        assert ev('document.querySelectorAll("svg").length') == 4
        shot("01-overview")
        stage = "full-run-filter"
        start = time.monotonic()
        click("#apply")
        wait()
        receipt["filter_seconds"] = time.monotonic() - start
        receipt["heap_after"] = ev("performance.memory?.usedJSHeapSize ?? null")
        if force_failure:
            raise AssertionError("Intentional failure verifies finally-close")
        if not capacity_only:
            stage = "hover-and-zoom"
            scroll("#event-chart")
            point = ev("""(()=>{const bars=[...document.querySelectorAll('#event-chart svg path')]
                .filter(e=>e.getAttribute('fill')==='#336e86');
                const r=bars[20].getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+2}})()""")
            ab("mouse", "move", str(int(point["x"])), str(int(point["y"])))
            ab(
                "wait",
                "--fn",
                "document.querySelector('#event-chart').textContent.includes('selected rows')",
            )
            shot("07-hover")
            psf_before = ev("document.querySelector('#psf-table').textContent")
            rect = ev("""(()=>{
                const chart=document.querySelector('#event-chart').getBoundingClientRect();
                const handles=[...document.querySelectorAll('#event-chart svg path')]
                    .map(e=>e.getBoundingClientRect())
                    .filter(r=>r.width>2&&r.width<20&&r.height>10&&r.y>chart.bottom-65)
                    .sort((a,b)=>a.x-b.x);
                if(!handles.length)throw Error('No slider handle');
                const r=handles[0];return {x:r.x+r.width/2,y:r.y+r.height/2};})()""")
            left, y = int(rect["x"]), int(rect["y"])
            ab("mouse", "move", str(left), str(y))
            ab("mouse", "down", "left")
            ab("mouse", "move", str(left + 180), str(y))
            ab("mouse", "up", "left")
            wait()
            zoom = ev("window.eventWindowResult")
            assert int(zoom["start"]) > 0, "Slider drag did not change interval"
            zoom_expected = oracle(zoom["run_id"], int(zoom["start"]), int(zoom["end"]))
            assert int(zoom["totals"]["memory_cycles"]) == zoom_expected["memory_cycles"]
            assert ev("document.querySelector('#psf-table').textContent") == psf_before
            receipt["zoom"] = {"start": zoom["start"], "end": zoom["end"], "oracle": zoom_expected}
            shot("08-zoom")
            click("#reset")
            wait()
            if profile_csv:
                probe = ROOT / "tools/tcp/profile_csv_browser.js"
                shutil.copyfile(probe, output / probe.name)
                receipt["csv_probe_sha256"] = hashlib.sha256(probe.read_bytes()).hexdigest()
                ev(probe.read_text())
            stage = "full-csv-export"
            scroll("#events-csv")
            csv_path = output / "full-events.csv"
            click("#events-csv")
            wait()
            downloaded = downloads / "A02-baseline-b1-1-1-events.csv"
            deadline = time.monotonic() + 20
            while not downloaded.exists() and time.monotonic() < deadline:
                time.sleep(0.1)
            assert downloaded.is_file(), "Full CSV download missing"
            if profile_csv:
                diagnostics = ev("window.csvDiagnostics")
                (output / "csv-diagnostics.json").write_text(
                    json.dumps(diagnostics, indent=2) + "\n"
                )
            stage = "full-csv-oracle"
            downloaded.rename(csv_path)
            count, cycles = 0, 0
            with csv_path.open(newline="") as stream:
                for row in csv.DictReader(stream):
                    assert int(row["index"]) == count
                    count += 1
                    cycles += sum(
                        int(row[k]) for k in ["l1i", "l1d", "l2", "ram_read", "ram_write"]
                    )
            assert count == 430324 and cycles == 1088094
            receipt["full_csv"] = {
                "rows": count,
                "memory_cycles": cycles,
                "bytes": csv_path.stat().st_size,
            }
            with (
                csv_path.open("rb") as source,
                gzip.open(csv_path.with_suffix(".csv.gz"), "wb") as target,
            ):
                shutil.copyfileobj(source, target)
            csv_path.unlink()
            stage = "export-cancel"
            download_names = sorted(p.name for p in downloads.iterdir())
            click("#events-csv")
            ab(
                "wait",
                "--fn",
                """(()=>{
                const p=document.querySelector('#progress').value;
                if(p>0&&p<1&&!window.eventWindowReady){
                    window.cancelProgress=p;document.querySelector('#cancel').click();return true;
                }return false;
            })()""",
            )
            assert not ev("window.eventWindowReady")
            assert ev("window.eventWindowResult") is None
            click("#apply")
            wait()
            assert sorted(p.name for p in downloads.iterdir()) == download_names
            receipt["export_cancel_retry"] = True
            receipt["cancel_progress"] = ev("window.cancelProgress")
            fill("#start", 1023)
            fill("#end", 2061)
            click("#apply")
            wait()
            r = ev("window.eventWindowResult")
            expected = oracle(r["run_id"], 1023, 2061)
            assert int(r["event_count"]) == expected["events"]
            assert int(r["totals"]["memory_cycles"]) == expected["memory_cycles"]
            assert int(r["totals"]["instructions"]) == expected["instructions"]
            shot("02-interval")
            ev(
                "window.savedCsv=[];window.originalObjectURL=URL.createObjectURL;"
                'URL.createObjectURL=function(b){if(b.type.startsWith("text/csv"))'
                "b.text().then(s=>window.savedCsv.push(s));return window.originalObjectURL(b)}"
            )
            click("#events-csv")
            wait()
            ab("wait", "--fn", "window.savedCsv.length===1")
            csv_text = ev("window.savedCsv[0]")
            (output / "events.csv").write_text(csv_text)
            rows = list(csv.DictReader(io.StringIO(csv_text)))
            assert len(rows) == expected["events"]
            assert [int(row["index"]) for row in rows] == list(range(1023, 2061))
            assert (
                sum(
                    sum(int(row[k]) for k in ["l1i", "l1d", "l2", "ram_read", "ram_write"])
                    for row in rows
                )
                == expected["memory_cycles"]
            )
            click("#next-page")
            wait()
            assert ev("window.eventWindowResult.event_page[0].index") == "1223"
            click("#event-table .tabulator-row")
            assert "elf" in ev('document.querySelector("#source").textContent')
            shot("03-source")
            scroll("#function-table")
            click("#function-table .tabulator-col[tabulator-field=value]")
            click("#functions-csv")
            ab("wait", "--fn", "window.savedCsv.length===2")
            text = ev("window.savedCsv[1]")
            (output / "functions.csv").write_text(text)
            values = [int(row["value"]) for row in csv.DictReader(io.StringIO(text))]
            assert values == sorted(values) or values == sorted(values, reverse=True)
            rect = ev(
                "(()=>{const e=document.querySelector("
                '"#function-table .tabulator-col[tabulator-field=name]")'
                ",r=e.getBoundingClientRect();return "
                "{x:r.right-2,y:r.top+r.height/2,width:r.width}})()"
            )
            ab("mouse", "move", str(int(rect["x"])), str(int(rect["y"])))
            ab("mouse", "down", "left")
            ab("mouse", "move", str(int(rect["x"] + 45)), str(int(rect["y"])))
            ab("mouse", "up", "left")
            width = ev(
                "document.querySelector("
                '"#function-table .tabulator-col[tabulator-field=name]")'
                ".getBoundingClientRect().width"
            )
            assert width > rect["width"] + 10, (width, rect)
            receipt["column_resize"] = {"before": rect["width"], "after": width}
            before_order = ev(
                "Array.from(document.querySelectorAll("
                '"#function-table .tabulator-col[tabulator-field]"))'
                '.map(e=>e.getAttribute("tabulator-field"))'
            )
            source = ev(
                "(()=>{const r=document.querySelector("
                '"#function-table .tabulator-col[tabulator-field=name]").getBoundingClientRect();'
                "return {x:r.left+40,y:r.top+r.height/2}})()"
            )
            ab("mouse", "move", str(int(source["x"])), str(int(source["y"])))
            ab("mouse", "down", "left")
            # Tabulator starts column movement only after its hold timer fires.
            ab("wait", "--fn", 'Boolean(document.querySelector(".tabulator-moving"))')
            target = ev(
                "(()=>{const r=document.querySelector("
                '"#function-table .tabulator-col[tabulator-field=value]").getBoundingClientRect();'
                "return {x:r.right-15,y:r.top+r.height/2}})()"
            )
            ab("mouse", "move", str(int(target["x"])), str(int(target["y"])))
            ab("mouse", "up", "left")
            after_order = ev(
                "Array.from(document.querySelectorAll("
                '"#function-table .tabulator-col[tabulator-field]"))'
                '.map(e=>e.getAttribute("tabulator-field"))'
            )
            assert before_order != after_order, "Column reorder did not change DOM order"
            receipt["column_order"] = {"before": before_order, "after": after_order}

            choose("#run", "A02-pbuf-b2-1-1")
            choose("#context", "task:2148022416") if "task:2148022416" in ev(
                'Array.from(document.querySelector("#context").options).map(o=>o.value)'
            ) else None
            available = ev('Array.from(document.querySelector("#context").options).map(o=>o.value)')
            task = next(c for c in available if c.startswith("task:"))
            choose("#context", task)
            fill("#function", "tcp_")
            click("#apply")
            wait()
            r = ev("window.eventWindowResult")
            expected = oracle(r["run_id"], int(r["start"]), int(r["end"]), task, "tcp_")
            assert int(r["totals"]["memory_cycles"]) == expected["memory_cycles"]
            shot("04-context")
            choose("#metric", "l2.misses")
            r = ev("window.eventWindowResult")
            assert int(r["totals"]["cache"]["l2"]["misses"]) == expected["l2.misses"]
            shot("05-misses")
            fill("#function", "does_not_exist_09")
            click("#apply")
            wait()
            assert ev("window.eventWindowResult.event_count") == "0"
            assert ev('document.querySelectorAll("#event-table .tabulator-row").length') == 0
            click("#cancel")
            assert not ev("window.eventWindowReady")
            click("#apply")
            wait()
            ab("set", "viewport", "390", "844")
            assert ev("document.documentElement.scrollWidth <= innerWidth")
            shot("06-mobile")
            receipt["interval_oracle"] = expected
            receipt["event_csv_rows"] = len(rows)
        resources = ev('performance.getEntriesByType("resource").map(r=>r.name)')
        errors = json.loads(ab("errors", "--json"))["data"]["errors"]
        assert not errors, errors
        if mode == "offline":
            assert not any(r.startswith(("http:", "https:")) for r in resources)
        receipt.update(interactions_passed=True, resources=resources, errors=errors)
    except Exception as error:
        receipt["failure"] = str(error)
        try:
            receipt["failure_status"] = ev('document.querySelector("#status")?.textContent')
        except Exception:
            pass
        raise
    finally:
        try:
            if browser_started:
                ab("close")
            receipt["browser_started"] = browser_started
            receipt["close_exit"] = 0
        except Exception as error:
            receipt.update(close_exit=1, close_error=str(error))
        done.set()
        monitor_thread.join()
        time.sleep(0.5)
        remaining = process_table()
        receipt["remaining_browser_pids"] = [pid for pid in tracked if pid in remaining]
        receipt["sampled_peak_rss_kib"] = max((s["rss_kib"] for s in samples), default=0)
        receipt["capacity_passed"] = bool(
            receipt.get("ready_seconds", 999) <= 25
            and receipt.get("filter_seconds", 999) <= 5
            and receipt["sampled_peak_rss_kib"] > 0
            and receipt["sampled_peak_rss_kib"] <= RSS_LIMIT_MIB * 1024
            and all(
                receipt.get(k) is not None and receipt[k] <= 128 * 1024 * 1024
                for k in ["heap_initial", "heap_after"]
            )
        )
        receipt["passed"] = (
            receipt.get("interactions_passed", False)
            and receipt["capacity_passed"]
            and receipt.get("close_exit") == 0
            and not receipt["remaining_browser_pids"]
        )
        (output / "rss-samples.json").write_text(json.dumps(samples, indent=2) + "\n")
        (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    assert receipt["passed"], receipt
    return receipt


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode", choices=["server", "offline"], required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--html", type=Path)
    p.add_argument("--browser-executable", type=Path)
    p.add_argument("--capacity-only", action="store_true")
    p.add_argument("--force-failure", action="store_true")
    p.add_argument("--profile-csv", action="store_true")
    a = p.parse_args()
    print(
        json.dumps(
            verify(
                a.mode,
                a.output,
                a.html,
                a.browser_executable,
                a.capacity_only,
                a.force_failure,
                a.profile_csv,
            )
        )
    )
