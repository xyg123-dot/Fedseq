from pathlib import Path
import json,time,concurrent.futures,subprocess,hashlib
ROOT=Path(__file__).resolve().parent;folder=ROOT/'full_results';exe=ROOT.parent/'tools/audit_quotas'
seen=set();progress={'completed':[],'failed':[],'complete':False}
def run(job):
 p=Path(job['target']);cmd=[str(exe),str(p),*job['command'][1:]]
 r=subprocess.run(cmd,capture_output=True,text=True,timeout=3600)
 if r.returncode:raise RuntimeError(job['id']+r.stderr)
 data=json.loads(r.stdout)|{'id':job['id']};p.with_suffix('.audit.json').write_text(json.dumps(data,indent=2));return data
while True:
 jobs=json.loads((folder/'case_index.json').read_text());pending=[j for j in jobs if j['id']not in seen and Path(j['target']+'.receipt.json').exists()]
 with concurrent.futures.ThreadPoolExecutor(max_workers=2)as pool:
  for data in pool.map(run,pending):seen.add(data['id']);progress['completed'].append(data);print('AUDITED',len(seen),len(jobs),data['id'],data['checked'],flush=True)
 state=json.loads((folder/'progress.json').read_text())if(folder/'progress.json').exists()else{}
 if state.get('failed'):raise RuntimeError('Native study failed')
 progress['strict_failures_replayed']=sum(x['checked']for x in progress['completed']);progress['distance_errors']=sum(x['distance_errors']for x in progress['completed']);progress['tie_only']=sum(x['tie_only']for x in progress['completed']);progress['auditor_source_sha256']=hashlib.sha256((ROOT.parent/'tools/audit_quotas.cpp').read_bytes()).hexdigest()
 progress['complete']=state.get('complete',False) and len(seen)==len(jobs);(ROOT/'audit_progress.json').write_text(json.dumps(progress,indent=2))
 if progress['complete']:break
 time.sleep(10)
