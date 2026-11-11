# 紧凑与可读性平衡版

- 图 1、3、4 保留矢量机制示例；引言和独立的第 V 章分析保持。
- 图 6 为检索参数对比：三行对应 DNA/Symbol/Rfam，每行四图依次为 IID-k、Non-IID-k、IID-m、Non-IID-m。
- 图 7 将隐私预算与消融合并：三行对应三个数据集，每行四图依次为 IID-ε、Non-IID-ε、干净消融、加噪消融。加噪消融列适当加宽，算法名横排、分行；图例共享。
- 图 8 为四个稳健性子图：三个集中度曲线和已有无结构 DNA 对照。最后一项来自原统计表，不是新实验；误差线为三个种子均值的范围。原无结构表在正文中由此图替代。
- 原有 27 个实验子图的数值全部保留，28 号子图重绘已有对照。所有实验 y 轴为 times (ms)，每个子图都有下方名称。
- 正文 12 页、参考文献 1 页，43 条引用；八张图、三份伪代码、四张活动表。

完整项目的最新生成入口：

```bash
python3 real_data/icde_revision/apply.py
```

它依次执行 restructure.py、graphics.py、balance_layout.py、compile.py、verify.py。不要在它之后单独运行历史论文生成脚本。所需依赖为 numpy、matplotlib、pypdf，以及支持 TikZ 的 pdfLaTeX/BibTeX。

本轮只改变图组和叙述引用，未重跑实验；源数据 SHA256 与原有证明的核对通过。对照数据仍可在 verified_statistics.json 的 unstructured 分组逐项核查。
