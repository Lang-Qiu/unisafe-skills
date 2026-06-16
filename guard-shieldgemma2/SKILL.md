---
name: guard-shieldgemma2
description: Run image safety guards over unified image_safety JSONL and score them. Wraps ShieldGemma 2 (google/shieldgemma-2-4b-it, local int8 baseline, 3 policies) plus a zero-dependency caption/OCR keyword baseline, emits the same unified guard-result schema as the text guards, and computes Accuracy/Macro-F1/Recall/FPR/AUROC with dual error basis. Use this skill to evaluate IMAGE safety guards (UnsafeBench-style data, image moderation, ShieldGemma), or to score / compute AUROC / precision / recall for an existing or saved set of image-guard predictions against gold labels. Do NOT use it for text prompt/response safety (that is guard-llama-guard) or for downloading/converting datasets (those are the dataset-* skills).
---

# guard-shieldgemma2 — image safety guards on unified JSONL

Same Guard interface as `guard-llama-guard`, generalized to images with zero
schema change: identical output records, identical metrics machine, identical
exit-code contract.

## When to use / when NOT to use

- **Use**: running an image guard (ShieldGemma 2 or the caption-rule baseline)
  over unified `image_safety` records; computing image-guard metrics; comparing
  image guards.
- **Do NOT use**: text prompt/response safety (→ `guard-llama-guard`); dataset
  download/conversion/format-checking (→ `dataset-*` skills); judging images
  by URL (this skill never downloads — url-only records become error rows).

## Quickstart (zero install, no GPU)

```bash
cd guard-shieldgemma2
python scripts/main.py --input examples/input.sample.jsonl --output-dir out_smoke --guards caption-rule
python scripts/validate.py out_smoke/predictions --against examples/input.sample.jsonl
python scripts/metrics.py --predictions out_smoke/predictions --dataset examples/input.sample.jsonl --output-dir out_smoke/metrics
```

Expected: `RESULT: ok predicted=3 errors=3 skipped=1`, then `RESULT: PASS`,
then `RESULT: ok guards=1 joined=6`. The 3 errors are deliberate demo rows
(url-only / missing file / missing caption — see Failure handling).

## Guards

| guard | layer | needs | notes |
|---|---|---|---|
| `caption-rule` | Core-Minimal | nothing (stdlib) | keyword match on the first image's caption/ocr TEXT; never reads pixels; **pipeline baseline only** — label it as such in any report |
| `shieldgemma2` | Core-Full | matching torch build + GPU + `pip install -r requirements-shieldgemma.txt` + model weights | ShieldGemma 2 4B, int8 CUDA baseline (8GB-VRAM budget); 4-bit NF4 is not used on this stack because it returns NaNs; 3 built-in policies → per-policy yes-probability; `confidence = max(yes_p)` |

ShieldGemma 2 weights: the official `google/shieldgemma-2-4b-it` is gated
(license click + `hf auth login`). A community mirror can be substituted via
`--model-id`; weights route, version coupling (torch 2.5.x needs
transformers <4.53), quantization basis (int8 — the 4-bit path NaNs on this
stack) and live measurements: [`references/shieldgemma2-notes.md`](references/shieldgemma2-notes.md).

## Input

Unified JSONL (dataset-format-checker PASS). Eligible = `task_type ==
"image_safety"` AND `modality == ["image"]` AND first image has `path` **or**
`url`. Relative `path` resolves against the **JSONL file's own directory**
(待甲确认.md #5). Anything else: wrong task/modality → out-of-scope skip;
no path and no url → missing-content skip. Multi-image records: first image
only + warnings (`run_metadata.warnings.multi_image_records`,
`prediction.warnings: ["multi_image_first_only"]`, `raw_output.image_index: 0`).

## Output

```
<output_dir>/
├── predictions/<guard>.predictions.jsonl   # one row per eligible record (conservation law)
├── metrics/metrics.{json,md}
└── run_metadata.json
```

Row schema = `schemas/guard_output.schema.json` (byte-identical with
guard-llama-guard; shared M0 §5 contract). Full I/O details:
`references/io-contract.md`.

## Execution steps

1. Route records (eligible / out_of_scope / missing_content) and pre-check
   images once (resolve path → exists → magic bytes).
2. Run requested guards (`--guards caption-rule,shieldgemma2`); pre-check
   failures become guard-independent error rows, no model call.
3. `validate.py <out>/predictions --against <input>` → `RESULT: PASS`.
4. `metrics.py` → metrics.json/md. Optional flags: `--by-category`
   (per-category recall/precision/F1 + taxonomy divergence, answered_only),
   `--adversarial-split` (tri-state; image data usually lands entirely in
   `unknown` — that is honest counting, not a bug), `--baseline <guard>`
   (comparison deltas when ≥2 guards are joined; default `caption-rule`).
5. *(optional)* `calibrate.py --predictions <out>/predictions --dataset <input>
   --output-dir <out>/calibration` → ROC operating-point table + recommended
   thresholds (`max_macro_f1` / `recall_at_fpr_budget`). **Calibrate on CPU bf16
   scores, not int8** — int8 scores carry quantization noise (notes §6); calibrating
   on them calibrates to the artifact.
6. Judge by **exit code + `RESULT:` line**; never pipe through `tail`.

Key options: `--threshold` (shieldgemma2 unsafe cut on max yes-probability;
**default 0.30** = M3.6 E1 int8 `recall@FPR<=0.1` calibration on real UnsafeBench
(`references/calibration-notes.md`); pass `0.5` to reproduce the old model-card
default; re-calibrate on new data/precision per calibration caveats); `--timeout-s`
(default: shieldgemma2 120s); `--device cuda|cpu`; `--limit N`; `--resume`.

## Failure handling

Exit codes: `0` all guards ok · `1` fatal / ALL guards failed · `2` partial
(≥1 ok, ≥1 guard-level failure). Record-level errors (row written,
`is_unsafe=null`, counted in dual-basis metrics):

| error prefix | meaning |
|---|---|
| `image_url_not_supported` | first image has url only; this skill never downloads |
| `image_not_found` | resolved path does not exist |
| `image_decode_error` | not a recognizable raster file (stdlib magic bytes; pixel-level failures from the adapter reuse the same name) |
| `missing_caption_ocr` | caption-rule only: no caption/ocr text — never silently judged safe |

## Sanity check

| command | expected |
|---|---|
| quickstart step 1 | `RESULT: ok predicted=3 errors=3 skipped=1`, exit 0 |
| quickstart step 2 | `RESULT: PASS files=1 records=6`, exit 0 |
| quickstart step 3 | `RESULT: ok guards=1 joined=6`; metrics.md shows head_binary ao accuracy 1.0 / fw accuracy 0.5 |
| `python -m unittest discover -s tests` | all green, stdlib only, no GPU/network (live tests are opt-in `SHIELDGEMMA2_LIVE=1`) |
| `--guards shieldgemma2` without deps/weights | guard-level failure + `FIX:` hint; alone → exit 1, with caption-rule → exit 2 |

## Troubleshooting

| symptom | cause / fix |
|---|---|
| `GUARD-FAILURE [shieldgemma2]: missing/broken dependency` | install the torch build matching your CUDA/CPU first, then `pip install -r requirements-shieldgemma.txt` (transformers ≥4.50 needed for the ShieldGemma2 class; torch is intentionally not pinned there) |
| gated 401/403 on model load | accept the license on the HF model page, `hf auth login`, or pass a mirror via `--model-id` |
| CUDA OOM at load | keep the default int8 path; close other GPU apps; fall back to `--device cpu` (slow but usable for small CPU-reference subsets) |
| many `missing_caption_ocr` errors | your dataset has no caption/ocr text — caption-rule cannot judge it; use shieldgemma2 |
| soft timeouts on a busy GPU | raise `--timeout-s` (CUDA steps cannot be interrupted; result is discarded on timeout) |

## Safety & limitations

- caption-rule is a **text-surrogate pipeline baseline** — never present its
  numbers as an image model's; tables must carry the guard name.
- int8 quantization can perturb per-policy probabilities (confidence source);
  4-bit NF4 returned NaNs in the measured stack and is kept only as a caveat
  and defense case; the quantization basis is recorded with every result. The
  default threshold is **0.30** (M3.6 E1 int8 `recall@FPR<=0.1` calibration; `0.5`
  was the uncalibrated model-card default) — AUROC is threshold-free; Acc/FPR are
  not, so re-calibrate on new data/precision (calibration caveats).
- Example/fixture images are tiny synthetic PNGs generated by
  `scripts/make_synth_images.py` — benign by construction; real evaluation
  imagery never enters this repository.
- This skill is read-only on inputs and never fetches remote images.
