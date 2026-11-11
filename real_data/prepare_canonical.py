import gzip,json,hashlib
from prepare_candidates import ROOT,prepare
rows=[]
snapshot=json.loads((ROOT/'source_snapshot_hashes.json').read_text())
expected={fam:snapshot[f'raw/{fam}.fa.gz']for fam in ['RF00001','RF00006']}
for fam in ['RF00001','RF00006']:
 assert hashlib.sha256((ROOT/'raw'/f'{fam}.fa.gz').read_bytes()).hexdigest()==expected[fam], 'Official CURRENT source changed; use the archived source snapshot for identical extraction.'
for fam in ['RF00001','RF00006']:
 p=ROOT/'raw'/f'{fam}.fa.gz';sid=None;seq=[]
 def save():
  if sid is None:return
  s=''.join(seq).upper().replace('U','T')
  if 16<=len(s)<=128 and set(s)<=set('ACGT'):rows.append((sid,fam,s))
 with gzip.open(p,'rt')as f:
  for line in f:
   if line.startswith('>'):save();sid=line[1:].strip().split()[0];seq=[]
   else:seq.append(line.strip())
  save()
prepare('Rfam_canonical',rows,cap=10000)

manifest=ROOT/'Rfam_canonical/manifest.json'
m=json.loads(manifest.read_text());m['sequence_changes']='uppercase and U-to-T nucleotide normalization before exact deduplication; no mutation, cropping or padding'
old=set()
for ds in ['Rfam_RNA','Rfam_full']:
 old|={s.replace('U','T')for s in(ROOT/ds/'pilot_queries.txt').read_text().splitlines()}
overlap=set((ROOT/'Rfam_canonical/queries.txt').read_text().splitlines())&old
assert not overlap,'Confirmation queries overlap exploratory queries'
m['original_pilot_overlap']=len(overlap);manifest.write_text(json.dumps(m,indent=2))
