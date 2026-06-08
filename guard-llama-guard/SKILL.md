---
name: guard-llama-guard
description: Run text safety guards over unified safety JSONL and emit unified guard-result records. Wraps Llama Guard 3 (local, MLCommons S1-S14), a keyword rule-based baseline, and the OpenAI Moderation API, then computes Accuracy, Macro-F1, AUROC, Recall, FPR, and Over-refusal Rate. Use this skill to evaluate text guards on a unified dataset.
---

# Guard: Llama Guard 3 (+ rule baseline + OpenAI Moderation)

> Status: **scaffold (M0)**. Implementation lands in **M1** on branch `feat/guard-llama-guard`.

Reads the unified dataset (e.g. `dataset-wildguardmix` output), routes each record by
`task_type`/`modality`, runs three text guards, and emits unified guard-result JSONL +
a multi-guard × multi-task metrics table.

## Planned structure

```
guard-llama-guard/
  SKILL.md  manifest.yaml  README.md  requirements.txt
  src/ (main.py guards/ metrics.py)
  config/category_mapping.json   # S1-S14 / OpenAI cats -> 22 canonical
  examples/ (input_example.jsonl output_example.jsonl)
  tests/test_basic.py
```

## Contract

Input/output schema, which fields to read per task, taxonomy mapping, and metric definitions
(**positive class = unsafe**): see [`../M0_接口约定.md`](../M0_接口约定.md) §3, §4, §5, §6.
Handle timeout/empty output by setting `prediction.is_unsafe=null` + `error`, excluding from
metrics and counting in metadata — never crash the batch. See the timeout example in
[`../M0_guard_output_sample.jsonl`](../M0_guard_output_sample.jsonl).
