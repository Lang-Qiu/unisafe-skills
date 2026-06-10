---
name: guard-shieldgemma2
description: Run image safety guards over unified image_safety JSONL and emit unified guard-result records. Wraps ShieldGemma 2 (local, sexually-explicit / violence-gore / dangerous-content policies) with OpenAI omni-moderation as an API cross-check, then computes Accuracy, Macro-F1, Recall, and FPR on image data. Use this skill to evaluate image guards on a unified dataset.
---

# Guard: ShieldGemma 2 (multimodal highlight)

> Status: **scaffold (M0)**. Implementation lands in **M3** on branch `feat/guard-shieldgemma2`.

Reads unified `image_safety` records (e.g. `dataset-unsafebench` output), runs ShieldGemma 2
(`google/shieldgemma-2-4b-it`, gated) per-policy, optionally cross-checks with OpenAI
omni-moderation (image input), and emits the same unified guard-result schema as the text guards
— demonstrating the Guard interface generalizes across modality with no interface change.

## Planned structure (standard skill layout; only SKILL.md required)

```
guard-shieldgemma2/
  SKILL.md  README.md  requirements.txt
  scripts/ (main.py guards/ metrics.py)
  references/category_mapping.json   # 3 ShieldGemma policies -> 22 canonical
  schemas/guard_output.schema.json   # shared with guard-llama-guard
  examples/ (input.sample.jsonl output.sample.jsonl)
  tests/ (test_validate.py fixtures/)
```

## Contract

Same unified guard-result schema and metric definitions as `guard-llama-guard`; see
[`../M0_接口约定.md`](../M0_接口约定.md) §4, §5, §6. Per-policy probabilities feed `confidence`.
Keep the evaluation sample small (200–500 images).
