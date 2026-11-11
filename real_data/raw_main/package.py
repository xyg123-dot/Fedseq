#!/usr/bin/env python3
"""Package current manuscript and retain complete experiment provenance."""
from pathlib import Path
import zipfile,os,shutil,json
ROOT=Path(__file__).resolve().parent;PROJ=ROOT.parent.parent;BASE=PROJ.parent;PAPER=PROJ/'paper'
def main():
 checks=json.loads((ROOT/'final_verification.json').read_text());assert checks['all_main_rfam_minimally_processed']and checks['pages']==13
 shutil.copy2(PAPER/'main.pdf',BASE/'FedSeq_ICDE_rewritten.pdf')
 target=BASE/'FedSeq_ICDE_rewritten_source.zip';temp=Path(str(target)+'.tmp')
 files=[Path(x)for x in ['main.tex','main.pdf','IEEEtran.cls','IEEEtran.bst','references.bib','Makefile','verified_numbers.tex','experiment_results.tex','real_setup.tex','real_results.tex','table_accuracy.tex','table_transport.tex','table_raw_rfam.tex','table_unstructured.tex','README.md','FINAL_REVIEW_CN.md','FINAL_CHECK.json','FINAL_NUMERICAL_AUDIT.json','CLAIM_EVIDENCE_CN.md','LAYOUT_UPDATE_CN.md','RAW_SOURCE_CHECK_CN.md','REFERENCE_AUDIT_42.md','DATA_REFERENCE_AUDIT.md','ICDE_AI_DISCLOSURE.tex']]
 files+=list(Path('algorithms').joinpath(p.name)for p in(PAPER/'algorithms').glob('*.tex'))
 files+=list(Path('figures').joinpath(p.name)for p in(PAPER/'figures').glob('*.tex'))
 files+=[Path('figures')/(n+'.'+e)for n in ['comparison_all','ablation_all','robustness_all']for e in ['pdf','png']]
 with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED,compresslevel=6)as z:
  for rel in files:z.write(PAPER/rel,'FedSeq_ICDE_source/'+rel.as_posix())
 os.replace(temp,target)
 target=BASE/'FedSeq_IID_NonIID_full.zip';temp=Path(str(target)+'.tmp');seen=set()
 with zipfile.ZipFile(target)as old,zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED,compresslevel=6)as z:
  for entry in old.infolist():
   if entry.is_dir()or entry.filename.endswith(('paper/supplementary.tex','paper/supplementary.pdf')):continue
   assert entry.filename.startswith('fedseq_revised/')
   rel=entry.filename[len('fedseq_revised/'):];p=PROJ/rel
   if p.is_file():z.write(p,entry.filename)
   else:z.writestr(entry,old.read(entry.filename))
   seen.add(entry.filename)
  for p in sorted(ROOT.rglob('*')):
   if not p.is_file()or'__pycache__'in p.parts or p.name.startswith('.'):continue
   arc='fedseq_revised/'+p.relative_to(PROJ).as_posix()
   if arc not in seen:z.write(p,arc);seen.add(arc)
 os.replace(temp,target)
 for name,prefix in [('FedSeq_ICDE_rewritten_source.zip','FedSeq_ICDE_source/'),('FedSeq_IID_NonIID_full.zip','fedseq_revised/paper/')]:
  with zipfile.ZipFile(BASE/name)as z:
   assert z.testzip()is None and z.read(prefix+'main.pdf')==(PAPER/'main.pdf').read_bytes()
   assert z.read(prefix+'real_results.tex')==(PAPER/'real_results.tex').read_bytes()
   if name=='FedSeq_IID_NonIID_full.zip':
    assert z.getinfo('fedseq_revised/benchmark/fedknn_benchmark').external_attr>>16&0o111
   print(name,(BASE/name).stat().st_size,len(z.namelist()),'CRC/content PASS')
if __name__=='__main__':main()
