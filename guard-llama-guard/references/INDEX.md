# references/ index

| File | Content | Status |
|---|---|---|
| [schema.md](schema.md) | **Self-contained I/O contract**: input fields, truth selection, guard-output schema, metadata counters, error levels, metric denominators | authoritative |
| [../schemas/guard_output.schema.json](../schemas/guard_output.schema.json) | Guard-output JSON Schema (machine-checkable; enforced by `scripts/validate.py`) | authoritative |
| optimization_notes.md | Performance ablation study (template correctness, logit scoring, threshold calibration, throughput, parsing robustness, cache/resume, optional vLLM) | produced in Plus P2 |
| trigger_eval.md | Skill trigger / mis-trigger evaluation set + results (P3a static proxy, P3b platform evidence) | produced in Plus P3 |

External (optional reading, NOT required for reproduction — schema.md is self-contained):

- `../../M0_接口约定.md` — project-wide interface agreement (dataset ↔ guard)
- `dataset-format-checker` example skill — validates the *input* dataset format
