"""Lancement borné des mesures CAO indépendantes, un processus à la fois."""
from pathlib import Path
import json,subprocess,sys,time,hashlib
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[4]
kind=sys.argv[1];first=int(sys.argv[2]);last=int(sys.argv[3]);results=[]
if kind=='protections':tasks=[('protections_cao.py',[phase,str(i)]) for i in range(first,last) for phase in ['run','check_sleeve','reopen_sleeve']]
elif kind=='suspension':tasks=[('suspension_cao.py',[str(i)]) for i in range(first,last)]
else:raise ValueError(kind)
for script,args in tasks:
 log=ROOT/'.runtime/reconstruction-faisceaux'/('_'.join([kind,*args])+'.log');cmd=[sys.executable,'-B',str(OUT/script),*args];t=time.monotonic();before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [OUT/script,OUT/'autonomie_cao.py']}
 with log.open('w',encoding='utf-8') as f:
  try:code=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=60).returncode;state='finished'
  except subprocess.TimeoutExpired:code=None;state='timeout_killed_dedicated_process'
 after={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [OUT/script,OUT/'autonomie_cao.py']}
 results.append({'command':cmd,'returncode':code,'state':state,'elapsed_s':time.monotonic()-t,'log':str(log.relative_to(ROOT)),'before':before,'after':after,'unchanged':before==after});(OUT/('execution_'+kind+'.json')).write_text(json.dumps(results,indent=2),encoding='utf-8');print(script,args,code,flush=True)
