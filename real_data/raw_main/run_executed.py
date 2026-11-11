#!/usr/bin/env python3
"""Frozen full Rfam replacement. Reuses the previously sealed raw sample verbatim."""
from pathlib import Path
import json,csv,random,hashlib,subprocess,time,os,concurrent.futures,queue,fcntl
ROOT=Path(__file__).resolve().parent;PROJ=ROOT.parent.parent;DATA=ROOT.parent/'minimal_processing/Rfam_raw'
MAIN='baseline,dann,fedseq,dann_star,fedseq_star'
ABL='dann,fedseq_legacy,dann_order,fedseq,dann_star,dann_order_star,fedseq_star_laplace,fedseq_star_laplace_zero,fedseq_star'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 ROOT.mkdir(exist_ok=True);(ROOT/'cases').mkdir(exist_ok=True);(ROOT/'assignments').mkdir(exist_ok=True)
 lock=(ROOT/'.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 meta=list(csv.DictReader((DATA/'records.metadata.csv').open()));n=len(meta);assert n==12391
 assignments={}
 for m in [4,8,12,16]:
  ids=list(range(n));random.Random(20261016+m).shuffle(ids);iid=[-1]*n
  for j,i in enumerate(ids):iid[i]=j%m
  counts={};special=[]
  for r in meta:
   fam=r['family'];v=counts.get(fam,0);special.append((0 if fam=='RF00001'else m//2)+v%(m//2));counts[fam]=v+1
  for part,values in [('IID',iid),('NonIID',special)]:
   p=ROOT/'assignments'/f'{part}_m{m}.txt';p.write_text(''.join(str(x)+'\n'for x in values));assignments[part,m]=p
   if m==8:assert sha(p)==sha(DATA/('IID_m8.txt'if part=='IID'else'FamilySpecialized_m8.txt'))
 jobs=[];base=dict(k=128,m=8,epsilon=1.0);points=[('default','1',base)]
 for axis,vs in [('k',[4,8,16,32,64,256]),('m',[4,12,16]),('epsilon',[2,.8,.6,.4,.2,.1,.05,.01,.001])]:points.extend((axis,str(v),base|{axis:v})for v in vs)
 points.append(('ablation','1',base))
 def command(dest,assignment,cfg,algs,transport=False):
  cmd=[str(PROJ/('system/benchmark/system_benchmark'if transport else'benchmark/fedknn_benchmark')),'--data',str(DATA/'records.txt'),'--queries',str(DATA/'queries.txt'),'--assignment',str(assignment),'--kind','text','--backend','scan','--m',str(cfg['m']),'--k',str(cfg['k']),'--epsilon',str(cfg['epsilon']),'--lambda','.05','--seed','42','--num-queries','50','--repeats','3','--algorithms',algs,'--privacy','calibrated','--noise-rng','private']
  cmd+=['--encryption','aes128gcm','--transport-rtt-ms','64','--transport-mbps','100']if transport else['--rtt-ms','0']
  return cmd+['--out',str(dest)]
 for part in ['IID','NonIID']:
  for section,value,cfg in points:
   algs=ABL if section=='ablation'else'dann_star,fedseq_star'if section=='epsilon'else MAIN+',dann_gram2'if section=='default'else MAIN
   name=f'Rfam_raw_{part}_{section}_{value}';dest=ROOT/'cases'/(name+'.csv')
   jobs.append(dict(id=name,dataset='Rfam_raw',partition=part,section=section,value=value,type='native',**cfg,algorithms=algs,runs=150*len(algs.split(',')),target=str(dest),command=command(dest,assignments[part,cfg['m']],cfg,algs)))
 for rho in [0,.5,1]:
  assignment=[-1]*n;famcounts=[]
  for fi,fam in enumerate(['RF00001','RF00006']):
   ids=[i for i,r in enumerate(meta)if r['family']==fam];random.Random(20261015+fi).shuffle(ids)
   weights=[(1-rho)/8+(rho/4 if p//4==fi else 0)for p in range(8)];raw=[len(ids)*v for v in weights];ns=[int(v)for v in raw]
   for p in sorted(range(8),key=lambda p:(-(raw[p]-ns[p]),p))[:len(ids)-sum(ns)]:ns[p]+=1
   at=0
   for p,num in enumerate(ns):
    for i in ids[at:at+num]:assignment[i]=p
    at+=num
   famcounts.append(ns)
  p=ROOT/'assignments'/f'rho_{rho:g}.txt';p.write_text(''.join(str(v)+'\n'for v in assignment));name=f'Rfam_raw_rho_{rho:g}';dest=ROOT/'cases'/(name+'.csv');algs=MAIN+',dann_gram2'
  jobs.append(dict(id=name,dataset='Rfam_raw',partition='graded',section='rho',value=rho,rho=rho,type='native',**base,algorithms=algs,runs=900,counts=famcounts,target=str(dest),command=command(dest,p,base,algs)))
 for part in ['IID','NonIID']:
  name=f'Rfam_raw_transport_{part}';dest=ROOT/'cases'/(name+'.csv')
  jobs.append(dict(id=name,dataset='Rfam_raw',partition=part,section='transport',value='1',type='transport',**base,algorithms=MAIN,runs=750,target=str(dest),command=command(dest,assignments[part,8],base,MAIN,True)))
 protocol=dict(description='Replace every main-manuscript Rfam measurement with this unchanged minimally processed sample. All cases fixed before outcomes; no result-dependent sample, query, parameter, or ownership changes.',source_protocol=sha(ROOT.parent/'minimal_processing/protocol.json'),inputs={n:sha(DATA/n)for n in ['records.txt','queries.txt','records.metadata.csv','queries.metadata.csv']},query_overlap='All 50 original held-out record queries retained, including 11 with identical database sequence content.',sample_seed=20261016,assignment_seed=20261015,native_workers=8,native_cores=list(range(1,9)),auditor_core=0,transport='Unrestricted original affinity; two cases sequential after native completion, concurrent providers.',native_cases=43,transport_cases=2,total_runs=27600,queries=50,repeats=3,jobs=jobs)
 path=ROOT/'protocol.json'
 if path.exists():assert json.loads(path.read_text())==protocol,'Protocol changed; do not overwrite existing experiment.'
 else:path.write_text(json.dumps(protocol,indent=2))
 (ROOT/'case_index.json').write_text(json.dumps(jobs,indent=2));state=dict(total=45,completed=[],failed=[],complete=False);leases=queue.Queue()
 for core in range(1,9):leases.put(core)
 def run(j,core):
  p=Path(j['target']);receipt=Path(str(p)+'.receipt.json');inputs={opt:sha(j['command'][j['command'].index(opt)+1])for opt in ['--data','--queries','--assignment']}
  if receipt.exists():
   old=json.loads(receipt.read_text());assert old['inputs']==inputs and old['binary_sha256']==sha(j['command'][0]);assert all(sha(p.parent/f)==h for f,h in old['outputs'].items());return old
  assert not p.exists(),'Unsealed partial output: retain and resolve before resuming.'
  start=time.time();cmd=(['taskset','-c',str(core)]if core is not None else[])+j['command']
  with Path(str(p)+'.log').open('w')as log:r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,timeout=7200)
  assert r.returncode in [0,2],j['id'];rows=list(csv.DictReader(p.open()));assert len(rows)==j['runs'];strict='exact_match'if j['type']=='native'else'strict_exact';dist='distance_topk_valid'if j['type']=='native'else'distance_topk_exact'
  assert all(x[strict]=='1'for x in rows if 'star'not in x['algorithm'])
  assert all(abs(float(x['total_cpu_ms'])-float(x['provider_cpu_ms'])-float(x['broker_cpu_ms']))<1e-5 for x in rows)
  for x in rows:
   assert x['privacy']=='calibrated'and x['noise_rng']=='private'
   assert abs(float(x['beta1'])-float(x['epsilon'])/4)<1e-8
   assert abs(float(x['beta2'])-float(x['epsilon'])/(2*(int(x['k'])+int(x['m']))))<1e-8
  audit=None
  if j['type']=='native':
   ar=subprocess.run(['taskset','-c','0',str(PROJ/'tools/audit_quotas'),str(p),*j['command'][1:]],capture_output=True,text=True,timeout=7200);assert ar.returncode==0,ar.stderr;audit=json.loads(ar.stdout);Path(str(p)+'.audit.json').write_text(json.dumps(audit,indent=2))
   sums={}
   for x in csv.DictReader(Path(str(p)+'.nodes.csv').open()):key=x['query'],x['repeat'],x['algorithm'];sums[key]=sums.get(key,0)+float(x['cpu_ms'])
   assert all(abs(float(x['provider_cpu_ms'])-sums[x['query'],x['repeat'],x['algorithm']])<1e-5 for x in rows)
  outputs={f.name:sha(f)for f in p.parent.glob(p.name+'*')if not f.name.endswith(('.receipt.json','.log'))}
  result=dict(id=j['id'],runs=len(rows),core=core,seconds=time.time()-start,inputs=inputs,binary_sha256=sha(j['command'][0]),outputs=outputs,audit=audit,strict_failures=sum(x[strict]=='0'for x in rows),distance_failures=sum(x[dist]=='0'for x in rows));receipt.write_text(json.dumps(result,indent=2));return result
 def native(j):
  core=leases.get()
  try:return run(j,core)
  finally:leases.put(core)
 def record(j,f):
  try:v=f();state['completed'].append(v);print('DONE',len(state['completed']),45,v['id'],round(v['seconds'],1),flush=True)
  except Exception as e:state['failed'].append(dict(id=j['id'],error=str(e)));print('FAIL',j['id'],str(e),flush=True)
  (ROOT/'progress.json').write_text(json.dumps(state,indent=2))
 with concurrent.futures.ThreadPoolExecutor(max_workers=8)as pool:
  fs={pool.submit(native,j):j for j in jobs if j['type']=='native'}
  for f in concurrent.futures.as_completed(fs):record(fs[f],f.result)
 assert not state['failed'],'Resolve failures without changing protocol.'
 for j in jobs:
  if j['type']=='transport':record(j,lambda:run(j,None))
 state['complete']=not state['failed'];(ROOT/'progress.json').write_text(json.dumps(state,indent=2));assert state['complete'];print('ALL COMPLETE',flush=True)
if __name__=='__main__':main()
