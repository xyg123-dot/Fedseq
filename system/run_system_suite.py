#!/usr/bin/env python3
"""Sequential configurations; simultaneous providers inside each TCP case."""
import argparse,csv,fcntl,hashlib,json,os,platform,random,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
ALGS='baseline,dann,fedseq,dann_star,fedseq_star'
PROFILES={
 'native':None,
 'tcp_plain':('none',0,0),
 'tcp_aes':('aes128gcm',0,0),
 'wan64_bw100':('aes128gcm',64,100),
 'wan16_bw100':('aes128gcm',16,100),
 'wan128_bw100':('aes128gcm',128,100),
 'wan64_bw10':('aes128gcm',64,10),
 'wan64_bw1000':('aes128gcm',64,1000),
}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def validate(path,expected):
 rows=list(csv.DictReader(path.open()))
 if len(rows)!=expected:raise ValueError(f'{path}: {len(rows)} != {expected}')
 for r in rows:
  if r['algorithm'] in ('baseline','dann','fedseq') and r['strict_exact']!='1':raise ValueError('nonnoise error')
  if abs(float(r['total_cpu_ms'])-float(r['broker_cpu_ms'])-float(r['provider_cpu_ms']))>1e-6:raise ValueError('CPU sum')
 return len(rows)
def main():
 p=argparse.ArgumentParser()
 p.add_argument('--queries',type=int,default=50);p.add_argument('--repeats',type=int,default=3)
 p.add_argument('--section',choices=['default','sensitivity','parameters','matched'],default='default')
 p.add_argument('--resume',action='store_true');p.add_argument('--out-dir',default='results/default')
 args=p.parse_args()
 if args.queries<=0 or args.repeats<=0:raise ValueError('positive sample sizes required')
 out=ROOT/args.out_dir;out.mkdir(parents=True,exist_ok=True)
 lock=(out/'.run.lock').open('a')
 try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:raise RuntimeError('This output directory already has an active experiment; do not run another copy concurrently.')
 subprocess.run(['make','-C',str(ROOT/'benchmark'),'-j2'],check=True)
 configs=[]
 for dataset in ['dna_cluster_order','symbol_cluster_order']:
  for split in ['IID','NonIID']:
   if args.section=='matched':points=[('default',128,8,1)];profiles=['wan64_bw100']
   elif args.section=='default':points=[('default',128,8,1)];profiles=['native','tcp_plain','tcp_aes','wan64_bw100']
   elif args.section=='sensitivity':points=[('default',128,8,1)];profiles=['wan16_bw100','wan128_bw100','wan64_bw10','wan64_bw1000']
   else:
    points=[('default',128,8,1)]+[(f'k{x}',x,8,1) for x in [4,8,16,32,64,256]]+[(f'm{x}',128,x,1) for x in [4,12,16]]+[(f'eps{x}',128,8,x) for x in [2,.8,.6,.4,.2,.1,.05,.01,.001]]
    profiles=['native','wan64_bw100']
   for point,k,m,eps in points:
    for profile in profiles:configs.append(dict(id=f'{dataset}_{split}_{point}_{profile}',dataset=dataset,split=split,point=point,k=k,m=m,epsilon=eps,profile=profile))
 random.Random(98371).shuffle(configs)
 fingerprint=hashlib.sha256(json.dumps({'args':{'queries':args.queries,'repeats':args.repeats,'section':args.section},'sources':{str(x.relative_to(ROOT)):sha(x) for x in sorted(ROOT.rglob('*')) if x.suffix in ('.cpp','.h') or x.name=='Makefile'},'inputs':{str(x.relative_to(ROOT)):sha(x) for folder in ['data','partitions'] for x in sorted((ROOT/folder).rglob('*.txt'))}},sort_keys=True).encode()).hexdigest()
 manifest=dict(configs=configs,queries=args.queries,repeats=args.repeats,fingerprint=fingerprint,platform=platform.platform(),affinity=sorted(os.sched_getaffinity(0)),openssl=subprocess.check_output(['openssl','version'],text=True).strip(),cpuinfo=Path('/proc/cpuinfo').read_text().split('\n\n')[0],cpu_quota=Path('/sys/fs/cgroup/cpu.max').read_text().strip(),sgx_devices=[str(x) for x in [Path('/dev/sgx_enclave'),Path('/dev/sgx/enclave')] if x.exists()],started=time.time())
 old=out/'experiment.json'
 if args.resume and old.exists():
  previous=json.loads(old.read_text())
  if previous['fingerprint']!=fingerprint:raise ValueError('resume source/input mismatch')
  manifest=previous;manifest['last_resume_checked_at']=time.time()
 old.write_text(json.dumps(manifest,indent=2))
 progress=dict(total=len(configs),completed=[],failed=[],complete=False)
 for c in configs:
  target=out/(c['id']+'.csv');receipt=target.with_suffix('.receipt.json');expected=args.queries*args.repeats*5
  if args.resume and receipt.exists():
   d=json.loads(receipt.read_text())
   if d['fingerprint']==fingerprint and d['sha256']==sha(target):
    validate(target,expected);progress['completed'].append(c['id']);print('CACHED',c['id'],flush=True);continue
  exe=ROOT/'benchmark'/('native_benchmark' if c['profile']=='native' else 'system_benchmark')
  command=[str(exe),'--data',str(ROOT/'data'/c['dataset']/'records.txt'),'--queries',str(ROOT/'data'/c['dataset']/'queries.txt'),'--assignment',str(ROOT/'partitions'/f"{c['dataset']}_{c['split']}_m{c['m']}.txt"),'--kind','dna' if c['dataset'].startswith('dna') else 'text','--m',str(c['m']),'--k',str(c['k']),'--epsilon',str(c['epsilon']),'--lambda','.05','--seed','42','--num-queries',str(args.queries),'--repeats',str(args.repeats),'--backend','scan','--algorithms',ALGS,'--out',str(target)]
  if PROFILES[c['profile']]:
   enc,rtt,bw=PROFILES[c['profile']];command+=['--encryption',enc,'--transport-rtt-ms',str(rtt),'--transport-mbps',str(bw)]
  started=time.time();print('RUN',c['id'],flush=True)
  with target.with_suffix('.log').open('w') as log:result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT)
  if result.returncode:raise RuntimeError(f'{c["id"]} exit {result.returncode}; see log')
  validate(target,expected);receipt.write_text(json.dumps(dict(fingerprint=fingerprint,sha256=sha(target),command=command,runs=expected,seconds=time.time()-started),indent=2))
  progress['completed'].append(c['id']);(out/'progress.json').write_text(json.dumps(progress,indent=2))
  print('DONE',len(progress['completed']),len(configs),round(time.time()-started,1),flush=True)
 progress['complete']=True;progress['runs']=len(configs)*expected;(out/'progress.json').write_text(json.dumps(progress,indent=2))
if __name__=='__main__':main()
