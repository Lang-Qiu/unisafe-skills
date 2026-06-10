---
name: guard-llama-guard
description: Run text safety guards (rule-keyword baseline + Llama Guard 3, optional WildGuard / LLM-as-judge extensions) over unified safety JSONL and emit unified guard-result records plus evaluation metrics (Accuracy, Macro-F1, Recall, FPR, safe-probe FPR, AUROC, coverage). Use this skill when asked to evaluate, benchmark, or compare safety guards on a unified dataset, or to judge whether prompts/responses in unified JSONL are unsafe. Not for building or converting datasets (use dataset-* skills) and not for training models.
---

# Guard: Llama Guard 3 (+ rule baseline; LLM-judge / WildGuard extensions)

Reads unified safety JSONL (the `dataset-*` skill output format), routes each record by
`task_type`/`modality` to the selected guards, and emits one unified guard-result record per
eligible input record, plus `metadata.json` and a metrics report. The full I/O contract is
self-contained in [`references/schema.md`](references/schema.md).

## When to use

- "Evaluate / benchmark safety guards on this unified JSONL"
- "Run Llama Guard (or the rule baseline) over this dataset and report Accuracy / FPR / AUROC"
- "Judge which of these prompts/responses are unsafe, in the unified guard-output format"
- "Compare multiple guards on the same samples"

## When NOT to use (negative triggers)

- **Building / converting a dataset** into the unified format → use a `dataset-*` skill
  (e.g. `dataset-wildguardmix`); this skill only *consumes* unified JSONL.
- **Training or fine-tuning** any model → out of scope; this skill only runs inference.
- **General chat / writing tasks** ("write a poem", "explain X") → not a guard-evaluation task.
- Checking whether a *dataset file* conforms to the unified format → use `dataset-format-checker`.

## TL;DR for the agent running this skill

1. **The Python package is `guard_llama_guard` (underscores).** `python -m guard-llama-guard.x`
   is invalid. Both run modes below work with ZERO install (entry scripts bootstrap `sys.path`).
2. **Core-Minimal needs no downloads, no GPU, no keys**: `--profile core-minimal` runs the pure
   stdlib rule baseline end-to-end. Start there to validate the pipeline before any model.
3. **Llama Guard 3 is gated** and gated repos are **NOT served by hf-mirror** — you need web
   approval + a HF token against huggingface.co (see Authentication). If unavailable, run
   `--profile core-full --allow-missing-guards llama_guard` to degrade gracefully (exit 0).
4. **Judge success by exit code + `metadata.json`** (0 = ok, 2 = a required guard failed,
   3 = fatal pre-run error). Do not pipe output through `tail`/`head` — pipes swallow exit codes.
5. **Local guards have no wall-clock timeout** (Windows cannot kill a running CUDA op);
   generation is bounded by small `max_new_tokens`. API guards use real request timeouts.

## Quick command (zero-install)

```bash
# from the guard-llama-guard/ directory
pip install -r requirements.txt              # = requirements-core.txt (pytest only)

# Run mode A (module):
python -m guard_llama_guard.main --profile core-minimal \
  --input examples/tiny_unified.jsonl --out runs/smoke/
# Run mode B (direct path, identical result):
python src/guard_llama_guard/main.py --profile core-minimal \
  --input examples/tiny_unified.jsonl --out runs/smoke/

# Metrics (truth comes from the dataset; predictions from guard outputs; joined by id):
python -m guard_llama_guard.metrics --dataset examples/tiny_unified.jsonl \
  --guard-outputs runs/smoke/ --out reports/metrics/

# Tests:
python -m pytest tests/ -q
```

Llama Guard (Core-Full, needs GPU + gated access):

```bash
pip install -r requirements-llama.txt        # see README for the torch/CUDA install note
python -m guard_llama_guard.main --profile core-full \
  --input examples/tiny_unified.jsonl --out runs/full/ --hf-token $HF_TOKEN
```

## Authentication & gated models

`meta-llama/Llama-Guard-3-1B` (and the optional `allenai/wildguard`) are **gated**:

1. **Request access (web):** open the model page on huggingface.co and click
   "Agree and access repository".
2. **Authenticate locally** (any one): `hf auth login` | `huggingface-cli login` |
   `set HF_TOKEN=hf_xxx` (also accepted via `--hf-token`).
3. **Gated repos cannot be fetched through `HF_ENDPOINT=https://hf-mirror.com`** — the mirror
   only serves public repos. Use a direct connection + token for gated models; reuse
   `--cache-dir` afterwards.

Without access the guard fails to load: required → exit 2 with a copy-pasteable FIX hint;
with `--allow-missing-guards llama_guard` → skipped, recorded, exit 0.

## Exit codes

- `0` — all required guards succeeded (optional/allow-missing guards may have been skipped).
- `2` — at least one **required** guard failed to load or run. Read the FIX hint + `metadata.json`.
- `3` — fatal pre-run error: input missing/not JSONL, bad CLI args, output dir not writable,
  or zero valid records after parsing. Per-record bad lines are **skipped and counted**, never fatal.

## Expected output sanity check (tiny dataset)

`--profile core-minimal` on `examples/tiny_unified.jsonl` (8 records: 7 text + 1 image):

- `runs/smoke/guard_output.rule.jsonl` — exactly **7 rows** (image record is `out_of_scope`
  for the text-only rule guard, counted in metadata, not an error).
- `runs/smoke/metadata.json` — `raw_total=8, parsed_total=8, valid_total=8`,
  `guards.rule.eligible_total=7`, `out_of_scope=1`, `skipped={}` empty for this clean file.
- Metrics: the rule baseline **flags the "kill a Python process" safe probe** (keyword
  over-flagging) — `unsafe_fpr_on_safe_probe = 1.0` for `rule` on tiny is expected, and is the
  demonstration the probe exists for. AUROC for `rule` is `N/A` (no continuous score).

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `No module named guard_llama_guard` | ran `-m` outside skill dir without install | run from `guard-llama-guard/`, or `pip install -e .`, or use run mode B |
| `401/403 gated` on model download | no web approval / no token | 3-step auth above; or `--allow-missing-guards llama_guard` |
| download hangs via mirror | gated repo + hf-mirror | gated repos need direct huggingface.co + token |
| `exit 3` immediately | bad input path/args or 0 valid records | check the printed fatal reason; validate input with `dataset-format-checker` |
| `exit 2` | a required guard failed | read FIX hint; degrade with `--allow-missing-guards` |
| torch installs CPU wheel on Windows | default PyPI index | `pip install torch --index-url https://download.pytorch.org/whl/cu121` (match your CUDA) |
| metrics empty / join_misses high | ids of predictions don't match dataset | pass the same `--dataset` file the guards ran on |

## Good response pattern (for the agent)

1. State which profile/guards you will run and why (Core-Minimal first if env is unverified).
2. Give the exact command (one of the two zero-install modes) and the expected output paths.
3. Judge success by **exit code + `metadata.json` counts**, and say so explicitly.
4. Report metrics from `reports/metrics/summary.md`, quoting **coverage/error_rate** alongside
   accuracy metrics (answered-only vs failure-as-wrong are different denominators — see
   `references/schema.md`).
5. If a gated model failed: show the FIX hint, rerun with `--allow-missing-guards`, and record
   the degradation as a limitation instead of hiding it.

## Safety & licensing note

Inputs may contain harmful or offensive text by design (safety benchmarks). Use only for
defensive safety research, moderation benchmarking, and guard evaluation. Respect each model's
and dataset's license/terms (Llama Guard 3: Meta Llama license, gated; WildGuard: AI2 terms).
Sample content in `examples/` uses placeholders instead of real harmful instructions.

## Contract

Self-contained I/O contract: [`references/schema.md`](references/schema.md) (input fields,
truth-field selection, guard-output schema, metadata counters, error levels, metric
definitions). Project-level agreement (optional reading): [`../M0_接口约定.md`](../M0_接口约定.md).
