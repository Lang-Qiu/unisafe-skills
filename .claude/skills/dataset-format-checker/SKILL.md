---
name: dataset-format-checker
description: Read-only checker that verifies whether a harmful-content / safety guard dataset (a directory or a single JSONL/JSON/CSV file) conforms to the unified safety schema, and reports PASS or FAIL. Use this skill when the user asks to check, verify, validate, or audit that a safety dataset — often one produced by another skill — matches the required unified format, including which fields are missing and whether field coverage is adequate. Non-essential fields that a dataset genuinely cannot provide (e.g. images for a text-only dataset) are tolerated.
---

# Dataset Format Checker

This skill **checks** whether a harmful-content / safety dataset conforms to a unified
JSONL schema and reports whether it **PASSES**. It does **not** convert or modify data.

Point it at a **directory** (e.g. an output folder produced by another skill) or a single
file. It scans every record, classifies each field as **required / conditional / non-essential**,
and prints a PASS/FAIL verdict with the exact problems and where they occur.

## When to use

- "check / verify / validate that this dataset is in the right format"
- "does `data/<...>` conform to the unified safety schema?"
- "audit the fields of this guard dataset; what's missing?"
- "did the dataset another skill generated come out in the correct format?"

## Two modes

Route by what the user is asking for:

### Mode 1 — provide a format guide
When the user wants the spec itself ("what should my data look like", "give me the format
guide", "I need to generate conformant data"), generate the authoring guide to the location
the user specifies:

```bash
python scripts/check_dataset_format.py --emit-guide <path/to/format_guide.md>
# add --force to overwrite an existing file
```

If the user didn't give a path, ask for one (or default to `./safety_dataset_format_guide.md`).
The guide is generated from the checker's own rules, so it always matches what the check
enforces — hand it to whoever (or whatever skill) produces the data.

### Mode 2 — check a directory
When the user wants to verify existing data ("check this directory"), run the checker and guide
them through the result — see **Check workflow** below.

## Check workflow (Mode 2)

1. Confirm the target path (a directory or a single file). Directory discovery defaults to `*.jsonl`.
2. Run: `python scripts/check_dataset_format.py <path>`
3. Read the verdict from the **exit code** + `RESULT:` line (never from `| tail`).
4. Guide the user by outcome:
   - **PASS / PASS (with warnings)** — conforms; mention warnings as optional polish.
   - **FAIL with a "flat schema" note** — the data is in a different/un-nested schema. Offer
     Mode 1 (`--emit-guide`) so they can regenerate/convert it to the unified shape, then re-check.
   - **FAIL on specific codes** — walk through the top ERROR codes and their example `file:line`
     locations; map each to its fix (both the report and the guide list fixes).
5. Re-run after each fix until the exit code is `0`.

## Read-only guarantee

The checker **never writes to or modifies the dataset being checked**. It only opens files
for reading. The only files it ever writes are ones **you** explicitly request: a JSON report
via `--report`, or the format guide via `--emit-guide` — both to paths you choose. Safe to run
on data you cannot afford to alter.

## Quick command

No installation needed — the checker is **pure Python standard library** (Python ≥ 3.8),
so any `python3` works; no `pip install`.

```bash
# Check a whole directory (auto-discovers *.jsonl, skips metadata/manifest/etc.)
python scripts/check_dataset_format.py data/safety_guard_2026

# Check a single file
python scripts/check_dataset_format.py path/to/dataset.jsonl

# Also discover .json, and save a machine-readable report
python scripts/check_dataset_format.py data/my_dataset \
  --include-ext .jsonl,.json \
  --report /tmp/format_report.json
```

Judge the result by the **exit code** and the **`RESULT:` line**, not by piping to
`tail`/`head` (a pipe hides the exit code).

## The unified format being checked

Each record is a JSON object with this shape (see `assets/unified_schema_v1.json` for the
authoritative JSON Schema, and `references/taxonomy.md` for the category definitions):

```json
{
  "id": "dataset_split_000001",
  "source":   { "dataset": "DatasetName", "split": "train", "subset": null, "url": null, "license": null },
  "modality": ["text"],
  "task_type": "prompt_only_safety",
  "language": "en",
  "content":  { "system": null, "prompt": "...", "response": null, "conversation": null,
                "images": [], "videos": [], "audio": [] },
  "label":    { "target": "prompt", "is_unsafe": true, "policy_action": "refuse",
                "canonical_categories": ["harassment_bullying"], "canonical_subcategories": [],
                "severity": "high", "is_refusal": null, "requires_refusal": true },
  "risk_metadata": {}, "annotation": {}, "generation_metadata": {},
  "dedup":    { "content_hash": "sha256...", "near_duplicate_group": null },
  "raw_label":   { "original_categories": [], "original_fields": {} },
  "raw_example": { }
}
```

Allowed enumerations (the checker validates against these):

- `task_type` ∈ `prompt_only_safety, response_only_safety, prompt_response_safety, conversation_safety, refusal_detection, jailbreak_detection, image_safety, image_text_safety, video_safety`
- `label.target` ∈ `prompt, response, prompt_response_pair, conversation, image, image_text_pair, video`
- `label.policy_action` ∈ `allow, refuse, safe_complete, warn, redirect, escalate, uncertain`
- `label.severity` ∈ `none, low, medium, high, critical` or `null`
- `label.is_unsafe` must be a real boolean `true`/`false` (not `null`, not `"unsafe"`)
- `label.canonical_categories` is a list drawn from the 22 canonical categories in `references/taxonomy.md`

## Field contract (what makes a record pass)

The checker sorts every field into three tiers. **Standard** strictness (default):

| Tier | Fields | Missing / invalid → |
|---|---|---|
| **Required** | `id` (non-empty); `source.dataset`; `task_type` ∈ enum; `content` has at least one non-empty of `prompt`/`response`/`conversation`/`images`/`videos`/`audio`; `label.target` ∈ enum; `label.is_unsafe` is boolean; `label.policy_action` ∈ enum; `label.canonical_categories` is a list | **ERROR → FAIL** |
| **Conditional** | only enforced when the record *declares* that modality/task: image modality/`image_*` task → `content.images`; video → `content.videos`; `response_only_safety`/`prompt_response_safety` or `target=response` → `content.response`; `conversation_safety` → `content.conversation` | **ERROR if declared-but-empty**; otherwise not required |
| **Non-essential** | `raw_example`, `raw_label`, `source.split`, `dedup.content_hash`, `modality` (defaults to `["text"]`), `severity` value validity, categories aligned to the taxonomy, `is_unsafe=true` having ≥1 category | **WARNING only** (does **not** fail) |

This is exactly why a **text-only dataset is not penalized for having no images** — image
content is *conditional*, required only when the record claims an image modality/task.

**Verdict:** `PASS` ⇔ no record has any ERROR **and** no line failed to parse. Warnings never
cause FAIL.

## Strictness presets (`--strictness`, default `standard`)

| Preset | Required | Conditional | Non-essential |
|---|---|---|---|
| `lenient` | only core (`id`, some content, `label.is_unsafe`) → ERROR; rest → WARNING | WARNING | WARNING |
| `standard` *(default)* | ERROR | ERROR | WARNING |
| `strict` | ERROR | ERROR | **ERROR** (full traceability required) |

## Exit codes

- `0` — **PASS** (all records conform; there may be tolerated warnings).
- `1` — **FAIL** (≥1 record has an ERROR, or a line failed to parse).
- `2` — usage / IO error (path missing, no checkable files discovered, no records found).

## Reading the report

The human-readable report contains:

- **RESULT** — `PASS`, `PASS (with warnings)`, or `FAIL`, plus `valid / invalid` record counts.
- **ERRORS** — aggregated by code, with a count and example `file:line` locations. Fix these.
- **WARNINGS** — tolerated issues, aggregated by code (do not affect PASS).
- **FIELD COVERAGE** — % of records with a non-empty value per key; low coverage on a required
  key flags a systematic problem.
- **DISTRIBUTIONS** — `label.is_unsafe`, `task_type`, `source.dataset`, categories.
- **NOTE: flat schema** — printed when records look like a **flat/un-nested** schema (top-level
  `text`/`safety_label`/`prompt`/… instead of nested `content`/`label`). This is the typical
  result of checking a dataset that has **not yet been converted** into the unified format.

## Common outcomes

- **PASS (with warnings)** — conforms; warnings (e.g. placeholder `dedup.content_hash`, missing
  `raw_example`) are optional polish. Nothing to fix to pass.
- **FAIL + many required errors on every record** — the dataset is in a *different* schema. If
  the "flat schema" note appears, the data needs to be regenerated/converted into the unified
  nested format first, then re-checked.
- **FAIL on a subset of records** — partial/dirty data; use the example `file:line` locations.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `exit 2: no checkable files` | directory has no `*.jsonl` | add extensions: `--include-ext .jsonl,.json,.csv`, or pass a file directly |
| `metadata.json` was ignored | bare-object JSON files are skipped on purpose (not records) | expected; only record-bearing files are checked |
| every record fails all required fields + "flat schema" note | dataset is not in the unified format | convert/regenerate into the unified schema, then re-check |
| `is_unsafe_invalid` everywhere | label is a string (`"unsafe"`) or `0/1`, not boolean | emit `label.is_unsafe` as JSON `true`/`false` |
| `category_not_in_taxonomy` warnings | category strings not among the 22 canonical ones | map them to `references/taxonomy.md`, or accept the warning |
| huge file is slow | checking every record | add `--sample 5000` to spot-check per file |
| want strict traceability enforced | `raw_example`/`dedup` only warn by default | run with `--strictness strict` |

## For skill authors: emit data that passes

The fastest way to hand these rules to a data producer is `--emit-guide <path>` (Mode 1), which
writes a standalone authoring guide generated from the live checker rules. Inline, every record
needs at minimum: `id`; `source.dataset`; a valid `task_type`; a non-empty content field; and a
`label` with a boolean `is_unsafe`, a valid `target`, a valid `policy_action`, and a
`canonical_categories` list. Include `raw_example`/`raw_label` for traceability (warned about
otherwise, required under `--strictness strict`). Run `check_dataset_format.py <output_dir>` as
the final acceptance gate.

## Files

- `scripts/check_dataset_format.py` — the read-only checker (Mode 2) plus the `--emit-guide` format-guide generator (Mode 1); pure stdlib.
- `assets/unified_schema_v1.json` — authoritative JSON Schema for a unified record.
- `references/taxonomy.md` — the 22 canonical harm categories and mapping principles.
- `examples/output_example.jsonl` — a conformant record (checker → PASS).
- `examples/noncompliant_example.jsonl` — a flat/non-conformant record (checker → FAIL); useful for a self-test.
- `requirements.txt` — documents that there are no third-party dependencies.

## Safety and licensing note

Safety datasets may contain harmful or offensive text. Use them only for safety research,
moderation benchmarking, red-teaming evaluation, or defensive model assessment. The checker
reads content only to validate structure; respect each source dataset's license and access terms.
