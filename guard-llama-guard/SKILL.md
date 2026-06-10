---
name: guard-llama-guard
description: Run text safety guards (Llama Guard 3, keyword rule baseline, OpenAI
  Moderation) over unified safety JSONL records and emit unified guard-result JSONL
  plus evaluation metrics (Accuracy, Macro-F1, Recall, FPR, AUROC, Over-refusal).
  Use this skill when the user asks to run, evaluate, score, or benchmark a guard or
  moderation model on a unified safety dataset, or to compute guard safety metrics.
  Not for building or converting datasets (use dataset-* skills) and not for checking
  dataset format (use dataset-format-checker).
---

# guard-llama-guard

Reads unified safety JSONL (data that passed `dataset-format-checker`), routes each
record by `task_type`/`modality`, runs the requested text guards, and writes unified
guard-result JSONL + a Guard × task metrics table. **Read-only**: the input dataset is
never modified. Core loop is pure stdlib (Python >= 3.9, no install, no network).

## When to use

- "Run Llama Guard on this dataset" / "用 guard 评测这份统一数据集"
- "Score these guard predictions" / "算一下 guard 的指标（Recall/FPR/AUROC）"
- "Benchmark the rule baseline against Llama Guard"
- "How often does the guard over-refuse on XSTest probes?"

## When NOT to use

- Building/converting a dataset → `dataset-wildguardmix` (or other dataset-* skills)
- Checking dataset format/schema → `dataset-format-checker`
- Image safety guards → `guard-shieldgemma2` (M3; image records here are skipped+counted)

## TL;DR for the agent

1. Judge results by **exit code + the final `RESULT:` line** — never pipe through `tail`.
2. Positive class = **unsafe**. FPR denominator is FP+TN (truth-safe records). Don't flip it.
3. Gated 401/403 → three steps: accept license on the model page → `hf auth login` →
   re-run. Meanwhile rule-baseline results still land on disk (exit 2 = partial, not a crash).
4. No GPU / no token? Run the zero-install smoke first (`--guards rule`).
5. `prediction.is_unsafe=null` is a legal **error record** (kept on disk, counted, dual-basis
   metrics handle it). Do not "fix" such rows.

## Quick workflow

Smoke (zero install, < 60 s, from this skill's directory):

```bash
python scripts/main.py --input examples/input.sample.jsonl --output-dir out_smoke --guards rule
python scripts/validate.py out_smoke/predictions --against examples/input.sample.jsonl
python scripts/metrics.py --predictions out_smoke/predictions --dataset examples/input.sample.jsonl --output-dir out_smoke/metrics
```

PowerShell: identical commands (paths use `/` fine; no glob expansion needed — pass
files or directories, never wildcards).

Full (Core-Full, GPU + HF gated access; adapter lands in M1 Phase 2 — until then
`--guards llama-guard` exits 1 as an unknown guard):

```bash
python -m venv .venv && . .venv/Scripts/activate   # PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements-llama.txt
python scripts/main.py --input <unified_dir> --output-dir out --guards rule,llama-guard --batch-size 8 --limit 200
```

Dependency layers: `requirements.txt` = core loop, **comments only, installs nothing**
(stdlib is enough); `requirements-llama.txt` = Llama Guard path; `requirements-api.txt`
= optional OpenAI Moderation baseline (Plus).

## Input format

Unified safety JSONL (one record/line) or a directory of `*.jsonl`. M1 consumes only
text records: `task_type ∈ {prompt_only_safety, prompt_response_safety}` and
`modality == ["text"]`; anything else is skipped and counted, never an error.
Consumed fields + eligible definition: [`references/io-contract.md`](references/io-contract.md) §1–2.

## Output format

One JSON per line (schema: [`schemas/guard_output.schema.json`](schemas/guard_output.schema.json)):

```json
{"id": "wildguardmix:test:000001",
 "guard": {"name": "rule", "version": "1.0", "modality": ["text"]},
 "prediction": {"is_unsafe": true, "risk_categories": ["cyber_safety"],
                "severity": null, "action": "refuse", "confidence": null},
 "raw_output": {"engine": "keyword-regex-v1", "matched": {"cyber_safety": ["phishing"]}},
 "runtime": {"latency_ms": 0.2, "cost": null, "device": "cpu"}, "error": null}
```

File layout under `--output-dir`: `predictions/<guard>.predictions.jsonl` +
`metrics/metrics.{json,md}` + `run_metadata.json`. Conservation: prediction lines =
eligible records (error rows included; skipped records excluded).

## Execution steps

1. Confirm the input path (file or directory of unified JSONL).
2. Pick guards (`--guards rule` zero-install; add `llama-guard` when GPU+token ready).
3. Run `scripts/main.py`; read exit code + `RESULT:` line.
4. Run `scripts/validate.py <out>/predictions --against <input>` (add
   `--metadata <out>/run_metadata.json` to also cross-check skip counts).
5. Run `scripts/metrics.py`; deliver `metrics/metrics.md` to the user.

## Failure handling

| code | meaning | `main.py` | `validate.py` | `metrics.py` |
|---|---|---|---|---|
| **0** | full success | all requested guards succeeded | PASS | metrics produced |
| **1** | failure (data/fatal) | fatal input/output, or **ALL** guards failed | FAIL (violations) | no joinable records / bad args / unimplemented flag |
| **2** | non-data degradation | partial: >=1 guard ok, >=1 guard-level failure | usage/IO error | usage/IO error |

Rulings: `--guards llama-guard` with no HF token → all-failed → **1**; `--guards
rule,llama-guard` with no token → rule succeeds → **2**; the smoke (`--guards rule`)
never needs tokens → **0**. Plus/API guards (OpenAI) stay out of the smoke and default
CI; missing keys only matter when you explicitly request those guards.

Error tiers (full table: [`references/io-contract.md`](references/io-contract.md) §4):
guard-level failure → skip guard + `FIX:` hint; record-level error → row kept with
`is_unsafe=null`; out-of-scope → skipped + counted.

## Sanity check (expected numbers)

| run | expectation |
|---|---|
| smoke on `examples/input.sample.jsonl` | `RESULT: ok predicted=5 errors=0 skipped=1` (1 image skip) |
| validate `--against` | `RESULT: PASS files=1 records=5`, exit 0 |
| metrics (rule) | head_binary Acc=0.8, Recall=1.0, FPR=0.3333; AUROC `-` (rule has no confidence); over-refusal probe FPR=1.0 with low_sample_warning |
| golden | output matches `examples/output.sample.jsonl` field-for-field except `runtime.latency_ms` |
| tests | `python -m unittest discover -s tests` → 35 tests OK, no keys/network needed |

Llama Guard sanity ranges: to be filled after Core-Full lands (M1 Phase 2).

## Good response pattern

When done, report: the exact commands run, exit codes, the three counts
(predicted/errors/skipped), the metrics table (or its path), and the output directory.

## Troubleshooting

| symptom | fix |
|---|---|
| 401/403 on model download | accept license on the HF model page → `hf auth login` → re-run; rule results are unaffected meanwhile |
| `No module named torch` | only the llama-guard path needs it: `pip install -r requirements-llama.txt`; or run `--guards rule` |
| CUDA out of memory | `--device cpu` (slow but works for 1B) or smaller `--batch-size`, or `--limit` |
| PowerShell passes literal `*.jsonl` | pass the directory instead of a glob; scripts discover `*.jsonl` themselves |
| AUROC is `-`/null for rule | expected: the rule baseline has no continuous confidence |
| many timeouts | raise `--timeout-s` (soft timeout: CUDA steps can't be interrupted mid-flight) |
| `RESULT: partial` (exit 2) | some guard failed guard-level; read its `FIX:` line; completed guards' outputs are valid |

## Safety & limitations

Datasets contain harmful text used strictly for defensive guard evaluation. Guard
verdicts are predictions, not ground truth — both misses and over-refusals occur (the
keyword baseline deliberately over-flags homonym probes like "kill a process"). Respect
model/dataset licenses; never commit HF tokens or API keys (run_metadata redacts them).
