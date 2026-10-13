"""Browser regressions with injected delayed requests; preserves original data files."""

import argparse
import json
import subprocess
import threading
import time
from pathlib import Path

from verify_event_window_dashboard import process_table


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--browser-executable", type=Path, required=True)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    downloads = a.output / "downloads"
    downloads.mkdir()
    session = "c2a-lifecycle"
    prefix = ["agent-browser", "--session", session]
    commands, receipt, owned = [], {"passed": False, "injected_fixture": True}, set()

    def ab(*args):
        r = subprocess.run(prefix + list(args), capture_output=True, text=True, timeout=50)
        commands.append(dict(args=args, code=r.returncode, stdout=r.stdout, stderr=r.stderr))
        (a.output / "commands.json").write_text(json.dumps(commands, indent=2) + "\n")
        if r.returncode:
            raise RuntimeError(r.stderr)
        return r.stdout

    def ev(code):
        return json.loads(ab("eval", "--json", code))["data"]["result"]

    def shot(name):
        ab("screenshot", str(a.output / (name + ".png")))

    done = threading.Event()

    def monitor():
        while not done.is_set():
            rows = process_table()
            try:
                daemon = int((Path.home() / ".agent-browser" / f"{session}.pid").read_text())
            except (ValueError, OSError):
                daemon = -1
            descendants = {daemon}
            for _ in range(10):
                descendants.update(pid for pid, r in rows.items() if r[0] in descendants)
            owned.update(
                pid
                for pid in descendants
                if pid in rows
                and ("chrome" in rows[pid][2].lower() or "chromium" in rows[pid][2].lower())
            )
            done.wait(0.2)

    thread = threading.Thread(target=monitor)
    thread.start()
    try:
        ab(
            "--executable-path",
            str(a.browser_executable),
            "--args",
            "--disable-gpu,--disable-software-rasterizer,--renderer-process-limit=1,"
            "--js-flags=--max-old-space-size=64",
            "--download-path",
            str(downloads.resolve()),
            "open",
            "http://127.0.0.1:8017/event-window.html",
        )
        ab("set", "viewport", "1600", "1050")
        ab("wait", "--fn", "window.eventWindowReady===true")
        ev("""window.realFetch=fetch;window.delayOne=true;
            window.fetch=(url,...args)=>{
              if(window.delayOne && String(url).endsWith('/A02-pbuf-b2-1-1')){
                window.delayOne=false;window.delayedStarted=true;
                return new Promise((resolve,reject)=>window.rejectOld=reject);
              }
              return window.realFetch(url,...args);
            };""")
        ab("select", "#run", "A02-pbuf-b2-1-1")
        ab("wait", "--fn", "window.delayedStarted===true")
        ab("click", "#cancel")
        assert ev("window.eventWindowResult") is None
        assert ev("document.querySelector('#evidence').textContent") == ""
        ev("window.rejectOld(Error('injected stale failure'))")
        assert ev("document.querySelector('#status').textContent") == "已取消；可重新分析。"
        shot("01-cancel-stale-error")
        ev("""window.fetch=(url,...args)=>{
            if(String(url).endsWith('/A02-pbuf-b2-1-1')){
                return new Promise((resolve,reject)=>window.realFetch(url,...args).then(r=>{
                    window.releaseB=()=>resolve(r);
                },reject));
            }return window.realFetch(url,...args);
        };""")
        ab("select", "#run", "A02-pbuf-b2-1-1")
        ab("wait", "--fn", "typeof window.releaseB==='function'")
        ab("select", "#run", "A02-baseline-b1-1-1")
        ab("wait", "--fn", "window.eventWindowReady===true")
        assert ev("window.eventWindowResult.run_id") == "A02-baseline-b1-1-1"
        assert (
            ev("""(async()=>{window.releaseB();
            await new Promise(r=>setTimeout(r,100));
            return window.eventWindowResult.run_id})()""")
            == "A02-baseline-b1-1-1"
        )
        assert ev("window.eventWindowResult.totals.memory_cycles") == "1088094"
        shot("02-rapid-run-switch")
        before_downloads = sorted(p.name for p in downloads.iterdir())
        ev("document.querySelector('#events-csv').scrollIntoView({block:'center'})")
        ab("click", "#events-csv")
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
        receipt["cancel_progress"] = ev("window.cancelProgress")
        assert not ev("window.eventWindowReady")
        assert ev("window.eventWindowResult") is None
        shot("04-export-cancelled-inflight")
        ev("document.querySelector('#apply').scrollIntoView({block:'center'})")
        ab("click", "#apply")
        ab("wait", "--fn", "window.eventWindowReady===true")
        assert sorted(p.name for p in downloads.iterdir()) == before_downloads
        receipt["inflight_export_cancel_no_download"] = True
        ev("""window.fetch=async(url,...args)=>{
            const response=await window.realFetch(url,...args);
            if(String(url).endsWith('/A02-pbuf-b2-1-1')){
                const m=await response.json();
                m.psf={clock:{origin_ticks:'4294967290'},
                  quality:{fixture:true,sequence_gaps:[{expected:8,actual:10}]},events:[
                    {sequence:7,ticks:'0',kind:'task',timestamp_raw:'4294967290'},
                    {sequence:10,ticks:'0',kind:'irq',timestamp_raw:'4294967290'},
                    {sequence:11,ticks:null,kind:'unknown',timestamp_raw:null},
                    {sequence:12,ticks:'12',kind:'task',timestamp_raw:'6'}]};
                return new Response(JSON.stringify(m));
            }return response;
        };""")
        ab("select", "#run", "A02-pbuf-b2-1-1")
        ab("wait", "--fn", "window.eventWindowReady===true")
        rows = ev("""[...document.querySelectorAll(
          '#psf-table .tabulator-row [tabulator-field=sequence]')].map(e=>e.textContent)""")
        assert rows == ["7", "10", "11", "12"], rows
        quality = ev("document.querySelector('#psf-quality').textContent")
        assert "sequence_gaps" in quality and "4294967290" in quality
        ev("document.querySelector('#psf-chart').scrollIntoView({block:'center'})")
        shot("03-psf-gap-fixture")
        receipt.update(
            cancelled_manifest=True,
            stale_error_ignored=True,
            quick_run_switch=True,
            psf_original_order=rows,
            psf_quality=quality,
            interactions_passed=True,
        )
    except Exception as error:
        receipt["failure"] = str(error)
        raise
    finally:
        try:
            ab("close")
            receipt["close_exit"] = 0
        except Exception as error:
            receipt.update(close_exit=1, close_error=str(error))
        done.set()
        thread.join()
        time.sleep(0.5)
        remaining = process_table()
        receipt["owned_browser_pids"] = sorted(owned)
        receipt["remaining_browser_pids"] = sorted(pid for pid in owned if pid in remaining)
        receipt["passed"] = bool(
            receipt.get("interactions_passed")
            and receipt.get("close_exit") == 0
            and owned
            and not receipt["remaining_browser_pids"]
        )
        (a.output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    assert receipt["passed"]


if __name__ == "__main__":
    main()
