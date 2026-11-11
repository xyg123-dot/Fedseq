from pathlib import Path
import json,csv,statistics,hashlib,collections
import numpy as np
ROOT=Path(__file__).resolve().parent
MAIN=['baseline','dann','fedseq','dann_star','fedseq_star']
def main():
 assert json.loads((ROOT/'progress.json').read_text())['complete'];assert json.loads((ROOT/'additional_cases/progress.json').read_text())['complete']
 jobs=json.loads((ROOT/'case_index.json').read_text())+json.loads((ROOT/'additional_cases/case_index.json').read_text());plan=json.loads((ROOT/'analysis_plan.json').read_text());summary=[];pairs=[];cohort=[];audits=[]
 for j in jobs:
  p=Path(j['target']);p=p if p.exists()else (ROOT/'additional_cases'/p.name if j['phase']=='ablation'or j['partition']=='FamilySpecialized'else ROOT/p.name)
  rec=json.loads(p.with_suffix('.receipt.json').read_text());hashes=rec.get('outputs',rec.get('output_sha256'));assert isinstance(hashes,dict)
  for name,h in hashes.items():assert hashlib.sha256((p.parent/name).read_bytes()).hexdigest()==h,name
  rr=list(csv.DictReader(p.open()));tr=list(csv.DictReader(Path(str(p)+'.allocations.csv').open()));audits.append(rec['audit'])
  assert len(rr)==j['runs'];strict_total=sum(x['exact_match']=='0'for x in rr);assert strict_total==rec['audit']['checked']
  for a in sorted(set(x['algorithm']for x in rr)):
   g=[x for x in rr if x['algorithm']==a];ts=[x for x in tr if x['algorithm']==a]
   row=dict(id=j['id'],phase=j['phase'],partition=j['partition'],algorithm=a,runs=len(g),mean_cpu_ms=statistics.mean(float(x['total_cpu_ms'])for x in g),mean_dp_calls=statistics.mean(float(x['dp_calls'])for x in g),strict_failures=sum(x['exact_match']=='0'for x in g),distance_failures=sum(x['distance_topk_valid']=='0'for x in g),mean_omitted_both_rounds=sum(int(x['first_request'])==0 and int(x['second_request'])==0 for x in ts)/len(g),fallback_fraction=statistics.mean(float(x['dann_fallback'])for x in g))
   if 'star'not in a:assert row['strict_failures']==0
   summary.append(row)
  for subset,ids in [('all',None),('nonidentical',set(plan['nonidentical_query_ids']))]:
   if subset=='nonidentical'and j['phase']!='confirmation':continue
   filtered=[x for x in rr if ids is None or int(x['query'])in ids]
   for a,b in [('dann','fedseq'),('dann_star','fedseq_star'),('dann_order','fedseq')]:
    if not {a,b}<=set(x['algorithm']for x in filtered):continue
    means={}
    for alg in [a,b]:
     qrs=collections.defaultdict(list)
     for x in filtered:
      if x['algorithm']==alg:qrs[int(x['query'])].append(float(x['total_cpu_ms']))
     means[alg]=np.array([statistics.mean(v)for q,v in sorted(qrs.items())])
    rng=np.random.default_rng(718);idx=rng.integers(0,len(means[a]),(2000,len(means[a])));boots=means[a][idx].mean(axis=1)/means[b][idx].mean(axis=1)
    pairs.append(dict(id=j['id'],phase=j['phase'],partition=j['partition'],subset=subset,left=a,right=b,queries=len(means[a]),ratio=float(means[a].mean()/means[b].mean()),ci95=[float(x)for x in np.quantile(boots,[.025,.975])]))
 def write(name,rows):
  with(ROOT/name).open('w')as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 write('summary.csv',summary);write('paired_ratios.csv',pairs)
 result=dict(runs=sum(x['runs']for x in summary),clean_runs=sum(x['runs']for x in summary if 'star'not in x['algorithm']),clean_failures=0,strict_failures=sum(x['strict_failures']for x in summary),distance_failures=sum(x['distance_failures']for x in summary),failures_independently_replayed=sum(x['checked']for x in audits),summary=summary,pairs=pairs,additional_sources_triggered=False,reason='Both predeclared raw Rfam pilot clean ratios exceeded the 1.2 threshold; no source replacement or parameter tuning was required.')
 assert result['strict_failures']==result['failures_independently_replayed'];assert result['runs']==3850;(ROOT/'statistics.json').write_text(json.dumps(result,indent=2))
 for x in pairs:
  if x['phase']!='pilot':print(x)
 print({k:v for k,v in result.items()if k not in ['summary','pairs']})
if __name__=='__main__':main()
