"""Validate guard-output JSONL against schemas/guard_output.schema.json.

Stdlib-only structural validator (no jsonschema dependency): enforces the
required keys, types, enums and the error-row invariant declared in the
schema file. The schema file is the formal contract; this script is its
executable check.

Usage (from the skill directory):
  python scripts/validate.py runs/smoke/guard_output.rule.jsonl [more.jsonl ...]
  python scripts/validate.py runs/smoke/            # validates guard_output.*.jsonl inside

Exit codes: 0 = all rows valid (PASS) | 2 = at least one invalid row (FAIL)
            3 = fatal (file/dir not found, no rows)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))  # scripts/ on path

MODALITIES = {"text", "image", "video", "audio"}
ACTIONS = {"allow", "refuse", "safe_complete", "warn", "redirect",
           "escalate", "uncertain"}
REQUIRED_TOP = {"id", "guard", "prediction", "raw_output", "runtime", "error"}


def validate_row(row: Any) -> Optional[str]:
    """Return None if valid, else a readable reason (first violation found)."""
    if not isinstance(row, dict):
        return "row is not a JSON object"
    missing = REQUIRED_TOP - set(row)
    if missing:
        return f"missing top-level keys: {sorted(missing)}"
    if not (isinstance(row["id"], str) and row["id"]):
        return "id must be a non-empty string"
    guard = row["guard"]
    if not isinstance(guard, dict) or not guard.get("name"):
        return "guard.name missing"
    mods = guard.get("modality")
    if not isinstance(mods, list) or not set(mods) <= MODALITIES:
        return f"guard.modality invalid: {mods!r}"
    pred = row["prediction"]
    if not isinstance(pred, dict):
        return "prediction missing"
    if "is_unsafe" not in pred or not isinstance(pred["is_unsafe"], (bool, type(None))):
        return f"prediction.is_unsafe must be bool|null, got {pred.get('is_unsafe')!r}"
    if not isinstance(pred.get("risk_categories"), list):
        return "prediction.risk_categories must be a list"
    if pred.get("action") not in ACTIONS:
        return f"prediction.action invalid: {pred.get('action')!r}"
    conf = pred.get("confidence")
    if conf is not None and not (isinstance(conf, (int, float)) and 0 <= conf <= 1):
        return f"prediction.confidence must be null or in [0,1], got {conf!r}"
    if not isinstance(row["raw_output"], dict):
        return "raw_output must be an object"
    error = row["error"]
    if error is not None and not isinstance(error, str):
        return "error must be null or string"
    # Error-row invariant (schema allOf): failed rows carry no verdict.
    if isinstance(error, str):
        if pred["is_unsafe"] is not None:
            return "error row must have prediction.is_unsafe=null"
        if pred.get("action") != "uncertain":
            return "error row must have prediction.action='uncertain'"
    return None


def validate_file(path: Path) -> Tuple[int, List[Tuple[int, str]]]:
    """Returns (n_rows, violations as (line_no, reason))."""
    violations: List[Tuple[int, str]] = []
    n = 0
    for line_no, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        n += 1
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            violations.append((line_no, f"malformed JSON: {exc}"))
            continue
        reason = validate_row(row)
        if reason:
            violations.append((line_no, reason))
    return n, violations


def main(argv: Optional[List[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print(__doc__, file=sys.stderr)
        return 3
    files: List[Path] = []
    for spec in args:
        p = Path(spec)
        if p.is_dir():
            files.extend(sorted(p.glob("guard_output.*.jsonl")))
        elif p.is_file():
            files.append(p)
        else:
            print(f"FATAL: not found: {p}", file=sys.stderr)
            return 3
    if not files:
        print("FATAL: no guard_output.*.jsonl files to validate", file=sys.stderr)
        return 3
    total_rows, total_violations = 0, 0
    for path in files:
        n, violations = validate_file(path)
        total_rows += n
        total_violations += len(violations)
        verdict = "PASS" if not violations else "FAIL"
        print(f"{path}: {n} rows, {len(violations)} invalid -> {verdict}")
        for line_no, reason in violations[:10]:
            print(f"    line {line_no}: {reason}")
    if total_rows == 0:
        print("FATAL: zero rows found", file=sys.stderr)
        return 3
    print(f"RESULT: {'PASS' if total_violations == 0 else 'FAIL'} "
          f"({total_rows} rows, {total_violations} invalid)")
    return 0 if total_violations == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
