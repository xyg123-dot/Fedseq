#!/usr/bin/env python3
"""Regroup the same measured cases into four-column figures."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent;PAPER=ROOT.parent.parent/'paper'
def main():
 p=PAPER/'main.tex';s=p.read_text();a=s.index('\\begin{figure*}',s.index('\\input{experiment_setup}'));b=s.index('\\input{table_accuracy}',a)
 s=s[:a]+r'''\begin{figure*}[t]
\centering
\includegraphics[width=\textwidth]{retrieval_all.pdf}
\caption{CPU versus retrieval parameters (ms). Rows: DNA, Symbol, Rfam. Columns: IID/$k$, Non-IID/$k$, IID/$m$, Non-IID/$m$. All five methods share the same measured cases; erroneous noisy runs remain included.}
\label{fig:comparison}
\end{figure*}
\begin{figure*}[t]
\centering
\includegraphics[width=\textwidth]{privacy_ablation.pdf}
\caption{Quota budgets and module ablations (ms). Rows: DNA, Symbol, Rfam. Columns: IID/$\varepsilon$, Non-IID/$\varepsilon$, clean ablation, noisy ablation. Lines show all five methods; solid/hatched bars denote IID/Non-IID. Lap1/Lap0 are frontier Laplace variants with floors one/zero. Ablations use matched cohorts; Rfam clean budget references reuse the default cohort.}
\label{fig:ablation}
\label{fig:privacy}
\end{figure*}
'''+s[b:];s=s.replace('\\input{table_unstructured}\n','');p.write_text(s)
 p=PAPER/'experiment_results.tex';s=p.read_text();a=s.index('\\begin{figure*}');b=s.index('\\end{figure*}',a)+len('\\end{figure*}');s=s[:a]+s[b:]
 s=s.replace(r'Figures~\ref{fig:comparison} and \ref{fig:comparison-symbol} compare the two synthetic datasets.',r'Figure~\ref{fig:comparison}(a)--(h) compares the two synthetic datasets.')
 s=s.replace('At $\\varepsilon=1$, the DANN',r'Figure~\ref{fig:privacy}(a,b,e,f,i,j) varies the joint quota budget. At $\varepsilon=1$, the DANN',1)
 s=s.replace(r'The clean panels of Figure~\ref{fig:ablation} isolate each module.',r'The clean panels of Figure~\ref{fig:ablation}(c,g,k) isolate each module.')
 a=s.index('\\begin{figure}');b=s.index('\\end{figure}',a)+len('\\end{figure}')
 s=s[:a]+r'''\begin{figure*}[t]
\centering
\includegraphics[width=\textwidth]{robustness_all.pdf}
\caption{Structure and ownership controls (ms). Panels (a)--(c) vary family concentration $\rho$ on DNA, Symbol and Rfam, retaining each population and its queries. Synthetic lines average three population seeds; shading shows their range. Rfam retains unequal family volumes under one assignment seed. Panel (d) replots the existing unclustered DNA control; bars show means and error bars the range of three seed means. All methods make 8,000 exact comparisons there. Each seed/configuration uses 50 queries and three repeats.}
\label{fig:robustness}
\end{figure*}
'''+s[b:]
 s=s.replace(r'Figure~\ref{fig:robustness} compares all three datasets',r'Figure~\ref{fig:robustness}(a)--(c) compares all three datasets')
 s=s.replace('The unclustered control removes centers and family structure.',r'Figure~\ref{fig:robustness}(d) removes centers and family structure in the unclustered control.')
 p.write_text(s)
 p=PAPER/'real_results.tex';s=p.read_text().replace(r'Figure~\ref{fig:comparison-rfam} and Figure~\ref{fig:ablation}(c,f)',r'Figure~\ref{fig:comparison}(i)--(l) and Figure~\ref{fig:ablation}(i)--(l)').replace(r'Figure~\ref{fig:robustness} gives clean CPU ratios',r'Figure~\ref{fig:robustness}(c) gives clean CPU ratios');p.write_text(s)
 p=PAPER/'table_raw_rfam.tex';s=p.read_text().replace(r'Figure~\ref{fig:comparison-rfam}',r'Figure~\ref{fig:comparison}(i)--(l)');p.write_text(s)
if __name__=='__main__':main()
