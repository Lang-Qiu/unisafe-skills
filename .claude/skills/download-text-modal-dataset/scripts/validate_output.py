#!/usr/bin/env python3
"""Validate normalized safety guard JSONL output."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

REQUIRED_FIELDS = [
    "id",
    "source_dataset",
    "source_split",
    "text",
    "response",
    "safety_label",
    "label",
    "nist_safety_categories",
    "category_scores",
    "confidence",
    "original_category",
    "source_id",
    "metadata",
]

VALID_LABELS = {0, 1}
VALID_SAFETY_LABELS = {"safe", "unsafe"}
VALID_CATEGORIES = {
    "violence",
    "hate_speech",
    "harassment",
    "sexual_content",
    "suicide_self_harm",
    "profanity",
    "threats",
    "health_misinformation",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("jsonl", help="Path to normalized JSONL file.")
    parser.add_argument("--max-errors", type=int, default=20)
    return parser.parse_args()


def validate_row(row: Dict[str, Any], line_no: int) -> List[str]:
    errors: List[str] = []
    for field in REQUIRED_FIELDS:
        if field not in row:
            errors.append(f"line {line_no}: missing field {field}")
    if errors:
        return errors

    if not isinstance(row["id"], str) or not row["id"]:
        errors.append(f"line {line_no}: id must be non-empty string")
    if not isinstance(row["text"], str) or not row["text"].strip():
        errors.append(f"line {line_no}: text must be non-empty string")
    if row["response"] is not None and not isinstance(row["response"], str):
        errors.append(f"line {line_no}: response must be string or null")
    if row["label"] not in VALID_LABELS:
        errors.append(f"line {line_no}: label must be 0 or 1")
    if row["safety_label"] not in VALID_SAFETY_LABELS:
        errors.append(f"line {line_no}: safety_label must be safe or unsafe")
    if (row["label"] == 1 and row["safety_label"] != "unsafe") or (row["label"] == 0 and row["safety_label"] != "safe"):
        errors.append(f"line {line_no}: label/safety_label mismatch")
    if not isinstance(row["nist_safety_categories"], list):
        errors.append(f"line {line_no}: nist_safety_categories must be list")
    else:
        for cat in row["nist_safety_categories"]:
            if cat not in VALID_CATEGORIES:
                errors.append(f"line {line_no}: unknown category {cat}")
    if not isinstance(row["category_scores"], dict):
        errors.append(f"line {line_no}: category_scores must be object")
    if not isinstance(row["metadata"], dict):
        errors.append(f"line {line_no}: metadata must be object")
    return errors


def main() -> int:
    args = parse_args()
    path = Path(args.jsonl)
    if not path.exists():
        raise SystemExit(f"File not found: {path}")

    errors: List[str] = []
    counts = Counter()
    source_counts = Counter()
    category_counts = Counter()
    n = 0

    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            n += 1
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"line {line_no}: invalid JSON: {exc}")
                if len(errors) >= args.max_errors:
                    break
                continue
            row_errors = validate_row(row, line_no)
            errors.extend(row_errors)
            counts[row.get("safety_label", "<missing>")] += 1
            source_counts[row.get("source_dataset", "<missing>")] += 1
            cats = row.get("nist_safety_categories", [])
            if cats:
                category_counts.update(cats)
            elif row.get("label") == 0:
                category_counts["safe"] += 1
            if len(errors) >= args.max_errors:
                break

    print(f"rows: {n}")
    print(f"by_label: {dict(counts)}")
    print(f"by_source: {dict(source_counts)}")
    print(f"by_category: {dict(category_counts)}")

    if errors:
        print("\nErrors:")
        for e in errors[: args.max_errors]:
            print(f"- {e}")
        return 1
    print("validation: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
