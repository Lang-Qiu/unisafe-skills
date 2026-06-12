# guard-llama-guard

Course project (UniSafe Skills, direction B): run text safety guards over unified
safety JSONL and score them. Model entry point for agents is [`SKILL.md`](SKILL.md);
this README is for humans.

## What it wraps

| guard | type | layer | source |
|---|---|---|---|
| `rule` | keyword baseline (stdlib, deterministic) | Core-Minimal | [`assets/rule_keywords.json`](assets/rule_keywords.json) |
| `llama-guard` | Llama Guard 3-1B, local inference | Core-Full (M1 Phase 2) | [model card](https://huggingface.co/meta-llama/Llama-Guard-3-1B) · [Llama Guard paper (arXiv:2312.06674)](https://arxiv.org/abs/2312.06674) · [Llama 3 herd report (arXiv:2407.21783)](https://arxiv.org/abs/2407.21783) |
| `llm-judge` | LLM-as-judge over any OpenAI-compatible chat endpoint (default model `mimo-v2.5-pro`; stdlib urllib, zero install; env `LLM_JUDGE_API_KEY`/`LLM_API_KEY` + `LLM_JUDGE_BASE_URL`) | Core-Full (M2 Phase 2) | [design notes](references/llm-judge-notes.md) — self-reported confidence is **not calibrated** |
| `openai` | OpenAI Moderation API (`omni-moderation-latest`) | Plus (M1 Phase 3) | [docs](https://platform.openai.com/docs/guides/moderation) |

## Reproduce in three steps (zero install)

```bash
cd guard-llama-guard
python scripts/main.py --input examples/input.sample.jsonl --output-dir out_smoke --guards rule
python scripts/validate.py out_smoke/predictions --against examples/input.sample.jsonl
python scripts/metrics.py --predictions out_smoke/predictions --dataset examples/input.sample.jsonl --output-dir out_smoke/metrics
```

Expected: `RESULT: ok predicted=5 errors=0 skipped=1`, then `RESULT: PASS`, then a
Guard × task metrics table in `out_smoke/metrics/metrics.md`. Tests:
`python -m unittest discover -s tests` (82 tests OK, 2 opt-in live skips; stdlib only, no network/keys).

For the Llama Guard path: `pip install -r requirements-llama.txt`, accept the model
license on the HF page, `hf auth login`, then add `--guards rule,llama-guard`.

## Contracts

- I/O contract + exit codes: [`references/io-contract.md`](references/io-contract.md)
- Output record schema: [`schemas/guard_output.schema.json`](schemas/guard_output.schema.json)
- Category mapping (bilateral, = M0 §4): [`references/category_mapping.json`](references/category_mapping.json)
- Metric formulas (positive class = unsafe, dual basis): [`references/metrics-definitions.md`](references/metrics-definitions.md)
- Team-level contract: [`../M0_接口约定.md`](../M0_接口约定.md), spec [`../M1_SPEC.md`](../M1_SPEC.md)
