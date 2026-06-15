#!/usr/bin/env python
"""Convert UnsafeBench to the unified safety JSONL format."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Mapping, Optional


DATASET_ID = "yiting/UnsafeBench"
DATASET_NAME = "UnsafeBench"
DATASET_URL = "https://huggingface.co/datasets/yiting/UnsafeBench"
DATASET_LICENSE = None
DEFAULT_SPLIT = "test"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert UnsafeBench into unified JSONL.")
    parser.add_argument("--split", default=DEFAULT_SPLIT, help="Dataset split to process. Default: test.")
    parser.add_argument("--limit", type=int, default=None, help="Optional maximum rows to process.")
    parser.add_argument("--output-dir", required=True, help="Output directory.")
    parser.add_argument("--cache-dir", default=None, help="Optional Hugging Face cache directory.")
    parser.add_argument("--hf-endpoint", default=None, help="Optional Hugging Face endpoint.")
    parser.add_argument("--token", default=None, help="Optional Hugging Face token.")
    return parser.parse_args()


def clean_label(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"none", "null", "nan", "n/a"}:
        return None
    return text


def load_mapping() -> Dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / "references" / "category_mapping.json"
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def map_category(category: Any, is_unsafe: bool, mapping: Mapping[str, Any]) -> list[str]:
    raw = clean_label(category)
    if raw is None:
        return [mapping.get("unsafe_no_category_fallback", "general_harm")] if is_unsafe else []

    exact_map = mapping.get("unsafebench", {}).get("exact_map", {})
    if raw in exact_map:
        return list(exact_map[raw]) if is_unsafe else []
    return [mapping.get("fallback", "other")] if is_unsafe else []


def safety_to_bool(value: Any) -> Optional[bool]:
    label = clean_label(value)
    if label is None:
        return None
    lowered = label.lower()
    if lowered == "unsafe":
        return True
    if lowered == "safe":
        return False
    return None


def content_hash(image_bytes: bytes, text: Any) -> str:
    digest = hashlib.sha256()
    digest.update(image_bytes)
    digest.update(json.dumps({"text": text}, ensure_ascii=False, sort_keys=True).encode("utf-8"))
    return "sha256:" + digest.hexdigest()


def load_dataset(args: argparse.Namespace) -> Any:
    try:
        from datasets import load_dataset
    except ImportError as exc:
        print("ERROR: Missing dependency 'datasets'. Install it with: pip install datasets", file=sys.stderr)
        raise SystemExit(1) from exc

    if args.hf_endpoint:
        os.environ["HF_ENDPOINT"] = args.hf_endpoint

    kwargs: Dict[str, Any] = {}
    if args.cache_dir:
        kwargs["cache_dir"] = args.cache_dir
    if args.token:
        kwargs["token"] = args.token

    try:
        return load_dataset(DATASET_ID, split=args.split, streaming=True, **kwargs)
    except Exception as exc:
        detail = str(exc)
        print("ERROR: Failed to load UnsafeBench from Hugging Face.", file=sys.stderr)
        print(f"DETAIL: {detail}", file=sys.stderr)
        if any(marker in detail.lower() for marker in ("gated", "403", "401", "restricted", "unauthorized")):
            print(
                "FIX: UnsafeBench is gated. Request access on Hugging Face, then run "
                "`huggingface-cli login`, or pass `--token <HF_TOKEN>`.",
                file=sys.stderr,
            )
        raise SystemExit(2) from exc


def image_to_bytes(image: Any) -> bytes:
    from io import BytesIO

    if image is None:
        raise ValueError("missing image")
    if isinstance(image, bytes):
        return image
    if isinstance(image, dict):
        if image.get("bytes"):
            return image["bytes"]
        if image.get("path"):
            return Path(image["path"]).read_bytes()
    if hasattr(image, "save"):
        buffer = BytesIO()
        if getattr(image, "mode", None) not in (None, "RGB"):
            image = image.convert("RGB")
        image.save(buffer, format="JPEG")
        return buffer.getvalue()
    raise TypeError(f"unsupported image type: {type(image).__name__}")


def save_image(image: Any, output_dir: Path, split: str, index: int) -> tuple[str, bytes]:
    image_bytes = image_to_bytes(image)
    rel_path = Path("images") / "unsafebench" / f"{split}_{index:06d}.jpg"
    abs_path = output_dir / "unified" / rel_path
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_bytes(image_bytes)
    return rel_path.as_posix(), image_bytes


def build_record(
    example: Mapping[str, Any],
    split: str,
    index: int,
    output_dir: Path,
    mapping: Mapping[str, Any],
) -> Optional[Dict[str, Any]]:
    is_unsafe = safety_to_bool(example.get("safety_label"))
    if is_unsafe is None:
        return None

    rel_image_path, image_bytes = save_image(example.get("image"), output_dir, split, index)
    category = clean_label(example.get("category"))
    categories = map_category(category, is_unsafe, mapping)
    original_categories = [category] if category else []
    record_id = f"unsafebench:{split}:{index:06d}"
    text = clean_label(example.get("text"))

    return {
        "id": record_id,
        "source": {
            "dataset": DATASET_NAME,
            "subset": None,
            "version": None,
            "split": split,
            "url": DATASET_URL,
            "license": DATASET_LICENSE,
        },
        "modality": ["image"],
        "task_type": "image_safety",
        "language": "en",
        "content": {
            "system": None,
            "prompt": None,
            "response": None,
            "conversation": None,
            "images": [
                {
                    "path": rel_image_path,
                    "url": None,
                    "caption": text,
                    "ocr": None,
                }
            ],
            "videos": [],
            "audio": [],
        },
        "label": {
            "target": "image",
            "is_unsafe": is_unsafe,
            "prompt_is_unsafe": None,
            "response_is_unsafe": None,
            "is_refusal": None,
            "requires_refusal": None,
            "response_is_safe": None,
            "canonical_categories": categories if is_unsafe else [],
            "canonical_subcategories": [],
            "severity": "high" if is_unsafe else "none",
            "policy_action": "refuse" if is_unsafe else "allow",
        },
        "risk_metadata": {},
        "annotation": {
            "annotator_type": "human",
            "confidence": 1.0,
        },
        "generation_metadata": {},
        "dedup": {
            "content_hash": content_hash(image_bytes, text),
            "near_duplicate_group": None,
        },
        "raw_label": {
            "original_categories": original_categories,
            "original_fields": {
                "safety_label": clean_label(example.get("safety_label")),
                "category": category,
                "source": clean_label(example.get("source")),
            },
        },
        "raw_example": {
            "safety_label": clean_label(example.get("safety_label")),
            "category": category,
            "source": clean_label(example.get("source")),
            "text": text,
            "image": rel_image_path,
        },
    }


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    unified_dir = output_dir / "unified"
    unified_dir.mkdir(parents=True, exist_ok=True)
    output_path = unified_dir / "unsafebench.unified.jsonl"
    metadata_path = unified_dir / "metadata.json"

    mapping = load_mapping()
    dataset = load_dataset(args)

    seen = 0
    written = 0
    skipped = Counter()
    errors = Counter()
    label_counts = Counter()
    category_counts = Counter()
    source_counts = Counter()
    load_errors: list[str] = []

    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        for example in dataset:
            if args.limit is not None and seen >= args.limit:
                break
            seen += 1
            try:
                record = build_record(example, args.split, written + 1, output_dir, mapping)
            except Exception as exc:
                errors[type(exc).__name__] += 1
                skipped["image_or_record_error"] += 1
                print(f"WARNING: skipped row {seen}: {exc}", file=sys.stderr)
                continue
            if record is None:
                skipped["invalid_safety_label"] += 1
                continue

            written += 1
            is_unsafe = record["label"]["is_unsafe"]
            label_counts["unsafe" if is_unsafe else "safe"] += 1
            for category in record["label"]["canonical_categories"]:
                category_counts[category] += 1
            source_counts[record["raw_label"]["original_fields"]["source"] or "<null>"] += 1
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    metadata = {
        "dataset": DATASET_ID,
        "split": args.split,
        "output_file": str(output_path),
        "total_seen": seen,
        "total_written": written,
        "skipped": dict(skipped),
        "errors": dict(errors),
        "label_counts": {
            "safe": label_counts["safe"],
            "unsafe": label_counts["unsafe"],
        },
        "category_counts": dict(sorted(category_counts.items())),
        "source_counts": dict(sorted(source_counts.items())),
        "image_dir": str(unified_dir / "images" / "unsafebench"),
        "load_errors": load_errors,
    }
    write_json(metadata_path, metadata)
    print(f"RESULT: ok total_seen={seen} total_written={written} skipped={sum(skipped.values())}")
    print(f"UNIFIED: {output_path}")
    print(f"METADATA: {metadata_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
