#!/usr/bin/env python3
"""Integrate only complete, integrity-checked real-sequence experiments."""
from pathlib import Path
import json,sys,csv,statistics,shutil
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parent;PROJECT=ROOT.parent;PAPER=PROJECT/'paper'
sys.path.insert(0,str(ROOT));from analyze_real import analyze
MAIN=['baseline','dann','fedseq','dann_star','fedseq_star']
LABEL={'baseline':'Baseline','dann':'DANN','fedseq':'FedSeq','dann_star':'DANN*','fedseq_star':'FedSeq*','fedseq_legacy':'+Cold','dann_order':'+Order','dann_order_star':'+Order','fedseq_star_laplace':'Lap1','fedseq_star_laplace_zero':'Lap0'}
COLOR={'baseline':'#555555','dann':'#d98200','fedseq':'#007c91','dann_star':'#b65d35','fedseq_star':'#445cb4','fedseq_legacy':'#c28f35','dann_order':'#72a78a','dann_order_star':'#72a78a','fedseq_star_laplace':'#b98bac','fedseq_star_laplace_zero':'#8ba2c5'}
AXES=[('k',[4,8,16,32,64,128,256],'Answer size k',128),('m',[4,8,12,16],'Providers m',8),('epsilon',[2,1,.8,.6,.4,.2,.1,.05,.01,.001],r'Joint quota budget $\epsilon$',1)]

def get(rows,split,axis,value,alg,dataset=None):
 base=128 if axis=='k'else 8 if axis=='m'else 1
 candidates=[x for x in rows if x['partition']==split and x['algorithm']==alg and(dataset is None or x['dataset']==dataset)]
 if axis=='epsilon'and 'star'not in alg and(dataset is None or dataset=='Rfam_canonical'):value=1
 sec='default'if float(value)==base else axis
 return next(x for x in candidates if x['section']==sec and(sec=='default'or float(x['value'])==float(value)))
def cpu(row):return row.get('mean_cpu_ms',row.get('mean_total_cpu_ms'))
def save(fig,name):
 for ext in ['pdf','png']:
  p=PROJECT/'figures'/f'{name}.{ext}';fig.savefig(p,dpi=300,bbox_inches='tight');shutil.copy2(p,PAPER/'figures'/p.name)
 plt.close(fig)
def panel(ax,rows,split,axis,values,xlabel,algorithms=MAIN,dataset=None):
 for alg in algorithms:
  ys=[cpu(get(rows,split,axis,v,alg,dataset))for v in values]
  ax.plot(range(len(values)),ys,label=LABEL[alg],color=COLOR[alg],linestyle='--'if'star'in alg else'-',marker='o',markersize=3,linewidth=1.3)
 ax.set_xticks(range(len(values)),[f'{x:g}'for x in values],rotation=40 if axis in ['k','epsilon']else 0);ax.tick_params(labelsize=9);ax.set_xlabel(xlabel);ax.set_ylim(bottom=0);ax.grid(alpha=.2)
 ax.spines[['top','right']].set_visible(False)
def main():
 s=analyze(ROOT/'full_results');audit=json.loads((ROOT/'audit_progress.json').read_text());assert audit['complete']and audit['strict_failures_replayed']==s['strict_failures']and audit['distance_errors']==s['distance_failures']
 rows=s['summary'];old=json.loads((PROJECT/'verified_statistics.json').read_text());plt.rcParams.update({'font.size':10,'axes.titlesize':11,'axes.labelsize':10,'legend.fontsize':10,'pdf.fonttype':42,'ps.fonttype':42})
 fig,axs=plt.subplots(2,3,figsize=(9,4.5));fig.subplots_adjust(top=.87,bottom=.15,hspace=.7,wspace=.33)
 for i,split in enumerate(['IID','NonIID']):
  for j,(axis,values,label,_)in enumerate(AXES):
   panel(axs[i,j],rows,split,axis,values,label);axs[i,j].set_title('Rfam / '+('Non-IID'if split=='NonIID'else split))
   if j==0:axs[i,j].set_ylabel('Total CPU (ms)')
 handles,labels=axs[0,0].get_legend_handles_labels();fig.legend(handles,labels,loc='upper center',ncol=5,frameon=False);save(fig,'real_comparison')
 fig,axs=plt.subplots(3,6,figsize=(17,8));fig.subplots_adjust(top=.92,bottom=.11,hspace=.65,wspace=.32)
 datasets=[('dna_cluster_order','DNA'),('symbol_cluster_order','Symbol'),('Rfam_canonical','Rfam')]
 for d,(ds,name)in enumerate(datasets):
  rr=rows if ds=='Rfam_canonical'else old['primary']
  for part,split in enumerate(['IID','NonIID']):
   for i,(axis,values,label,_)in enumerate(AXES):
    ax=axs[i,2*d+part];panel(ax,rr,split,axis,values,label,dataset=ds);ax.set_title(name+' / '+('Non-IID'if split=='NonIID'else split))
    if 2*d+part==0:ax.set_ylabel('Total CPU (ms)')
 handles,labels=axs[0,0].get_legend_handles_labels();fig.legend(handles,labels,loc='upper center',ncol=5,frameon=False);save(fig,'comparison_three_datasets')
 groups=[['dann','fedseq_legacy','dann_order','fedseq'],['dann_star','dann_order_star','fedseq_star_laplace','fedseq_star_laplace_zero','fedseq_star']]
 fig,axs=plt.subplots(2,6,figsize=(17,5.7));fig.subplots_adjust(top=.9,bottom=.16,hspace=.65,wspace=.3)
 for d,(ds,name)in enumerate(datasets):
  rr=rows if ds=='Rfam_canonical'else old['primary']
  for part,split in enumerate(['IID','NonIID']):
   for i,algs in enumerate(groups):
    vals=[next(x for x in rr if x['dataset']==ds and x['partition']==split and x['section']=='ablation'and x['algorithm']==alg)for alg in algs]
    ax=axs[i,2*d+part];ax.bar(range(len(algs)),[cpu(x)for x in vals],color=[COLOR[x]for x in algs]);ax.set_xticks(range(len(algs)),[LABEL[x]for x in algs],rotation=42,ha='right');ax.tick_params(labelsize=9);ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
    if i==0:ax.set_title(name+' / '+('Non-IID'if split=='NonIID'else split))
    if 2*d+part==0:ax.set_ylabel('Total CPU (ms)')
 save(fig,'ablation_three_datasets')
 def default(split,alg):return get(rows,split,'k',128,alg)
 ratios={split:next(x for x in s['pairs']if x['id']==f'Rfam_canonical_{split}_default_1'and x['left']=='dann')for split in ['IID','NonIID']}
 def f(v):return f'{v:.2f}'
 def ratio_text(split):
  x=ratios[split];return f(x['cpu_ratio'])+r'$\times$ (95\% query-bootstrap interval '+f(x['ratio_ci95'][0])+'--'+f(x['ratio_ci95'][1])+r'$\times$)'
 text=r'''\subsection{Real Nucleotide Sequences}
\label{sec:real}
\begin{figure*}[t]
\centering
\includegraphics[width=\textwidth]{real_comparison.pdf}
\caption{Rfam confirmation on 50 held-out queries, three repeats. Columns vary $k$, $m$, and $\varepsilon$; rows use mixed and family-specialized ownership. Three clean curves in the budget column reuse their default CPU measurements. All perturbed runs, including errors, remain in the averages.}
\label{fig:real}
\end{figure*}
'''
 text+='On Rfam, the default DANN/FedSeq CPU ratios are '+ratio_text('IID')+' under IID and '+ratio_text('NonIID')+' under specialization. Figure~\\ref{fig:real} shows the parameter sweeps.\n\n'
 for split in ['IID','NonIID']:
  b,d,c=[default(split,a)for a in ['baseline','dann','fedseq']];gram=default(split,'dann_gram2');starD=default(split,'dann_star');starF=default(split,'fedseq_star')
  text+=('Under '+('IID'if split=='IID'else 'Non-IID')+', Baseline, DANN, and FedSeq average '+f(b['mean_cpu_ms'])+', '+f(d['mean_cpu_ms'])+', and '+f(c['mean_cpu_ms'])+' ms. Verification falls from '+f(d['mean_dp_calls'])+' to '+f(c['mean_dp_calls'])+'; FedSeq omits '+f(c['mean_two_round_zero_nodes'])+' providers in both rounds on average. The DANN+Bigram control takes '+f(gram['mean_cpu_ms'])+' ms. The DANN$^*$/FedSeq$^*$ CPU ratio is '+f(starD['mean_cpu_ms']/starF['mean_cpu_ms'])+r'$\times$.'+'\n\n')
 abl={split:{a:next(x for x in rows if x['partition']==split and x['section']=='ablation'and x['algorithm']==a)for a in ['dann','fedseq_legacy','dann_order','fedseq']}for split in ['IID','NonIID']}
 apair=next(x for x in s['pairs']if x['id']=='Rfam_canonical_NonIID_ablation_1'and x['left']=='dann_order')
 saved=100*(1-abl['NonIID']['fedseq']['mean_dp_calls']/abl['NonIID']['dann_order']['mean_dp_calls'])
 text+='The matched ablation separates the mechanisms: under IID, cold-only, order-only, and combined search evaluate '+', '.join(f(abl['IID'][a]['mean_dp_calls'])for a in ['fedseq_legacy','dann_order','fedseq'])+' exact distances; under specialization the counts are '+', '.join(f(abl['NonIID'][a]['mean_dp_calls'])for a in ['fedseq_legacy','dann_order','fedseq'])+'. Combining the modules removes '+f(saved)+r'\% of order-only verification under specialization and reduces CPU by '+f(apair['cpu_ratio'])+r'$\times$ (95\% interval '+f(apair['ratio_ci95'][0])+'--'+f(apair['ratio_ci95'][1])+'). Cold-only scheduling barely reduces verification: stronger frontier evidence enables omission. All 10,500 clean Rfam runs match the stable-key oracle. Table~\\ref{tab:accuracy} includes the noisy Rfam errors.\n\n'
 text+='Padding leaves only '+f(default('NonIID','fedseq_star')['mean_two_round_zero_nodes'])+' mean omissions in FedSeq$^*$ at default, explaining part of the smaller noisy gain. Other pilots, including the unsuccessful Splice case, are retained in the artifacts.\n'
 (PAPER/'real_results.tex').write_text(text)
 exp=(PAPER/'experiment_results.tex').read_text()
 compact={
 'The gains address two different costs.':r'Composition-only filtering retains reordered strings within a family; order evidence reduces their verification. At specialized providers, even a positive quota of one can scan an irrelevant shard. Frontier evidence lets the broker omit that search. The ablation separates these costs.',
 'The calibrated second-round rate':r'Conditional sensitivity makes the second-round noise rate small. Positive padding then moves many requests toward $k$, weakening omission. Smaller budgets add work where clean search stops early, but little at an already fully scanned shard. Noise generation is timed.',
 'The reference comparator retains':r'DANN$^*$ refines using its clean allocation map; FedSeq$^*$ certifies the actual perturbed first prefix. Its accuracy therefore reflects the full workflow, not geometric noise alone.',
 'We report strict stable-key':r'We distinguish stable-key mismatches from distance-top-$k$ errors: the latter compare cardinality and sorted oracle distances while allowing boundary ties. Every mismatch is independently reconstructed using recorded quotas and exhaustive distances, without broker allocation or noise code. Timing retains all failures.',
 'The noisy ablation separates':r'The large clean gains do not come from integer noise. Padding often revives unselected providers: (\ref{eq:zero-prob}) predicts 5.64 positive first requests among six zero-origin providers at default. No perturbation distribution guarantees faster retrieval.',
 'Figure~\\ref{fig:robustness} varies':r'Figure~\ref{fig:robustness} changes composition at balanced sizes. The response is not monotonic: at $\rho=.75$, positive prefixes can exceed small relevant-family slices and require other-family verification. At $\rho=1$, six irrelevant providers are omitted. The benefit depends on sufficient exclusion evidence rather than a generic Non-IID label.',
 'CPU sums provider and broker processing':r'CPU includes broker/provider serialization and encryption but excludes blocking waits; wall time follows concurrent providers and communication. A separate SDK simulation probe checked the sorting ECALL interface. Retrieval runs outside hardware SGX, so these measurements characterize local transport under the stated quota model.',
 }
 lines=exp.splitlines()
 for i,line in enumerate(lines):
  for key,value in compact.items():
   if line.startswith(key):lines[i]=value;break
 exp='\n'.join(lines)+'\n'
 exp=exp.replace('Across the main sweeps','Across the synthetic sweeps').replace('We rerun the four default population/partition settings','We rerun the four synthetic default population/partition settings').replace('All 67,200 clean runs across the main, ablation, heterogeneity, edit-generator, and unclustered studies','All 67,200 clean runs in the synthetic studies')
 start=exp.find(r'\subsection{Discussion}')
 if start>=0:exp=exp[:start]

 if r'\input{real_results}'not in exp:exp=exp.replace(r'\subsection{Local Encrypted Transport}',r'\input{real_results}'+'\n\n'+r'\subsection{Local Encrypted Transport}')
 (PAPER/'experiment_results.tex').write_text(exp)
 ptransport=PAPER/'table_transport.tex'
 ptransport.write_text(ptransport.read_text().replace(r'\begin{table}[t]',r'\begin{table}[!htbp]'))
 accuracy=PAPER/'table_accuracy.tex';t=accuracy.read_text()
 import re
 t=re.sub(r'Rfam[^\n]*\n','',t)
 add=[]
 for split in ['IID','NonIID']:
  vals=[]
  for alg in ['dann_star','fedseq_star']:
   rr=[x for x in rows if x['partition']==split and x['algorithm']==alg and x['section']!='ablation'];assert sum(x['runs']for x in rr)==2850
   vals.extend([sum(x['strict_failures']for x in rr),sum(x['distance_failures']for x in rr)])
  add.append('Rfam '+('IID'if split=='IID'else'Non-IID')+' & '+' & '.join(map(str,vals))+r' \\')
 accuracy.write_text(t.replace(r'\bottomrule','\n'.join(add)+'\n'+r'\bottomrule'))
 mfile=PAPER/'main.tex';maintext=mfile.read_text();a=maintext.index(r'\section{Conclusion}');b=maintext.index(r'\clearpage',a)
 maintext=maintext[:a]+r'''\section{Conclusion}
FedSeq couples order-aware filtering with certified zero-permitting prefixes. Correctness and conditional sensitivity analyses support exact retrieval and calibrated quota release. Ablation and held-out Rfam tests show complementary filtering and scheduling gains. Unclustered sequences and transport measurements identify limits from weak pruning and communication.

'''+maintext[b:];mfile.write_text(maintext)
 clean=sum(x['runs']for x in rows if 'star'not in x['algorithm']);assert clean==10500
 manifest=json.loads((ROOT/'Rfam_canonical/manifest.json').read_text())
 family_labels=[x['family']for x in csv.DictReader((ROOT/'Rfam_canonical/queries.txt.metadata.csv').open())]
 family_rows=[]
 for split in ['IID','NonIID']:
  path=ROOT/'full_results/cases'/f'Rfam_canonical_{split}_default_1.csv'
  rr=list(csv.DictReader(path.open()))
  for family in sorted(set(family_labels)):
   for alg in MAIN+['dann_gram2']:
    g=[x for x in rr if x['algorithm']==alg and family_labels[int(x['query'])]==family]
    family_rows.append({'partition':split,'family':family,'algorithm':alg,'queries':len(g)//3,'runs':len(g),'mean_cpu_ms':statistics.mean(float(x['total_cpu_ms'])for x in g),'mean_dp_calls':statistics.mean(float(x['dp_calls'])for x in g),'strict_failures':sum(x['exact_match']=='0'for x in g),'distance_failures':sum(x['distance_topk_valid']=='0'for x in g)})
 with (ROOT/'family_breakdown.csv').open('w')as f0:
  w=csv.DictWriter(f0,fieldnames=list(family_rows[0]));w.writeheader();w.writerows(family_rows)

 report={'confirmed_dataset':manifest,'confirmed_runs':s['runs'],'clean_runs':clean,'noisy_runs':s['runs']-clean,'default_ratios':ratios,'strict_failures':s['strict_failures'],'distance_failures':s['distance_failures'],'audited_failures':audit['strict_failures_replayed'],'all_pilots':json.loads((ROOT/'selection.json').read_text())}
 (ROOT/'confirmed_report.json').write_text(json.dumps(report,indent=2))
 (ROOT/'REPORT_CN.md').write_text('# 真实序列确认实验\n\n数据集：Rfam 的 5S rRNA 与 vault RNA 匹配序列，统一 T/U 后去重，无人工扰动或重复扩充。数据库 '+str(manifest['records'])+' 条，独立确认查询 50 条、每条重复 3 次。IID / Non-IID 下默认 DANN/FedSeq CPU 比值为 '+f(ratios['IID']['cpu_ratio'])+' / '+f(ratios['NonIID']['cpu_ratio'])+'。\n\n40 个配置共 '+str(s['runs'])+' 次运行；'+str(clean)+' 次干净算法全部严格匹配精确答案。加噪严格不匹配 '+str(s['strict_failures'])+' 次，其中真实距离 top-k 错误 '+str(s['distance_failures'])+' 次，均保留并独立重放。\n\n候选筛选及全部先导结果见 selection.json、pilot_results 和 pilot_extra_results；确认查询不参与先导筛选。源序列是真实数据库记录，节点归属是模拟的。大图见 figures/comparison_three_datasets.pdf 和 figures/ablation_three_datasets.pdf；正文另给 Rfam 参数图以保持文字可读性。\n')
 base_report=(PROJECT/'REPORT_CN.md').read_text().split('<!-- REAL_DATA -->')[0].rstrip()
 combined=base_report+'\n\n<!-- REAL_DATA -->\n\n'+(ROOT/'REPORT_CN.md').read_text()
 (PROJECT/'REPORT_CN.md').write_text(combined)
 (PAPER/'CLAIM_EVIDENCE_CN.md').write_text(combined)
 print('Wrote verified real-data figures and manuscript',s['runs'],ratios,flush=True)
if __name__=='__main__':main()
