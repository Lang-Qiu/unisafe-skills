# Revision Roadmap — UniSafe Skills 课程报告（methodology-focus 审查后）

> 日期：2026-06-17。来源：academic-paper-reviewer（methodology-focus，EIC + 方法学审稿人）。
> 决定：**Minor Revision**（无 CRITICAL；数字与 metrics.md 逐位一致）。
> 修订对象：`report_artifacts/report.tex`。**仅处理审查指出处，不扩 scope**；reviewer 错误处用 AUTHOR_DISAGREE 标注（本轮无）。
> 格式：R（审查关切）→ A（作者动作）→ Status。优先级 = 修订顺序。

## MAJOR

### M4 — as-run / shipped 阈值口径未标（优先级 1）
- **R**：表1/2 为 as-run 阈值（llama native argmax、sg2=0.5），§4.5 为 shipped（0.55/0.30），sg2 Macro-F1 出现 0.480 与 0.523 两值、over-refusal 6.4% 与 6.0%，无标注易混。
- **A**：表1/2 caption 标 "as-run 阈值"；§4.2 over-refusal 标 (as-run；shipped 6.0%)；§4.5 标 "shipped 默认"。
- **Status**：✅ applied。

### M3 — 比较性结论缺显著性 / CI 未入表（优先级 2）
- **R**："judge 召回最高 0.750" 与 llama 0.660 的 95% CI 重叠（[0.598,0.858] vs [0.601,0.715]），n=120 未做配对检验；CI 未入表。
- **A**：表1/2 加 Recall 的 95% Wilson CI 列；§4.2 "综合最强"改 "AUROC/Macro-F1/FPR 最强"，judge 召回最高处加 "CI 与 llama 重叠、差异未检验未必显著"；§5 局限注 "未做配对显著性、仅报 CI"。
- **Status**：✅ applied。

### M2 — fig1 跨基准率比 Accuracy（优先级 3）
- **R**：fig1 把 14.5%/≈33%/38% 三种基准率的 guard 并列比 Acc，跨基准率 Acc 不可比，易误导。
- **A**：fig1 caption 加基准率注 + "Acc 跨基准率不可比，宜以 AUROC/Macro-F1 为准"。（图本体分面留作可选后续；本轮以 caption + 正文导向修正。）
- **Status**：✅ applied（caption 级）。

### M1 — §2 数据集为空（优先级 6；甲补）
- **R**：报告缺数据集说明（40% 结构分依赖）；§1/§4 引用的规模/基准率无处建立。
- **A**：§2 由甲填（保留占位）；乙在 §4.1 加前向引用 "(数据集构建/规模/基准率见 §2)"。
- **Status**：✅ 乙侧前向引用 applied；§2 正文待甲。

## MINOR

### m5 — 双口径定义未在正文给全
- **R**：§4.4 有语义无映射定义（error→FN/FP、coverage 公式）。
- **A**：§4.4 加一句定义 + 指向 metrics-definitions.md §3；加 \label 供交叉引用。**Status**：✅。

### m6 — §3.3 断引用（见 §4.3 应为 §4.4）
- **A**：改用 \ref{sec:dual} 自动编号。**Status**：✅。

### m7 — "证明 / 扎实 / 稳健"措辞偏强
- **A**：摘要 "表现稳健"→给召回漏报率；§5 "证明"→"展示"、"扎实"→事实陈述（105/110 全绿、离线全链）。**Status**：✅。

### m8 — E3 全量 ~100% 是投影 + 机制档排除未声明
- **A**：§4.6 注投影假设 + 子集 n=100/CI 宽不外推；§4.1 注 "仅报 formal+cpu-ref+E3，机制/smoke 已排除"。**Status**：✅。

### m9 — 复现参数未在正文 + 真数据复现限制未进局限 + n 含义
- **A**：§4.7 加复现关键参数（seed/revision/库版本/硬件）；§5 加 "真数据级复现需 GPU+HF+真数据，仓库仅 fixture 级"；表 caption 标 $n$=eligible。**Status**：✅。

## 通过项（保留，不动）
- guard 方法↔实验一致（5 guard 对应）；机制样本未误入结果表；图文表分开；数字 100% 可追溯且与 metrics.md 一致；诚实口径（precision-favoring / E3 覆盖率非质量 / 结构上限仅定位）。
