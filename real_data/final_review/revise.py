#!/usr/bin/env python3
"""Compact figures and consistency edits; uses only already measured, sealed results."""
from pathlib import Path
import json,csv,sys,statistics,shutil,re
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
HERE=Path(__file__).resolve().parent;REAL=HERE.parent;PROJ=REAL.parent;PAPER=PROJ/'paper'
sys.path.insert(0,str(REAL));from write_real_paper import panel,AXES,MAIN,LABEL,COLOR,cpu
LABEL['dann_gram2']='DANN+Bigram';COLOR['dann_gram2']='#7b4c9b'
DS=[('dna_cluster_order','DNA'),('symbol_cluster_order','Symbol'),('Rfam_canonical','Rfam')]
def read(p):return list(csv.DictReader(p.open()))
def save(fig,name):
 for ext in ['pdf','png']:
  for base in [PROJ/'figures',PAPER/'figures']:fig.savefig(base/f'{name}.{ext}',dpi=260,bbox_inches='tight')
 plt.close(fig)
def style(ax):
 ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True);ax.set_ylim(bottom=0)
def main():
 old=json.loads((PROJ/'verified_statistics.json').read_text());real=json.loads((REAL/'full_results/statistics.json').read_text())['summary'];extra=read(REAL/'layout_extension/summary_native.csv');fam=read(REAL/'family_breakdown.csv')
 files=['main.tex','experiment_results.tex','real_results.tex','real_setup.tex','algorithms/fedseq.tex','algorithms/star.tex','README.md']
 snap=HERE/'manuscript_base.json'
 if not snap.exists():snap.write_text(json.dumps({name:(PAPER/name).read_text()for name in files},indent=2))
 base=json.loads(snap.read_text());plt.rcParams.update({'font.size':10,'axes.titlesize':10,'axes.labelsize':10,'xtick.labelsize':9,'ytick.labelsize':9,'legend.fontsize':10,'pdf.fonttype':42,'ps.fonttype':42})
 fig,axs=plt.subplots(6,3,figsize=(8.6,6.6),sharex='col');fig.subplots_adjust(top=.92,bottom=.12,left=.105,right=.985,hspace=.22,wspace=.32)
 for d,(ds,name)in enumerate(DS):
  rr=real if ds=='Rfam_canonical'else old['primary']
  for part,split in enumerate(['IID','NonIID']):
   row=2*d+part
   for col,(axis,values,label,_)in enumerate(AXES):
    ax=axs[row,col];panel(ax,rr,split,axis,values,'',dataset=ds)
    ax.tick_params(axis='both',labelsize=8.5)
    if row<5:ax.tick_params(axis='x',labelbottom=False)
    else:ax.set_xlabel(label)
    if col==0:ax.set_ylabel(name+' / '+('Non-IID'if part else'IID')+'\nCPU (ms)',fontsize=9)
    if row==0:ax.set_title(['Vary answer size','Vary provider count','Vary quota budget'][col])
 fig.legend(*axs[0,0].get_legend_handles_labels(),loc='upper center',ncol=5,frameon=False);save(fig,'comparison_all')
 groups=[['dann','fedseq_legacy','dann_order','fedseq'],['dann_star','dann_order_star','fedseq_star_laplace','fedseq_star_laplace_zero','fedseq_star']]
 names=[['DANN','+Cold','+Order','FedSeq'],['DANN*','+Order','Lap1','Lap0','FedSeq*']]
 fig,axs=plt.subplots(3,2,figsize=(8.6,4.5));fig.subplots_adjust(top=.88,bottom=.09,left=.085,right=.99,hspace=.55,wspace=.30)
 for d,(ds,name)in enumerate(DS):
  rr=real if ds=='Rfam_canonical'else old['primary']
  for col,algs in enumerate(groups):
   ax=axs[d,col]
   for s,part in enumerate(['IID','NonIID']):
    vals=[cpu(next(x for x in rr if x['dataset']==ds and x['partition']==part and x['section']=='ablation'and x['algorithm']==a))for a in algs]
    ax.bar(np.arange(len(algs))+(s-.5)*.36,vals,.36,color=[COLOR[a]for a in algs],edgecolor='#333',linewidth=.45,hatch='///'if s else None)
   ax.set_xticks(range(len(algs)),names[col],fontsize=9);ax.set_ylabel(name+' CPU (ms)');style(ax)
   if d==0:ax.set_title('Unperturbed'if col==0 else'Perturbed')
 from matplotlib.patches import Patch
 fig.legend(handles=[Patch(facecolor='white',edgecolor='#333',label='IID'),Patch(facecolor='white',edgecolor='#333',hatch='///',label='Non-IID')],loc='upper center',ncol=2,frameon=False);save(fig,'ablation_all')
 # Fig. 9 now compares the same independent variable on all three datasets.
 algs=['baseline','dann','dann_gram2','fedseq']
 def trend(ax,rr,name,gen=None):
  for a in algs:
   g=[x for x in rr if x['algorithm']==a and(gen is None or(x['dataset']==name and x['generator']==gen))];vs=sorted(set(float(x['rho'])for x in g));ys=[];lo=[];hi=[]
   for rho in vs:
    nums=[float(x['mean_total_cpu_ms'])for x in g if float(x['rho'])==rho];assert len(nums)==(3 if gen else 1);ys.append(statistics.mean(nums));lo.append(min(nums));hi.append(max(nums))
   ax.plot(vs,ys,color=COLOR[a],marker='o',ms=3,lw=1.2,label=LABEL[a])
   if gen:ax.fill_between(vs,lo,hi,color=COLOR[a],alpha=.12)
  ax.set_title(name);ax.set_xlabel(r'Family concentration $\rho$');ax.set_xticks(vs);style(ax)
 fig,axs=plt.subplots(1,3,figsize=(9,2.5));fig.subplots_adjust(top=.73,bottom=.23,left=.075,right=.99,wspace=.35)
 for ax,name in zip(axs,['DNA','Symbol']):trend(ax,old['supplement'],name,'swap')
 trend(axs[2],extra,'Rfam');axs[0].set_ylabel('CPU (ms)');fig.legend(*axs[0].get_legend_handles_labels(),loc='upper center',ncol=4,frameon=False);save(fig,'robustness_all')
 # Separate supplementary panels preserve the distinct generator/subgroup questions.
 fig,axs=plt.subplots(1,2,figsize=(8,2.6));fig.subplots_adjust(top=.73,bottom=.23,left=.08,right=.99,wspace=.30)
 for ax,name in zip(axs,['DNA','Symbol']):trend(ax,old['supplement'],name,'edit')
 axs[0].set_ylabel('CPU (ms)');fig.legend(*axs[0].get_legend_handles_labels(),loc='upper center',ncol=4,frameon=False);save(fig,'supplement_edit')
 fig,axs=plt.subplots(1,2,figsize=(8,2.6));fig.subplots_adjust(top=.73,bottom=.23,left=.08,right=.99,wspace=.30)
 for ax,part in zip(axs,['IID','NonIID']):
  for z,a in enumerate(algs):
   vals=[float(next(x for x in fam if x['algorithm']==a and x['partition']==part and x['family']==f)['mean_cpu_ms'])for f in ['RF00001','RF00006']]
   ax.bar(np.arange(2)+(z-1.5)*.18,vals,.18,color=COLOR[a],label=LABEL[a])
  ax.set_title('Rfam / '+('Non-IID'if part=='NonIID'else'IID'));ax.set_xticks([0,1],['5S rRNA','Vault RNA']);style(ax)
 axs[0].set_ylabel('CPU (ms)');fig.legend(*axs[0].get_legend_handles_labels(),loc='upper center',ncol=4,frameon=False);save(fig,'supplement_rfam_family')
 for extn in ['pdf','png']:
  for directory in [PROJ/'figures',PAPER/'figures']:
   for src,dest in [('comparison_all','comparison_three_datasets'),('ablation_all','ablation_three_datasets')]:shutil.copy2(directory/f'{src}.{extn}',directory/f'{dest}.{extn}')
 exp=base['experiment_results.tex'].replace(r'\includegraphics[width=\textwidth]{comparison_all.pdf}',r'\includegraphics[width=.95\textwidth]{comparison_all.pdf}').replace(r'\includegraphics[width=\textwidth]{ablation_all.pdf}',r'\includegraphics[width=.92\textwidth]{ablation_all.pdf}').replace(r'\includegraphics[width=.86\textwidth]{robustness_all.pdf}',r'\includegraphics[width=.95\textwidth]{robustness_all.pdf}')
 exp=exp.replace(r'\subsection{Heterogeneity and Independent Generation}',r'\subsection{Provider Concentration and Robustness}')
 exp=re.sub(r'\\caption\{Compact robustness comparison\..*?\}\n\\label\{fig:robustness\}',r'\\caption{Effect of simulated provider concentration on CPU cost. All panels vary $\\rho$ while retaining each population and its queries. DNA and Symbol average three population seeds at five levels; shading is the seed range. Rfam uses one fixed real collection and assignment seed at three levels. Its unequal family sizes are retained. Each point uses 50 queries and three repeats. DANN+Bigram retains DANN allocation.}\n\\label{fig:robustness}',exp,flags=re.S)
 exp=exp.replace('The edit generator does not preserve character histograms and allows variable record lengths.','The independent edit-generator check (Supplementary Figure S1) does not preserve character histograms and allows variable record lengths.')
 exp=exp.replace('Figure~\\ref{fig:robustness} changes synthetic provider composition at balanced sizes.','Figure~\\ref{fig:robustness} compares all three datasets along the same concentration axis. The synthetic assignments preserve balanced shard sizes.')
 exp=exp.replace('Across the synthetic sweeps,','Across the synthetic main parameter sweeps,')
 exp=exp.replace('Each panel uses its matched ablation cohort; CPU levels should not be compared with a separately timed parameter cohort.','Panels use matched ablation cohorts; absolute CPU levels across separate timing cohorts are not a workload effect.')
 (PAPER/'experiment_results.tex').write_text(exp)
 realtext=base['real_results.tex'];realtext=realtext.replace('The lower-right panel separates the same confirmation queries by source family; its seven vault queries are a descriptive breakdown, not independent confirmation.','Supplementary Figure S2 separates the original confirmation queries by source family (43 5S and seven vault queries); it is a descriptive subgroup analysis.')
 a=realtext.index('Under IID, Baseline');b=realtext.index('The matched ablation',a)
 realtext=realtext[:a]+r'''Under IID, FedSeq averages 101.67 ms versus 749.06 ms for DANN and 916.91 ms for Baseline; under Non-IID the corresponding means are 125.53, 1023.82, and 1127.31 ms. DANN/FedSeq verification counts are 10620.48/1102.30 under IID and 11302.00/1292.72 under Non-IID. FedSeq omits 0.00 and 3.70 providers in both rounds, respectively. DANN+Bigram takes 750.82 and 1069.25 ms. The noisy DANN$^*$/FedSeq$^*$ CPU ratios are 3.67$\times$ and 2.62$\times$, respectively.

'''+realtext[b:]
 a=realtext.index('With the real sequences fixed,')
 realtext=realtext[:a]+r'''With the collection fixed, Figure~\ref{fig:robustness} gives DANN/FedSeq CPU ratios of 7.35$\times$, 7.41$\times$, and 7.23$\times$ at $\rho=0,0.5,1$. All 1,800 clean concentration-test runs are exact. Order filtering remains useful across these assignments; greater concentration alone does not guarantee a larger gain. Supplementary Figure S2 separates the original 43/7 confirmation queries by source family and reports their different verification costs.
'''
 (PAPER/'real_results.tex').write_text(realtext)
 setup=base['real_setup.tex']+'\nFor the Rfam concentration check, we keep this collection and its confirmation queries fixed, set $m=8$, and assign a fraction $\\rho$ of each family to four family-specific home providers while distributing the remainder uniformly. We use $\\rho\\in\\{0,0.5,1\\}$ and assignment seed 20261015; family and provider sizes need not be equal. Six methods (the five main algorithms and DANN+Bigram) add 2,700 runs. These assignments are distinct from the frozen IID/Non-IID parameter-sweep assignments. Source-family plots reuse the original 43/7-query split and appear in the supplement.\n'
 (PAPER/'real_setup.tex').write_text(setup)
 maintext=base['main.tex'];maintext=maintext.replace('In the fallback branch, the first prefix has length $c_i$.','In the fallback branch, every raw origin count is positive and the first prefix has length $a_i$.').replace('the same lemma gives $c_i+k-p_i$','the same lemma gives $a_i+k-p_i$')
 maintext=maintext.replace('Independent cases run on distinct physical cores;','Independent native cases run on distinct CPU cores;')
 maintext=maintext.replace('There are 19 unique main configurations per population/partition,','For the two synthetic datasets there are 19 unique main configurations per population/partition,')
 maintext=maintext.replace('Each case uses 50 queries and three repeats,','Each reported evaluation case uses 50 queries and three repeats,')
 maintext=maintext.replace('The 48 supplementary configurations add 34,200 runs, and the unclustered control adds 1,800.','The 48 synthetic robustness configurations add 34,200 runs, and the unclustered control adds 1,800. Rfam contributes its separately specified 40 main/ablation and three concentration configurations. The encrypted-transport study adds six dataset/partition cases.')
 maintext=maintext.replace('We fix $g=1$ and share a scan backend; the MinSearch index and positional pipeline are excluded~\\cite{minsearch}.','We use the released MinSearch count-signature component with $g=1$ on a shared scan backend; its index and positional pipeline are excluded~\\cite{minsearch}.')
 maintext=maintext.replace('A second request can therefore extend a local prefix without recomputing distances already evaluated.','Algorithm~\\ref{alg:local} implements $\\mathsf{LocalKNN}(t)$ and returns the full prefix, so the two replies may overlap. A second request can therefore extend a local prefix without recomputing distances already evaluated.')
 # Clarify logical versus experimental parallelism and the bound's cost amortization.
 maintext=maintext.replace('Figure~\\ref{fig:architecture} and Algorithm~\\ref{alg:fedseq} give the complete query.','Figure~\\ref{fig:architecture} and Algorithm~\\ref{alg:fedseq} give the complete query. Provider steps are logically independent; the native benchmark executes them serially to sum CPU, whereas the transport experiment uses concurrent processes.')
 maintext=maintext.replace('Every record receives a bound before retrieval, including at zero-quota providers.', 'The stopping comparison uses the full stable key. Equal numeric distances alone do not settle a boundary tie: a candidate with a smaller persistent identifier may still belong in the answer. The tuple comparison in Algorithm~\\ref{alg:local} preserves the same deterministic order used by the oracle.\n\nEvery record receives a bound before retrieval, including at zero-quota providers.')
 maintext=maintext.replace('Bound construction scans signatures and sequences; sorting costs $\\sum_iO(|D_i|\\log|D_i|)$. Broker merges use at most $mk$ summary keys and $O(mk)$ real keys per round. Frontier extraction scans sorted keys past sent identifiers without evaluating new distances.', r'''Let $n_i=|D_i|$ and let $V_i$ count distinct records whose exact distance is evaluated at provider $i$. With a fixed signature dimension and a query of at most 128 bytes, count filtering costs $O(N)$ and the added order scan costs $O(\sum_{x\in D}|x|)$ word operations. Query masks cost $O(m|q|)$ to prepare and are reused within each provider. Sorting the bound keys costs $\sum_iO(n_i\log n_i)$. The exact-distance term is
\begin{equation*}
 \sum_i\sum_{x\in\mathcal V_i}O(|q||x|),\qquad |\mathcal V_i|=V_i.
\end{equation*}
Here $\mathcal V_i$ includes all verified records, not only the returned prefix. This distinction matters when weak bounds force a provider to inspect most of its shard for a request of one result.

The two rounds share their exact-distance cache. A repeated prefix scan can revisit cached keys and update its top-$t$ heap, but never reevaluates a cached distance. Heap maintenance adds $O(H\log(k+1))$ for $H\leq2N$ visited bound entries across the two scans. Frontier extraction builds the sent-identifier set and scans the already sorted bound keys until it finds an unsent record; it performs no new edit-distance computations. Broker merges consume at most $mk$ summary keys and $O(mk)$ real keys per round, using the same stable-key order.

The added bound and certificate are useful when the exact-distance work they avoid exceeds their own scan, sorting, and allocation overhead. Cold scheduling saves real prefix search, not the initial bound construction at every provider. The order-only and cold-only ablations separate these costs. On unstructured data, where nearly all records remain verifiable, the added scan instead becomes overhead; the negative control tests this case directly.

Communication has a separate cost. The allocation methods retain one summary exchange and two retrieval phases even when a provider performs no real prefix search. Unperturbed replies carry the requested real prefixes; the noisy variants fill each retrieval reply to $k$ slots. Thus a smaller $V_i$ can substantially reduce CPU without removing a round-trip boundary or proportionally reducing the padded response. The transport experiment measures this distinction.''')
 (PAPER/'main.tex').write_text(maintext)
 for name in ['algorithms/fedseq.tex','algorithms/star.tex']:
  s=base[name].replace('LocalPrefix','LocalKNN').replace(r'$B_i\gets\mathsf{LocalPrefix}',r'$E_i\gets\mathsf{LocalPrefix}').replace(r'(A_i\cup B_i)',r'(A_i\cup E_i)');(PAPER/name).write_text(s)
 (PAPER/'supplementary.tex').write_text(r'''\documentclass[10pt,letterpaper]{article}
\usepackage[margin=.8in]{geometry}
\usepackage{graphicx,amsmath,booktabs}
\graphicspath{{figures/}}
\renewcommand{\thefigure}{S\arabic{figure}}
\setlength{\parindent}{0pt}
\setlength{\parskip}{4pt}
\title{FedSeq: Supplementary Experimental Checks}
\author{}
\date{}
\begin{document}
\maketitle
\vspace{-2em}
\textbf{Independent edit generation.} This control tests whether the filtering benefit depends on the histogram-preserving swap construction. Four random centers generate 8,000 distinct records through 4--32 edits: insertions and deletions each have probability .2, and substitutions have probability .6. Fifty held-out length-128 queries receive 4--8 distinct substitutions. The three preselected seeds, concentration levels $0,0.5,1$, three repeats, and algorithm settings are those specified in the main manuscript. No new measurements are introduced here.

\begin{figure}[htbp]
\centering
\includegraphics[width=.91\textwidth]{supplement_edit.pdf}
\caption{Independent edit-generator check on DNA and Symbol. CPU means average three population seeds; shaded bands show their range, not confidence intervals. Each seed/level contains 50 queries and three repeats.}
\end{figure}

\textbf{Rfam source-family breakdown.} These panels regroup the same 50 confirmation queries used at the main default setting: 43 5S rRNA and seven vault RNA queries, each repeated three times. They do not constitute a second confirmation sample. All methods use the same database and ownership within each panel. FedSeq reduces verification for both families; under specialized ownership, its mean exact-distance counts are 858.47 for 5S and 3960.29 for vault. The result is consistent with a certificate requiring selective unsent frontiers, rather than provider specialization alone.

\begin{figure}[htbp]
\centering
\includegraphics[width=.91\textwidth]{supplement_rfam_family.pdf}
\caption{Rfam default CPU by query family under the original IID/Non-IID assignments. The family subsets are unequal and descriptive. These are the main confirmation cohort's timings, not the separately measured concentration cohort.}
\end{figure}
\end{document}
''')
 (PAPER/'README.md').write_text(base['README.md'].replace('Figure 9 adds real-sequence ownership and query-family panels; generator-only panels retain their synthetic interpretation.','Figure 9 compares simulated provider concentration on all three datasets. Independent edit-generation and source-family panels are in the separate supplement.')+'\nFinal review: Figures 7/8 are compact; Figure 9 compares concentration for all three datasets. Distinct generator/family checks appear in supplementary.tex/PDF. Build the supplement with `pdflatex supplementary.tex`. Final consistency pass: real_data/final_review/revise.py, applied after the historical layout integration.\n')
 # Stable record of the quantitative claims checked during this revision.
 assert old['primary_runs']==62400 and old['supplement_runs']==34200 and old['unstructured_runs']==1800 and old['clean_runs']==67200 and old['clean_failures']==0
 for alg,strict,dist in [('dann_star',644,363),('fedseq_star',258,81)]:
  rr=[x for x in old['primary']if x['algorithm']==alg and x['section']!='ablation'];assert sum(x['runs']for x in rr)==11400;assert sum(x['strict_failures']for x in rr)==strict;assert sum(x['distance_failures']for x in rr)==dist
 audit=dict(fig9_common_axis='simulated family concentration rho',no_new_measurements=True,raw_results_unchanged=True,clean_counts_checked=True,main_noisy_counts_checked=True,notation='B_i certificate count; E_i second-round candidate set',cohort_scope='synthetic main, robustness, Rfam confirmation/concentration and transport distinguished',privacy_scope='conditional protected joint quota view, ideal sampler',supplement='independent edit generator and Rfam source-family breakdown')
 (HERE/'consistency_checks.json').write_text(json.dumps(audit,indent=2));print('Figures and consistency edits complete')
if __name__=='__main__':main()
