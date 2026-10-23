import json,subprocess,time
from pathlib import Path
out=Path('artifacts/local/c2a-csv-20261023/http-native-probe-rerun');out.mkdir()
log=[];prefix=['agent-browser','--session','c2a-http-probe'];started=False

def ab(*args):
 global started
 command=prefix
 if not started and args[0]=='open':
  command=prefix+['--download-path',str(out.resolve()),'--executable-path','/Users/swchen.tw/Library/Caches/ms-playwright/chromium_headless_shell-1243/chrome-headless-shell-mac-arm64/chrome-headless-shell','--args','--disable-gpu,--disable-software-rasterizer,--renderer-process-limit=1,--js-flags=--max-old-space-size=64'];started=True
 p=subprocess.run(command+list(args),capture_output=True,text=True,timeout=50);log.append(dict(args=args,exit=p.returncode,stdout=p.stdout,stderr=p.stderr));(out/'commands.json').write_text(json.dumps(log,indent=2));assert p.returncode==0,p.stderr;return p.stdout
try:
 ab('open','http://127.0.0.1:8017/no-such-probe')
 ab('eval',"document.body.innerHTML='<button id=go>CSV</button>';window.delay=0;document.querySelector('#go').onclick=()=>setTimeout(()=>{let a=document.createElement('a');a.href='/api/event-windows/A08-baseline-b1-1-1/events.csv?start=0&end=2';a.download='probe.csv';a.click()},window.delay)")
 for label,delay in [('immediate',0),('delayed',7000)]:
  ab('eval',f'window.delay={delay}')
  ab('click','#go');time.sleep(delay/1000+3)
  files=[f for f in out.glob('*.csv') if f.name not in {'immediate.csv','delayed.csv'}]
  if files:files[0].rename(out/(label+'.csv'))
  print(label,[f.name for f in out.glob('*.csv')],flush=True)
finally:
 if started:ab('close')
