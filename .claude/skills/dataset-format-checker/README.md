# dataset-format-checker

A portable, **read-only** Skill that checks whether a harmful-content / safety guard dataset
conforms to a unified JSONL schema and reports **PASS / FAIL**. It does not convert or modify
data — it only validates structure and reports what's wrong.

Two modes:
- **Check** a dataset directory/file and report PASS/FAIL (the default).
- **Emit a format guide** (`--emit-guide`) — a standalone Markdown spec for whoever produces the
  data, generated from the checker's own rules so it never drifts.

Typical use: verify that a dataset directory produced by another skill came out in the required
unified format.

## Why

Different safety benchmarks name equivalent fields differently and nest them differently. This
checker defines one unified schema and a clear **required / conditional / non-essential** field
contract, then tells you whether a given directory/file satisfies it. Fields a dataset genuinely
cannot provide (e.g. images for a text-only dataset) are **tolerated**, not failed.

## Install

Nothing to install — the checker is **pure Python standard library** (Python ≥ 3.8). Any
`python3` works; no `pip`.

## Contents

```text
dataset-format-checker/
  SKILL.md
  scripts/
    check_dataset_format.py     # read-only checker
  assets/
    unified_schema_v1.json      # authoritative JSON Schema for a unified record
  references/
    taxonomy.md                 # 22 canonical harm categories
  examples/
    output_example.jsonl        # conformant record  -> PASS
    noncompliant_example.jsonl  # flat/non-conformant -> FAIL
  requirements.txt              # documents: no third-party deps
```

## Usage

```bash
# Check a whole directory (auto-discovers *.jsonl, skips metadata/manifest/etc.)
python scripts/check_dataset_format.py data/safety_guard_2026

# Check a single file; save a JSON report; spot-check huge files
python scripts/check_dataset_format.py dataset.jsonl --report /tmp/report.json --sample 5000

# Discover .json too; enforce full traceability
python scripts/check_dataset_format.py data/my_dataset --include-ext .jsonl,.json --strictness strict

# MODE 1 — generate the format authoring guide (no checking); add --force to overwrite
python scripts/check_dataset_format.py --emit-guide ./safety_dataset_format_guide.md
```

Exit code: `0` = PASS, `1` = FAIL, `2` = usage/IO error (path missing, no checkable files).
Judge by the exit code and the `RESULT:` line — **not** by piping to `tail` (a pipe hides the
exit code).

## Smoke test

```bash
# Conformant example -> PASS (exit 0)
python scripts/check_dataset_format.py examples/output_example.jsonl

# Non-conformant (flat) example -> FAIL (exit 1) with a "flat schema" hint
python scripts/check_dataset_format.py examples/noncompliant_example.jsonl
```

## Read-only guarantee

The checker never writes to or modifies the dataset being checked. The only files it writes are
ones you request: the `--report` JSON, or the `--emit-guide` Markdown — both to paths you choose.
See `SKILL.md` for the two modes, the full field contract, strictness presets, report fields, and
the troubleshooting table.
