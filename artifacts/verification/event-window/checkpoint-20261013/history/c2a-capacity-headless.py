import subprocess,json,time,threading,sys
from pathlib import Path
mode=sys.argv[1];out=Path('artifacts/local/c2a-capacity-headless-'+mode);out.mkdir(exist_ok=False)
session='c2a-capacity';log=[];samples=[];stopping=False

def processes():
 text=subprocess.check_output(['ps','-axo','pid=,ppid=,rss=,comm='],text=True)
 rows={}
 for line in text.splitlines():
  p=line.strip().split(None,3)
  if len(p)==4: rows[int(p[0])]={'parent':int(p[1]),'rss_kib':int(p[2]),'name':Path(p[3]).name}
 return rows
before=processes(); tracked=set()
def sample():
 while not stopping:
  rows=processes()
  pidfile=Path.home()/'.agent-browser'/f'{session}.pid'
  try: daemon=int(pidfile.read_text().strip())
  except (ValueError,OSError): daemon=-1
  descendants={daemon}
  for _ in range(10):
   descendants.update(pid for pid,row in rows.items() if row['parent'] in descendants)
  tracked.update(pid for pid in descendants if pid in rows and ('chrome' in rows[pid]['name'].lower() or 'chromium' in rows[pid]['name'].lower()))
  samples.append({'seconds':time.monotonic(),'rss_kib':sum(rows[p]['rss_kib'] for p in tracked if p in rows),'pids':sorted(p for p in tracked if p in rows)})
  time.sleep(.2)
def ab(*args):
 p=subprocess.run(['agent-browser','--session',session,'--executable-path','/Users/swchen.tw/Library/Caches/ms-playwright/chromium_headless_shell-1243/chrome-headless-shell-mac-arm64/chrome-headless-shell',*args],capture_output=True,text=True,timeout=45)
 log.append({'args':args,'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr});(out/'commands.json').write_text(json.dumps(log,indent=2));return p
def ev(code):
 p=ab('eval','--json',code);return json.loads(p.stdout)['data']['result']
r={'mode':mode,'passed':False};thread=threading.Thread(target=sample);thread.start()
try:
 target='http://127.0.0.1:8017/event-window.html' if mode=='server' else (Path.cwd()/'artifacts/local/c2a-pilot-A02-dedup.html').as_uri()
 started=time.monotonic();ab('open',target);wait=ab('wait','--fn','window.eventWindowReady === true');r['ready_seconds']=time.monotonic()-started;r['ready_exit']=wait.returncode
 r['initial']=ev('({status:document.querySelector("#status").textContent,heap:performance.memory?.usedJSHeapSize,events:window.eventWindowResult?.event_count})')
 start=time.monotonic();ab('click','#apply');wait=ab('wait','--fn','window.eventWindowReady === true');r['filter_seconds']=time.monotonic()-start;r['filter_exit']=wait.returncode
 r['after']=ev('({status:document.querySelector("#status").textContent,heap:performance.memory?.usedJSHeapSize,events:window.eventWindowResult?.event_count})')
 ab('screenshot','--full',str(out/'screen.png'))
finally:
 closed=ab('close');r['close_exit']=closed.returncode;stopping=True;thread.join();time.sleep(.5);rows=processes();r['remaining_browser_pids']=[p for p in tracked if p in rows];r['sampled_peak_rss_kib']=max(s['rss_kib'] for s in samples);r['sample_interval_seconds']=.2;r['samples']=samples
 (out/'receipt.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items() if k!='samples'}))
