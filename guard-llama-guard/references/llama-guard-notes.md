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

## Spike ① — verdict token splitting & probability extraction

Status: **method implemented generically; exact token ids pending model access**
(see gated note below). Llama Guard 3 outputs `\n\nsafe` or `\n\nunsafe\nS<k>`.
The adapter does not assume "unsafe" is a single token:

1. candidate ids = first sub-token of `encode("safe")` / `encode("unsafe")`;
2. scan generation steps for the first step whose emitted token is one of the
   two candidates (skips leading newline tokens robustly);
3. at that step, `confidence = p(unsafe_first) / (p(unsafe_first) + p(safe_first))`
   (two-way renormalized — comparable across records even when other tokens
   take probability mass);
4. if no verdict token is found, the verdict comes from text parsing and
   `confidence = null` (record stays answered, excluded from AUROC only).

If the spike shows "unsafe" splits into multiple sub-tokens for this tokenizer,
the first sub-token disambiguates against "safe" only if the pair differs at
position 0 — verify and record the actual ids here after access:

- [ ] `encode("safe")` = (pending)
- [ ] `encode("unsafe")` = (pending)
- [ ] chat template tail for prompt-only and pair conversations (pending)

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
