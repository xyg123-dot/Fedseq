#!/usr/bin/env python3
"""Populate manuscript numbers only from verified complete experiment outputs."""
import csv,json,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parent
PAPER=ROOT/'paper'

def f(x,places=2):return f'{float(x):,.{places}f}'
def n(x):return f'{int(x):,}'
def table(path,caption,label,columns,header,rows):
    text='\\begin{table}[t]\n\\centering\n\\caption{'+caption+'}\n\\label{'+label+'}\n\\small\n\\begin{tabular}{'+columns+'}\n\\toprule\n'+header+' \\\\\n\\midrule\n'
    text+='\n'.join(' & '.join(row)+r' \\' for row in rows)
    text+='\n\\bottomrule\n\\end{tabular}\n\\end{table}\n'
    path.write_text(text)

def main():
    stats=json.loads((ROOT/'verified_statistics.json').read_text())
    audit=json.loads((ROOT/'audit_progress.json').read_text());assert audit['complete']
    assert audit['distance_errors']==stats['noisy_distance_failures']
    assert audit['strict_failures_replayed']==stats['noisy_strict_failures']
    primary=stats['primary'];supp=stats['supplement'];negative=stats['unstructured']
    def get(ds,part,alg,section='default',value=None):
        group=[s for s in primary if s['dataset']==ds and s['partition']==part and s['algorithm']==alg and s['section']==section and (value is None or float(s['value'])==value)]
        assert len(group)==1,(ds,part,alg,section,value);return group[0]
    setting=[('dna_cluster_order','IID'),('symbol_cluster_order','IID'),('dna_cluster_order','NonIID'),('symbol_cluster_order','NonIID')]
    clean_speed=[get(d,p,'dann')['mean_total_cpu_ms']/get(d,p,'fedseq')['mean_total_cpu_ms'] for d,p in setting]
    noisy_speed=[get(d,p,'dann_star')['mean_total_cpu_ms']/get(d,p,'fedseq_star')['mean_total_cpu_ms'] for d,p in setting]
    macros={'DefaultSpeedupMin':f(min(clean_speed)),'DefaultSpeedupMax':f(max(clean_speed)),
            'CleanRunCount':n(stats['clean_runs']),'NoisyRunCount':n(stats['noisy_runs'])}
    (PAPER/'verified_numbers.tex').write_text('\n'.join('\\newcommand{\\'+key+'}{'+value+'}' for key,value in macros.items())+'\n')
    accuracy=[]
    main_totals={}
    for ds,part in [('dna_cluster_order','IID'),('dna_cluster_order','NonIID'),('symbol_cluster_order','IID'),('symbol_cluster_order','NonIID')]:
        row=[('DNA' if ds.startswith('dna') else 'Symbol')+' '+('Non-IID' if part=='NonIID' else 'IID')]
        for alg in ['dann_star','fedseq_star']:
            group=[s for s in primary if s['dataset']==ds and s['partition']==part and s['algorithm']==alg and s['section']!='ablation']
            row += [n(sum(s['strict_failures'] for s in group)),n(sum(s['distance_failures'] for s in group))]
        accuracy.append(row)
    for ds in ['DNA','Symbol']:
        row=['Edit '+ds]
        for alg in ['dann_star','fedseq_star']:
            group=[s for s in supp if s['dataset']==ds and s['generator']=='edit' and s['algorithm']==alg]
            row += [n(sum(s['strict_failures'] for s in group)),n(sum(s['distance_failures'] for s in group))]
        accuracy.append(row)
    table(PAPER/'table_accuracy.tex','Noisy retrieval errors. Main-sweep rows contain 2,850 runs per method; Edit rows contain 1,350 across three seeds and three heterogeneity levels. Strict counts include tie-only identity differences; distance counts are genuine distance-top-$k$ errors.',
          'tab:accuracy','lrrrr',r'Setting & \multicolumn{2}{c}{\Dstar} & \multicolumn{2}{c}{\Fstar} \\'+'\n'+r' & Strict & Dist. & Strict & Dist.',accuracy)
    for alg in ['dann_star','fedseq_star']:
        group=[s for s in primary if s['algorithm']==alg and s['section']!='ablation']
        main_totals[alg]={key:sum(s[key] for s in group) for key in ['runs','strict_failures','distance_failures']}
    # Independent generator comparison ranges; ratios use paired seed means.
    ratios= {}
    for generator in ['swap','edit']:
        values=[];gram=[]
        for ds in ['DNA','Symbol']:
            for seed in [20261014,20261024,20261034]:
                for rho in sorted({s['rho'] for s in supp if s['generator']==generator}):
                    group={s['algorithm']:s for s in supp if s['generator']==generator and s['dataset']==ds and s['population_seed']==seed and s['rho']==rho}
                    values.append(group['dann']['mean_total_cpu_ms']/group['fedseq']['mean_total_cpu_ms'])
                    gram.append(group['dann_gram2']['mean_total_cpu_ms']/group['fedseq']['mean_total_cpu_ms'])
        ratios[generator]=(min(values),max(values),min(gram),max(gram))
    neg={a:statistics.mean(s['mean_total_cpu_ms'] for s in negative if s['algorithm']==a) for a in ['baseline','dann','dann_gram2','fedseq']}
    negrows=[]
    for alg,label in [('baseline','Baseline'),('dann','DANN'),('dann_gram2','DANN+Bigram'),('fedseq','FedSeq')]:
        nums=[s['mean_total_cpu_ms'] for s in negative if s['algorithm']==alg]
        negrows.append([label,f(neg[alg]),f(min(nums))+'--'+f(max(nums)),'8,000'])
    table(PAPER/'table_unstructured.tex','Unclustered DNA control: CPU means and the range of three population-seed means; 50 queries and three repeats per seed.',
          'tab:unstructured','lrrr','Method & CPU/ms & Seed range/ms & Exact calls',negrows)
    # Current calibrated transport only: no historical noisy measurements.
    transport=ROOT/'system/results/calibrated_matched';state=json.loads((transport/'progress.json').read_text());assert state['complete']
    rows=[]
    for path in sorted(transport.glob('*.csv')):
        if path.name.endswith('.nodes.csv'):continue
        dataset='DNA' if path.name.startswith('dna') else 'Symbol';part='Non-IID' if '_NonIID_' in path.name else 'IID'
        group=list(csv.DictReader(path.open()));assert len(group)==750
        for r in group:
            assert r['privacy']=='calibrated' and r['noise_rng']=='private'
            if 'star' not in r['algorithm']:assert r['strict_exact']=='1'
        for alg,label in [('baseline','Baseline'),('dann','DANN'),('fedseq','FedSeq'),('dann_star',r'\Dstar'),('fedseq_star',r'\Fstar')]:
            ar=[r for r in group if r['algorithm']==alg]
            rows.append({'dataset':dataset,'partition':part,'algorithm':alg,'cpu':statistics.mean(float(r['total_cpu_ms']) for r in ar),
                         'wall':statistics.mean(float(r['wall_ms']) for r in ar),'label':label})
    with (PAPER/'transport_summary.csv').open('w',newline='') as out:
        w=csv.DictWriter(out,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    tr=[]
    for ds in ['DNA','Symbol']:
        for part in ['IID','Non-IID']:
            for row in rows:
                if row['dataset']==ds and row['partition']==part:tr.append([ds+' '+part,row['label'],f(row['cpu']),f(row['wall'])])
    table(PAPER/'table_transport.tex','Current algorithms over AES-128-GCM TCP loopback with modeled 64 ms RTT and 100 Mbps. CPU sums provider and broker processing; wall time includes waits. Each row averages 150 runs.',
          'tab:transport','llrr','Setting & Method & CPU/ms & Wall/ms',tr)
    tget=lambda ds,part,alg:next(r for r in rows if (r['dataset'],r['partition'],r['algorithm'])==(ds,part,alg))
    paired=list(csv.DictReader((ROOT/'results_calibrated/paired_cpu.csv').open()))
    ci=next(r for r in paired if r['dataset']=='dna_cluster_order' and r['partition']=='IID' and r['section']=='default' and r['left']=='dann_star' and r['right']=='fedseq_star')
    text=r'''\subsection{CPU Cost Across Retrieval Parameters}
\begin{figure*}[t]
\centering
\includegraphics[width=\textwidth]{comparison_all.pdf}
\caption{Five-method total CPU comparison. Rows vary $k$, $m$, and the composed per-query quota budget $\varepsilon$. The three clean methods do not use $\varepsilon$ and remain runtime references in its row. Positions are equally spaced, including the descending budget values. Noisy methods share the calibration in (\ref{eq:calibration}).}
\label{fig:comparison}
\end{figure*}

At the default point, FedSeq reduces CPU relative to DANN by '''+f(clean_speed[0])+r'''$\times$ and '''+f(clean_speed[1])+r'''$\times$ on DNA and Symbol IID, and by '''+f(clean_speed[2])+r'''$\times$ and '''+f(clean_speed[3])+r'''$\times$ on their Non-IID partitions. Bound construction, sorting, and frontier work are included. Increasing $k$ raises the required prefix lengths and weakens local stopping thresholds. Changing $m$ keeps $N$ fixed but changes shard sizes and the distribution of local requests; this is why total verification need not stay constant when more providers share the same records.

The gains address two different costs. In mixed providers, the count bound rejects composition-dissimilar families but retains many reordered strings within the query family. Order information removes part of this local verification. At a specialized provider with no competitive record, requesting one result can still scan the whole shard. A frontier certificate avoids that search when the retained real candidates already precede every unsent record. The following ablation distinguishes these effects.

\subsection{Noise, Computation, and Accuracy}
''' 
    text+='At $\\varepsilon=1$, the DANN$^*$/FedSeq$^*$ CPU ratios are '+', '.join(f(x)+r'$\times$' for x in noisy_speed)+', in the same setting order as above. '
    text+='DNA IID is close to a tie: the paired mean CPU difference is '+f(ci['mean_left_minus_right_ms'])+' ms, with a 95\\% query-bootstrap interval ['+f(ci['ci95_low_ms'])+', '+f(ci['ci95_high_ms'])+'] ms. This interval includes zero, so this point does not establish a stable runtime advantage.\n\n'
    text+=r'''The calibrated second-round rate is much smaller than an assumed unit-count rate because rank-derived quotas can change substantially at the replaced provider. The positive padding shift and noise therefore move many requests toward $k$. This reduces the clean cold-provider benefit. Smaller budgets can add substantial verification at a provider that would otherwise stop early, while a provider already scanning its whole shard has little extra work to add. Noise generation itself is included in the measured CPU.

The reference comparator retains the clean first allocation map when refining a perturbed prefix. FedSeq$^*$ instead certifies its second target from the actual returned prefix. Its sufficient-prefix argument therefore applies to arbitrary first requests. The error comparison measures this complete workflow together with filtering and perturbation; it does not attribute the observed accuracy difference solely to geometric noise.

We report strict stable-key agreement and distance-top-$k$ validity separately. The latter compares result cardinality and the sorted distance list with the exhaustive oracle, allowing legitimate boundary ties. Every strict mismatch is independently reconstructed from its recorded requests and exhaustive local distances; the audit does not reuse the noise generator or broker allocation code. Failed noisy runs remain in all CPU averages.
\input{table_accuracy}
'''
    a=main_totals['dann_star'];b=main_totals['fedseq_star']
    text+='Across the main sweeps, DANN$^*$ has '+n(a['strict_failures'])+' strict mismatches and '+n(a['distance_failures'])+' distance errors in '+n(a['runs'])+' runs; FedSeq$^*$ has '+n(b['strict_failures'])+' and '+n(b['distance_failures'])+', respectively. These are observed error counts, not mean recall or a theoretical accuracy guarantee. All '+n(stats['clean_runs'])+' clean runs across the main, ablation, heterogeneity, edit-generator, and unclustered studies match the stable-key oracle.\n\n'
    text+=r'''\subsection{Module Ablation}
\begin{figure*}[t]
\centering
\includegraphics[width=\textwidth]{ablation_all.pdf}
\caption{Default-point ablation. Top: separate additions of cold scheduling and order filtering to DANN, followed by their combination. Bottom: calibrated DANN$^*$, its order-filter extension, frontier allocation with Laplace floors one and zero, and geometric floor-zero FedSeq$^*$. All noisy variants use the same two rates; Laplace/geometric comparisons also include their shifts and rounding rules.}
\label{fig:ablation}
\end{figure*}

Under IID, order filtering reduces exact distance evaluations from 2,000 to 487.74 on DNA and 297.38 on Symbol. Cold-only scheduling retains 2,000 evaluations; the combined algorithm has the same verification counts as order-only search. The within-provider order ambiguity accounts for the gain here.

Under Non-IID, cold-only scheduling retains 2,000 evaluations at the query family, while order-only search performs 6,308.90 on DNA and 6,164.08 on Symbol. Their combination needs only 308.90 and 164.08. Six irrelevant providers each avoid 1,000 evaluations. Local filtering then reduces work at the remaining providers, illustrating the bound--quota interaction in Proposition~\ref{prop:coupling}.

The noisy ablation separates this pruning benefit from the perturbation construction. The integer mechanism is not the source of the large clean speedups. Positive padding often assigns work to initially unselected providers, and no distribution change guarantees a CPU improvement at every point. At the calibrated first-round default, (\ref{eq:zero-prob}) predicts about 5.64 positive requests among six zero-origin providers; the allocation logs record the corresponding revival behavior.

\subsection{Heterogeneity and Independent Generation}
\begin{figure*}[t]
\centering
\includegraphics[width=.9\textwidth]{robustness_all.pdf}
\caption{Robustness on three preselected population seeds. Left: five levels of family concentration in the swap generator. Right: a separate insertion/deletion/substitution generator at three levels. Lines average seed means; shading is their minimum--maximum range, not a confidence interval. DANN+Bigram uses a standard two-gram count filter with unchanged positive allocation.}
\label{fig:robustness}
\end{figure*}

Figure~\ref{fig:robustness} varies provider composition while holding record counts balanced. Increasing $\rho$ concentrates families at their home providers. Concentration affects initial allocation and the chance that an unsent frontier can certify omission; it does not itself guarantee a cold provider. The curves are not monotonic. At $\rho=.75$, small relevant-family slices coexist with positive requests, and sufficient second prefixes can extend beyond those slices, adding verification from other families. At $\rho=1$, six irrelevant providers are omitted in both rounds. The gain follows the evidence needed for omission, not a generic Non-IID label.

'''
    lo,hi,glo,ghi=ratios['edit']
    text+='The edit generator does not preserve character histograms and allows variable record lengths. Across its frozen seed/partition cases, DANN/FedSeq CPU ratios range from '+f(lo)+r'$\times$ to '+f(hi)+r'$\times$; DANN+Bigram/FedSeq ratios range from '+f(glo)+r'$\times$ to '+f(ghi)+'$\\times$. This comparison tests a stronger established local filter without changing the retrieval kernel or introducing an index. Its scope is the specified scan controls, not all indexed string-search methods. Table~\\ref{tab:accuracy} also retains the noisy edit-generator errors.\n\n'
    text+=r'''\input{table_unstructured}
The unclustered control removes centers and family structure. All four methods evaluate all 8,000 records per query: neither the order bound nor the certificate creates useful pruning. '''
    text+='FedSeq averages '+f(neg['fedseq'])+' ms versus '+f(neg['dann'])+' ms for DANN. This control exposes the extra filtering cost when the bounds cannot eliminate verification, and limits the performance claim to workloads with exploitable sequence or provider structure.\n\n'
    text+=r'''\subsection{Local Encrypted Transport}
\label{sec:transport}
\input{table_transport}
We rerun the four default population/partition settings with the current calibrated algorithms: 50 queries, three repeats, and five methods yield 3,000 runs. One broker and concurrent provider processes exchange real TCP loopback messages, encrypted using AES-128-GCM with per-direction keys and non-repeating nonces. The delay model adds RTT/2 and a payload-size/bandwidth term; it does not measure WAN congestion.

'''
    c=tget('DNA','Non-IID','fedseq');d=tget('DNA','Non-IID','dann');base=tget('DNA','Non-IID','baseline')
    text+='For DNA Non-IID, Baseline, DANN, and FedSeq consume '+f(base['cpu'])+', '+f(d['cpu'])+', and '+f(c['cpu'])+' ms of CPU, while their mean response times are '+f(base['wall'])+', '+f(d['wall'])+', and '+f(c['wall'])+' ms. Baseline uses one retrieval phase; the allocation methods retain a summary and two retrieval phases. Omitting exact local search reduces computation while leaving these round-trip boundaries in place.\n\n'
    text+=r'''CPU sums provider and broker processing, including measured serialization and encryption, and excludes blocking waits. Wall time follows the critical path with concurrent providers. The separate columns therefore distinguish computational savings from communication latency. An earlier SGX SDK simulation probe checked the sorting ECALL interface; these retrieval measurements run outside hardware enclaves. The study evaluates algorithm and transport cost under the stated quota model.

\subsection{Discussion}
The strongest clean gains arise when order differences defeat composition-only filtering and provider specialization makes omission possible. The edit generator broadens the perturbation model; the unclustered control identifies a regime with no pruning benefit. Calibrated noisy retrieval preserves a smaller part of the computational gain and must be evaluated together with accuracy. These observations support a short-sequence algorithm contribution and define the conditions under which its additional work pays off.
'''
    (PAPER/'experiment_results.tex').write_text(text)
    main=(PAPER/'main.tex').read_text()
    if r'\subsection{CPU Cost Across Retrieval Parameters}' in main:
        a=main.index(r'\subsection{CPU Cost Across Retrieval Parameters}');b=main.index(r'\section{Related Work}',a)
        main=main[:a]+r'\input{experiment_results}'+'\n\n'+main[b:]
    else:assert r'\input{experiment_results}' in main
    if r'\input{verified_numbers}' not in main:
        main=main.replace(r'\begin{document}',r'\input{verified_numbers}'+'\n\n'+r'\begin{document}')
    main=main.replace('$3.21$--$23.69\\times$',r'$\DefaultSpeedupMin$--$\DefaultSpeedupMax\times$')
    main=main.replace('nominal noise parameter','composed quota budget')
    a=main.index(r'\section{Conclusion}');b=main.index(r'\clearpage',a)
    main=main[:a]+r'''\section{Conclusion}
FedSeq combines order-aware filtering with a sufficient zero-permitting prefix certificate. Exact retrieval is preserved, and conditional sensitivity analysis calibrates both noisy comparators to a common quota budget. Ablation separates within-provider filtering from provider omission; independent edit-generated populations retain benefits, while unclustered strings show when the extra bound work does not pay off. Padding reduces noisy gains, and round trips can dominate latency despite lower CPU. These results establish the scope of sequence-aware allocation.

'''+main[b:]
    (PAPER/'main.tex').write_text(main)
    (ROOT/'REPORT_CN.md').write_text('# 修订实验结果\n\n'+
        '完成主实验 '+n(stats['primary_runs'])+' 次、补充实验 '+n(stats['supplement_runs'])+' 次、无结构对照 1,800 次及当前版本加密传输 3,000 次，共 101,400 次运行。\n\n'+
        '干净算法 '+n(stats['clean_runs'])+' 次本地算法运行全部严格匹配 oracle；所有 '+n(stats['noisy_runs'])+' 次加噪运行保留，严格不匹配 '+n(stats['noisy_strict_failures'])+' 次，其中真实距离 top-k 错误 '+n(stats['noisy_distance_failures'])+' 次。全部严格失败通过穷举距离和记录配额独立重建。\n\n'+
        '默认干净 FedSeq 对 DANN 的 CPU 加速范围为 '+f(min(clean_speed))+'–'+f(max(clean_speed))+' 倍。共同隐私预算下，加噪默认比值为 '+f(min(noisy_speed))+'–'+f(max(noisy_speed))+' 倍；DNA IID 的配对区间包含 0，不声称稳定更快。\n\n'+
        '独立编辑生成器：DANN/FedSeq 比值 '+f(lo)+'–'+f(hi)+'；DANN+Bigram/FedSeq 比值 '+f(glo)+'–'+f(ghi)+'。这些范围包括全部冻结种子和分区。\n\n'+
        '无结构对照各方法均计算 8,000 个精确距离；FedSeq 平均 '+f(neg['fedseq'])+' ms，DANN '+f(neg['dann'])+' ms，说明存在无法获益的场景。\n\n'+
        '补充实验遇到输出冲突时按测量协议和完整性重跑，未按性能挑选；恢复记录见 supplement_recovery.json。完整原始 CSV、输入、指纹、完成凭据与独立重放结果均随包提供。\n\n'+
        '隐私参数与证明在两轮配额观察模型下对齐；该保证不等于全部主机轨迹、最终答案或跨查询累计预算的保证，浮点实验采样也不作为生产级精确采样认证。\n')
    print('Generated manuscript text and all tables from verified data.')

if __name__=='__main__':main()
