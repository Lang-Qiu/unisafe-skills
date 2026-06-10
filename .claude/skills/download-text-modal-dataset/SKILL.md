---
name: download-text-modal-dataset
description: Download and normalize text-only safety guard benchmark datasets into a unified JSONL format. Use this skill when the user asks to reproduce or construct the 2026 “Benchmarking Open-Source Safety Guard Models” dataset, or asks to download HarmBench, StrongREJECT, RealToxicityPrompts, and BeaverTails into a usable text safety/moderation dataset.
---

# download-text-modal-dataset

This skill downloads and normalizes text-only safety/moderation datasets into a common JSONL schema.

Primary use case: construct a paper-like dataset for **Benchmarking Open-Source Safety Guard Models: A Comprehensive Evaluation (2026)** from these public source datasets:

- `walledai/HarmBench` (gated; multiple configs)
- `walledai/StrongREJECT` (gated)
- `allenai/real-toxicity-prompts`
- `PKU-Alignment/BeaverTails`, default split `30k_train`

Important: the paper describes a 79,331-sample curated benchmark, but does not appear to release a single consolidated dataset artifact. This skill reconstructs a transparent, configurable, paper-like dataset from public sources. Exact counts may differ if upstream datasets change, access-gated datasets are unavailable, or source schemas change.

## When to use

Use this skill when the user asks for any of the following:

- “download the Benchmarking Open-Source Safety Guard Models dataset”
- “construct the safety guard benchmark data”
- “download HarmBench / StrongREJECT / RealToxicityPrompts / BeaverTails and format them”
- “make a unified JSONL for harmful content / safety guard evaluation”
- “use download-text-modal-dataset to construct usable data”

## TL;DR for the agent running this skill

Read these five points before running anything — they are the failure modes seen in practice:

1. **Install into an isolated env** (venv/conda) using `python -m pip`, never bare `pip`. The system Python often has no `pip` and no `huggingface-cli`.
2. **HarmBench & StrongREJECT are gated.** Without access they are skipped automatically; the script still builds the dataset from the other sources and returns **exit code 2** (partial failure, *not* a crash).
3. **The output file is OVERWRITTEN on every run.** To backfill gated sources later, re-run with `--sources all` — never a partial `--sources`, or you drop the other sources.
4. **Judge success by the exit code and the final `SUMMARY` / `metadata.json`** — not by piping to `tail`/`head` (a pipe swallows the script's real exit code).
5. **Small HarmBench/StrongREJECT counts are expected** (~25 and ~213). Most of their categories are dropped by the paper-like filter on purpose; this is not a bug.

## Required user confirmations

If the user did not specify them, ask for or assume sensible defaults for:

1. `output_dir`: default `data/safety_guard_2026`
2. dataset sources: default `all`
3. Hugging Face access: HarmBench and StrongREJECT are gated — see **Authentication & gated datasets** below.
4. whether they want paper-like filtering: default yes.

If the user wants an immediately runnable answer, provide the commands below without extra discussion.

## Quick command

Run from the skill folder. Steps 1–3 are one-time setup.

```bash
# 1) Isolated environment (do NOT install into system Python).
python -m venv .venv && source .venv/bin/activate
#    If venv fails with "No module named ensurepip", use conda instead:
#    conda create -n harmful-content python=3.10 -y && conda activate harmful-content

# 2) Dependencies. Use `python -m pip`, not bare `pip`.
python -m pip install -r requirements.txt

# 3) Authentication — ONLY needed for the gated sources (HarmBench, StrongREJECT).
#    Skip this step if you only want RealToxicityPrompts + BeaverTails.
#    See "Authentication & gated datasets" for the required web-approval step.
hf auth login            # new CLI; or: huggingface-cli login ; or: export HF_TOKEN=hf_xxx

# 4) Build the dataset.
python scripts/download_text_modal_dataset.py \
  --output-dir data/safety_guard_2026 \
  --sources all \
  --threshold 0.5 \
  --include-raw
```

The final normalized dataset is written to:

```text
data/safety_guard_2026/normalized/safety_guard_2026.jsonl
```

Metadata and counts are written to:

```text
data/safety_guard_2026/normalized/metadata.json
```

In addition, the same data is written in the **unified nested schema** validated by the
sibling skill `dataset-format-checker` (see `safety_dataset_format_guide.md`). This is
**purely additive** — it never modifies `raw/` or `normalized/`:

```text
data/safety_guard_2026/unified/safety_guard_2026.unified.jsonl
data/safety_guard_2026/unified/metadata.json
```

Self-check that this extra output conforms (exit 0 = PASS):

```bash
python ../dataset-format-checker/scripts/check_dataset_format.py data/safety_guard_2026/unified
```

Pass `--no-unified` to the downloader to skip this extra output.

## Authentication & gated datasets

`walledai/HarmBench` and `walledai/StrongREJECT` are **gated**. Web approval alone is not enough — the download also needs local credentials. Three steps:

1. **Request access (web):** open each dataset page and click **“Agree and access repository”**:
   - https://huggingface.co/datasets/walledai/HarmBench
   - https://huggingface.co/datasets/walledai/StrongREJECT
2. **Authenticate locally** (any one):
   - `hf auth login` (huggingface_hub ≥ 1.0 ships the `hf` CLI; `huggingface-cli` may not exist)
   - `huggingface-cli login` (older versions)
   - `export HF_TOKEN=hf_xxx` (get a read token at https://huggingface.co/settings/tokens) — the script also accepts `--hf-token`.
3. **Run** with `--sources all`.

If you skip authentication, the script logs the failure to `metadata.json` → `load_errors`, builds the dataset from the remaining sources, prints a `FIX (gated dataset)` hint, and exits with code **2**.

## Exit codes

- `0` — all requested sources loaded successfully.
- `2` — **partial success**: at least one source failed to load (almost always gated/auth). The dataset *was still produced* from the sources that worked. Inspect `metadata.json` → `load_errors`, fix access, then re-run `--sources all`. This is not a crash.

## Expected counts (sanity check)

Approximate, with defaults (`--threshold 0.5`, dedupe on); upstream changes shift these:

| Source | Raw | Kept (normalized) |
|---|---|---|
| RealToxicityPrompts | ~99,442 | ~99,000 (safe + unsafe) |
| BeaverTails `30k_train` | ~27,186 | ~4,800 (heavy category filtering) |
| StrongREJECT | ~313 | ~213 |
| HarmBench (standard+contextual) | ~300 | ~25 |
| **Total (all 4, deduped)** | | **~104,000** |

HarmBench/StrongREJECT are small because most of their categories (chemical/biological, cyber, illegal goods, disinformation, copyright) are intentionally dropped — they fall outside the eight NIST categories. To keep more, add `--allow-text-keyword-fallback` and/or `--keep-unmapped` (this departs from the paper-like default).

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `No module named pip` / `pip: command not found` | system Python has no pip | use an isolated env and `python -m pip`; if `venv` lacks `ensurepip`, use conda |
| `huggingface-cli: command not found` | new `huggingface_hub` ships `hf`, not `huggingface-cli` | use `hf auth login`, or the env's absolute path to the CLI |
| `... is a gated dataset` / 401 / 403 | no access or not logged in | web "Agree and access" → authenticate → re-run `--sources all` (see Authentication) |
| `Config name is missing` | dataset has multiple configs | HarmBench is already handled; for other datasets, add the config to `SOURCE_CONFIGS` (the script prints the available configs) |
| script exits with code `2` | a source failed to load | not a crash — read `metadata.json` → `load_errors`, fix, re-run `--sources all` |
| HarmBench/StrongREJECT have very few rows | paper-like filter drops most categories | expected; add `--keep-unmapped` / `--allow-text-keyword-fallback` to keep more |
| all sources 0 rows / network errors | no network / HF unreachable | check connectivity; in restricted networks try a mirror, e.g. `export HF_ENDPOINT=https://hf-mirror.com` |

## Unified schema

> This is the **flat** common schema shared across the four sources (the
> `normalized/` output). A second, **nested** copy that conforms to
> `dataset-format-checker` is also written to `unified/` — see the Quick command
> output section and `scripts/to_unified_format.py`.

Each output JSONL record has this schema:

```json
{
  "id": "rtp:train:0",
  "source_dataset": "real_toxicity_prompts",
  "source_split": "train",
  "text": "User-facing prompt or behavior text",
  "response": null,
  "safety_label": "safe|unsafe",
  "label": 0,
  "nist_safety_categories": ["harassment"],
  "category_scores": {"harassment": 0.73},
  "confidence": 0.73,
  "original_category": "toxicity/insult",
  "source_id": "original source id if available",
  "metadata": {}
}
```

Label convention:

- `label = 1`: unsafe
- `label = 0`: safe

NIST safety categories used by the skill:

- `violence`
- `hate_speech`
- `harassment`
- `sexual_content`
- `suicide_self_harm`
- `profanity`
- `threats`
- `health_misinformation`

## Paper-like construction logic

The downloader follows these default rules:

1. RealToxicityPrompts
   - Uses toxicity-score dimensions except flirtation.
   - Combines prompt and continuation scores by averaging available scores per dimension.
   - Marks a sample unsafe if the maximum mapped category score is greater than or equal to `--threshold`, default `0.5`.
   - Keeps safe and unsafe samples.

2. BeaverTails
   - Uses category annotations when present.
   - Keeps samples mapped to the eight NIST safety categories.
   - Drops categories related to terrorism/weapons, financial crime, privacy, politics, and non-violent unethical behavior by default.
   - Output labels are unsafe for retained harmful categories.

3. HarmBench and StrongREJECT
   - HarmBench requires a config: the script loads the `standard` and `contextual` behavior configs and **skips `copyright`** (see `SOURCE_CONFIGS` in the script).
   - Treat retained samples as unsafe, because these are adversarial/refusal-style datasets.
   - Uses source category fields when available.
   - Drops copyright, cyber/security, general illegal activity, and non-safety misinformation categories by default — which is why retained counts are small.

## Scripts

- `scripts/download_text_modal_dataset.py`: main downloader and normalizer. On a load failure it prints actionable `FIX:` hints; at the end it prints a `SUMMARY` of per-source success/failure. By default it also emits the unified-nested output (disable with `--no-unified`).
- `scripts/to_unified_format.py`: converts the flat `normalized/` records into the unified nested schema for `dataset-format-checker` (pure stdlib). Run standalone on an existing file: `python scripts/to_unified_format.py --input normalized/safety_guard_2026.jsonl --output unified/safety_guard_2026.unified.jsonl`.
- `scripts/validate_output.py`: validates the flat normalized JSONL schema and reports counts.

## Good response pattern

When using this skill, provide:

1. install command **in an isolated env** (`python -m pip install -r requirements.txt`)
2. for gated sources, the **three-step authentication** (web approval → login → run)
3. the download/format command and the output paths
4. how to judge success: **exit code + final `SUMMARY` + `metadata.json`** (do not rely on `| tail`/`| head`, which hide the exit code)
5. to backfill gated sources later: **re-run with `--sources all`** (the output file is overwritten; a partial `--sources` drops the others)
6. note that HarmBench/StrongREJECT keep few rows by design, and that this reconstructs the benchmark from public sources rather than downloading an official released master file

## Safety and licensing note

These datasets may contain harmful or offensive text. Use them only for safety research, moderation benchmarking, red-teaming evaluation, or defensive model assessment. Always check and respect each source dataset’s license and access terms.
