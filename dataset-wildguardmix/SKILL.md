---
name: dataset-wildguardmix
description: Download and normalize the WildGuardMix safety dataset into unified JSONL for text safety evaluation. Use this skill to produce WildGuardTest or WildGuardTrain records, and to append XSTest safe probes when building WildGuardTest artifacts for over-refusal evaluation.
---

# Dataset: WildGuardMix

Use this skill to build a real text safety dataset artifact from WildGuardMix
(`allenai/wildguardmix`, gated, odc-by) for downstream guard evaluation.

Prefer this skill when the user asks to:
- convert WildGuardMix into unified JSONL
- prepare real text data for `guard-llama-guard`
- generate WildGuardTest records with XSTest over-refusal probes following file under example/
- produce a text dataset artifact for guard benchmarking

Do not use this skill for:
- image datasets like UnsafeBench
- running guards or computing guard metrics
- schema validation by itself

## Files

- Entry point: `scripts/main.py`
- Taxonomy mapping: `references/category_mapping.json`
- Output sample along with XSTest: `examples/wildguardmix_unified_sample.jsonl`

Prefer using the existing script instead of re-implementing the converter from
scratch.

## Inputs

The current script accepts:

- `--split`
  - `wildguardtest` or `test`
  - `wildguardtrain` or `train`
- `--limit`
- `--output-dir`
- `--cache-dir`
- `--hf-endpoint`
- `--token`

WildGuardMix is gated, so access or token setup may be required before a run
will succeed. 

## Core behavior

- `wildguardtest` produces test-set unified records.
- `wildguardtrain` produces train-set unified records.
- Records without `response` become `prompt_only_safety`.
- Records with `response` become `prompt_response_safety`.
- Head unsafe label:
  - prompt-only -> from `prompt_harm_label`
  - prompt-response pair -> from `response_harm_label`
- If the required harm label is null, the record is skipped and counted.
- Unsafe records with null `subcategory` fall back to `general_harm`.
- Unsafe records with unmapped `subcategory` fall back to `other`.
- Safe records keep `label.canonical_categories = []`.
- When building `wildguardtest`, the script also appends XSTest safe probes with
  `risk_metadata.over_refusal_probe = true`.

## Pinned output paths

Given `--output-dir <OUT>`, the current script writes:

- `<OUT>/unified/wildguardtest.unified.jsonl` when `--split wildguardtest`
- `<OUT>/unified/wildguardtrain.unified.jsonl` when `--split wildguardtrain`
- `<OUT>/unified/metadata.json`

For `wildguardtest`, the unified file contains:
- WildGuardTest text records
- XSTest safe probe records

For `wildguardtrain`, the unified file contains:
- WildGuardTrain text records only

## Output contents

The unified JSONL output contains:

- stable ids such as `wildguardmix:test:000001`
- stable probe ids such as `xstest:test:000001`
- preserved original fields in `raw_label.original_fields`
- mapped canonical categories from `references/category_mapping.json`
- all parts can be found in the output sample

The metadata output contains:

- total seen / written counts
- skipped null-label count
- safe / unsafe counts
- adversarial counts
- category counts
- XSTest probe counts

## Success signal

On success, `scripts/main.py` exits with code `0` and prints lines in this
shape:

```text
RESULT: ok total_seen=... total_written=... skipped_null_label=... xstest_written=...
UNIFIED: <path-to-unified-jsonl>
METADATA: <path-to-metadata-json>
```

Interpretation:

- `RESULT: ok` means the conversion run itself completed
- `total_seen` is how many source rows were visited
- `total_written` is how many unified records were emitted
- `skipped_null_label` is how many WildGuardMix rows were dropped because the
  required harm label was null
- `xstest_written` is how many safe probe rows were appended for over-refusal
  evaluation

## Suggested run order

1. Run `wildguardtest` with a small `--limit` smoke run.
2. Check that both the unified JSONL file and `metadata.json` were created.
3. If the smoke run looks correct, rerun without `--limit`.
4. Hand off the `unified/` directory artifact for downstream validation and
   guard evaluation.
