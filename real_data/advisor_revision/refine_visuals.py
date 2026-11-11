#!/usr/bin/env python3
"""Apply the final, data-preserving editorial selection of method illustrations."""
from pathlib import Path
import shutil
ROOT=Path(__file__).resolve().parent;PAPER=ROOT.parent.parent/'paper'
def main():
 for f in (ROOT/'vector_refinement').glob('*.tex'):shutil.copy2(f,PAPER/'figures'/f.name)
 p=PAPER/'main.tex';s=p.read_text().replace('\\input{figures/local_pruning}\n','').replace(' (Figure~\\ref{fig:local-pruning})','')
 s=s.replace('Figure~\\ref{fig:cold-example} shows the records, returned prefix and unsent frontiers behind this certificate.','Figure~\\ref{fig:cold-example} traces the sequence records to their returned prefix and unsent frontiers.')
 p.write_text(s)
if __name__=='__main__':main()
