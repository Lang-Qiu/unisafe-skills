#!/usr/bin/env python3
"""
Read-only format checker for unified harmful-content / safety guard datasets.

Given a data DIRECTORY (or a single file), verify that every record conforms
to the unified JSONL schema defined by this skill (see assets/unified_schema_v1.json,
references/taxonomy.md, and SKILL.md), then report whether the dataset PASSES.

Design goals: portability + robustness.
  * Pure standard library. No third-party dependencies.
  * READ-ONLY. This tool never modifies the data it checks. The only thing it
    may write is an optional --report JSON file at a path you choose.
  * Never crashes on a bad line / bad file: problems are reported, not raised.

Field tiers (standard strictness):
  * required   -> missing/invalid is an ERROR (fails the check)
  * conditional-> only required when the record declares that modality/task
                  (e.g. an image dataset must have content.images); a text-only
                  dataset is NOT required to have images -> tolerated.
  * recommended-> missing is a WARNING only (does not fail the check)

Strictness presets:
  * lenient  -> only core fields (id, some content, label.is_unsafe) are errors.
  * standard -> required + conditional are errors; recommended are warnings. (default)
  * strict   -> recommended fields are errors too (full traceability required).

Verdict: PASS  <=>  no record has an ERROR and no line failed to parse.

Exit codes:
  0 = PASS
  1 = FAIL (at least one record has an error, or a line failed to parse)
  2 = usage / IO error (path missing, no checkable files, no records)

Example:
  python scripts/check_dataset_format.py data/safety_guard_2026
  python scripts/check_dataset_format.py some.jsonl --strictness strict
  python scripts/check_dataset_format.py data/ --include-ext .jsonl,.json --report /tmp/report.json
"""

from __future__ import annotations

import argparse
import csv
import fnmatch
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

# --------------------------------------------------------------------------- #
# Allowed enumerations — kept in sync with assets/unified_schema_v1.json
# --------------------------------------------------------------------------- #
TASK_TYPES = {
    "prompt_only_safety",
    "response_only_safety",
    "prompt_response_safety",
    "conversation_safety",
    "refusal_detection",
    "jailbreak_detection",
    "image_safety",
    "image_text_safety",
    "video_safety",
}
TARGETS = {
    "prompt",
    "response",
    "prompt_response_pair",
    "conversation",
    "image",
    "image_text_pair",
    "video",
}
POLICY_ACTIONS = {"allow", "refuse", "safe_complete", "warn", "redirect", "escalate", "uncertain"}
SEVERITIES = {"none", "low", "medium", "high", "critical"}
MODALITIES = {"text", "image", "video", "audio"}

# Canonical harm taxonomy (references/taxonomy.md). canonical_categories values
# outside this set are warned about (not aligned), not failed.
CANONICAL_CATEGORIES = {
    "hate_discrimination",
    "harassment_bullying",
    "sexual_content",
    "child_safety",
    "self_harm",
    "violence",
    "weapons",
    "illicit_behavior",
    "cyber_safety",
    "drugs",
    "chemical_biological",
    "fraud_financial_crime",
    "privacy_pii",
    "extremism_terrorism",
    "misinformation",
    "copyright",
    "animal_abuse",
    "profanity_toxicity",
    "political_persuasion",
    "medical_safety",
    "legal_safety",
    "general_harm",
    "other",
}

DEFAULT_EXCLUDE_GLOBS = [
    "*metadata*",
    "*manifest*",
    "*summary*",
    "*.schema.json",
    "README*",
    "readme*",
]

# Top-level keys that strongly suggest a FLAT (un-nested) schema rather than the
# unified nested one. Used only for the diagnostic "looks like flat schema" hint.
FLAT_SIGNAL_KEYS = {"text", "safety_label", "nist_safety_categories", "category_scores"}


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
def is_empty(value: Any) -> bool:
    """True if value is None, blank string, or empty list/dict. Numbers/bools are non-empty."""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, dict, tuple, set)):
        return len(value) == 0
    return False


def get(obj: Dict[str, Any], *path: str) -> Any:
    cur: Any = obj
    for part in path:
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def level_of(tier: str, strictness: str) -> str:
    """Map a field tier to error/warning given the strictness preset."""
    if tier == "core":
        return "error"
    if tier in ("required", "conditional"):
        return "error" if strictness in ("standard", "strict") else "warning"
    # recommended
    return "error" if strictness == "strict" else "warning"


# --------------------------------------------------------------------------- #
# Per-record checks -> list of (tier, code, detail)
# --------------------------------------------------------------------------- #
def check_record(obj: Any) -> List[Tuple[str, str, str]]:
    issues: List[Tuple[str, str, str]] = []
    if not isinstance(obj, dict):
        issues.append(("core", "not_an_object", "record is not a JSON object"))
        return issues

    # id ----------------------------------------------------------------- #
    if is_empty(obj.get("id")):
        issues.append(("core", "id_missing", "top-level 'id' missing or empty"))

    # source ------------------------------------------------------------- #
    source = obj.get("source")
    if not isinstance(source, dict):
        issues.append(("required", "source_missing", "'source' missing or not an object"))
        source = {}
    if is_empty(source.get("dataset")):
        issues.append(("required", "source_dataset_missing", "'source.dataset' missing or empty"))
    if is_empty(source.get("split")):
        issues.append(("recommended", "source_split_missing", "'source.split' missing (provenance)"))

    # task_type ---------------------------------------------------------- #
    task_type = obj.get("task_type")
    if task_type not in TASK_TYPES:
        issues.append(("required", "task_type_invalid", f"task_type={task_type!r} not in allowed set"))

    # modality ----------------------------------------------------------- #
    modality = obj.get("modality")
    mod_list: List[str] = []
    if "modality" not in obj or is_empty(modality):
        issues.append(("recommended", "modality_missing", "'modality' missing; assuming ['text']"))
        mod_list = ["text"]
    elif not isinstance(modality, list):
        issues.append(("recommended", "modality_not_list", "'modality' should be a list; assuming ['text']"))
        mod_list = ["text"]
    else:
        mod_list = [str(m) for m in modality]
        unknown = [m for m in mod_list if m not in MODALITIES]
        if unknown:
            issues.append(("recommended", "modality_unknown", "unknown modality: " + ",".join(unknown[:5])))

    # content ------------------------------------------------------------ #
    content = obj.get("content")
    if not isinstance(content, dict):
        issues.append(("core", "content_missing", "'content' missing or not an object"))
        content = {}

    has_text = any(not is_empty(content.get(k)) for k in ("prompt", "response", "conversation"))
    has_image = not is_empty(content.get("images"))
    has_video = not is_empty(content.get("videos"))
    has_audio = not is_empty(content.get("audio"))
    if not (has_text or has_image or has_video or has_audio):
        issues.append((
            "core",
            "content_empty",
            "no content found: prompt/response/conversation/images/videos/audio all empty",
        ))

    # label -------------------------------------------------------------- #
    label = obj.get("label")
    if not isinstance(label, dict):
        issues.append(("required", "label_missing", "'label' missing or not an object"))
        label = {}

    target = label.get("target")
    if target not in TARGETS:
        issues.append(("required", "label_target_invalid", f"label.target={target!r} not in allowed set"))

    is_unsafe = label.get("is_unsafe")
    if not isinstance(is_unsafe, bool):
        issues.append(("core", "is_unsafe_invalid", f"label.is_unsafe must be true/false (got {is_unsafe!r})"))

    policy = label.get("policy_action")
    if policy not in POLICY_ACTIONS:
        issues.append(("required", "policy_action_invalid", f"label.policy_action={policy!r} not in allowed set"))

    cats = label.get("canonical_categories")
    if not isinstance(cats, list):
        issues.append(("required", "canonical_categories_type", "label.canonical_categories must be a list"))
    else:
        bad = [c for c in cats if c not in CANONICAL_CATEGORIES]
        if bad:
            issues.append((
                "recommended",
                "category_not_in_taxonomy",
                "categories outside taxonomy: " + ",".join(str(b) for b in bad[:5]),
            ))
        if is_unsafe is True and len(cats) == 0:
            issues.append(("recommended", "unsafe_no_category", "is_unsafe=true but canonical_categories is empty"))

    severity = label.get("severity")
    if severity is not None and severity not in SEVERITIES:
        issues.append(("recommended", "severity_invalid", f"label.severity={severity!r} not in allowed set"))

    # conditional content requirements ----------------------------------- #
    declares_image = ("image" in mod_list) or (task_type in {"image_safety", "image_text_safety"})
    if declares_image and is_empty(content.get("images")):
        issues.append(("conditional", "images_missing", "modality/task declares image but content.images is empty"))

    declares_video = ("video" in mod_list) or (task_type == "video_safety")
    if declares_video and is_empty(content.get("videos")):
        issues.append(("conditional", "videos_missing", "modality/task declares video but content.videos is empty"))

    if "audio" in mod_list and is_empty(content.get("audio")):
        issues.append(("conditional", "audio_missing", "modality declares audio but content.audio is empty"))

    needs_response = (task_type in {"response_only_safety", "prompt_response_safety"}) or (target == "response")
    if needs_response and is_empty(content.get("response")):
        issues.append(("conditional", "response_missing", "task/target requires a response but content.response is empty"))

    if task_type == "conversation_safety" and is_empty(content.get("conversation")):
        issues.append(("conditional", "conversation_missing", "conversation_safety requires content.conversation"))

    # recommended traceability ------------------------------------------- #
    if not isinstance(obj.get("raw_example"), dict) or is_empty(obj.get("raw_example")):
        issues.append(("recommended", "raw_example_missing", "'raw_example' missing/empty (loses traceability)"))
    if not isinstance(obj.get("raw_label"), dict):
        issues.append(("recommended", "raw_label_missing", "'raw_label' missing (loses original labels)"))

    dedup = obj.get("dedup")
    chash = dedup.get("content_hash") if isinstance(dedup, dict) else None
    if is_empty(chash) or chash in {"...", "sha256...", "sha256"}:
        issues.append(("recommended", "dedup_hash_missing", "dedup.content_hash missing or placeholder"))

    return issues


# --------------------------------------------------------------------------- #
# Field coverage / distribution tracking
# --------------------------------------------------------------------------- #
COVERAGE_PATHS = [
    ("id",),
    ("source", "dataset"),
    ("source", "split"),
    ("task_type",),
    ("modality",),
    ("content", "prompt"),
    ("content", "response"),
    ("content", "conversation"),
    ("content", "images"),
    ("label", "is_unsafe"),
    ("label", "target"),
    ("label", "policy_action"),
    ("label", "canonical_categories"),
    ("raw_example",),
    ("dedup", "content_hash"),
]


# --------------------------------------------------------------------------- #
# File discovery & reading
# --------------------------------------------------------------------------- #
def discover_files(path: Path, include_ext: set, exclude_globs: List[str]) -> List[Path]:
    if path.is_file():
        return [path]
    files: List[Path] = []
    for root, _dirs, names in os.walk(path):
        for name in sorted(names):
            if Path(name).suffix.lower() not in include_ext:
                continue
            if any(fnmatch.fnmatch(name, g) for g in exclude_globs):
                continue
            files.append(Path(root) / name)
    return sorted(files)


def read_records(path: Path) -> Iterable[Tuple[int, Any, Optional[str]]]:
    """Yield (line_no, obj, parse_error). Exactly one of obj/parse_error is set.

    Returns nothing (and is a no-op) for a .json file that is a bare object
    (e.g. a metadata.json) rather than a list of records.
    """
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        with open(path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    yield line_no, json.loads(line), None
                except json.JSONDecodeError as e:
                    yield line_no, None, f"invalid JSON: {e}"
    elif suffix == ".json":
        with open(path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                yield 1, None, f"invalid JSON: {e}"
                return
        rows: Optional[list] = None
        if isinstance(data, list):
            rows = data
        elif isinstance(data, dict):
            for key in ("data", "examples", "records", "items", "rows"):
                if isinstance(data.get(key), list):
                    rows = data[key]
                    break
        if rows is None:
            # Bare object (metadata-like) — not a records file; skip silently.
            return
        for i, obj in enumerate(rows, start=1):
            yield i, obj, None
    elif suffix == ".csv":
        with open(path, "r", encoding="utf-8", newline="") as f:
            for i, row in enumerate(csv.DictReader(f), start=1):
                yield i, dict(row), None
    else:
        return


# --------------------------------------------------------------------------- #
# Main check
# --------------------------------------------------------------------------- #
def run_check(args: argparse.Namespace) -> Tuple[int, Dict[str, Any]]:
    root = Path(args.path)
    if not root.exists():
        return 2, {"error": f"path does not exist: {root}"}

    include_ext = {e if e.startswith(".") else "." + e for e in
                   (x.strip().lower() for x in args.include_ext.split(",") if x.strip())}
    exclude_globs = list(DEFAULT_EXCLUDE_GLOBS) + [g for g in (args.exclude_glob or [])]

    files = discover_files(root, include_ext, exclude_globs)
    if not files:
        return 2, {
            "error": f"no checkable files under {root} (looked for {sorted(include_ext)})",
            "hint": "use --include-ext to add extensions, or point at a specific file",
        }

    strictness = args.strictness
    total = 0
    valid = 0
    invalid = 0
    parse_errors = 0
    err_counts: Counter = Counter()
    warn_counts: Counter = Counter()
    err_detail: Dict[str, str] = {}
    warn_detail: Dict[str, str] = {}
    err_examples: Dict[str, List[str]] = defaultdict(list)
    warn_examples: Dict[str, List[str]] = defaultdict(list)
    coverage: Counter = Counter()
    dist_is_unsafe: Counter = Counter()
    dist_task: Counter = Counter()
    dist_dataset: Counter = Counter()
    dist_split: Counter = Counter()
    dist_category: Counter = Counter()
    key_signatures: Counter = Counter()
    n_content_dict = 0
    n_flat_signal = 0
    file_rows: List[Tuple[str, int]] = []

    def relname(p: Path) -> str:
        try:
            return str(p.relative_to(root)) if root.is_dir() else p.name
        except ValueError:
            return str(p)

    for fp in files:
        rel = relname(fp)
        rows_here = 0
        try:
            record_iter = read_records(fp)
        except OSError as e:
            err_counts["file_unreadable"] += 1
            err_detail.setdefault("file_unreadable", "could not open file")
            if len(err_examples["file_unreadable"]) < args.max_examples:
                err_examples["file_unreadable"].append(f"{rel}: {e}")
            continue

        while True:
            try:
                line_no, obj, perr = next(record_iter)
            except StopIteration:
                break
            except OSError as e:
                err_counts["file_read_error"] += 1
                err_detail.setdefault("file_read_error", "error while reading file")
                if len(err_examples["file_read_error"]) < args.max_examples:
                    err_examples["file_read_error"].append(f"{rel}: {e}")
                break

            if args.sample and rows_here >= args.sample:
                break
            rows_here += 1
            total += 1
            loc = f"{rel}:{line_no}"

            if perr is not None:
                parse_errors += 1
                invalid += 1
                err_counts["parse_error"] += 1
                err_detail.setdefault("parse_error", "line could not be parsed as JSON")
                if len(err_examples["parse_error"]) < args.max_examples:
                    err_examples["parse_error"].append(f"{loc}: {perr}")
                continue

            # diagnostics for the flat-schema hint
            if isinstance(obj, dict):
                key_signatures[tuple(sorted(obj.keys()))] += 1
                if isinstance(obj.get("content"), dict):
                    n_content_dict += 1
                if (FLAT_SIGNAL_KEYS & set(obj.keys())) or (
                    "prompt" in obj and not isinstance(obj.get("content"), dict)
                ):
                    n_flat_signal += 1

                # coverage
                for p in COVERAGE_PATHS:
                    if not is_empty(get(obj, *p)):
                        coverage[".".join(p)] += 1

                # distributions
                iu = get(obj, "label", "is_unsafe")
                dist_is_unsafe[iu if isinstance(iu, bool) else "missing/invalid"] += 1
                dist_task[obj.get("task_type") if obj.get("task_type") in TASK_TYPES else "missing/invalid"] += 1
                ds = get(obj, "source", "dataset")
                dist_dataset[ds if not is_empty(ds) else "missing"] += 1
                sp = get(obj, "source", "split")
                dist_split[sp if not is_empty(sp) else "missing"] += 1
                cc = get(obj, "label", "canonical_categories")
                if isinstance(cc, list):
                    for c in cc:
                        dist_category[c] += 1

            # checks
            issues = check_record(obj)
            has_error = False
            for tier, code, detail in issues:
                lvl = level_of(tier, strictness)
                if lvl == "error":
                    has_error = True
                    err_counts[code] += 1
                    err_detail.setdefault(code, detail)
                    if len(err_examples[code]) < args.max_examples:
                        err_examples[code].append(loc)
                else:
                    warn_counts[code] += 1
                    warn_detail.setdefault(code, detail)
                    if len(warn_examples[code]) < args.max_examples:
                        warn_examples[code].append(loc)
            if has_error:
                invalid += 1
            else:
                valid += 1

        file_rows.append((rel, rows_here))

    if total == 0:
        return 2, {"error": f"no records found in {len(files)} file(s) under {root}"}

    flat_like = (n_content_dict / total < 0.5) and (n_flat_signal / total > 0.5)
    passed = invalid == 0 and parse_errors == 0

    report = {
        "path": str(root),
        "strictness": strictness,
        "result": "PASS" if passed else "FAIL",
        "files_checked": [{"file": f, "records": n} for f, n in file_rows],
        "records": {"total": total, "valid": valid, "invalid": invalid, "parse_errors": parse_errors},
        "errors": [
            {"code": c, "count": n, "detail": err_detail.get(c, ""), "examples": err_examples.get(c, [])}
            for c, n in err_counts.most_common()
        ],
        "warnings": [
            {"code": c, "count": n, "detail": warn_detail.get(c, ""), "examples": warn_examples.get(c, [])}
            for c, n in warn_counts.most_common()
        ],
        "field_coverage": {".".join(p): round(100.0 * coverage[".".join(p)] / total, 1) for p in COVERAGE_PATHS},
        "distributions": {
            "label.is_unsafe": {str(k): v for k, v in dist_is_unsafe.most_common()},
            "task_type": {str(k): v for k, v in dist_task.most_common()},
            "source.dataset": {str(k): v for k, v in dist_dataset.most_common(20)},
            "source.split": {str(k): v for k, v in dist_split.most_common(20)},
            "canonical_categories": {str(k): v for k, v in dist_category.most_common(30)},
        },
        "flat_schema_suspected": flat_like,
    }
    if flat_like and key_signatures:
        sig, sig_n = key_signatures.most_common(1)[0]
        report["flat_schema_hint"] = {
            "observed_top_level_keys": list(sig),
            "records_with_this_signature": sig_n,
        }

    return (0 if passed else 1), report


# --------------------------------------------------------------------------- #
# Human-readable rendering
# --------------------------------------------------------------------------- #
def render(report: Dict[str, Any]) -> str:
    if "error" in report:
        return f"ERROR: {report['error']}" + (f"\nhint: {report['hint']}" if report.get("hint") else "")

    L: List[str] = []
    bar = "=" * 64
    L.append(bar)
    L.append("DATASET FORMAT CHECK")
    L.append(bar)
    L.append(f"path:        {report['path']}")
    L.append(f"strictness:  {report['strictness']}")
    L.append(f"files:       {len(report['files_checked'])} checked")
    for fc in report["files_checked"]:
        L.append(f"  - {fc['file']}   ({fc['records']} records)")
    L.append("")
    rec = report["records"]
    mark = "PASS  ✅" if report["result"] == "PASS" else "FAIL  ❌"
    if report["result"] == "PASS" and report["warnings"]:
        mark = "PASS (with warnings)  ⚠️"
    L.append(f"RESULT: {mark}")
    L.append("")
    L.append(f"records:  {rec['total']} total  |  {rec['valid']} valid  |  "
             f"{rec['invalid']} invalid (>=1 error)")
    if rec["parse_errors"]:
        L.append(f"parse errors: {rec['parse_errors']} line(s) could not be parsed")
    L.append("")

    if report["errors"]:
        L.append("ERRORS (must fix to PASS)")
        for e in report["errors"]:
            L.append(f"  {e['count']:>8} ×  {e['code']:<26} {e['detail']}")
            if e["examples"]:
                L.append(f"            e.g. {', '.join(e['examples'])}")
        L.append("")
    else:
        L.append("ERRORS: none")
        L.append("")

    if report["warnings"]:
        L.append("WARNINGS (tolerated — do not affect PASS)")
        for w in report["warnings"]:
            L.append(f"  {w['count']:>8} ×  {w['code']:<26} {w['detail']}")
        L.append("")

    L.append("FIELD COVERAGE  (% of records with a non-empty value)")
    for k, pct in report["field_coverage"].items():
        flag = "  <- required, low coverage" if pct < 50.0 and k in (
            "id", "source.dataset", "task_type", "label.is_unsafe",
            "label.target", "label.policy_action", "label.canonical_categories",
        ) else ""
        L.append(f"  {k:<28} {pct:>5.1f}%{flag}")
    L.append("")

    d = report["distributions"]
    L.append("DISTRIBUTIONS")
    L.append(f"  label.is_unsafe: {d['label.is_unsafe']}")
    L.append(f"  task_type:       {d['task_type']}")
    L.append(f"  source.dataset:  {d['source.dataset']}")
    if d["canonical_categories"]:
        L.append(f"  categories:      {d['canonical_categories']}")
    L.append("")

    if report.get("flat_schema_suspected"):
        L.append("NOTE: records look like a FLAT (un-nested) schema, not the unified one.")
        hint = report.get("flat_schema_hint", {})
        if hint.get("observed_top_level_keys"):
            L.append("  observed top-level keys: " + ", ".join(map(str, hint["observed_top_level_keys"])))
        L.append("  The unified format needs nested objects:")
        L.append("    content{prompt|response|conversation|images...},")
        L.append("    label{target, is_unsafe(bool), policy_action, canonical_categories[]},")
        L.append("    source{dataset, split}, plus top-level id and task_type.")
        L.append("  -> Regenerate/convert this dataset into the unified format, then re-check.")
        L.append("")

    if report["result"] == "FAIL" and not report.get("flat_schema_suspected"):
        L.append("FIX: address every ERROR code above (see e.g. line locations), then re-run the checker.")
        L.append("")

    L.append(bar)
    return "\n".join(L)


def build_format_guide() -> str:
    """Render the unified-format authoring guide as Markdown.

    Built from the SAME enums/contract this checker enforces, so the guide can
    never drift from the validation rules.
    """
    minimal = '''{
  "id": "mydataset:train:000001",
  "source": {"dataset": "MyDataset", "split": "train"},
  "task_type": "prompt_only_safety",
  "content": {"prompt": "How do I pick a lock?"},
  "label": {"target": "prompt", "is_unsafe": true,
            "policy_action": "refuse", "canonical_categories": ["illicit_behavior"]}
}'''
    full = '''{
  "id": "mydataset:train:000001",
  "source": {"dataset": "MyDataset", "subset": null, "version": null,
             "split": "train", "url": null, "license": null},
  "modality": ["text"],
  "task_type": "prompt_response_safety",
  "language": "en",
  "content": {"system": null, "prompt": "...user prompt...",
              "response": "...model response...", "conversation": null,
              "images": [], "videos": [], "audio": []},
  "label": {"target": "prompt_response_pair", "is_unsafe": true,
            "prompt_is_unsafe": true, "response_is_unsafe": true,
            "is_refusal": false, "requires_refusal": true, "response_is_safe": false,
            "canonical_categories": ["weapons"], "canonical_subcategories": [],
            "severity": "high", "policy_action": "refuse"},
  "risk_metadata": {"jailbreak": false, "adversarial": false},
  "annotation": {"annotator_type": "human", "confidence": 0.9},
  "generation_metadata": {"response_model": "some-model"},
  "dedup": {"content_hash": "sha256:...", "near_duplicate_group": null},
  "raw_label": {"original_categories": ["..."], "original_fields": {}},
  "raw_example": {"note": "the original source record, verbatim"}
}'''
    cats = "\n".join("- `" + c + "`" for c in sorted(CANONICAL_CATEGORIES))
    L: List[str] = []
    a = L.append
    a("# Unified Safety Dataset Format — Authoring Guide")
    a("")
    a("Produce data that conforms to this so it PASSES `dataset-format-checker`.")
    a("This guide is generated by the checker itself, so it matches the rules it enforces.")
    a("Storage: one JSON object per line (JSONL), UTF-8 encoded.")
    a("")
    a("## Minimal conformant record")
    a("")
    a("```json")
    a(minimal)
    a("```")
    a("")
    a("## Full record shape (all fields)")
    a("")
    a("```json")
    a(full)
    a("```")
    a("")
    a("## Field contract")
    a("")
    a("### Required — missing or invalid FAILS the check")
    a("- `id` — non-empty string, unique per record.")
    a("- `source.dataset` — non-empty source dataset name.")
    a("- `task_type` — one of the allowed values listed below.")
    a("- `content` — object with at least ONE non-empty of "
      "`prompt`/`response`/`conversation`/`images`/`videos`/`audio`.")
    a("- `label.target` — one of the allowed targets below.")
    a('- `label.is_unsafe` — a real boolean `true`/`false` (NOT the string `"unsafe"`, NOT `0`/`1`, NOT null).')
    a("- `label.policy_action` — one of the allowed actions below.")
    a("- `label.canonical_categories` — a list (may be empty for safe records).")
    a("")
    a("### Conditional — required only when the record declares that modality/task")
    a("- image modality or `image_safety`/`image_text_safety` task → non-empty `content.images`.")
    a("- video modality or `video_safety` task → non-empty `content.videos`.")
    a("- audio modality → non-empty `content.audio`.")
    a("- `response_only_safety`/`prompt_response_safety` task or `target=response` → non-empty `content.response`.")
    a("- `conversation_safety` task → non-empty `content.conversation`.")
    a("- A text-only dataset is NOT required to provide images/videos/audio — absent is tolerated.")
    a("")
    a("### Non-essential — recommended; absence is only a WARNING (still PASSES)")
    a("- `raw_example` and `raw_label` (objects) — keep the original record/labels for traceability.")
    a("- `source.split`, `source.url`, `source.license`.")
    a('- `modality` (defaults to `["text"]` when omitted).')
    a("- `label.severity` (must be valid if present), `language`, `dedup.content_hash`.")
    a("- For `is_unsafe=true`, at least one `canonical_categories` entry is recommended.")
    a("- Turn these into hard requirements with `--strictness strict`.")
    a("")
    a("## Allowed values")
    a("")
    a("- **task_type**: " + ", ".join("`" + x + "`" for x in sorted(TASK_TYPES)))
    a("- **label.target**: " + ", ".join("`" + x + "`" for x in sorted(TARGETS)))
    a("- **label.policy_action**: " + ", ".join("`" + x + "`" for x in sorted(POLICY_ACTIONS)))
    a("- **label.severity**: " + ", ".join("`" + x + "`" for x in sorted(SEVERITIES)) + ", or `null`")
    a("- **modality** items: " + ", ".join("`" + x + "`" for x in sorted(MODALITIES)))
    a("")
    n_specific = len(CANONICAL_CATEGORIES - {"other"})
    a("## Canonical harm categories (" + str(n_specific) + ", plus an `other` fallback)")
    a("")
    a(cats)
    a("")
    a("Use `other` only when nothing else fits; always keep source labels in `raw_label`.")
    a("")
    a("## Common mistakes (checker error code → fix)")
    a("")
    a("- `is_unsafe_invalid` → emit `label.is_unsafe` as a JSON boolean, not a string/number.")
    a("- `content_empty` / `content_missing` → nest text under `content.prompt`/`content.response`.")
    a("- `label_*_invalid` → nest fields under `label{}` and use the allowed enum values.")
    a("- `task_type_invalid` → set `task_type` from the list above.")
    a("- `source_dataset_missing` → set `source.dataset`.")
    a('- "flat schema" note → your records are flat; wrap them into the nested shape shown above.')
    a("")
    a("## Self-check before delivery")
    a("")
    a("```bash")
    a("python scripts/check_dataset_format.py <your_output_dir>")
    a("# exit 0 = PASS, 1 = FAIL, 2 = usage/IO error")
    a("```")
    a("")
    return "\n".join(L)


def write_guide(out: Path, force: bool = False) -> int:
    """Write the authoring guide to `out`. Returns a process exit code."""
    if out.exists() and not force:
        print("ERROR: " + str(out) + " already exists. Pass --force to overwrite.", file=sys.stderr)
        return 2
    try:
        if out.parent and not out.parent.exists():
            out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            f.write(build_format_guide())
    except OSError as e:
        print("ERROR: could not write guide to " + str(out) + ": " + str(e), file=sys.stderr)
        return 2
    print("Wrote unified-format authoring guide to: " + str(out))
    return 0


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Read-only checker for the unified safety format. Check a dataset directory/file, "
                    "or generate the format authoring guide with --emit-guide.",
    )
    p.add_argument("path", nargs="?", default=None,
                   help="data directory or a single .jsonl/.json/.csv file (omit when using --emit-guide)")
    p.add_argument("--strictness", choices=["lenient", "standard", "strict"], default="standard")
    p.add_argument("--include-ext", default=".jsonl",
                   help="comma-separated extensions to discover in a directory (default: .jsonl)")
    p.add_argument("--exclude-glob", action="append", default=[],
                   help="extra filename glob(s) to skip (repeatable); defaults already skip metadata/manifest/etc.")
    p.add_argument("--sample", type=int, default=None, help="check at most N records per file (speed up huge files)")
    p.add_argument("--max-examples", type=int, default=5, help="example locations shown per issue code")
    p.add_argument("--report", default=None, help="also write the machine-readable JSON report to this path")
    p.add_argument("--quiet", action="store_true", help="print only the one-line RESULT verdict")
    p.add_argument("--emit-guide", metavar="OUTPUT.md", default=None,
                   help="GUIDE MODE: write the unified-format authoring guide to this path and exit (no checking)")
    p.add_argument("--force", action="store_true",
                   help="with --emit-guide, overwrite OUTPUT.md if it already exists")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    # GUIDE MODE: generate the authoring guide, no dataset checking.
    if args.emit_guide:
        return write_guide(Path(args.emit_guide), force=args.force)

    # CHECK MODE: a dataset path is required.
    if not args.path:
        print("ERROR: provide a dataset path to check, or use --emit-guide OUTPUT.md "
              "to generate the format guide.", file=sys.stderr)
        return 2

    code, report = run_check(args)

    if args.report and "error" not in report:
        try:
            with open(args.report, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
        except OSError as e:
            print(f"WARNING: could not write report to {args.report}: {e}", file=sys.stderr)

    if args.quiet and "error" not in report:
        print(f"{report['result']}: {report['path']} "
              f"({report['records']['valid']}/{report['records']['total']} valid)")
    else:
        print(render(report))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
