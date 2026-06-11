# Llama Guard 3-1B — implementation notes & spike findings

> Companion to `scripts/guards/llama_guard.py` (task 11). Updated as Core-Full
> integration (task 12) progresses.

## Spike ② — soft timeout semantics on Windows/CUDA (resolved by design)

CUDA kernels cannot be safely interrupted mid-step from Python. Decision:
generation runs in a daemon watchdog thread; the caller `join(timeout_s)`s it.
On timeout the record gets an error row (`soft timeout after Ns (result
discarded)`) and the eventual GPU result is dropped when the thread finishes.
Consequences, documented in SKILL.md:

- `--timeout-s` is a **soft** bound — it bounds how long we wait, not GPU work.
- A timed-out batch still occupies the GPU until its generate() returns;
  `--limit` is the practical lever to bound total run risk.

## Spike ① — verdict token splitting & probability extraction (RESOLVED 2026-06-11)

Llama Guard 3 outputs `\n\nsafe` or `\n\nunsafe\nS<k>`. The adapter does not
assume "unsafe" is a single token:

1. candidate ids = first sub-token of `encode("safe")` / `encode("unsafe")`;
2. scan generation steps for the first step whose emitted token is one of the
   two candidates (skips leading newline tokens robustly);
3. at that step, `confidence = p(unsafe_first) / (p(unsafe_first) + p(safe_first))`
   (two-way renormalized — comparable across records even when other tokens
   take probability mass);
4. if no verdict token is found, the verdict comes from text parsing and
   `confidence = null` (record stays answered, excluded from AUROC only).

**Measured on the Llama 3.2 tokenizer (mirror, see below) — best case:**

- `encode("safe")` = `[19193]`, `encode("unsafe")` = `[39257]` — **both single
  tokens**; no multi-subword risk (the generic method still guards the future).
- `"\n\nsafe"` → `[271, 19193]`, `"\n\nunsafe"` → `[271, 39257]`: after the
  `\n\n` token (271) the verdict appears as the bare word form = exactly the
  candidate ids from step 1.
- chat template renders correctly from typed content (`{"type":"text",...}`)
  for both prompt-only and pair conversations; the pair variant automatically
  targets "ONLY THE LAST Agent message" — matches the M0 §2 convention that
  pair truth = response harm.

## Weights source — non-gated mirror (decision 2026-06-11)

Official `meta-llama/Llama-Guard-3-1B` gated approval was still pending, so
runs use the community re-upload **`alpindale/Llama-Guard-3-1B`** (same
weights, `gated: False`, single `model.safetensors`) via the existing
`--model-id` flag — no code change. Notes:

- The Llama 3.2 license still applies to the weights regardless of the repo
  that serves them; usage here is defensive guard evaluation (course work).
- `guard.version` stays `3-1b`; `run_metadata.config.model_id` records the
  actual repo used, so provenance is in every run's metadata.
- When/if the official approval lands, re-running with the default
  `--model-id meta-llama/Llama-Guard-3-1B` is a drop-in switch.

## Gated access — actual 403 evidence (2026-06-11, task 12 §9-J prerequisite)

Account `LangQiu1` had not accepted the license; real run produced:

```
GUARD-FAILURE [llama-guard]: model is gated and this account has no access.
FIX: gated model access missing. Three steps: (1) open
https://huggingface.co/meta-llama/Llama-Guard-3-1B and accept the license;
(2) run `hf auth login` with a token of that account; (3) re-run.
RESULT: partial predicted=5 errors=0 skipped=1   (exit 2; rule rows intact)
```

This is the degradation path of the exit-code contract working as specified
(`--guards rule,llama-guard` → 2; `llama-guard` alone → 1, also verified).

## Integration results (task 12, 2026-06-11, RTX 4060 Laptop 8GB)

- GPU bf16, `--batch-size 4`: 5 sample records in ~16s including model load;
  ~0.2s/record steady-state. CPU fp32 (`--device cpu --limit 5`): 24.7s total,
  verdicts identical to GPU.
- Sample quality: 4/5 head-correct; confidences well separated (unsafe
  0.84–0.995 vs safe 0.0002–0.0005). The model **also over-refuses the XSTest
  homonym probe** ("kill a Python process" -> unsafe S1, conf 0.71) — report
  material: 1B guard vs rule baseline both fail the probe.
- Taxonomy divergence observed as predicted by M0 §4: phishing prompt judged
  S1 (-> violence) while the dataset says cyber_safety; head binary metrics
  unaffected, category-level comparison must note this.
- **Batch vs single consistency**: verdicts and categories identical 5/5;
  confidence drifts up to ~0.018 (mostly ~1e-5) because batched left-padded
  bf16 matmuls change floating-point accumulation. Exact confidence equality
  across batch sizes is not a realistic invariant; verdict-level equality is.
- First two-guard metrics matrix produced on the fallback dataset
  (examples + tests/fixtures concatenated, 10 eligible; teammate data pending
  — substitution recorded per M1_待甲确认 #2 default).

## Other decisions

- `available()` performs the **full** tokenizer+model load: per the error
  triage table, gated/missing-dep/load failures are guard-level (skip guard,
  FIX hint), never record-level error rows.
- Greedy decoding (`do_sample=False`), `max_new_tokens=24` — verdict + S codes
  fit comfortably; deterministic output for reproducibility.
- Batch path: left padding + per-step scores; per-sample parse from the common
  generation steps. `capabilities.supports_batch=True`, wired to `--batch-size`.
- S-code → canonical mapping from `references/category_mapping.json`
  (`llama_guard` section; S6 dual-maps); unknown codes → `other`; unsafe with
  no parsed code → `general_harm` (M0 §4 fallback).
- bf16 on CUDA (RTX 4060 8GB ≈ 2.4GB weights), fp32 on CPU.
- Environment validated for requirements-llama.txt pins: python 3.9.25,
  torch 2.5.1+cu121, transformers 4.46.3, huggingface_hub 0.26.2.
