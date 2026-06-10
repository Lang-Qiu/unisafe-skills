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
