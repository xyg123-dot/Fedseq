#!/usr/bin/env python3
"""Frozen Rfam follow-up: graded simulated ownership and matched encrypted transport."""
from pathlib import Path
import csv,json,hashlib,subprocess,random,time,concurrent.futures,os,statistics
ROOT=Path(__file__).resolve().parent; REAL=ROOT.parent; PROJ=REAL.parent; DATA=REAL/'Rfam_canonical'
ALGS='baseline,dann,fedseq,dann_star,fedseq_star'; RHOS=[0,.5,1];SEED=20261015
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 meta=list(csv.DictReader((DATA/'records.txt.metadata.csv').open())); fams=sorted(set(x['family']for x in meta)); jobs=[]
 for rho in RHOS:
  assignment=[-1]*len(meta);counts=[]
  for fi,f in enumerate(fams):
   ids=[i for i,x in enumerate(meta)if x['family']==f];random.Random(SEED+fi).shuffle(ids)
   weights=[(1-rho)/8+(rho/4 if p//4==fi else 0)for p in range(8)]
   raw=[len(ids)*v for v in weights];ns=[int(x)for x in raw]
   for p in sorted(range(8),key=lambda p:(-(raw[p]-ns[p]),p))[:len(ids)-sum(ns)]:ns[p]+=1
   at=0
   for p,n in enumerate(ns):
    for i in ids[at:at+n]:assignment[i]=p
    at+=n
   counts.append(ns)
  assert min(assignment)>=0
  member=ROOT/f'rho_{rho:g}.txt';member.write_text(''.join(str(x)+'\n'for x in assignment))
  name=f'Rfam_rho_{rho:g}';target=ROOT/f'{name}.csv'
  cmd=[str(PROJ/'benchmark/fedknn_benchmark'),'--data',str(DATA/'records.txt'),'--queries',str(DATA/'queries.txt'),'--assignment',str(member),'--kind','text','--backend','scan','--m','8','--k','128','--epsilon','1','--lambda','.05','--seed','42','--num-queries','50','--repeats','3','--algorithms',ALGS+',dann_gram2','--privacy','calibrated','--noise-rng','private','--rtt-ms','0','--out',str(target)]
  jobs.append(dict(id=name,type='native',rho=rho,counts=counts,target=str(target),command=cmd))
 for split in ['IID','NonIID']:
  name='Rfam_transport_'+split;target=ROOT/f'{name}.csv'
  cmd=[str(PROJ/'system/benchmark/system_benchmark'),'--data',str(DATA/'records.txt'),'--queries',str(DATA/'queries.txt'),'--assignment',str(DATA/f'{split}_m8.txt'),'--kind','text','--backend','scan','--m','8','--k','128','--epsilon','1','--lambda','.05','--seed','42','--num-queries','50','--repeats','3','--algorithms',ALGS,'--privacy','calibrated','--noise-rng','private','--encryption','aes128gcm','--transport-rtt-ms','64','--transport-mbps','100','--out',str(target)]
  jobs.append(dict(id=name,type='transport',partition=split,target=str(target),command=cmd))
 manifest=dict(transport_affinity='Unrestricted original process affinity, concurrent providers; executed after native cases complete.',protocol='Fixed before execution; no performance-based exclusions or parameter changes.',rho=RHOS,assignment_seed=SEED,queries=50,repeats=3,k=128,m=8,epsilon=1,inputs={p.name:sha(p)for p in [DATA/'records.txt',DATA/'queries.txt']},jobs=jobs)
 (ROOT/'protocol.json').write_text(json.dumps(manifest,indent=2));progress=dict(total=len(jobs),completed=[],complete=False)
 def run(j,core):
  target=Path(j['target']);start=time.time();cmd=(['taskset','-c',str(core)]if core is not None else [])+j['command']
  if j['type']=='native'and target.with_suffix('.receipt.json').exists():
   old=json.loads(target.with_suffix('.receipt.json').read_text());assert sha(target)==old['output_sha256'];return old
  with target.with_suffix('.log').open('w')as log:r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,timeout=7200)
  assert r.returncode in [0,2],j['id']
  rows=list(csv.DictReader(target.open()));assert len(rows)==(900 if j['type']=='native'else 750)
  key='exact_match'if j['type']=='native'else'strict_exact'
  assert all(x[key]=='1'for x in rows if 'star'not in x['algorithm'])
  assert all(abs(float(x['total_cpu_ms'])-float(x['broker_cpu_ms'])-float(x['provider_cpu_ms']))<1e-5 for x in rows)
  for x in rows:assert x['privacy']=='calibrated'and x['noise_rng']=='private'
  audit=None
  if j['type']=='native':
   ar=subprocess.run(['taskset','-c','6',str(PROJ/'tools/audit_quotas'),str(target),*j['command'][1:]],capture_output=True,text=True,timeout=3600);assert ar.returncode==0,ar.stderr;audit=json.loads(ar.stdout);target.with_suffix('.audit.json').write_text(json.dumps(audit,indent=2))
  result=dict(id=j['id'],runs=len(rows),core=core,seconds=time.time()-start,output_sha256=sha(target),command=cmd,audit=audit,source_sha256=sha(j['command'][0]))
  target.with_suffix('.receipt.json').write_text(json.dumps(result,indent=2));return result
 # Native cases reuse their sealed outputs. TCP runs afterward with the original unrestricted affinity.
 with concurrent.futures.ThreadPoolExecutor(max_workers=3)as pool:
  for v in pool.map(lambda item:run(item[1],item[0]+1),enumerate(jobs[:3])):
   progress['completed'].append(v);(ROOT/'progress.json').write_text(json.dumps(progress,indent=2))
 for j in jobs[3:]:
  v=run(j,None);progress['completed'].append(v);(ROOT/'progress.json').write_text(json.dumps(progress,indent=2));print('DONE',len(progress['completed']),len(jobs),flush=True)
 progress['complete']=True;(ROOT/'progress.json').write_text(json.dumps(progress,indent=2));print('ALL COMPLETE',flush=True)
if __name__=='__main__':main()
