# download-text-modal-dataset

A portable skill for downloading and normalizing text-only safety guard datasets, focused on reconstructing a paper-like dataset for **Benchmarking Open-Source Safety Guard Models: A Comprehensive Evaluation (2026)**.

## What it builds

It downloads four public Hugging Face source datasets and converts them into one JSONL file with a consistent schema:

- `walledai/HarmBench` (gated; loads the `standard` + `contextual` configs, skips `copyright`)
- `walledai/StrongREJECT` (gated)
- `allenai/real-toxicity-prompts`
- `PKU-Alignment/BeaverTails`, default split `30k_train`

The output categories are the eight NIST SAFETY-style categories used by the paper:

- violence
- hate_speech
- harassment
- sexual_content
- suicide_self_harm
- profanity
- threats
- health_misinformation

## Install

Install into an **isolated environment** — do not pollute system Python, which often has no `pip`:

```bash
python -m venv .venv && source .venv/bin/activate
# If venv fails with "No module named ensurepip", use conda instead:
# conda create -n harmful-content python=3.10 -y && conda activate harmful-content

python -m pip install -r requirements.txt   # use `python -m pip`, not bare `pip`
```

## Authentication (only for gated sources)

`walledai/HarmBench` and `walledai/StrongREJECT` are gated. Web approval alone is not enough; you also need local credentials:

1. Open each dataset page and click **“Agree and access repository”**
   (`huggingface.co/datasets/walledai/HarmBench`, `.../StrongREJECT`).
2. Authenticate: `hf auth login` (new CLI) — or `huggingface-cli login`, or `export HF_TOKEN=hf_xxx`.

Skip this if you only want RealToxicityPrompts + BeaverTails. Without access, those two sources are skipped and the run exits with code 2 (see below).

## Run

```bash
python scripts/download_text_modal_dataset.py \
  --output-dir data/safety_guard_2026 \
  --sources all \
  --threshold 0.5 \
  --include-raw
```

Exit code `0` = all sources loaded; `2` = partial success (a source failed to load — not a crash; the dataset is still built from the rest). Judge success by the exit code and the final `SUMMARY` / `metadata.json`, **not** by piping to `tail`.

## Output

```text
data/safety_guard_2026/
  raw/                              # optional, only with --include-raw
  normalized/
    safety_guard_2026.jsonl         # final dataset, flat schema (shared across sources)
    metadata.json                   # counts, skipped rows, load errors, unmapped categories
  unified/                          # ADDITIONAL: nested schema for dataset-format-checker
    safety_guard_2026.unified.jsonl
    metadata.json
```

The `unified/` output is **purely additive** — it does not modify `raw/` or `normalized/`.
It re-shapes the same data into the unified nested schema (`content{}` / `label{}` /
`source{}` + top-level `id`/`task_type`) defined in `safety_dataset_format_guide.md`, so it
PASSES the sibling `dataset-format-checker`. Disable it with `--no-unified`.

## Validate

```bash
# Flat normalized output (this skill's own validator)
python scripts/validate_output.py data/safety_guard_2026/normalized/safety_guard_2026.jsonl

# Unified nested output — must PASS dataset-format-checker (exit 0)
python ../dataset-format-checker/scripts/check_dataset_format.py data/safety_guard_2026/unified
```

## Common options

```bash
# Quick smoke test without downloading/writing everything
python scripts/download_text_modal_dataset.py \
  --output-dir data/smoke_test \
  --sources real_toxicity_prompts,beavertails \
  --max-samples-per-source 100

# Backfill gated sources AFTER getting access — re-run the FULL set, not a partial one.
# The output file is overwritten, so `--sources harmbench,strongreject` alone would
# drop RTP/BeaverTails. Always use --sources all to keep everything:
python scripts/download_text_modal_dataset.py \
  --output-dir data/safety_guard_2026 \
  --sources all --threshold 0.5 --include-raw

# Change RTP threshold
python scripts/download_text_modal_dataset.py \
  --output-dir data/safety_guard_2026_t03 \
  --threshold 0.3

# Keep rows that cannot be mapped to the eight categories (keeps more HarmBench/BeaverTails)
python scripts/download_text_modal_dataset.py \
  --output-dir data/safety_guard_2026_keep_unmapped \
  --keep-unmapped --allow-text-keyword-fallback
```

## Notes

- This is a reconstruction utility, not an official release of the paper's final master dataset.
- Exact counts may vary because upstream Hugging Face datasets can change.
- HarmBench/StrongREJECT keep few rows (~25 / ~213) **by design** — most of their categories fall outside the eight NIST categories and are dropped.
- On a load failure the script prints actionable `FIX:` hints and a per-source `SUMMARY`; it records skipped/unmapped categories and `load_errors` in `metadata.json`. Inspect that file for strict reproducibility.
- See `SKILL.md` for the full troubleshooting table.
- The datasets may contain harmful/offensive text; use them for defensive safety evaluation and respect source licenses.
