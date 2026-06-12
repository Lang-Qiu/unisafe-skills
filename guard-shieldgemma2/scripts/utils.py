"""Shared helpers for guard-shieldgemma2 scripts. Stdlib only (Python >= 3.9).

Derived from guard-llama-guard@e72fa2bea4dde4a8252e2b6c3d76af8baa0e8f9f
scripts/utils.py. Image adaptation (the complete thin-diff list; anything else
that differs from upstream is a defect):
  1. route_record implements the image_safety eligible rules
     (references/io-contract.md section 2 image edition; M3_SPEC 4.1 plan B:
     first image needs path OR url, both empty -> missing_content).
  2. record_text -> record_caption_text (first image caption+ocr; pixels are
     never read here — caption-rule contract, M3_SPEC 4.4).
  3. Added image helpers: first_image / resolve_image_path (relative paths
     resolve against the unified JSONL's directory, 待甲确认.md #5 point 1) /
     image_magic_ok (stdlib magic-bytes check backing the L0 tier of
     image_decode_error, M3_SPEC 4.2).

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

# M3 scope: image-only safety tasks (io-contract.md section 1)
IMAGE_TASK_TYPES = ("image_safety",)

ROUTE_ELIGIBLE = "eligible"
ROUTE_OUT_OF_SCOPE = "out_of_scope"
ROUTE_MISSING_CONTENT = "missing_content"

# stdlib magic-bytes table (L0 image_decode_error tier; pixel-level decode
# failures belong to the L1 adapter and reuse the same error name)
_MAGIC_PREFIXES = (
    b"\x89PNG\r\n\x1a\n",  # PNG
    b"\xff\xd8\xff",        # JPEG
    b"GIF87a",              # GIF
    b"GIF89a",
    b"BM",                  # BMP
)


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


def first_image(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """First entry of content.images, or None when absent/empty/non-dict."""
    images = (record.get("content") or {}).get("images")
    if isinstance(images, list) and images and isinstance(images[0], dict):
        return images[0]
    return None


def route_record(record: Dict[str, Any]) -> Tuple[str, str]:
    """Route one unified record per io-contract.md section 2 (image edition).

    Returns (bucket, reason) with bucket in {eligible, out_of_scope, missing_content}.
    Plan B (M3_SPEC 4.1): a record whose first image has a path OR a url is
    eligible; url-only records become image_url_not_supported error rows later.
    """
    task_type = record.get("task_type")
    modality = record.get("modality")
    if task_type not in IMAGE_TASK_TYPES:
        return ROUTE_OUT_OF_SCOPE, f"task_type={task_type!r} not in M3 scope"
    if modality != ["image"]:
        return ROUTE_OUT_OF_SCOPE, f"modality={modality!r} != ['image']"
    image = first_image(record)
    if image is None:
        return ROUTE_MISSING_CONTENT, "content.images is empty"
    if not _non_empty_str(image.get("path")) and not _non_empty_str(image.get("url")):
        return ROUTE_MISSING_CONTENT, "first image has neither path nor url"
    return ROUTE_ELIGIBLE, ""


def record_caption_text(record: Dict[str, Any]) -> str:
    """caption-rule input: first image's caption + ocr text (never pixels)."""
    image = first_image(record) or {}
    parts = [part.strip() for part in (image.get("caption"), image.get("ocr"))
             if _non_empty_str(part)]
    return "\n".join(parts)


def resolve_image_path(record: Dict[str, Any], dataset_dir: Path) -> Optional[Path]:
    """Resolve the first image's path against the unified JSONL's directory.

    Absolute paths pass through unchanged; url-only records return None
    (-> image_url_not_supported error row, never a download).
    """
    image = first_image(record) or {}
    raw = image.get("path")
    if not _non_empty_str(raw):
        return None
    path = Path(raw)
    return path if path.is_absolute() else Path(dataset_dir) / path


def image_magic_ok(path: Path) -> bool:
    """True when the file starts with a known raster signature (stdlib only)."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(16)
    except OSError:
        return False
    if any(head.startswith(prefix) for prefix in _MAGIC_PREFIXES):
        return True
    return head[:4] == b"RIFF" and head[8:12] == b"WEBP"


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
