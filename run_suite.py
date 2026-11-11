#!/usr/bin/env python3
"""Full IID/Non-IID one-factor-at-a-time comparison and module ablation."""
import argparse,concurrent.futures,csv,fcntl,hashlib,json,os,platform,queue,random,shutil,subprocess,time
from pathlib import Path
MAIN='baseline,dann,fedseq,dann_star,fedseq_star'
ABLATION='dann,fedseq_legacy,dann_order,fedseq,dann_star,dann_order_star,fedseq_star_laplace,fedseq_star_laplace_zero,fedseq_star'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def design():
    base={'k':128,'m':8,'epsilon':1.0,'lam':.05};points=[('default',1,base)]
    for axis,values in [('k',[4,8,16,32,64,256]),('m',[4,12,16]),('epsilon',[2,.8,.6,.4,.2,.1,.05,.01,.001])]:
        for v in values:points.append((axis,v,base|{axis:v}))
    return points+[('ablation',1,base)]

def main():
    root=Path(__file__).resolve().parent;ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out-dir',type=Path,default=root/'results');ap.add_argument('--queries',type=int,default=50);ap.add_argument('--repeats',type=int,default=3)
    ap.add_argument('--workers',type=int,default=1);ap.add_argument('--resume',action='store_true');ap.add_argument('--sections',default='default,k,m,epsilon,ablation')
    a=ap.parse_args();wanted=set(a.sections.split(','));assert wanted<=set(['default','k','m','epsilon','ablation'])
    if a.queries<1 or a.queries>52 or a.repeats<1 or a.workers<1:ap.error('queries=1..52, repeats/workers>=1')
    out=a.out_dir.resolve();out.mkdir(parents=True,exist_ok=True);casesdir=out/'cases';casesdir.mkdir(exist_ok=True)
    run_lock=(out/'.run.lock').open('a')
    try:fcntl.flock(run_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:raise RuntimeError('Another runner is using this output directory; choose a different directory.')
    affinity=sorted(os.sched_getaffinity(0))if hasattr(os,'sched_getaffinity')else []
    physical=[];seen=set()
    for cpu in affinity:
        topo=Path('/sys/devices/system/cpu')/f'cpu{cpu}'/'topology'
        key=tuple((topo/f).read_text().strip()for f in ['physical_package_id','core_id'])if topo.exists()else(cpu,)
        if key not in seen:seen.add(key);physical.append(cpu)
    cores=physical[:a.workers]if shutil.which('taskset')else []
    if a.workers>1 and len(cores)<a.workers:ap.error('parallel cases require enough distinct physical cores and taskset')
    leases=queue.Queue()
    for cpu in cores or [None]:leases.put(cpu)
    source_files=[root/'run_suite.py',root/'prepare_partitions.py',*sorted((root/'benchmark').glob('*.cpp')),*sorted((root/'benchmark').glob('*.h'))]
    source_sha={str(p.relative_to(root)):sha(p)for p in source_files}
    inputs=[*sorted((root/'partitions').glob('*.txt'))]
    for ds in ['dna_cluster_order','symbol_cluster_order']:
        inputs += [root/'datasets'/ds/f for f in ['records.txt','queries.txt','record_metadata.csv']]
    input_sha={str(p.relative_to(root)):sha(p)for p in inputs}
    protocol={'queries':a.queries,'repeats':a.repeats,'sections':sorted(wanted),'workers':a.workers,'affinity_cores':cores,
              'source_sha256':source_sha,'input_sha256':input_sha,'algorithms':MAIN,'ablation_algorithms':ABLATION}
    fingerprint=hashlib.sha256(json.dumps(protocol,sort_keys=True).encode()).hexdigest()
    experiment={'fingerprint':fingerprint,'protocol':protocol,'platform':platform.platform(),
                'cpu_model':next((x.split(':',1)[1].strip()for x in Path('/proc/cpuinfo').read_text().splitlines()if x.startswith('model name')),'unknown'),
                'compiler':subprocess.check_output(['g++','--version'],text=True).splitlines()[0],
                'timing':'Each query executes serial providers in one process; total process CPU includes all nodes and broker. Independent cases may run concurrently on distinct pinned physical cores. Not distributed latency.',
                'privacy':'Protected joint quota view: Delta1<=2, common Delta2<=k+m; beta1=epsilon/4, beta2=epsilon/(2*(k+m)); private OpenSSL randomness. No full host-trace guarantee.'}
    prior=out/'experiment.json'
    if a.resume and prior.exists():
        if json.loads(prior.read_text())['fingerprint']!=fingerprint:raise ValueError('Resume requires identical sources, inputs and timing protocol; use a new output directory')
    elif any(casesdir.glob('*.csv')):raise ValueError('Output already has cases; use --resume or a new directory')
    prior.write_text(json.dumps(experiment,indent=2));jobs=[]
    for ds,kind in [('dna_cluster_order','dna'),('symbol_cluster_order','text')]:
        for partition in ['IID','NonIID']:
            for axis,value,cfg in design():
                if axis not in wanted:continue
                tag=f'{ds}_{partition}_{axis}_{value}';target=casesdir/(tag+'.csv')
                membership=root/'partitions'/f'{ds}_{partition}_m{cfg["m"]}.txt';algorithms=ABLATION if axis=='ablation'else MAIN
                cmd=[str(root/'benchmark/fedknn_benchmark'),'--data',str(root/'datasets'/ds/'records.txt'),'--queries',str(root/'datasets'/ds/'queries.txt'),
                     '--assignment',str(membership),'--kind',kind,'--backend','scan','--m',str(cfg['m']),'--k',str(cfg['k']),'--epsilon',str(cfg['epsilon']),
                     '--lambda',str(cfg['lam']),'--num-queries',str(a.queries),'--repeats',str(a.repeats),'--algorithms',algorithms,'--privacy','calibrated','--noise-rng','private','--rtt-ms','0','--out',str(target)]
                jobs.append({'id':tag,'dataset':ds,'kind':kind,'partition':partition,'section':axis,'value':value,**cfg,'algorithms':algorithms,'command':cmd,'target':str(target)})
    (out/'case_index.json').write_text(json.dumps(jobs,indent=2));random.Random(4271).shuffle(jobs)
    progress={'total':len(jobs),'completed':[],'failed':[],'start_unix':time.time()};(out/'progress.json').write_text(json.dumps(progress,indent=2))
    def work(job):
        cpu=leases.get();target=Path(job['target']);receipt=Path(str(target)+'.receipt.json');started=time.time()
        try:
            cached=False
            if a.resume and receipt.exists():
                r=json.loads(receipt.read_text());cached=r['fingerprint']==fingerprint and all(Path(path).exists()and sha(Path(path))==digest for path,digest in r['output_sha256'].items())
            if not cached:
                cmd=(['taskset','-c',str(cpu)]if cpu is not None else [])+job['command']
                run=subprocess.run(cmd,capture_output=True,text=True,timeout=3600)
                Path(str(target)+'.log').write_text(run.stdout+run.stderr)
                if run.returncode not in [0,2]:raise RuntimeError(run.stdout+run.stderr)
            rows=list(csv.DictReader(target.open()));expected=a.queries*a.repeats*len(job['algorithms'].split(','));assert len(rows)==expected
            sums={}
            for row in csv.DictReader(Path(str(target)+'.nodes.csv').open()):
                key=row['query'],row['repeat'],row['algorithm'];sums[key]=sums.get(key,0)+float(row['cpu_ms'])
            for row in rows:
                assert int(row['m'])==job['m']and int(row['k'])==job['k']and float(row['epsilon'])==job['epsilon']
                assert 0<=float(row['recall'])<=1
                if 'star'not in row['algorithm']:assert row['exact_match']=='1','Non-noisy correctness failure'
                assert abs(float(row['total_cpu_ms'])-float(row['provider_cpu_ms'])-float(row['broker_cpu_ms']))<1e-5
                assert abs(float(row['provider_cpu_ms'])-sums[row['query'],row['repeat'],row['algorithm']])<1e-5
            outputs=[target,Path(str(target)+'.allocations.csv'),Path(str(target)+'.nodes.csv'),Path(str(target)+'.failures.csv')]
            result={'id':job['id'],'fingerprint':fingerprint,'cpu_core':cpu,'cached':cached,'wall_seconds':time.time()-started,
                    'runs':len(rows),'strict_failures':sum(r['exact_match']=='0'for r in rows),'nonnoisy_failures':0,
                    'output_sha256':{str(p):sha(p)for p in outputs}}
            if not cached:receipt.write_text(json.dumps(result,indent=2))
            return result
        finally:leases.put(cpu)
    print('Frozen design:',len(jobs),'cases;',sum(a.queries*a.repeats*len(j['algorithms'].split(','))for j in jobs),'algorithm runs;',a.workers,'workers',flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers)as pool:
        futures={pool.submit(work,j):j for j in jobs}
        for f in concurrent.futures.as_completed(futures):
            job=futures[f]
            try:r=f.result();progress['completed'].append(r);print(f"[{len(progress['completed'])}/{len(jobs)}] {job['id']} strict_mismatches={r['strict_failures']}",flush=True)
            except Exception as e:
                progress['failed'].append({'id':job['id'],'error':str(e)});print('FAILED',job['id'],str(e),flush=True)
            (out/'progress.json').write_text(json.dumps(progress,indent=2))
    if progress['failed']:raise RuntimeError('Failed cases retained in progress.json')
    progress['finished_unix']=time.time();progress['complete']=True;(out/'progress.json').write_text(json.dumps(progress,indent=2));print('COMPLETE all cases; CPU decompositions and non-noisy exactness verified; noisy failures retained.',flush=True)
if __name__=='__main__':main()
