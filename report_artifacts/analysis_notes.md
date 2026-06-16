# 结果分析说明（analysis_notes）— UniSafe Skills

> 日期：2026-06-17。数据来源：**已落盘的预测 JSONL + 真值标签 + run_metadata**（**未重训、未重跑模型**）。
> 复算脚本：`report_artifacts/_analyze_results.py`；明细表：`report_artifacts/result_summary.csv`。
> 口径依据：`guard-llama-guard/references/metrics-definitions.md`（正类=unsafe；双口径；FPR 分母=FP+TN）。
> **禁止补造**：缺的标 `N/A` 并注原因；每个数字可追溯到 `predictions/*.jsonl` + `metrics/metrics.md` + `run_metadata.json`。
> **自校验**：复算的 answered_only head_binary 与权威 `metrics.md` **逐位一致**（rule Acc 0.7984/Recall 0.2711、llama Acc 0.8985/Recall 0.6604、E3 Acc 0.790/Recall 0.393 全部 OK）。

## 1. 样本量汇总（各 Guard × 数据集 × 运行状态）

恒等式自检均成立：`eligible = answered + error`、`coverage + failure_rate = 1`。

| 层 | 数据集 | guard | eligible | answered | error | coverage | failure_rate |
|---|---|---|---|---|---|---|---|
| formal | WildGuardMix 1959 | rule | 1959 | 1959 | 0 | 1.000 | 0.000 |
| formal | WildGuardMix 1959 | **llama-guard** | 1959 | 1911 | 48 | 0.976 | 0.024 |
| formal | Judge 子集 120 | rule | 120 | 120 | 0 | 1.000 | 0.000 |
| formal | Judge 子集 120 | llama-guard | 120 | 118 | 2 | 0.983 | 0.017 |
| formal | Judge 子集 120 | **llm-judge** | 120 | 119 | 1 | 0.992 | 0.008 |
| formal | UnsafeBench 2037 | caption-rule | 2037 | 1428 | 609 | 0.701 | 0.299 |
| formal | UnsafeBench 2037 | **shieldgemma2(int8)** | 2037 | 1642 | **395** | 0.806 | **0.194** |
| cpu-ref | UnsafeBench 150 | shieldgemma2(bf16) | 150 | 150 | 0 | 1.000 | 0.000 |
| cpu-ref | UnsafeBench NaN-crosscheck 18 | shieldgemma2(bf16) | 18 | 18 | 0 | 1.000 | 0.000 |
| **E3** | NaN 子集 100 | shieldgemma2(int8→cpu-bf16) | 100 | **100** | **0** | **1.000** | **0.000** |

skipped（out_of_scope/missing_content）= total − eligible，本批 formal 三档 skipped 均为 0（路由后全 in-scope）。

**全运行台账（29 个 run，按层）**：formal 3 / **E3-recovery 1** / cpu-ref 2 / performance 3（W4 并发计时 j1/j4、W1 元数据核查）/ mechanism 3（out_m2_threeguard 顶替矩阵、out_m3_twoguard 合成双 guard、out_e2_newint8 升栈 spike）/ smoke·dev 17。**仅 formal + cpu-ref + E3 进入指标分析**；mechanism/smoke 仅计数（合成/小样本，不作头条指标）。`out_e3` 此前为后台进行中，现已收口纳入。

## 2. 双口径指标（answered_only / failure_as_wrong 同时算）

完整 6 项（Accuracy/Precision/Recall/F1_unsafe/Coverage/FailureRate）+ Macro-F1 + FPR + AUROC + Recall/FPR 的 **Wilson 95% CI** 见 `result_summary.csv`（20 行 = 10 guard×run × 2 口径）。头条（answered_only）：

| guard（层） | n | Acc | Recall [95% CI] | FPR [95% CI] | Macro-F1 | AUROC |
|---|---|---|---|---|---|---|
| **llama-guard**（文本 1959） | 1911 | 0.899 | 0.660 [0.601,0.715] | 0.063 [0.052,0.076] | 0.792 | **0.888** |
| rule（文本 1959） | 1959 | 0.798 | 0.271 [0.223,0.326] | 0.112 | 0.582 | N/A* |
| **llm-judge**（子集 120） | 119 | 0.815 | **0.750 [0.598,0.858]** | **0.152 [0.089,0.247]** | 0.795 | 0.895 |
| llama-guard（子集 120） | 118 | 0.805 | 0.579 [0.422,0.721] | 0.088 | 0.760 | 0.909 |
| **shieldgemma2 int8**（图像 2037） | 1642 | 0.622 | 0.125 [0.101,0.152] | 0.051 | 0.480 | **0.613** |
| caption-rule（图像 2037） | 1428 | 0.605 | **0.020 [0.011,0.035]** | 0.014 | 0.395 | N/A* |
| shieldgemma2 **bf16 真值**（CPU-ref 150） | 150 | 0.733 | 0.350 [0.242,0.476] | 0.011 | 0.664 | **0.719** |
| **E3 恢复子集**（100，cpu-bf16@0.30） | 100 | 0.790 | 0.393 [0.236,0.576] | 0.056 | 0.689 | **0.675** |

*\* rule / caption-rule 为关键词 0/1，无连续置信分 → AUROC 按设计 **N/A**（不是缺数据，是方法无 ranking）。*

failure_as_wrong（保守口径，error 计错）关键变化：llama Acc 0.899→0.877、Macro-F1 0.792→0.759；**shieldgemma2 int8 Acc 0.622→0.502、Macro-F1 0.480→0.394**（395 NaN 全计错，落差最大）；caption-rule Acc 0.605→0.424（609 缺图/缺 caption 计错）。

## 3. 数据分层（正式 / 机制验证 / smoke / CPU 参考 / E3）

- **正式真数据（headline）**：out_text_real（文本全量 1959+250 探针）、out_judge_subset（judge 三 guard 子集 120）、out_m3_real（图像全量 2037）。
- **CPU bf16 参考真值**：out_cpu_ref150（150）、out_cpu_crosscheck（18）——量化质量的"真值锚"，**非生产精度**。
- **E3 覆盖率回退（M3.7）**：out_e3（100 NaN 图经 cpu-bf16 恢复）——见 §6。
- **机制验证（不作头条）**：out_m2_threeguard（10 eligible 合成顶替矩阵，已退役）、out_m3_twoguard（合成图 6 张，5 error）、out_e2_newint8（20 探针升栈 spike）。
- **smoke/dev（17 个）**：5–13 条 fixture/示例，仅验流程，**严禁进结果表**。

## 4. 分母 / 缺失 / 失败 / 标签映射检查

- **分母**：FPR 分母 = FP+TN（真值 safe 总数），非全体 N（已核）；coverage/error_rate 分母 = eligible；恒等式 `coverage+failure_rate=1` 全档成立。
- **缺失真值**：head_binary 真值 = `label.is_unsafe`（布尔）；本批 formal 各 guard **0 行缺真值**（脚本 `missing_truth` 计数为 0，否则会在 note 标出）。
- **失败样本**：record-level error（`is_unsafe=null` + `error≠null`）双口径分别处理——answered_only **剔除**（乐观）、failure_as_wrong **计错**（保守，truth unsafe→FN / truth safe→FP）。两口径并列即"防剔除虚高"的护栏。
- **标签映射**：头部二分类只用 `is_unsafe`，不涉及 22/23 类 canonical 映射（后者属 by-category，见 `metrics-definitions.md §9`，本表未展开）。规则基线/judge 的连续分语义不同：**judge 置信度经方向映射后才参与 AUROC，跨 guard AUROC 不可直接混比**（M2 实证未映射前 AUROC 仅 0.375）。

## 5. 可能导致结果虚高 / 虚低的因素（务必写进报告）

| 因素 | 方向 | 说明 / 证据 |
|---|---|---|
| **int8 NaN 计入口径** | 虚低(fw)/虚高(ao) | 19.4%（395/2037）NaN：answered_only 把最难的 19.4% 剔除→偏乐观；failure_as_wrong 全计错→偏悲观。真值落在两者之间；**E3 回退后覆盖率补回**（§6）。 |
| **int8 量化漂移** | 虚低 | int8 AUROC **0.613** 是量化**下界**；CPU bf16 真值 **0.719**。即便非 NaN 的 int8 分也只约一半可信（notes §6.1a）。**报告须用 int8/bf16 双值，不可只报 0.613 当"模型真水平"**。 |
| **三策略天花板** | 结构上限 | ShieldGemma 2 仅 dangerous/sexual/violence；UnsafeBench 11 类里 8 类无策略 → 即便 CPU bf16 AUROC 也 ~0.72 封顶。**非校准/工程可解。** |
| **caption-rule 近盲** | 真实弱基线 | 真图无描述性 caption → 召回 **0.020**、覆盖仅 0.701（609 缺 caption/图计 error）。作为**零依赖下界基线**诚实呈现，别当可用 guard。 |
| **judge 子集偏置** | 不可比 | 子集 = 分层 40 unsafe/40 safe/40 XSTest（≈非自然基准率），**Acc/FPR 不能与全量 1959 的 14.5% 基准率直接比**；AUROC（阈值无关）更可比。判官**对抗坍塌** AUROC 0.976→0.633（M2_summary §2.2，本表未含对抗分桶）。 |
| **小样本** | CI 变宽 | judge 120 / cpu-ref 150 / **crosscheck 18 / E3 100** 的 Recall CI 很宽（如 E3 Recall 0.393 **[0.236,0.576]**）；crosscheck n<30 标 `low_sample_warn=yes`。**点估计须带 CI 报。** |
| **AS-RUN 阈值 ≠ 出厂阈值** | 口径混淆 | 本表 formal 为**当时跑**的阈值（llama native argmax、sg2=0.5）；**出厂/shipped**（llama 0.55、sg2 0.30）的 before→after 在 `M3.6_summary.md §2.0`。报告引用 shipped 战绩以 §2.0 为准，本表为 as-run 对照。 |
| **规则基线无 AUROC** | 非缺陷 | rule/caption-rule 只有 0/1，无 ranking → AUROC N/A 是方法属性，**诚实标注**而非补造。 |

## 6. E3 NaN 回退结果增补（M3.7，2026-06-17 收口）

机制：int8 在真图返回 NaN（确定性伪影）→ 逐记录回退非量化精度（cpu-bf16）重算单图。`--nan-fallback none` 默认（复现旧 error-row 行为）；评测用 `cpu --timeout-s 300`。

- **覆盖率赢点**：100 NaN 子集**恢复 100/100**（`nan_fallback_recovered=100`，0 error，全部 `quant=int8->cpu-bf16`）；**子集覆盖率 0%→100%**；**全量投影 80.6%→~100%**。
- **恢复子集判别质量**（cpu-bf16@0.30 vs 真值，n=100，真值 28 unsafe/72 safe）：Acc **0.790**、Recall 0.393 [0.236,0.576]、FPR 0.056、Macro-F1 0.689、**AUROC 0.675**。
  - 恢复分**是 truth-grade**：AUROC 0.675 贴近 CPU bf16 真值水平（全量 0.719）、远高于 int8 下界 0.613 → 回退找回的是**有用判定**，不是垃圾。
  - 这 100 张是 int8 **连分都给不出**（NaN）的更难子集，其绝对 Recall 不与全量直接可比；价值在"从全丢 → truth-grade 已答"。
- **诚实 caveat（关键）**：**E3 = 覆盖率/鲁棒性赢点，不是 int8 质量修复**。全量 E3 后是**混精度**——80.6% 仍是漂移的 int8 + 19.4% truth-grade bf16；多数 int8 判别漂移**未解**。阈值 0.30 在 int8 上校准、这里套 bf16，AUROC（阈值无关）证排序合理但 0.30 对 bf16 非最优。
- 证据：`M3.7_summary.md §2`、`guard-shieldgemma2/references/shieldgemma2-notes.md §6.3`、`全量标注结果/unsafebench_test/out_e3/{predictions,run_metadata.json}`。

## 7. 交付物与可追溯性

- `report_artifacts/result_summary.csv`：20 行明细（layer/dataset/guard/basis × counts + 6 项指标 + Macro-F1 + FPR + AUROC + Recall/FPR Wilson CI + low_sample_warn + note）。
- `report_artifacts/_analyze_results.py`：复算脚本（含 vs metrics.md 自校验、Wilson CI、运行台账）。
- 所有 formal 数字 = 复算且与权威 `metrics.md` 逐位一致；E3 = 复算且与 `M3.7_summary.md §2.3` 一致；**无任何数字为人工填入**。
