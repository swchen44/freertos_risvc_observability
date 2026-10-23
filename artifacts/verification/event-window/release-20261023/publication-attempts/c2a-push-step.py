import json,os,pathlib,re,subprocess,sys,time
commit=sys.argv[1];receipt=pathlib.Path(sys.argv[2]);branch='poc-history'
assert re.fullmatch('[0-9a-f]{7,40}',commit)
local=subprocess.check_output(['git','rev-parse',commit],text=True).strip()
r=dict(branch=branch,target_commit=local,verified=False)
env=dict(os.environ,GIT_TERMINAL_PROMPT='0')
t=time.monotonic()
try:
 p=subprocess.run(['git','-c','pack.threads=1','-c','pack.windowMemory=32m','push','origin',local+':'+branch],capture_output=True,text=True,env=env,timeout=600)
 s=(p.stdout+p.stderr).lower()
 terms={'non_fast_forward':['non-fast-forward','fetch first'],'authentication':['authentication failed','could not read username','permission denied','invalid username'],'large_file':['gh001','large files detected','exceeds github'],'policy':['gh013','protected branch','repository rule'],'network':['rpc failed','remote end hung up','connection','http 5','curl 92','curl 56'],'up_to_date':['up-to-date']}
 r.update(push_exit=p.returncode,categories=[k for k,ts in terms.items() if any(x in s for x in ts)],http_statuses=re.findall(r'http (\d{3})',s),curl_codes=re.findall(r'curl (\d+)',s))
except subprocess.TimeoutExpired:
 r.update(push_exit=None,categories=['timeout'])
r['duration_seconds']=time.monotonic()-t
try:
 q=subprocess.run(['git','ls-remote','origin','refs/heads/'+branch],capture_output=True,text=True,env=env,timeout=45)
 m=re.fullmatch(r'([0-9a-f]{40})\s+refs/heads/'+branch,q.stdout.strip()) if q.returncode==0 else None
 r['remote_commit']=m.group(1) if m else None
 r['verified']=r['remote_commit']==local
except subprocess.TimeoutExpired:r['remote_check']='timeout'
receipt.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r));sys.exit(not r['verified'])
