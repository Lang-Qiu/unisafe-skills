---
name: dataset-unsafebench
description: Download and normalize the UnsafeBench image safety dataset (Safe/Unsafe label across 11 categories, real + AI-generated images) into the unified safety JSONL schema with image modality. Use this skill to construct image_safety records that pass dataset-format-checker.
---

# Dataset: UnsafeBench

Use this skill to build a real image safety dataset artifact from UnsafeBench
(`yiting/UnsafeBench`) for downstream guard evaluation.

Prefer this skill when the user asks to:
- convert UnsafeBench into unified JSONL
- prepare real image data for `guard-shieldgemma2`
- produce an `image_safety` dataset artifact for guard benchmarking
- download and normalize a small real UnsafeBench subset

Do not use this skill for:
- text datasets like WildGuardMix
- running guards or computing guard metrics
- schema validation by itself

## Files

- Entry point: `scripts/main.py`
- Taxonomy mapping: `references/category_mapping.json`
- Output sample: `examples/output.sample.jsonl`

Prefer using the existing script instead of re-implementing the converter from
scratch.

## Inputs

The current script accepts:

- `--split`
  - `test` by default
- `--limit`
- `--output-dir`
- `--cache-dir`
- `--hf-endpoint`
- `--token`

UnsafeBench access or token setup may be required before a run will succeed.

## Core behavior

- Produces unified `image_safety` records with `modality = ["image"]`.
- Saves each source image to disk and records its relative path in
  `content.images[0].path`.
- Uses source `text` as image `caption` when available.
- Maps `safety_label`:
  - `Unsafe` -> `label.is_unsafe = true`
  - `Safe` -> `label.is_unsafe = false`
- Maps the 11 UnsafeBench categories through
  `references/category_mapping.json`.
- Unsafe records with null category fall back to `general_harm`.
- Unsafe records with unmapped category fall back to `other`.
- Safe records keep `label.canonical_categories = []`.
- Does not append XSTest probes and does not write
  `risk_metadata.over_refusal_probe`.

## Pinned output paths

Given `--output-dir <OUT>`, the current script writes:

- `<OUT>/unified/unsafebench.unified.jsonl`
- `<OUT>/unified/metadata.json`
- `<OUT>/unified/images/unsafebench/...`

The unified file contains UnsafeBench image records only.

## Output contents

The unified JSONL output contains:

- stable ids such as `unsafebench:test:000001`
- saved local image paths under `content.images`
- preserved original fields in `raw_label.original_fields`
- mapped canonical categories from `references/category_mapping.json`
- both safe and unsafe image records in unified schema form

The metadata output contains:

- total seen / written counts
- skipped count
- error counts
- safe / unsafe counts
- category counts
- source counts
- image output directory

## Success signal

On success, `scripts/main.py` exits with code `0` and prints lines in this
shape:

```text
RESULT: ok total_seen=... total_written=... skipped=...
UNIFIED: <path-to-unified-jsonl>
METADATA: <path-to-metadata-json>
```

Interpretation:

- `RESULT: ok` means the conversion run itself completed
- `total_seen` is how many source rows were visited
- `total_written` is how many unified records were emitted
- `skipped` is how many source rows were dropped during conversion

## Suggested run order

1. Run a small smoke conversion with `--limit`.
2. Check that the unified JSONL file, `metadata.json`, and image directory were created.
3. Run `dataset-format-checker` on the output directory.
4. If the smoke run looks correct, rerun with the target sample size and hand
   off the `unified/` directory artifact for downstream guard evaluation.
