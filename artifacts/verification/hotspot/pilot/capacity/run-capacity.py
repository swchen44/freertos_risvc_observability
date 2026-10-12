import subprocess,json,time,platform
from pathlib import Path
out=Path('artifacts/local/c1-pilot-capacity');out.mkdir(exist_ok=True)
def ab(*args):
 p=subprocess.run(['agent-browser','--session','c1-pilot-capacity',*args],capture_output=True,text=True,timeout=60)
 if p.returncode:raise RuntimeError(p.stderr)
 return p.stdout
rows=[]
try:
 for i in range(3):
  ab('open','about:blank');ab('set','offline','on');ab('network','route','http://*','--abort');ab('network','route','https://*','--abort')
  start=time.monotonic();ab('open',(Path.cwd()/'artifacts/local/c1-pilot-A02.html').as_uri());ab('wait','--fn','window.hotspotReady === true')
  load=time.monotonic()-start
  ab('select','#family','b2');ab('wait','--fn','window.hotspotReady === true')
  data=json.loads(ab('eval','--json','({renderMs:window.hotspotLastRenderMs, resources:performance.getEntriesByType("resource").map(r=>r.name),svg:document.querySelectorAll(".hotspot-chart svg").length})'))['data']['result']
  assert data['svg']==4 and not any(s.startswith(('http:','https:')) for s in data['resources'])
  assert json.loads(ab('errors','--json'))['data']['errors']==[]
  rows.append(dict(iteration=i+1,load_wall_seconds=load,**data));ab('close')
finally:
 ab('close')
(out/'receipt.json').write_text(json.dumps(dict(passed=True,platform=platform.platform(),runs=rows),indent=2)+'\n')
print(rows)
