<!-- Report section template: "Guard methods & results".
     Fill every {{placeholder}}; field names map 1:1 to metrics/metrics.json
     (see references/metrics-definitions.md). Delete comments before use. -->

## Guard 评测：{{guard_name}}

**方法**。{{guard_name}}（版本 {{guard_version}}）在 {{dataset_name}}（{{n_records}} 条，
eligible {{eligible_total}} 条）上运行；输入路由与字段消费见 `references/io-contract.md`。
正类 = unsafe；指标公式与双口径定义见 `references/metrics-definitions.md`。
命令：`{{command_line}}`（exit {{exit_code}}，`RESULT: {{result_line}}`）。

**结果（头部二分类，双口径并列）**

| basis | n | Accuracy | Recall | FPR | Macro-F1 | AUROC |
|---|---|---|---|---|---|---|
| answered_only | {{ao_n}} | {{ao_accuracy}} | {{ao_recall}} | {{ao_fpr}} | {{ao_macro_f1}} | {{auroc}} |
| failure_as_wrong | {{fw_n}} | {{fw_accuracy}} | {{fw_recall}} | {{fw_fpr}} | {{fw_macro_f1}} | {{auroc}} |

覆盖情况：coverage = {{coverage}}，error_rate = {{error_rate}}
（eligible_total = {{eligible_total}}，answered_total = {{answered_total}}）。
AUROC 口径说明：{{auroc_note}}。

**Over-refusal（XSTest 探针子集）**。over_refusal_rate（= 探针子集 FPR）：
answered_only = {{or_answered_only}}，failure_as_wrong = {{or_failure_as_wrong}}，
探针数 {{probe_n}}{{#low_sample_warning}}（low_sample_warning：样本不足 30，
不具统计意义，仅作趋势参考）{{/low_sample_warning}}。

**误判案例（3–5 例）**

| id | 真值 | 预测 | 类别 | 简析 |
|---|---|---|---|---|
| {{case_1_id}} | {{case_1_truth}} | {{case_1_pred}} | {{case_1_cats}} | {{case_1_note}} |
| {{case_2_id}} | {{case_2_truth}} | {{case_2_pred}} | {{case_2_cats}} | {{case_2_note}} |
| {{case_3_id}} | {{case_3_truth}} | {{case_3_pred}} | {{case_3_cats}} | {{case_3_note}} |

**分析**。{{analysis_paragraph}}
<!-- 建议素材：规则基线在探针上的设计性高 FPR（"kill a process"）；error 剔除 vs
     计为错判的双口径差值反映 guard 稳定性；AUROC 仅对有连续分的 guard 可比。 -->

<!-- ===== v2（M2）：以下各块对应 metrics.json 的新分节，字段名 1:1 ===== -->

## 多 Guard 对比（metrics.json `comparison`，基线 {{comparison_baseline}}）

<!-- 行 = guard；直接搬 metrics.md 的 comparison 表，或按下行模板逐 guard 填 -->

| guard | eligible | coverage | error_rate | Acc (ao) | Recall (ao) | FPR (ao) | Macro-F1 (ao) | AUROC | Acc (fw) | Macro-F1 (fw) | ΔAcc (ao) | ΔAcc (fw) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| {{cmp_guard}} | {{cmp_eligible_total}} | {{cmp_coverage}} | {{cmp_error_rate}} | {{cmp_ao_accuracy}} | {{cmp_ao_recall}} | {{cmp_ao_fpr}} | {{cmp_ao_macro_f1}} | {{cmp_ao_auroc}} | {{cmp_fw_accuracy}} | {{cmp_fw_macro_f1}} | {{cmp_delta_ao_accuracy}} | {{cmp_delta_fw_accuracy}} |

探针对比（`comparison.buckets.over_refusal_probe`）：{{cmp_probe_summary}}
<!-- 叙事建议："哪个 guard 更不易过度拒答" + ao/fw 分叉是否由 error 行造成 -->

## 按类别分析（metrics.json `by_category`，仅 answered_only 口径）

| category | support | binary_recall | category_recall | divergence | precision | F1 |
|---|---|---|---|---|---|---|
| {{bc_category}} | {{bc_support}} | {{bc_binary_recall}} | {{bc_category_recall}} | {{bc_taxonomy_divergence}} | {{bc_category_precision}} | {{bc_category_f1}} |

macro（support≥1 共 {{bc_categories_counted}} 类）：recall = {{bc_macro_category_recall}}，
F1 = {{bc_macro_category_f1}}。数据缺口与审计：unsafe_missing_category =
{{bc_unsafe_missing_category}}，unknown_category_values = {{bc_unknown_category_values}}，
category_audit = {{bc_category_audit_summary}}。
<!-- 叙事建议：taxonomy_divergence 是 M0 §4 预告的分歧的量化（如 phishing→S1），
     binary 对而类别错 ≠ guard 错——写清这层区分是按类别分析的核心论点 -->

## 对抗分桶（metrics.json `adversarial_split`）

| slice | n | Acc (ao) | Recall (ao) | FPR (ao) | Macro-F1 (ao) | Acc (fw) | low_sample |
|---|---|---|---|---|---|---|---|
| adversarial | {{adv_n}} | {{adv_ao_accuracy}} | {{adv_ao_recall}} | {{adv_ao_fpr}} | {{adv_ao_macro_f1}} | {{adv_fw_accuracy}} | {{adv_low_sample}} |
| non_adversarial | {{nadv_n}} | {{nadv_ao_accuracy}} | {{nadv_ao_recall}} | {{nadv_ao_fpr}} | {{nadv_ao_macro_f1}} | {{nadv_fw_accuracy}} | {{nadv_low_sample}} |

unknown 切片（缺布尔 adversarial 字段，仅计数）：{{adv_unknown_n}} 条。
<!-- 叙事建议：对抗 vs 非对抗的 Recall 差 = 越狱鲁棒性；llm-judge 有指令面，
     对抗样本可能"说服"判官——与无指令面的 rule/llama 形成对照 -->

## Metric Caveats（报告必须保留的四条）

1. by-category 仅 answered_only 口径（error 行无类别，避免造假精度）；
2. llm-judge 的 confidence 为自报值，非校准概率，跨 guard AUROC 对比须注明；
3. 任何 low_sample_warning / low_support_warning 桶不作强结论；
4. fallback/顶替数据的数字不可作为最终全量结果（提交前以真实数据重跑）。
