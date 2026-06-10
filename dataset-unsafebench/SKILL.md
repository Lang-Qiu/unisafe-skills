---
name: dataset-unsafebench
description: Download and normalize the UnsafeBench image safety dataset (Safe/Unsafe label across 11 categories, real + AI-generated images) into the unified safety JSONL schema with image modality. Use this skill to construct image_safety records that pass dataset-format-checker.
---

# Dataset: UnsafeBench (multimodal highlight)

> Status: **scaffold (M0)**. Implementation lands in **M3** on branch `feat/dataset-unsafebench`.

Use this skill when converting UnsafeBench (`yiting/UnsafeBench`) into the unified format with
`modality:["image"]` / `task_type:image_safety`. It has both Safe and Unsafe images, so the
multimodal side can still compute FPR. Keep the sample small (200–500 images).

## Planned structure (standard skill layout; only SKILL.md required)

```
dataset-unsafebench/
  SKILL.md  README.md  requirements.txt
  scripts/ (main.py utils.py validate.py)
  references/category_mapping.json   # 11 UnsafeBench cats -> 22 canonical
  examples/ (output.sample.jsonl)
  tests/ (test_validate.py fixtures/)
```

## Field mapping & conventions

See [`../M0_接口约定.md`](../M0_接口约定.md) §4 (UnsafeBench 11 → canonical). Save image to disk;
record path + caption/OCR in `content.images`. `safety_label` Safe/Unsafe → `label.is_unsafe`.
Demonstrates the unified schema generalizes from text to image with zero schema change.
