import json,os,signal,subprocess,time,shutil,sys
from pathlib import Path
root=Path.cwd();out=root/'artifacts/local/c2a-csv-20261023';driver=out/'fast-driver';driver.mkdir()
exe='/Users/swchen.tw/Library/Caches/ms-playwright/chromium_headless_shell-1243/chrome-headless-shell-mac-arm64/chrome-headless-shell'
steps=[]

def save():
 (driver/'status.json').write_text(json.dumps(steps,indent=2)+'\n')

def run(name,command,receipt):
 target=out/name
 if target.exists():raise RuntimeError('Existing case requires manual audit: '+name)
 entry=dict(name=name,state='running',command=command,host_load_before=os.getloadavg(),started=time.time());steps.append(entry);save()
 with (driver/(name+'.log')).open('w') as f:
  p=subprocess.run(command,stdout=f,stderr=subprocess.STDOUT)
 d=json.loads((target/receipt).read_text())
 entry.update(state='finished',exit=p.returncode,passed=d.get('passed'),host_load_after=os.getloadavg(),finished=time.time());save()
 if d.get('close_exit')!=0 or d.get('remaining_browser_pids'):
  raise RuntimeError('Browser closure failed '+name)
 if p.returncode and not d.get('interactions_passed'):
  raise RuntimeError('Functional failure '+name)
 print(name,entry['passed'],flush=True)

def dashboard(name,mode,workload,capacity=False):
 cmd=['.venv/bin/python','tools/tcp/verify_event_window_dashboard.py','--mode',mode,'--workload',workload,'--output',str(out/name),'--browser-executable',exe]
 if mode=='offline':cmd+=['--html',str(root/'artifacts/offline/event-window'/f'{workload}.html')]
 if capacity:cmd+=['--capacity-only']
 run(name,cmd,'receipt.json')

def stop_port(port):
 r=subprocess.run(['lsof','-t',f'-iTCP:{port}','-sTCP:LISTEN'],capture_output=True,text=True)
 for text in r.stdout.split():
  pid=int(text);cmd=subprocess.check_output(['ps','-p',text,'-o','command='],text=True)
  if f'-m psf_lab serve --port {port}' not in cmd:raise RuntimeError('Unexpected listener')
  os.kill(pid,signal.SIGINT)
 for _ in range(50):
  r=subprocess.run(['curl','--silent','--max-time','1',f'http://127.0.0.1:{port}/'],capture_output=True)
  if r.returncode:return
  time.sleep(.1)
 raise RuntimeError('Server still reachable')

dashboard('fast-A08-server','server','A08')
dashboard('fast-A02-server','server','A02')
run('fast-lifecycle',['.venv/bin/python','tools/tcp/verify_event_window_lifecycle.py','--output',str(out/'fast-lifecycle'),'--browser-executable',exe],'receipt.json')
# C1 Web uses its original heap policy and the same current server.
log=(driver/'c1-current-server.log').open('w')
server=subprocess.Popen(['.venv/bin/python','-m','psf_lab','serve','--port','8016'],stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,PYTHONPATH='src'))
try:
 for _ in range(100):
  r=subprocess.run(['curl','--silent','--max-time','1','http://127.0.0.1:8016/api/hotspots'],capture_output=True)
  if r.returncode==0:break
  time.sleep(.1)
 run('fast-c1-server',['.venv/bin/python','tools/tcp/verify_hotspot_dashboard.py','--mode','server','--output',str(out/'fast-c1-server'),'--browser-executable',exe],'assertions.json')
finally:
 server.send_signal(signal.SIGINT);server.wait(timeout=20);log.close()
stop_port(8017)
dashboard('fast-A08-offline','offline','A08')
dashboard('fast-A02-offline','offline','A02')
for i in [1,3,4,5,6,7]:dashboard(f'fast-A{i:02}-offline-capacity','offline',f'A{i:02}',True)
name='fast-force-failure';target=out/name
command=['.venv/bin/python','tools/tcp/verify_event_window_dashboard.py','--mode','offline','--workload','A01','--html',str(root/'artifacts/offline/event-window/A01.html'),'--capacity-only','--force-failure','--output',str(target),'--browser-executable',exe]
with (driver/(name+'.log')).open('w') as f:p=subprocess.run(command,stdout=f,stderr=subprocess.STDOUT)
d=json.loads((target/'receipt.json').read_text())
assert p.returncode!=0 and d.get('failure')=='Intentional failure verifies finally-close'
assert d['close_exit']==0 and not d['remaining_browser_pids'] and d['browser_started']
steps.append(dict(name=name,state='finished',passed=True,expected_failure=True));save()
run('fast-capabilities',['.venv/bin/python','tools/tcp/verify_event_window_capabilities.py','--output',str(out/'fast-capabilities'),'--browser-executable',exe],'receipt.json')
# Preserve and restore tracked browser artifacts around the existing single-worker suite.
pw=out/'playwright-fast';pw.mkdir()
files=[root/'artifacts/browser'/name for name in ['results.json','capacity.json']]
backups={f:f.read_bytes() for f in files if f.exists()}
try:
 with (pw/'run.log').open('w') as f:p=subprocess.run(['npm','--prefix','web','run','test:e2e','--','--workers=1'],stdout=f,stderr=subprocess.STDOUT)
 for f in files:
  if f.exists():shutil.copyfile(f,pw/f.name)
 (pw/'receipt.json').write_text(json.dumps(dict(passed=p.returncode==0,exit=p.returncode))+'\n')
finally:
 for f,b in backups.items():f.write_bytes(b)
print('driver finished',flush=True)
