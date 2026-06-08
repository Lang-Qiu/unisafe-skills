---
name: dataset-wildguardmix
description: Download and normalize the WildGuardMix safety dataset (prompt-harm / response-harm / refusal labels, adversarial flag, fine-grained subcategory) into the unified safety JSONL schema. Use this skill to construct WildGuardTest/WildGuardTrain records that pass dataset-format-checker.
---

# Dataset: WildGuardMix

> Status: **scaffold (M0)**. Implementation lands in **M1** on branch `feat/dataset-wildguardmix`.

Use this skill when converting WildGuardMix (`allenai/wildguardmix`, gated, odc-by) into the
unified safety benchmark format. It fills the schema most fully — prompt harm, response harm,
refusal, adversarial, and a mappable fine-grained `subcategory`.

## Planned structure (per assignment)

```
dataset-wildguardmix/
  SKILL.md  manifest.yaml  README.md  requirements.txt
  src/ (main.py utils.py)
  config/category_mapping.json   # subcategory -> 22 canonical
  examples/ (input_example.jsonl output_example.jsonl)
  tests/test_basic.py
```

## Field mapping & conventions

See [`../M0_接口约定.md`](../M0_接口约定.md) §2 (WildGuardMix → unified) and §4 (taxonomy).
Key rules: `is_unsafe` by `target` (pair → response harm); fill all sub-labels; **null harm
label → skip + count in metadata.json**; `subcategory` → 22 canonical (unmapped → `other`).

## Acceptance

`python ../InfoSec-example-skills/.../dataset-format-checker/scripts/check_dataset_format.py <unified_dir>` → exit 0 (PASS).
