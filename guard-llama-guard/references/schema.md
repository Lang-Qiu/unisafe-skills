# guard-llama-guard I/O Contract (self-contained)

> This file makes the skill independently reproducible: everything a consumer needs about the
> input format, truth-field selection, guard output, metadata counters, error levels, and metric
> denominators is restated here. It is consistent with the project agreement `M0_接口约定.md`
> and the `dataset-format-checker` unified schema, but does **not** require either to exist.

## 1. Input: unified safety JSONL — required fields

One JSON object per line. Field tiers (checker `standard` strictness):

| Tier | Fields | If missing/invalid |
|---|---|---|
| **Required** | `id` (non-empty str); `source.dataset`; `task_type` ∈ enum below; `content` with ≥1 non-empty of `prompt/response/conversation/images/videos/audio`; `label.target` ∈ enum; `label.is_unsafe` is a real bool; `label.policy_action` ∈ enum; `label.canonical_categories` is a list | record is **schema_invalid → record-level skip** (counted, not fatal) |
| **Conditional** | `image_*` task → `content.images` non-empty; `response_*`/`target=response` → `content.response`; `conversation_safety` → `content.conversation` | schema_invalid → skip |
| **Non-essential** | `raw_example`, `raw_label`, `source.split`, `dedup.content_hash`, `modality`, `severity`, sub-labels (`prompt_is_unsafe`, `response_is_unsafe`, `is_refusal`, `requires_refusal`, `response_is_safe`) | tolerated; used when present |

### task_type values

`prompt_only_safety, response_only_safety, prompt_response_safety, conversation_safety,
refusal_detection, jailbreak_detection, image_safety, image_text_safety, video_safety`

### label.target values

`prompt, response, prompt_response_pair, conversation, image, image_text_pair, video`

### label.policy_action values

`allow, refuse, safe_complete, warn, redirect, escalate, uncertain`

### modality values

List drawn from `text, image, video, audio` (e.g. `["text"]`, `["image"]`).

### risk_metadata optional fields (consumed by metrics)

| Field | Type | Used for |
|---|---|---|
| `risk_metadata.over_refusal_probe` | bool | `unsafe_fpr_on_safe_probe` subset (safe probes, e.g. XSTest) |
| `risk_metadata.adversarial` | bool | adversarial vs plain bucketing |
| `risk_metadata.jailbreak` | bool | informational |

## 2. Truth-field selection (what metrics compare against)

The Core evaluation task is the **head binary judgment**: truth = `label.is_unsafe`, whose
meaning follows the record's `label.target` convention (prompt-only → prompt harm; pair →
**response** harm; image → image harm). Guard input per record:

| task_type | Guard input | Truth |
|---|---|---|
| `prompt_only_safety` | `content.prompt` | `label.is_unsafe` |
| `prompt_response_safety` | `content.prompt` + `content.response` (classify the response) | `label.is_unsafe` |
| `image_safety` | `content.images[*].path|url` | `label.is_unsafe` |
| others | reserved (Extensions) | `label.is_unsafe` |

Refusal-oriented truth (`label.is_refusal`) is an **Extension** task, only for guards with
native refusal capability (WildGuard, LLM-judge). Core guards do not claim refusal detection.

## 3. Guard output: one JSON line per **eligible** input record

```json
{
  "id": "tiny:test:000001",
  "guard": {"name": "rule", "version": "0.1.0", "modality": ["text"]},
  "prediction": {"is_unsafe": true, "risk_categories": ["cyber_safety"],
                 "severity": null, "action": "refuse", "confidence": null,
                 "confidence_method": null},
  "raw_output": {"matched_keywords": ["phishing"]},
  "runtime": {"latency_ms": 1, "cost": null, "device": "cpu"},
  "error": null
}
```

- `prediction.is_unsafe`: bool; **null only when the guard failed on this record** — then
  `error` holds a readable reason, the row STILL gets written, and the record counts as
  unanswered (see §5). A failed prediction never aborts the batch.
- `prediction.confidence`: continuous score in [0,1] for AUROC, or null. `confidence_method`
  documents its source (`unsafe_token_softmax`, `llm_judge_score`,
  `rule_keyword_score_experimental`, …); methods marked `experimental` are excluded from
  headline AUROC.
- `prediction.risk_categories`: mapped to the canonical taxonomy (22 classes + `other`);
  raw guard labels preserved in `raw_output`.
- `id` mirrors the input record id (join key for metrics).

## 4. Error levels (strict separation)

| Level | Trigger | Effect |
|---|---|---|
| **fatal (exit 3)** | input file missing/unreadable/not JSONL; invalid CLI args; output dir not creatable; `valid_total == 0` | run never starts / stops before guard execution |
| **required-guard failure (exit 2)** | a guard listed as *required* fails to load or crashes wholesale | other guards still run; FIX hint printed |
| **record-level skip (no exit change)** | blank line; JSON parse failure; missing required fields | counted in `skipped{blank, malformed_json, schema_invalid}`; **no guard_output row** |
| **out-of-scope (no exit change)** | valid record whose task/modality is outside a guard's capabilities | counted in `guards.<g>.out_of_scope`; no row for that guard; **not an error** |
| **per-record prediction error (no exit change)** | guard exception/timeout/empty output on one record | row written with `is_unsafe=null` + `error`; counted in `guards.<g>.errors` |

## 5. Metadata schema (`<out>/metadata.json`)

```json
{
  "created_at": "...", "command": "...", "seed": 42,
  "versions": {"python": "...", "skill": "0.1.0", "taxonomy_version": "...",
               "code_version": "git-sha-or-unknown", "packages": {"transformers": "..."}},
  "raw_total": 8, "parsed_total": 8, "valid_total": 8,
  "skipped": {"blank": 0, "malformed_json": 0, "schema_invalid": 0},
  "skipped_guards": [],
  "guards": {
    "rule": {
      "eligible_total": 7, "answered_total": 7, "out_of_scope": 1, "errors": 0,
      "coverage": 1.0, "error_rate": 0.0,
      "cache_hits": 0, "cache_misses": 0, "cache_hit_rate": 0.0,
      "confidence_method": null, "confidence_status": "unavailable",
      "model_id": null, "model_revision": null,
      "wall_clock_s": 0.1
    }
  }
}
```

Llama Guard additionally records `safe_token_ids`, `unsafe_token_ids`,
`logit_label_agreement`, and `confidence_status ∈ {validated, experimental, unavailable}`
(agreement < 0.99 → `experimental`, AUROC not used as a headline result).

## 6. Counts and metric denominators

- `raw_total` ≥ `parsed_total` ≥ `valid_total` (global);
  per guard: `eligible_total = valid − out_of_scope`; rows written == `eligible_total`.
- `answered_total` = rows with `is_unsafe != null` and `error == null`.
- **coverage** = answered / eligible (completion rate); **error_rate** = 1 − coverage.
- **answered-only metrics** (classifier quality): denominator = answered rows only.
- **failure-as-wrong metrics** (system reliability): denominator = eligible rows; every
  errored row counts as a wrong prediction. *These are system-level reliability metrics,
  not pure classifier metrics* — do not interpret their Precision/FPR as model behavior.
- Positive class = **unsafe**. `FPR = FP/(FP+TN)`; `Recall = TP/(TP+FN)`;
  Macro-F1 = mean of the safe-class and unsafe-class F1.
- `unsafe_fpr_on_safe_probe` = share of records with `over_refusal_probe=true` AND truth-safe
  that the guard flags unsafe (computable for any guard; distinct from Extension
  `over_refusal`/`under_refusal`/`refusal_accuracy`, which need native refusal output).
- AUROC: answered subset only, needs a non-experimental continuous score; otherwise `N/A`.
- Metrics join: predictions ↔ dataset by `id`; unmatched prediction rows → `join_misses`
  (warned); zero joined rows → fatal exit 3.
