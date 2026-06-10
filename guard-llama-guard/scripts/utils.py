"""Shared helpers for guard-llama-guard scripts. Stdlib only (Python >= 3.9).

Routing rules implement references/io-contract.md section 2 (eligible definition).
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

SKILL_ROOT = Path(__file__).resolve().parents[1]
CATEGORY_MAPPING_PATH = SKILL_ROOT / "references" / "category_mapping.json"
SCHEMA_PATH = SKILL_ROOT / "schemas" / "guard_output.schema.json"

# M1 scope: text-only safety tasks (io-contract.md section 1)
TEXT_TASK_TYPES = ("prompt_only_safety", "prompt_response_safety")

ROUTE_ELIGIBLE = "eligible"
ROUTE_OUT_OF_SCOPE = "out_of_scope"
ROUTE_MISSING_CONTENT = "missing_content"


def load_category_mapping(path: Optional[Path] = None) -> Dict[str, Any]:
    mapping_path = Path(path) if path else CATEGORY_MAPPING_PATH
    with open(mapping_path, encoding="utf-8") as fh:
        return json.load(fh)


def canonical_categories(mapping: Optional[Dict[str, Any]] = None) -> List[str]:
    if mapping is None:
        mapping = load_category_mapping()
    return list(mapping["canonical_categories"])


def discover_jsonl_files(path: Path) -> List[Path]:
    """A file is taken as-is; a directory yields its *.jsonl files (sorted).

    Bare-object files such as metadata.json are .json, so the glob already
    excludes them (mirrors dataset-format-checker discovery).
    """
    path = Path(path)
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(p for p in path.glob("*.jsonl") if p.is_file())
    return []


def iter_jsonl(path: Path) -> Iterator[Tuple[int, Optional[Dict[str, Any]], Optional[str]]]:
    """Yield (lineno, record, parse_error). Exactly one of record/parse_error is None."""
    with open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                obj = json.loads(stripped)
            except json.JSONDecodeError as exc:
                yield lineno, None, f"JSON parse error: {exc}"
                continue
            if not isinstance(obj, dict):
                yield lineno, None, "line is not a JSON object"
                continue
            yield lineno, obj, None


def write_jsonl_line(fh, obj: Dict[str, Any]) -> None:
    fh.write(json.dumps(obj, ensure_ascii=False) + "\n")


def _non_empty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def route_record(record: Dict[str, Any]) -> Tuple[str, str]:
    """Route one unified record per io-contract.md section 2.

    Returns (bucket, reason) with bucket in {eligible, out_of_scope, missing_content}.
    """
    task_type = record.get("task_type")
    modality = record.get("modality")
    if task_type not in TEXT_TASK_TYPES:
        return ROUTE_OUT_OF_SCOPE, f"task_type={task_type!r} not in M1 scope"
    if modality != ["text"]:
        return ROUTE_OUT_OF_SCOPE, f"modality={modality!r} != ['text']"
    content = record.get("content") or {}
    if not _non_empty_str(content.get("prompt")):
        return ROUTE_MISSING_CONTENT, "content.prompt is empty"
    if task_type == "prompt_response_safety" and not _non_empty_str(content.get("response")):
        return ROUTE_MISSING_CONTENT, "content.response is empty"
    return ROUTE_ELIGIBLE, ""


def record_text(record: Dict[str, Any]) -> str:
    """Guard input text: prompt, plus response for pair tasks (M0 section 3)."""
    content = record.get("content") or {}
    parts = [content.get("prompt") or ""]
    response = content.get("response")
    if _non_empty_str(response):
        parts.append(response)
    return "\n".join(parts)


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


class Timer:
    """Context manager measuring wall-clock seconds (perf_counter)."""

    def __enter__(self) -> "Timer":
        self._start = time.perf_counter()
        self.seconds = 0.0
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.seconds = time.perf_counter() - self._start
