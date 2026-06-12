# guard-shieldgemma2

Course project (UniSafe Skills, direction B, M3 multimodal highlight): run image
safety guards over unified `image_safety` JSONL and score them. Model entry
point for agents is [`SKILL.md`](SKILL.md); this README is for humans.

## What it wraps

| guard | type | layer | source |
|---|---|---|---|
| `caption-rule` | keyword baseline on image caption/OCR text (stdlib, deterministic; **pipeline baseline**, never reads pixels) | Core-Minimal | [`assets/caption_keywords.json`](assets/caption_keywords.json) |
| `shieldgemma2` | ShieldGemma 2 4B image classifier, local int8 inference, 3 policies → per-policy yes-probability | Core-Full (M3 Phase 2) | [model card](https://huggingface.co/google/shieldgemma-2-4b-it) (gated; mirror via `--model-id`) |

Same unified guard-result schema and metric definitions as
[`guard-llama-guard`](../guard-llama-guard/) — the Guard interface generalizes
from text to image with zero schema change.

## Reproduce in three steps (zero install, no GPU)

```bash
cd guard-shieldgemma2
python scripts/main.py --input examples/input.sample.jsonl --output-dir out_smoke --guards caption-rule
python scripts/validate.py out_smoke/predictions --against examples/input.sample.jsonl
python scripts/metrics.py --predictions out_smoke/predictions --dataset examples/input.sample.jsonl --output-dir out_smoke/metrics
```

Expected: `RESULT: ok predicted=3 errors=3 skipped=1` (3 errors are deliberate
demo rows: url-only / missing file / missing caption), then `RESULT: PASS`,
then a metrics table in `out_smoke/metrics/metrics.md`. Tests:
`python -m unittest discover -s tests` (stdlib only, no network/GPU; ShieldGemma
live tests are opt-in via `SHIELDGEMMA2_LIVE=1`).

For the ShieldGemma 2 path: install the torch build matching your CUDA/CPU
first, then `pip install -r requirements-shieldgemma.txt`, accept the license
on the HF page (`hf auth login`), then add `--guards caption-rule,shieldgemma2`.
8GB-VRAM machines use the default int8 CUDA load; 4-bit NF4 is documented as
N/A on this stack because it returned NaNs in M3.

## Contracts

- I/O contract (image edition) + exit codes: [`references/io-contract.md`](references/io-contract.md)
- Output record schema (byte-identical with guard-llama-guard, test-locked): [`schemas/guard_output.schema.json`](schemas/guard_output.schema.json)
- Category mapping (3 policies → 22 canonical, = M0 §4): [`references/category_mapping.json`](references/category_mapping.json)
- Metric formulas: inherited verbatim from [`../guard-llama-guard/references/metrics-definitions.md`](../guard-llama-guard/references/metrics-definitions.md) (v1+v2, zero new formulas)
- Synthetic example/fixture images: regenerate via `python scripts/make_synth_images.py` (deterministic, <1KB each, benign by construction)
- Team-level contract: [`../M0_接口约定.md`](../M0_接口约定.md), spec [`../M3_SPEC.md`](../M3_SPEC.md)
