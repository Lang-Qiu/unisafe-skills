# Trigger Eval — guard-shieldgemma2（图文互斥档）

> 目的：验证本 skill 的 frontmatter description 在"图像安全评测"请求上正确触发，
> 且与 `guard-llama-guard`（文本）/`dataset-*`（数据集）**互斥不串台**。
> 协议与文本侧一致（见 [`../../guard-llama-guard/references/trigger-eval.md`](../../guard-llama-guard/references/trigger-eval.md)）：
> 每条 prompt 在**全新会话**（装好全部 skills）逐条实测，记录实际触发的 skill；
> 实测档与 M2 任务 16 / 甲 #3 盲测合并为同一轮（三方一次测完）。

## 1. 正例（应触发本 skill，≥4 条）

| # | prompt | 预期 | 实测 |
|---|---|---|---|
| P1 | 用 ShieldGemma 2 评测这批图片的安全性 | guard-shieldgemma2 | 待测 |
| P2 | 对 unified JSONL 里的 image_safety 记录跑图像 guard 并出指标 | guard-shieldgemma2 | 待测 |
| P3 | 帮我比较两个图像安全 guard 在 UnsafeBench 输出上的 FPR | guard-shieldgemma2 | 待测 |
| P4 | 这批图像数据有的缺图有的只有 URL，跑安全判定时怎么处理并统计 | guard-shieldgemma2 | 待测 |
| P5 | 给图像安全预测结果算 Accuracy/AUROC 并出对比表 | guard-shieldgemma2 | 待测 |
| P6 | 我有一份图像 guard 的预测 JSONL，对着真值标签算 AUROC/准确率 | guard-shieldgemma2 | 待测 |

## 2. 负例（不应触发本 skill，≥6 条；与文本侧/数据集侧互斥）

| # | prompt | 预期 | 实测 |
|---|---|---|---|
| N1 | 用 Llama Guard 评测这批文本 prompt 的安全性 | guard-llama-guard | 待测 |
| N2 | 对 prompt_response_safety 记录跑文本 guard 并算 over-refusal | guard-llama-guard | 待测 |
| N3 | 下载 UnsafeBench 并转换成统一格式 | dataset-unsafebench | 待测 |
| N4 | 检查这个数据集是否符合 unified schema | dataset-format-checker | 待测 |
| N5 | 把 WildGuardMix 转成统一 JSONL | dataset-wildguardmix | 待测 |
| N6 | 帮我给这张图片写个文艺的 caption | （不触发任何 guard skill） | 待测 |
| N7 | 用 LLM-as-judge 评一批文本对话的安全性 | guard-llama-guard | 待测 |

## 3. 记录规则

1. 每条新会话；只记"是否触发 + 触发了哪个 skill"，不追问模型理由；
2. 正例命中目标 ≥4/5、负例 0 误触发为通过线（与文本侧口径一致）；
3. 结果回填本表"实测"列并注日期与会话环境；
4. **实测档状态：N/A（需人工多个全新会话；与 M2 任务 16、甲 #3 同轮，顺延 M4 报告期前）**。

## 4. 实测记录（before/after 回归）

> 与文本侧对齐（M3.5 W2）：人工盲测=回归报告项，不作交付门。图像侧此前**未盲测过**，故 before 空缺。

| 阶段 | 日期 | 模型版本 | 正例通过 | 负例误触 | 结论 |
|---|---|---|---|---|---|
| **before** | —（图像侧未实测） | — | — | — | 文本侧 2026-06-15 已测；图像侧顺延 M4 同轮补 |
| **after**（M3.5 W2 description 调优后） | 待测（M4 前人工） | — | — | — | description 已扩"评估已有预测/算指标"语义 + 新增 P6；达标线正例 ≥4/5、负例 0 |

## 5. 自动锚点覆盖自检（佐证，**非真触发结果**）

> 工具与文本侧同：`reports/calibration/_anchor_coverage.py`（gitignored）。**非触发测试**，仅验证
> `SKILL.md` description 锚点对本表 §1/§2 探针的覆盖，用于人工复测前暴露锚点缺口。

- 结果（2026-06-16，自动）：正例 **6/6** 命中、负例 **7/7** 正确排除、**0 代理误触发**。
- 负例排除覆盖：跨模态文本路由（N1/N2/N7 → guard-llama-guard）、数据集路由（N3-N5 → dataset-*）、
  纯 caption 无评测语义（N6）均被正确判为不触发本 skill。
- 无代理风险点；但**图像侧此前从未人工实测**（§4 before 空缺），after 仍须人工同轮补。
