from pathlib import Path
import json,time,subprocess,shutil
ROOT=Path(__file__).resolve().parent;PROJECT=ROOT.parent
while True:
 try:
  p=json.loads((ROOT/'full_results/progress.json').read_text());a=json.loads((ROOT/'audit_progress.json').read_text())
  assert not p.get('failed') and not a.get('failed')
  if p.get('complete') and a.get('complete'):break
 except (FileNotFoundError,json.JSONDecodeError):pass
 time.sleep(10)
for script in ['analyze_real.py','write_real_paper.py']:
 r=subprocess.run(['python3',str(ROOT/script)],capture_output=True,text=True)
 (ROOT/(script+'.log')).write_text(r.stdout+r.stderr)
 if r.returncode:raise RuntimeError(r.stdout+r.stderr)
print('STATS AND FIGURES COMPLETE',flush=True)
dst=Path('/tmp/fedseq_real_final_build');shutil.copytree(PROJECT/'paper',dst,dirs_exist_ok=True)
for cmd in [['pdflatex','-interaction=nonstopmode','-halt-on-error','main.tex'],['bibtex','main'],['pdflatex','-interaction=nonstopmode','-halt-on-error','main.tex'],['pdflatex','-interaction=nonstopmode','-halt-on-error','main.tex']]:
 r=subprocess.run(cmd,cwd=dst,capture_output=True,text=True)
 if r.returncode:raise RuntimeError(r.stdout[-3500:])
info=subprocess.check_output(['pdfinfo',str(dst/'main.pdf')],text=True);print(info,flush=True)
shutil.copy2(dst/'main.pdf',PROJECT/'paper/main.pdf');shutil.copy2(dst/'main.pdf',PROJECT.parent/'FedSeq_ICDE_rewritten.pdf')
(ROOT/'local_completion.json').write_text(json.dumps({'statistics':True,'figures':True,'compiled':True,'visual_review_pending':True},indent=2))
