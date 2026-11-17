"""Infrastructure de lancement séquentiel borné, journal d'exécution distinct des mesures."""
from pathlib import Path
import sys,subprocess,json,time,hashlib
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[4]
params=Path(sys.argv[1]).resolve();rows=json.loads(params.read_text('utf-8'))['candidates']
start=int(sys.argv[2]);stop=int(sys.argv[3]);phases=sys.argv[4:]
logdir=ROOT/'.runtime/reconstruction-faisceaux';logdir.mkdir(parents=True,exist_ok=True)
journal=OUT/('execution_'+params.stem+'.json')
results=json.loads(journal.read_text('utf-8')) if journal.exists() else []
for index in range(start,min(stop,len(rows))):
 for phase in phases:
  if phase!='generate' and not rows[index]['polyline_feasible']:continue
  cmd=[sys.executable,'-B',str(OUT/'autonomie_cao.py'),phase,str(params),str(index)]
  log=logdir/(rows[index]['id']+'_'+phase+'.log');t=time.monotonic()
  before={'params_sha256':hashlib.sha256(params.read_bytes()).hexdigest(),'adapter_sha256':hashlib.sha256((OUT/'autonomie_cao.py').read_bytes()).hexdigest()}
  with log.open('w',encoding='utf-8') as f:
   try:code=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=60).returncode;state='finished'
   except subprocess.TimeoutExpired:code=None;state='timeout_killed_dedicated_process'
  after={'params_sha256':hashlib.sha256(params.read_bytes()).hexdigest(),'adapter_sha256':hashlib.sha256((OUT/'autonomie_cao.py').read_bytes()).hexdigest()}
  result={'id':rows[index]['id'],'phase':phase,'command':cmd,'returncode':code,'state':state,'elapsed_s':time.monotonic()-t,'log':str(log.relative_to(ROOT)),'before':before,'after':after,'inputs_unchanged_during_process':before==after}
  results.append(result);journal.write_text(json.dumps(results,indent=2),encoding='utf-8');print(result['id'],phase,code,state,flush=True)
  if code!=0:break
  if phase=='generate' and not rows[index]['polyline_feasible']:break
