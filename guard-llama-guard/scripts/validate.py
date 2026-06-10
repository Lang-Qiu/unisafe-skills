"""Validate guard prediction JSONL files. Stdlib only.

Checks (references/io-contract.md sections 2/3; schemas/guard_output.schema.json):
  - structural: required keys, types, is_unsafe in {true,false,null} (never a
    string), risk_categories within the canonical set, the bidirectional rule
    "is_unsafe=null <=> error is a non-empty string", confidence in [0,1]|null.
  - --against <input>: prediction ids must match the ELIGIBLE id set of the
    input bidirectionally (no missing, no extra, no duplicates). Skipped
    records (out-of-scope / missing content) must NOT have predictions.
  - --metadata <run_metadata.json> (optional, requires --against): counts in
    run_metadata (eligible, skipped.out_of_scope, skipped.missing_content)
    must match what the input actually yields.
If the `jsonschema` package happens to be installed, a full schema validation
runs as an extra layer; its absence is never an error.

Exit codes (authoritative table: references/io-contract.md section 7):
  0 = PASS    1 = FAIL (violations found)    2 = usage / IO error
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils import (
    ROUTE_ELIGIBLE,
    SCHEMA_PATH,
    canonical_categories,
    discover_jsonl_files,
    iter_jsonl,
    route_record,
)

REQUIRED_TOP_KEYS = ("id", "guard", "prediction", "raw_output", "runtime", "error")
REQUIRED_PREDICTION_KEYS = ("is_unsafe", "risk_categories", "severity", "action", "confidence")
REQUIRED_GUARD_KEYS = ("name", "version", "modality")
REQUIRED_RUNTIME_KEYS = ("latency_ms", "cost", "device")
VALID_ACTIONS = ("allow", "refuse", "safe_complete", "warn", "redirect", "escalate", "uncertain")
MAX_REPORTED_VIOLATIONS = 50


def check_record(record: Dict[str, Any], canonical: set) -> List[str]:
    """Return human-readable violation messages for one prediction record."""
    problems: List[str] = []
    for key in REQUIRED_TOP_KEYS:
        if key not in record:
            problems.append(f"missing top-level key {key!r}")
    if problems:
        return problems

    if not isinstance(record["id"], str) or not record["id"]:
        problems.append("id must be a non-empty string")

    guard = record["guard"]
    if not isinstance(guard, dict):
        problems.append("guard must be an object")
    else:
        for key in REQUIRED_GUARD_KEYS:
            if key not in guard:
                problems.append(f"guard missing key {key!r}")
        if not isinstance(guard.get("name"), str) or not guard.get("name"):
            problems.append("guard.name must be a non-empty string")
        if not isinstance(guard.get("modality"), list):
            problems.append("guard.modality must be a list")

    prediction = record["prediction"]
    if not isinstance(prediction, dict):
        problems.append("prediction must be an object")
        return problems
    for key in REQUIRED_PREDICTION_KEYS:
        if key not in prediction:
            problems.append(f"prediction missing key {key!r}")
    if problems:
        return problems

    is_unsafe = prediction["is_unsafe"]
    if not (is_unsafe is None or isinstance(is_unsafe, bool)):
        problems.append(
            f"prediction.is_unsafe must be true/false/null, got {type(is_unsafe).__name__} {is_unsafe!r}"
        )

    categories = prediction["risk_categories"]
    if not isinstance(categories, list):
        problems.append("prediction.risk_categories must be a list")
    else:
        unknown = [c for c in categories if c not in canonical]
        if unknown:
            problems.append(f"risk_categories outside canonical set: {unknown}")
        if len(set(categories)) != len(categories):
            problems.append("risk_categories contains duplicates")

    severity = prediction["severity"]
    if not (severity is None or (isinstance(severity, int) and not isinstance(severity, bool) and severity >= 0)):
        problems.append(f"prediction.severity must be a non-negative integer or null, got {severity!r}")

    if prediction["action"] not in VALID_ACTIONS:
        problems.append(f"prediction.action {prediction['action']!r} not in {VALID_ACTIONS}")

    confidence = prediction["confidence"]
    if not (
        confidence is None
        or (isinstance(confidence, (int, float)) and not isinstance(confidence, bool) and 0 <= confidence <= 1)
    ):
        problems.append(f"prediction.confidence must be in [0,1] or null, got {confidence!r}")

    if not isinstance(record["raw_output"], dict):
        problems.append("raw_output must be an object")

    runtime = record["runtime"]
    if not isinstance(runtime, dict):
        problems.append("runtime must be an object")
    else:
        for key in REQUIRED_RUNTIME_KEYS:
            if key not in runtime:
                problems.append(f"runtime missing key {key!r}")

    error = record["error"]
    if not (error is None or isinstance(error, str)):
        problems.append("error must be a string or null")

    # bidirectional rule: is_unsafe=null <=> error is a non-empty string
    if is_unsafe is None and not (isinstance(error, str) and error):
        problems.append("orphan error record: is_unsafe=null requires a non-empty error string")
    if is_unsafe is not None and error is not None:
        problems.append("inconsistent record: is_unsafe is set but error is non-null")

    return problems


def _try_jsonschema(files: List[Path]) -> Optional[List[str]]:
    """Optional extra layer; returns violations or None when jsonschema is absent."""
    try:
        import jsonschema  # type: ignore
    except ImportError:
        return None
    if not SCHEMA_PATH.is_file():
        return None
    with open(SCHEMA_PATH, encoding="utf-8") as fh:
        validator = jsonschema.Draft202012Validator(json.load(fh))
    problems: List[str] = []
    for path in files:
        for lineno, record, err in iter_jsonl(path):
            if err is not None:
                continue
            for issue in validator.iter_errors(record):
                problems.append(f"{path.name}:{lineno}: [jsonschema] {issue.message}")
    return problems


def _eligible_ids(input_path: Path) -> Optional[Dict[str, int]]:
    """Return {bucket counts and id set} for the input, or None on IO failure."""
    files = discover_jsonl_files(input_path)
    if not files:
        return None
    ids: List[str] = []
    out_of_scope = 0
    missing_content = 0
    total = 0
    for path in files:
        for _lineno, record, err in iter_jsonl(path):
            if err is not None:
                continue
            total += 1
            bucket, _reason = route_record(record)
            if bucket == ROUTE_ELIGIBLE:
                ids.append(record.get("id"))
            elif bucket == "out_of_scope":
                out_of_scope += 1
            else:
                missing_content += 1
    return {
        "ids": ids,
        "total": total,
        "out_of_scope": out_of_scope,
        "missing_content": missing_content,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="validate.py", description="Validate guard prediction JSONL files."
    )
    parser.add_argument("target", help="prediction .jsonl file or directory")
    parser.add_argument("--against", default=None,
                        help="unified input file/dir; enforce bidirectional id coverage of the eligible set")
    parser.add_argument("--metadata", default=None,
                        help="run_metadata.json; additionally check skip/eligible counts (requires --against)")
    args = parser.parse_args(argv)

    if args.metadata and not args.against:
        print("ERROR: --metadata requires --against (counts are derived from the input)")
        return 2
    target = Path(args.target)
    if not target.exists():
        print(f"ERROR: target path does not exist: {target}")
        return 2
    files = discover_jsonl_files(target)
    if not files:
        print(f"ERROR: no .jsonl files to validate under: {target}")
        return 2
    try:
        canonical = set(canonical_categories())
    except OSError as exc:
        print(f"ERROR: cannot load category mapping: {exc}")
        return 2

    violations: List[str] = []
    records_checked = 0
    ids_per_file: Dict[Path, List[str]] = {}
    for path in files:
        ids_per_file[path] = []
        for lineno, record, err in iter_jsonl(path):
            if err is not None:
                violations.append(f"{path.name}:{lineno}: {err}")
                continue
            records_checked += 1
            ids_per_file[path].append(record.get("id"))
            for problem in check_record(record, canonical):
                violations.append(f"{path.name}:{lineno}: {problem}")

    extra = _try_jsonschema(files)
    if extra:
        violations.extend(extra)

    if args.against:
        input_path = Path(args.against)
        if not input_path.exists():
            print(f"ERROR: --against path does not exist: {input_path}")
            return 2
        derived = _eligible_ids(input_path)
        if derived is None:
            print(f"ERROR: no .jsonl files under --against path: {input_path}")
            return 2
        eligible = set(derived["ids"])
        for path, ids in ids_per_file.items():
            seen = set()
            duplicates = sorted({i for i in ids if i in seen or seen.add(i)})
            if duplicates:
                violations.append(f"{path.name}: duplicate ids: {duplicates[:5]}")
            missing = sorted(eligible - set(ids))
            if missing:
                violations.append(
                    f"{path.name}: missing predictions for eligible ids: {missing[:5]}"
                    f"{' ...' if len(missing) > 5 else ''}"
                )
            unexpected = sorted(set(ids) - eligible)
            if unexpected:
                violations.append(
                    f"{path.name}: predictions for non-eligible ids: {unexpected[:5]}"
                    f"{' ...' if len(unexpected) > 5 else ''}"
                )

        if args.metadata:
            metadata_path = Path(args.metadata)
            if not metadata_path.is_file():
                print(f"ERROR: --metadata file does not exist: {metadata_path}")
                return 2
            with open(metadata_path, encoding="utf-8") as fh:
                metadata = json.load(fh)
            counts = metadata.get("counts", {})
            skipped = counts.get("skipped", {})
            checks = (
                ("counts.eligible", counts.get("eligible"), len(eligible)),
                ("counts.skipped.out_of_scope", skipped.get("out_of_scope"), derived["out_of_scope"]),
                ("counts.skipped.missing_content", skipped.get("missing_content"), derived["missing_content"]),
            )
            for label, recorded, actual in checks:
                if recorded != actual:
                    violations.append(
                        f"run_metadata: {label}={recorded!r} does not match input-derived value {actual}"
                    )

    for line in violations[:MAX_REPORTED_VIOLATIONS]:
        print(f"VIOLATION: {line}")
    if len(violations) > MAX_REPORTED_VIOLATIONS:
        print(f"... and {len(violations) - MAX_REPORTED_VIOLATIONS} more")

    if violations:
        print(f"RESULT: FAIL files={len(files)} records={records_checked} violations={len(violations)}")
        return 1
    print(f"RESULT: PASS files={len(files)} records={records_checked}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
