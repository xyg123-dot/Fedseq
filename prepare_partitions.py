#!/usr/bin/env python3
"""Freeze balanced random IID simulations and single-family Non-IID shards."""
import collections,csv,hashlib,json,math,random
from pathlib import Path

def main():
    root=Path(__file__).resolve().parent;out=root/'partitions';out.mkdir(exist_ok=True);reports=[]
    for ds in ['dna_cluster_order','symbol_cluster_order']:
        folder=root/'datasets'/ds;meta=list(csv.DictReader((folder/'record_metadata.csv').open()));n=len(meta)
        for m in [4,8,12,16]:
            for mode in ['IID','NonIID']:
                rng=random.Random(20261010+m);assignment=[-1]*n
                if mode=='IID':
                    ids=list(range(n));rng.shuffle(ids)
                    for j,i in enumerate(ids):assignment[i]=j%m
                else:
                    homes=m//4
                    for family in range(4):
                        ids=[i for i,r in enumerate(meta)if int(r['family'])==family];rng.shuffle(ids)
                        for j,i in enumerate(ids):assignment[i]=family*homes+j%homes
                target=out/f'{ds}_{mode}_m{m}.txt';target.write_text(''.join(str(x)+'\n'for x in assignment))
                counts=[collections.Counter()for _ in range(m)]
                for r,pid in zip(meta,assignment):counts[pid][int(r['family'])]+=1
                assert all(sum(c.values())>0 for c in counts)
                assert max(sum(c.values())for c in counts)-min(sum(c.values())for c in counts)<=1
                if mode=='NonIID':assert all(len(c)==1 for c in counts)
                report={'dataset':ds,'partition':mode,'m':m,'seed':20261010+m,'file':str(target.relative_to(root)),
                        'records':n,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'node_family_counts':[dict(c)for c in counts],
                        'mean_node_family_entropy_bits':sum(-sum((v/sum(c.values()))*math.log2(v/sum(c.values()))for v in c.values())for c in counts)/m,
                        'max_family_fraction_deviation_from_quarter':max(abs(c.get(f,0)/sum(c.values())-.25)for c in counts for f in range(4))}
                reports.append(report)
    (out/'partition_report.json').write_text(json.dumps(reports,indent=2));print('PASS 16 partition files: full membership, balanced counts, NonIID single family verified')
if __name__=='__main__':main()
