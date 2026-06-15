# Trigger eval — guard-llama-guard 触发评测

> 状态：**已实测一轮（2026-06-15，见 §5 before）**：负例 0 误触、正例 7/8（唯 P8 AUROC 未触发）。M3.5 W2 据此调 description 后需**人工复测一轮**（§5 after，顺延 M4）。
> 判定依据：本 skill frontmatter description 的动词锚点（run/evaluate/score/benchmark）+
> 名词锚点（guard/moderation/metrics/unified safety dataset）+ 显式负触发（dataset-* 与
> dataset-format-checker 的职责排除）。
> 记录日期：2026-06-11；目标环境：Claude Code + 已安装全部 4 个 skills。

## 1. 正例（应触发本 skill，≥8 条）

| # | 用户原话 | 预期判定 | 依据 |
|---|---|---|---|
| P1 | "Run Llama Guard on this unified dataset" | 触发 | 动词 run + 名词 Llama Guard |
| P2 | "评测一下 guard 在统一数据集上的指标" | 触发 | 评测/guard/指标三锚点 |
| P3 | "Score these guard predictions against the dataset labels" | 触发 | score + guard predictions |
| P4 | "Benchmark the rule baseline vs Llama Guard" | 触发 | benchmark + 两个 guard 名 |
| P5 | "算一下这个 guard 输出的 Recall 和 FPR" | 触发 | 指标名 + guard 输出 |
| P6 | "How often does the guard over-refuse on XSTest probes?" | 触发 | over-refuse + guard |
| P7 | "用关键词基线先跑个 smoke，再上 llama-guard" | 触发 | smoke/基线/llama-guard |
| P8 | "Compute AUROC for the moderation model's predictions" | 触发 | AUROC + moderation |
| P9 | "我有一份 guard 预测的 JSONL，对着真值标签算一下 AUROC/准确率" | 触发 | 评估**已有预测文件** + 指标（补 P8 盲测缺口的"评估既有预测"语义，W2 description 已覆盖） |
| P10 | "Score my saved guard predictions against the gold labels and give me precision/recall" | 触发 | score + saved predictions + 指标 |

## 2. 负例

| # | 用户原话 | 预期判定 | 应触发 |
|---|---|---|---|
| N1 | "转换 WildGuardMix 到统一格式" | 不触发 | dataset-wildguardmix |
| N2 | "检查这个数据集格式对不对" | 不触发 | dataset-format-checker |
| N3 | "下载 UnsafeBench 数据集" | 不触发 | 甲的 dataset skill |
| N4 | "Validate that my unified JSONL passes the schema" | 不触发 | dataset-format-checker |
| N5 | "把 HarmBench 下载下来转成统一 JSONL" | 不触发 | download-text-modal-dataset |
| N6 | "给这个图像数据集跑安全分类" | 不触发 | guard-shieldgemma2（M3）；本 skill 的 When-NOT-to-use 已排除 |

## 3. 实测协议

1. 在装好全部 skills 的环境中，**每条 prompt 开一个全新会话**提问；
2. 记录模型是否调用 `guard-llama-guard`（以工具调用/SKILL.md 读取为准）；
3. 正例答案为"触发"，负例答案为"不触发"；逐条填入实测列；
4. 负例由甲盲测（甲不知道预期答案，见 `待甲确认.md` #3），结果回填本表；
5. 记录测试日期与模型版本。

## 4. 达标线与回流

- **达标**：正例 ≥7/8 触发；负例 0 误触。
- **不达标**：修订 frontmatter description（增/删锚点词或负触发短语），回流 **M3.5 W2-T4**
  （description 调优）后重测，旧结果保留在本文件 §5 作 before/after 对照。

## 5. 实测记录（before/after 回归）

> M3.5 W2 把人工盲测从"通过门"移为**回归报告项**（M3.5_SPEC 必改 1）：before=M2 基线，after=description 调优后人工复测（顺延 M4）。

| 阶段 | 日期 | 模型版本 | 正例通过 | 负例误触 | 结论 |
|---|---|---|---|---|---|
| **before**（M2 基线） | 2026-06-15 | GPT 5.4 Thinking HIGH | 7/8 | 0 | 通过；P8 的 AUROC 提示词在"无成型文件"时因不够直接未触发本 skill |
| **after**（M3.5 W2 description 调优后） | 待测（M4 前人工） | — | — | — | description 已扩"评估已有预测/算指标"语义 + 新增 P9/P10；预期补上 P8 类触发、负例仍 0 |
