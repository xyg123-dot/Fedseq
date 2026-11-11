#!/usr/bin/env python3
from pathlib import Path
import json,shutil
ROOT=Path(__file__).resolve().parent;PROJ=ROOT.parent.parent;PAPER=PROJ/'paper'
def main():
 s=json.loads((ROOT/'statistics.json').read_text());assert s['runs']==27600 and s['all_clean_exact']
 rows=s['summary'];pairs=s['pairs']
 def ratio(part,a='dann',section='default'):return next(x for x in pairs if x['partition']==part and x['section']==section and x['left']==a and x['right']==('fedseq_star'if a=='dann_star'else'fedseq')and x['subset']=='all')
 a=ratio('NonIID','dann_order','ablation')
 text='''# 当前论文：统一采用最少预处理 Rfam

论文中的所有 Rfam 参数、消融、集中度和本地加密传输结果，都来自同一批最少预处理记录；旧的规范化/筛选/去重/家族封顶子集不再用于正文任何图表或结论。

## 数据

- 原始来源：RF00001（5S）与 RF00006（vault）的归档 FASTA，共 597,812 条源记录。
- 固定种子 20261016 的全局均匀抽样：数据库 12,391 条（12,323 5S、68 vault）；保留原始重复记录、字符、长度和家族比例。10,326 种内容，长度 48–178。
- 唯一处理是解析 FASTA 标题和折行；没有 U/T 转换、大小写统一、字符或长度筛选、去重、按家族封顶、裁剪、变异或扩充。
- 50 条固定确认记录与数据库/先导源记录身份不重叠；自然抽样后均为 5S，长度 79–123。11 条与库中记录内容相同，主结果全部保留；39 条非相同内容查询另作描述性核对。
- IID 为均匀打散，Non-IID 为家族分别占据一半节点，保留自然体量差异；m=8 时四个 vault 节点各 17 条。这些都是模拟归属。

## 完整实验

40 个原生参数/消融配置：23,400 次方法运行；3 个集中度配置：2,700 次；2 个本地 TCP/AES 配置：1,500 次。共 27,600 次，每配置 50 查询、3 重复。

k=4,8,16,32,64,128,256；m=4,8,12,16；epsilon=2,1,.8,.6,.4,.2,.1,.05,.01,.001。默认 k=128、m=8、epsilon=1、lambda=.05。预算曲线绘制五算法，其中三条无噪声线复用同一默认测量。三集中度为 0,.5,1；真实 TCP/AES-128-GCM 搭配模拟 64 ms RTT 与 100 Mbps，检索不在硬件 SGX 中运行。

## 主要结果

| 划分 | DANN/FedSeq CPU 比 | DANN*/FedSeq* CPU 比 |
|---|---:|---:|
'''
 for part,label in [('IID','IID'),('NonIID','Non-IID')]:text+=f"| {label} | {ratio(part)['cpu_ratio']:.3f} | {ratio(part,'dann_star')['cpu_ratio']:.3f} |\n"
 text+=f"\nNon-IID 下，仅顺序下界/完整 FedSeq 的 CPU 比为 {a['cpu_ratio']:.3f}，95% 查询自助区间 {a['ratio_ci95'][0]:.3f}–{a['ratio_ci95'][1]:.3f}；以本轮测量为准，不沿用旧子集中的冷节点增益。\n"
 text+=f"\n12,300 次原生无噪声与 900 次传输无噪声运行均严格正确。原生有噪声严格不匹配 {s['native_strict_replayed']} 次，其中距离 top-k 错误 {s['native_distance_errors']} 次；严格不匹配全部独立重放。传输有噪声严格不匹配 {s['transport_strict_errors']} 次，其中距离错误 {s['transport_distance_errors']} 次，直接对照测量区间外的穷举答案。所有错误均保留在 CPU/响应时间均值中。\n"
 text+='''
## 复现

在项目根目录运行：

```bash
make -C benchmark
make -C system/benchmark
python3 real_data/raw_main/run.py --out-dir real_data/raw_main_local
```

该命令在新目录重跑完整 45 配置，不覆盖交付结果；默认八个原生工作线程固定使用 CPU 1–8，另使用 CPU 0 做独立审计，需要这些 CPU 可用。算法本身不要求九核；在较小机器上可按原 case_index.json 中的命令逐个运行，保持每个配置内部的测量协议即可。传输阶段在原生阶段完成后运行，两配置顺序执行、提供方并发。私有噪声重新采样，因此错误次数与耗时不保证逐位相同。

交付结果的完整性检查和绘图（不重新测量）：

```bash
python3 real_data/raw_main/analyze.py
python3 real_data/raw_main/integrate.py
make -C paper
```

analyze.py 核对全部输入/输出哈希、每节点 CPU 分解、无噪声准确性和独立重放凭据；配对置信区间先按查询平均三次重复，再对 50 个查询重采样 2,000 次。论文生成的最后整合步骤是 raw_main/integrate.py；不要随后运行历史的 capped 子集论文整合脚本。

run_executed.py 保留实际执行版本；交付版 run.py 额外允许选择新的输出目录。协议、完整命令、CSV、配额轨迹、节点 CPU、失败与重放记录均在本目录。源序列样本位于 real_data/minimal_processing/Rfam_raw/，直接重跑无需下载全量 FASTA。

real_data/full_results、layout_extension 和早期 minimal_processing 结果保留历史追溯用途；当前正文仅使用 raw_main 的完整新测量，不与旧 Rfam 结果拼接。两个合成数据集的既有实测数据未改变。
'''
 (ROOT/'README_CN.md').write_text(text);(PAPER/'RAW_SOURCE_CHECK_CN.md').write_text(text)
 report='''# 当前论文实验范围

合成主实验 62,400 次、稳健性实验 34,200 次、无结构对照 1,800 次、合成本地加密传输 3,000 次，保留原始实测结果；Rfam 全部替换为最少预处理样本上的 27,600 次新测量。当前论文所用实验合计 129,000 次方法运行；历史先导和旧 Rfam 子集不计入此总数。

合成原生 67,200 次无噪声和 Rfam 原生 12,300 次无噪声严格正确。传输另有合成 1,800 次及 Rfam 900 次无噪声严格正确。CPU 表示进程计算消耗，不是能耗；加密传输响应时间另计，不能直接把 CPU 加速解释为同等响应时间加速。

所有论文 Rfam 图表使用同一批原始抽样记录，详细协议、结果与启动方式如下。

'''+text
 old=PROJ/'REPORT_CN.md'
 if not(ROOT/'historical_report_before.md').exists():shutil.copy2(old,ROOT/'historical_report_before.md')
 old.write_text(report)
 snap=ROOT/'project_readme_before.md'
 if not snap.exists():shutil.copy2(PROJ/'README.md',snap)
 readme=snap.read_text()
 readme='''<!-- CURRENT_RAW_MAIN -->
# 当前论文的最终实验版本

所有 Rfam 图表和正文已统一为最少预处理样本上的完整新实验。请先阅读 real_data/raw_main/README_CN.md；当前汇总为 real_data/raw_main/statistics.json，完整协议为 real_data/raw_main/protocol.json。图 7、8、9，表 I、III、IV 均使用新 Rfam 测量。原两个合成数据集结果保留。

在新目录重跑 Rfam：`python3 real_data/raw_main/run.py --out-dir real_data/raw_main_local`。重画当前论文的最后步骤：`python3 real_data/raw_main/integrate.py`。不要再调用历史 Rfam 论文写入脚本覆盖当前稿。

'''+readme
 (PROJ/'README.md').write_text(readme)
 (PAPER/'README.md').write_text('''# FedSeq manuscript

The main manuscript is self-contained: 12 body pages and one reference page, six editable method diagrams, three experimental composites, three algorithms, four tables, and 43 cited references. Build main.tex with pdfLaTeX/BibTeX (`make`), or upload this directory to Overleaf.

Every Rfam result in Figures 7–9 and Tables I, III, IV comes from the same minimally processed raw-record sample. Only FASTA parsing and global uniform sampling were performed; original duplicates, characters, lengths, and family proportions remain. The full 27,600-run protocol and evidence are in real_data/raw_main/ in the experiment package. The synthetic measurements are unchanged. Table IV is the native default cohort used in Figure 7, not a separate dataset or validation sample.

The final paper integration script is real_data/raw_main/integrate.py. Historic capped-data integration scripts are retained for provenance and must not be run afterward. FINAL_REVIEW_CN.md documents the current checks. The quota theorem assumes an ideal sampler and the specified protected quota view; it is not a hardware SGX or full-trace privacy claim. ICDE_AI_DISCLOSURE.tex records assistance scope for adaptation to the submission venue and is not included in main.tex.
''')
 claim='''# 当前贡献与证据对应

- 顺序过滤：图 7/8，合成与 Rfam 的精确距离计数；LCS 和位并行算法本身明确归属已有工作。
- 有证书零分配：正确性证明、图 8 的 cold/order/combined 消融；如实区分自然小分片与合成大分片，不能把冷节点数量等同于 CPU 收益。
- 两轮配额隐私：固定历史的条件敏感度、共同组合预算、表 I 的实际有噪声误差；不将噪声机制更换单独表述为新分布，也不保证有噪声检索总是精确。
- 真实来源：所有 Rfam 主文结果来自同一最少预处理样本，统计与输出哈希见 real_data/raw_main/statistics.json、protocol.json 和 cases/*.receipt.json。
- 运行环境：CPU、并发响应时间、真实本地 TCP/AES 与模拟 RTT/带宽分别定义；无硬件 SGX 检索或云端系统完整复现声明。

主文所需信息均在正文，无独立补充材料依赖；原始数据与历史证据保留在完整代码包。
'''
 (PAPER/'CLAIM_EVIDENCE_CN.md').write_text(claim)
 (PAPER/'LAYOUT_UPDATE_CN.md').write_text('''# 当前排版

图 1–6 为方法图，图 7 为三数据集/两划分/三类变量的五算法对比，图 8 为三数据集消融，图 9 统一比较节点集中度。表 III 横向展示三数据集的真实本地加密传输 CPU/响应时间，表 IV 展示同一 Rfam 默认原生测量。所有 Rfam 测量已统一为最少预处理样本。

以 FINAL_REVIEW_CN.md、FINAL_CHECK.json 为本轮实际编译和视觉检查记录。历史版的生成器/来源家族辅助图不属于本轮正文。
''')
 (PAPER/'FINAL_NUMERICAL_AUDIT.json').write_text(json.dumps({k:v for k,v in s.items()if k not in ['summary','pairs']}|dict(current_rfam_statistics='real_data/raw_main/statistics.json',historical_rfam_in_manuscript=False),indent=2))
 print('Current raw-main documentation and evidence map written.')
if __name__=='__main__':main()
