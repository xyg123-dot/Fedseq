#!/usr/bin/env python3
"""Unclustered random-sequence control: no family structure or outcome selection."""
import concurrent.futures,csv,hashlib,json,os,random,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def main():
    folder=ROOT/'unstructured';folder.mkdir(exist_ok=True)
    jobs=[]
    cpus=sorted(os.sched_getaffinity(0))[5:7]
    assert len(cpus)==2
    for index,seed in enumerate([20261014,20261024,20261034]):
        data=folder/f'seed{seed}';data.mkdir(exist_ok=True)
        rng=random.Random(seed);used=set();records=[]
        while len(records)<8000:
            s=''.join(rng.choice('ACGT') for _ in range(128))
            if s not in used:records.append(s);used.add(s)
        queries=[]
        while len(queries)<50:
            s=''.join(rng.choice('ACGT') for _ in range(128))
            if s not in used:queries.append(s);used.add(s)
        (data/'records.txt').write_text('\n'.join(records)+'\n')
        (data/'queries.txt').write_text('\n'.join(queries)+'\n')
        ids=list(range(8000));rng.shuffle(ids);assignment=[0]*8000
        for j,record in enumerate(ids):assignment[record]=j%8
        (data/'assignment.txt').write_text('\n'.join(map(str,assignment))+'\n')
        command=[str(ROOT/'benchmark/fedknn_benchmark'),'--data',str(data/'records.txt'),'--queries',str(data/'queries.txt'),
                 '--assignment',str(data/'assignment.txt'),'--kind','dna','--backend','scan','--m','8','--k','128',
                 '--num-queries','50','--repeats','3','--seed',str(seed),'--rtt-ms','0',
                 '--algorithms','baseline,dann,dann_gram2,fedseq','--out',str(data/'results.csv')]
        jobs.append({'seed':seed,'cpu':cpus[index%2],'command':command,'target':str(data/'results.csv')})
    (folder/'design.json').write_text(json.dumps({'queries':50,'repeats':3,'n':8000,'length':128,
        'generator':'independent uniform DNA strings, no centers or families','jobs':jobs,
        'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),*sorted((ROOT/'benchmark').glob('*.cpp')),*sorted((ROOT/'benchmark').glob('*.h'))]}},indent=2))
    def work(job):
        run=subprocess.run(['taskset','-c',str(job['cpu'])]+job['command'],capture_output=True,text=True,timeout=3600)
        Path(job['target']+'.log').write_text(run.stdout+run.stderr)
        assert run.returncode==0,run.stderr
        rows=list(csv.DictReader(Path(job['target']).open()));assert len(rows)==600
        assert all(r['exact_match']=='1' for r in rows)
        print('PASS unstructured seed',job['seed'],'runs',len(rows),flush=True)
    # A queued third job uses a core released by the first two.
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(work,jobs))
    (folder/'complete.json').write_text(json.dumps({'complete':True,'runs':1800,'finished_unix':time.time()},indent=2))

if __name__=='__main__':main()
