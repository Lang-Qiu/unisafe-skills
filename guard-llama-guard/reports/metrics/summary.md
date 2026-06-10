# Guard metrics summary

- dataset: `examples/tiny_unified.jsonl`
- generated: 2026-06-10T05:23:04.681135+00:00
- positive class = **unsafe**; two denominators per guard (answered-only = classifier quality; failure-as-wrong = system reliability, errors counted as wrong - not a pure classifier metric).

## rule
(join_misses: 0)

| task | mode | n | acc | macro-F1 | recall | FPR | unsafe_fpr_on_safe_probe | AUROC | coverage | error_rate |
|---|---|---|---|---|---|---|---|---|---|---|
| ALL | answered_only | 7 | 0.7143 | 0.7083 | 1.0000 | 0.5000 | 1.0000 | N/A (n/a) | 1.0000 | 0.0000 |
| ALL | failure_as_wrong | 7 | 0.7143 | 0.7083 | 1.0000 | 0.5000 | 1.0000 | - | 1.0000 | 0.0000 |
| prompt_only_safety | answered_only | 4 | 0.7500 | 0.7333 | 1.0000 | 0.5000 | 1.0000 | N/A (n/a) | 1.0000 | 0.0000 |
| prompt_only_safety | failure_as_wrong | 4 | 0.7500 | 0.7333 | 1.0000 | 0.5000 | 1.0000 | - | 1.0000 | 0.0000 |
| prompt_response_safety | answered_only | 3 | 0.6667 | 0.6667 | 1.0000 | 0.5000 | N/A | N/A (n/a) | 1.0000 | 0.0000 |
| prompt_response_safety | failure_as_wrong | 3 | 0.6667 | 0.6667 | 1.0000 | 0.5000 | N/A | - | 1.0000 | 0.0000 |
