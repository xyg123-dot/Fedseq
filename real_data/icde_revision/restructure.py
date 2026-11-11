#!/usr/bin/env python3
from pathlib import Path
import json,re
ROOT=Path(__file__).resolve().parent;PAPER=ROOT.parent.parent/'paper'
def main():
 base=json.loads((ROOT/'base_text.json').read_text());s=base['main.tex']
 a=s.index('\\section{Introduction}');b=s.index('\\section{System Model',a);s=s[:a]+(ROOT/'introduction.tex').read_text()+s[b:]
 s=s.replace('\\section{System Model and Preliminaries}','\\section{System Model and Preliminaries}\n\\label{sec:model}')
 a=s.index('\\subsection{Computational Cost}');b=s.index('\\section{\\texorpdfstring',a);cost=s[a:b];s=s[:a]+s[b:]
 a=s.index('\\section{\\texorpdfstring');b=s.index('\\subsection{Neighboring Relation',a)
 private=s[a:b].replace(r'\section{\texorpdfstring{FedSeq$^*$}{FedSeq*} and Quota Privacy}',r'\section{Private FedSeq Query Processing}').replace(r'\label{sec:noise}',r'\label{sec:private}')
 e=s.index('\\section{Experimental Evaluation}',b);security=s[b:e]
 security=security.replace('\\subsection{Neighboring Relation and Protected View}','\\subsection{Security Model and Protected View}').replace('\\subsection{Sensitivity and Geometric-Mechanism Analysis}','\\subsection{Sensitivity of Adaptive Allocation}').replace('\\subsection{Padding Tail and Execution Interface}','\\subsection{Retrieval Accuracy and Execution Interface}')
 cost=cost.replace('\\subsection{Computational Cost}','\\subsection{Computational Complexity}')
 cost=cost.replace('Order filtering and certification pay off when saved verification exceeds their scan and allocation overhead. Cold scheduling does not remove initial bound construction; the unstructured control tests the case where that added cost brings little pruning. Communication is separate: allocation retains a summary exchange and two retrieval phases. Clean replies carry real prefixes, while noisy replies occupy $k$ slots. CPU savings therefore need not remove round-trip boundaries or padded payloads; the transport experiment measures this distinction.','The bound and sorting costs are paid even at a cold provider; the saved term is exact verification. Thus the worst case still verifies every record, and improvement requires pruning to repay the additional scan. Table~\\ref{tab:complexity} summarizes the stages. Here $\\mathcal L=\\sum_x|x|$, $V_L=\\sum_i\\sum_{x\\in\\mathcal V_i}|x|$, and $Q=|q|$; the order-scan term assumes the supported short-query path.\n\\input{table_complexity}\n\n\\subsection{Communication and Working Memory}\nEach provider sends at most $k$ bound keys and two prefixes of at most $k$ real records. The clean procedure therefore uses $O(mk)$ key/record slots over a fixed summary exchange and two retrieval phases. The noisy procedure fills every reply with $k$ real or dummy slots, preserving the same slot bound even when a real quota is zero. These are slot counts; encoded bytes also depend on the record representation.\n\nPer-query sorted keys and distance caches occupy $O(N)$ entries across providers. The broker retains $O(mk)$ candidates, while an exact pair uses linear dynamic-programming workspace. At fixed query width, bound signatures and masks do not change the asymptotic entry count. CPU savings can therefore coexist with fixed round-trip boundaries and padded payloads, as tested in Section~\\ref{sec:transport}.')
 cost=r'''\subsection{Computational Complexity}
Let $Q=|q|$, $\mathcal L=\sum_x|x|$, and $\mathcal V_i$ be the records verified at $P_i$. Table~\ref{tab:complexity} bounds each stage. At fixed signature dimension, supported short queries add one linear order scan to count filtering. Caching limits exact work to distinct verified records across both rounds; $H\leq2N$ counts visited heap entries. Cold providers still pay for bounds and sorting. The worst case verifies every record, so speedup requires saved verification to repay the added scan.
\input{table_complexity}

\subsection{Communication and Working Memory}
A summary and two prefixes each contain at most $k$ keys or records per provider, giving $O(mk)$ slots. Noisy replies pad to $k$ slots even at zero real quota; encoded bytes depend on record representation. Sorted keys and caches occupy $O(N)$ entries across providers; broker candidates use $O(mk)$ entries, and exact pair verification uses linear workspace. Fixed rounds and padded replies explain why CPU and latency gains can differ (Section~\ref{sec:transport}).

'''
 security=security.replace(r'Quota privacy extends to an external transcript only if every additional observation is a data-independent function of the private quota view and public information. This requires a fixed contact schedule and protection of raw broker states and reply contents. Host-visible branches, memory accesses, timing, and plaintext frontiers require additional protection; fixed-length dummy replies alone address message cardinality. Differentially oblivious operators~\cite{do,adore} provide the relevant execution framework. Our theorem is therefore stated for the defined quota view, while the local benchmark and encrypted transport measure its algorithmic and communication costs.',r'Extending quota privacy to an external transcript requires all further observations to be post-processing of private quotas and public information. This entails a fixed contact schedule and protected raw states and replies. Padding addresses message cardinality; branches, memory accesses and timing require additional protection, as in differentially oblivious execution~\cite{do,adore}. The benchmark measures costs under the stated quota view.')
 cost+=(ROOT/'cost_interpretation.tex').read_text()
 analysis='\\section{Complexity and Security Analysis}\n\\label{sec:analysis}\n\\label{sec:noise}\nWe analyze query costs by stage and then state the protected view, sensitivity and privacy guarantee. The execution model in Section~\\ref{sec:model} supplies the assumptions for both analyses.\n\n'+cost+security
 s=s[:a]+private+analysis+s[e:]
 # Replace the 18-panel full-page float with three six-panel double-column floats.
 a=s.index('\\begin{figure*}',s.index('\\input{experiment_setup}'));b=s.index('\\end{figure*}',a)+len('\\end{figure*}')
 floats=[]
 for asset,label,name in [('dna','comparison','DNA'),('symbol','comparison-symbol','Symbol'),('rfam','comparison-rfam','Rfam')]:
  floats.append(r'''\begin{figure*}[t]
\centering
\includegraphics[width=\textwidth]{comparison_'''+asset+r'''.pdf}
\caption{'''+name+r''' CPU comparison (ms). Panels (a)--(c): IID; (d)--(f): Non-IID. Each group varies $k$, $m$, then composed quota budget $\varepsilon$. All five methods are shown; errors remain included.'''+(' Clean budget references reuse the default cohort.'if asset=='rfam'else'')+r'''}
\label{fig:'''+label+r'''}
\end{figure*}''')
 s=s[:a]+'\n'.join(floats)+s[b:]
 s=s.replace(r"Provider steps are logically independent; the native benchmark executes them serially to sum CPU, whereas the transport experiment uses concurrent processes. Providers reuse exact distances between rounds. The stronger bound operates in both allocation branches; FedSeq specializes DANN's two-round template~\cite{fedknn} with zero-permitting refinement.",r"Both allocation branches use the stronger bound and reuse exact distances across rounds. FedSeq specializes DANN's two-round template~\cite{fedknn} with zero-permitting refinement.")
 s=s.replace('As the noise rate decreases, both dispersion and the positive padding shift increase, making requests more likely to reach $k$. Larger requests add few distance calculations at a provider whose scan is already cached. They add much more work when the clean query would stop early.',r'The effect of padding on cached and early-stopping providers is evaluated in Section~\ref{sec:exp}.')
 s=s.replace("At the revised first-round default $\\varepsilon=1$, $\\beta_1=.25$ and $\\lambda=.05$, $\\eta_1=9$, giving a zero-request probability near .0593. Six initially unselected providers therefore yield about 5.64 expected positive first requests. Figure~\\ref{fig:quota-noise} makes the underlying trade-off explicit: a zero clamp permits omission, but positive padding deliberately favors larger requests.","At $\\varepsilon=1$, $\\beta_1=.25$ and $\\lambda=.05$, $\\eta_1=9$ gives zero-request probability .0593 (Figure~\\ref{fig:quota-noise}).")
 s=s.replace(' Real predecessors, rather than an empty initial origin count, certify omission. The clean fallback retains DANN allocation when every provider has a positive origin count.','')
 s=s.replace(' Our analysis concerns a particular adaptive release: the second target depends on exact prefixes retrieved under the first noisy requests. Fixing that released history yields the conditional sensitivity needed to compose both rounds under one query budget.',' The conditional sensitivity analysis here composes two rank-derived quota releases.')
 (PAPER/'main.tex').write_text(s)
 exp=base['experiment_results.tex'].replace('Figure~\\ref{fig:comparison}(a)--(l) compares the two synthetic datasets.','Figures~\\ref{fig:comparison} and \\ref{fig:comparison-symbol} compare the two synthetic datasets.').replace(r'\includegraphics[width=.92\textwidth]',r'\includegraphics[width=\textwidth]')
 exp=exp.replace('Panels (a,b): DNA; (c,d): Symbol; (e,f): Rfam. Left:','Panels (a)--(c): DNA, Symbol, Rfam clean ablations:').replace(' Right: DANN',' Panels (d)--(f): the corresponding noisy ablations: DANN')
 a=exp.index('\\begin{figure*}',exp.index('\\label{fig:ablation}'));b=exp.index('\\end{figure*}',a)+len('\\end{figure*}')
 block=exp[a:b].replace('figure*','figure').replace(r'width=.95\textwidth',r'width=\columnwidth')
 block=block.replace('Each point uses 50 queries and three repeats. DANN+Bigram retains DANN allocation.','Each point uses 50 queries and three repeats; DANN+Bigram retains DANN allocation.')
 exp=exp[:a]+exp[b:]
 # Put concentration plot beside the relevant discussion instead of queueing all floats together.
 needle='\\subsection{Provider Concentration and Robustness}';exp=exp.replace(needle,needle+'\n'+block)
 (PAPER/'experiment_results.tex').write_text(exp)
 rr=base['real_results.tex'].replace(r'Figure~\ref{fig:comparison}(m)--(r)',r'Figure~\ref{fig:comparison-rfam}').replace(r'Figure~\ref{fig:ablation}(e,f)',r'Figure~\ref{fig:ablation}(c,f)');(PAPER/'real_results.tex').write_text(rr)
 for name in ['experiment_setup.tex','real_setup.tex','table_raw_rfam.tex']:(PAPER/name).write_text(base[name])
 # Reference the actual three dataset comparisons, never a hard-coded former number range.
 p=PAPER/'table_raw_rfam.tex';z=p.read_text().replace(r'Figures~\ref{fig:comparison}--\ref{fig:robustness}',r'Figure~\ref{fig:comparison-rfam} and the Rfam ablation and concentration panels');p.write_text(z)
 (PAPER/'table_complexity.tex').write_text(r'''\begin{table}[t]
\centering
\caption{Query CPU bounds by stage. $Q=|q|$, $\mathcal L=\sum_x|x|$, $V_L=\sum_i\sum_{x\in\mathcal V_i}|x|$; $H$ counts visited heap entries.}
\label{tab:complexity}
\small
\begin{tabular}{@{}ll@{}}
\toprule
Stage & CPU bound \\
\midrule
Count and short-query order bounds & $O(N+\mathcal L)$ \\
Local key sorting & $O(\sum_i n_i\log(n_i+1))$ \\
Distinct exact comparisons & $O(QV_L)$ \\
Prefix heap updates & $O(H\log(k+1))$ \\
Broker merge and refinement & $O(mk\log(mk+1))$ \\
Two noisy quota vectors & $2m$ scalar draws \\
\bottomrule
\end{tabular}
\end{table}
''')
 print('Restructured Introduction, private method, independent analysis, compact comparison floats.')
if __name__=='__main__':main()
