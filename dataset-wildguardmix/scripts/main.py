#!/usr/bin/env python

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional


DATASET_ID = "allenai/wildguardmix"
DATASET_URL = "https://huggingface.co/datasets/allenai/wildguardmix"
DATASET_NAME = "WildGuardMix"
DATASET_LICENSE = "odc-by"
XSTEST_ID = "walledai/XSTest"
XSTEST_URL = "https://huggingface.co/datasets/walledai/XSTest"
XSTEST_LICENSE = "cc-by-4.0"
DEFAULT_CONFIG = "wildguardtest"
HF_CONFIGS = {
    "wildguardtest": ("wildguardtest", "test"),
    "test": ("wildguardtest", "test"),
    "WildGuardTest": ("wildguardtest", "test"),
    "wildguardtrain": ("wildguardtrain", "train"),
    "train": ("wildguardtrain", "train"),
    "WildGuardTrain": ("wildguardtrain", "train"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert WildGuardMix into unified JSONL.")
    parser.add_argument(
        "--split",
        default=DEFAULT_CONFIG,
        help="WildGuardMix split/config to process. Default: wildguardtest.",
    )
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


def harm_to_bool(value: Any) -> Optional[bool]:
    label = clean_label(value)
    if label is None:
        return None
    lowered = label.lower()
    if lowered == "harmful":
        return True
    if lowered == "unharmful":
        return False
    return None


def refusal_to_bool(value: Any) -> Optional[bool]:
    label = clean_label(value)
    if label is None:
        return None
    lowered = label.lower()
    if lowered == "refusal":
        return True
    if lowered == "compliance":
        return False
    return None


def has_response(example: Mapping[str, Any]) -> bool:
    response = example.get("response")
    return response is not None and str(response).strip() != ""


def normalize_text(value: Any) -> str:
    text = clean_label(value) or ""
    text = text.lower()
    text = re.sub(r"[_/|]+", " ", text)
    text = re.sub(r"[^a-z0-9+\-. ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def load_mapping() -> Dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / "references" / "category_mapping.json"
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def dedupe(values: Iterable[str]) -> List[str]:
    seen = set()
    out = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


def map_categories(subcategory: Any, is_unsafe: bool, mapping: Mapping[str, Any]) -> List[str]:
    raw = clean_label(subcategory)
    fallback = mapping.get("fallback", "other")
    unsafe_no_category = mapping.get("unsafe_no_category_fallback", "general_harm")
    wildguardmix = mapping.get("wildguardmix", {})
    exact_map = wildguardmix.get("exact_map", {})
    keyword_map = wildguardmix.get("keyword_map", {})

    if raw is None:
        return [unsafe_no_category] if is_unsafe else []

    if raw in exact_map:
        mapped = exact_map[raw]
        return list(mapped) if mapped else []

    normalized = normalize_text(raw)
    matches: List[str] = []
    for keyword, categories in keyword_map.items():
        if normalize_text(keyword) in normalized:
            matches.extend(categories)
    if matches:
        return dedupe(matches)

    return [fallback] if is_unsafe else []


def original_categories(subcategory: Any) -> List[str]:
    value = clean_label(subcategory)
    return [value] if value else []


def content_hash(prompt: Any, response: Any) -> str:
    payload = json.dumps({"prompt": prompt, "response": response}, ensure_ascii=False, sort_keys=True)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8", errors="ignore")).hexdigest()


def resolve_split(split_arg: str) -> tuple[str, str, str]:
    config, hf_split = HF_CONFIGS.get(split_arg, (split_arg.lower(), "test"))
    output_split = "test" if config == "wildguardtest" else "train" if config == "wildguardtrain" else hf_split
    return config, hf_split, output_split


def load_dataset(config: str, hf_split: str, args: argparse.Namespace) -> Any:
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
        return load_dataset(DATASET_ID, config, split=hf_split, **kwargs)
    except Exception as exc:
        detail = str(exc)
        print("ERROR: Failed to load WildGuardMix from Hugging Face.", file=sys.stderr)
        print(f"DETAIL: {detail}", file=sys.stderr)
        if any(marker in detail.lower() for marker in ("gated", "403", "401", "restricted", "unauthorized")):
            print(
                "FIX: WildGuardMix is gated. Request access on Hugging Face, then run "
                "`huggingface-cli login`, or pass `--token <HF_TOKEN>`.",
                file=sys.stderr,
            )
        print("FIX: For the test set, use `--split wildguardtest`.", file=sys.stderr)
        raise SystemExit(2) from exc


def load_xstest(args: argparse.Namespace) -> Any:
    try:
        from datasets import load_dataset
    except ImportError as exc:
        print("ERROR: Missing dependency 'datasets'. Install it with: pip install datasets", file=sys.stderr)
        raise SystemExit(1) from exc

    kwargs: Dict[str, Any] = {}
    if args.cache_dir:
        kwargs["cache_dir"] = args.cache_dir
    if args.token:
        kwargs["token"] = args.token

    try:
        return load_dataset(XSTEST_ID, split="test", **kwargs)
    except Exception as exc:
        detail = str(exc)
        print("ERROR: Failed to load XSTest from Hugging Face.", file=sys.stderr)
        print(f"DETAIL: {detail}", file=sys.stderr)
        if any(marker in detail.lower() for marker in ("gated", "403", "401", "restricted", "unauthorized")):
            print(
                "FIX: XSTest may require access approval. Request access on Hugging Face, then run "
                "`huggingface-cli login`, or pass `--token <HF_TOKEN>`.",
                file=sys.stderr,
            )
        raise SystemExit(2) from exc


def annotator_type(config: str) -> str:
    return "human" if config == "wildguardtest" else "llm"


def build_record(
    example: Mapping[str, Any],
    output_split: str,
    written_index: int,
    config: str,
    mapping: Mapping[str, Any],
) -> Optional[Dict[str, Any]]:
    response_present = has_response(example)
    task_type = "prompt_response_safety" if response_present else "prompt_only_safety"
    target = "prompt_response_pair" if response_present else "prompt"

    prompt_is_unsafe = harm_to_bool(example.get("prompt_harm_label"))
    response_is_unsafe = harm_to_bool(example.get("response_harm_label"))
    is_refusal = refusal_to_bool(example.get("response_refusal_label"))
    if response_present:
        if response_is_unsafe is None:
            return None
        is_unsafe = response_is_unsafe
    else:
        if prompt_is_unsafe is None:
            return None
        is_unsafe = prompt_is_unsafe

    response_is_safe = None if response_is_unsafe is None else not response_is_unsafe
    requires_refusal = prompt_is_unsafe
    categories = map_categories(example.get("subcategory"), is_unsafe, mapping)
    subcategories = original_categories(example.get("subcategory"))
    adversarial = bool(example.get("adversarial")) if example.get("adversarial") is not None else False
    jailbreak = bool(adversarial and prompt_is_unsafe)
    record_id = f"wildguardmix:{output_split}:{written_index:06d}"

    label_fields = {
        "prompt_harm_label": clean_label(example.get("prompt_harm_label")),
        "response_harm_label": clean_label(example.get("response_harm_label")),
        "response_refusal_label": clean_label(example.get("response_refusal_label")),
        "adversarial": example.get("adversarial"),
        "subcategory": clean_label(example.get("subcategory")),
    }

    return {
        "id": record_id,
        "source": {
            "dataset": DATASET_NAME,
            "subset": config,
            "version": None,
            "split": output_split,
            "url": DATASET_URL,
            "license": DATASET_LICENSE,
        },
        "modality": ["text"],
        "task_type": task_type,
        "language": "en",
        "content": {
            "system": None,
            "prompt": example.get("prompt"),
            "response": example.get("response") if response_present else None,
            "conversation": None,
            "images": [],
            "videos": [],
            "audio": [],
        },
        "label": {
            "target": target,
            "is_unsafe": is_unsafe,
            "prompt_is_unsafe": prompt_is_unsafe,
            "response_is_unsafe": response_is_unsafe,
            "is_refusal": is_refusal,
            "requires_refusal": requires_refusal,
            "response_is_safe": response_is_safe,
            "canonical_categories": categories if is_unsafe else [],
            "canonical_subcategories": subcategories if is_unsafe else [],
            "severity": "high" if is_unsafe else "none",
            "policy_action": "refuse" if is_unsafe else "allow",
        },
        "risk_metadata": {
            "adversarial": adversarial,
            "jailbreak": jailbreak,
        },
        "annotation": {
            "annotator_type": annotator_type(config),
            "confidence": 1.0,
        },
        "generation_metadata": {},
        "dedup": {
            "content_hash": content_hash(example.get("prompt"), example.get("response")),
            "near_duplicate_group": None,
        },
        "raw_label": {
            "original_categories": subcategories,
            "original_fields": label_fields,
        },
        "raw_example": dict(example),
    }


def build_xstest_record(example: Mapping[str, Any], written_index: int) -> Optional[Dict[str, Any]]:
    if clean_label(example.get("label")) and clean_label(example.get("label")).lower() != "safe":
        return None

    prompt = example.get("prompt")
    if clean_label(prompt) is None:
        return None

    record_id = f"xstest:test:{written_index:06d}"
    original_fields = {
        "label": clean_label(example.get("label")),
        "type": clean_label(example.get("type")),
        "focus": clean_label(example.get("focus")),
        "note": clean_label(example.get("note")),
    }

    return {
        "id": record_id,
        "source": {
            "dataset": "XSTest",
            "subset": None,
            "version": None,
            "split": "test",
            "url": XSTEST_URL,
            "license": XSTEST_LICENSE,
        },
        "modality": ["text"],
        "task_type": "prompt_only_safety",
        "language": "en",
        "content": {
            "system": None,
            "prompt": prompt,
            "response": None,
            "conversation": None,
            "images": [],
            "videos": [],
            "audio": [],
        },
        "label": {
            "target": "prompt",
            "is_unsafe": False,
            "prompt_is_unsafe": False,
            "response_is_unsafe": None,
            "is_refusal": None,
            "requires_refusal": False,
            "response_is_safe": None,
            "canonical_categories": [],
            "canonical_subcategories": [],
            "severity": "none",
            "policy_action": "allow",
        },
        "risk_metadata": {
            "jailbreak": False,
            "adversarial": False,
            "over_refusal_probe": True,
        },
        "annotation": {
            "annotator_type": "human",
            "confidence": 1.0,
        },
        "generation_metadata": {},
        "dedup": {
            "content_hash": content_hash(prompt, None),
            "near_duplicate_group": None,
        },
        "raw_label": {
            "original_categories": ["safe"],
            "original_fields": original_fields,
        },
        "raw_example": dict(example),
    }


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    config, hf_split, output_split = resolve_split(args.split)
    mapping = load_mapping()
    unified_dir = Path(args.output_dir) / "unified"
    unified_dir.mkdir(parents=True, exist_ok=True)
    output_path = unified_dir / f"{config}.unified.jsonl"
    metadata_path = unified_dir / "metadata.json"

    load_errors: List[str] = []
    dataset = load_dataset(config, hf_split, args)

    wildguardmix_seen = 0
    wildguardmix_written = 0
    skipped = Counter()
    label_counts = Counter()
    adversarial_counts = Counter()
    category_counts = Counter()
    xstest_probe_counts = Counter()

    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        for example in dataset:
            if args.limit is not None and wildguardmix_seen >= args.limit:
                break
            wildguardmix_seen += 1
            record = build_record(example, output_split, wildguardmix_written + 1, config, mapping)
            if record is None:
                skipped["null_label"] += 1
                continue

            wildguardmix_written += 1
            is_unsafe = record["label"]["is_unsafe"]
            label_counts["unsafe" if is_unsafe else "safe"] += 1
            adversarial_counts["true" if record["risk_metadata"]["adversarial"] else "false"] += 1
            for category in record["label"]["canonical_categories"]:
                category_counts[category] += 1
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

        if config == "wildguardtest":
            xstest_dataset = load_xstest(args)
            for example in xstest_dataset:
                xstest_probe_counts["seen"] += 1
                record = build_xstest_record(example, xstest_probe_counts["written"] + 1)
                if record is None:
                    xstest_probe_counts["skipped"] += 1
                    continue

                xstest_probe_counts["written"] += 1
                label_counts["safe"] += 1
                adversarial_counts["false"] += 1
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    total_seen = wildguardmix_seen + xstest_probe_counts["seen"]
    total_written = wildguardmix_written + xstest_probe_counts["written"]
    metadata = {
        "dataset": DATASET_ID,
        "config": config,
        "split": hf_split,
        "output_split": output_split,
        "output_file": str(output_path),
        "total_seen": total_seen,
        "total_written": total_written,
        "wildguardmix_counts": {
            "seen": wildguardmix_seen,
            "written": wildguardmix_written,
        },
        "skipped": {
            "null_label": skipped["null_label"],
        },
        "label_counts": {
            "safe": label_counts["safe"],
            "unsafe": label_counts["unsafe"],
        },
        "adversarial_counts": {
            "true": adversarial_counts["true"],
            "false": adversarial_counts["false"],
        },
        "category_counts": dict(sorted(category_counts.items())),
        "xstest_probe_counts": {
            "seen": xstest_probe_counts["seen"],
            "written": xstest_probe_counts["written"],
            "skipped": xstest_probe_counts["skipped"],
        },
        "load_errors": load_errors,
    }
    write_json(metadata_path, metadata)
    print(
        f"RESULT: ok total_seen={total_seen} total_written={total_written} "
        f"skipped_null_label={skipped['null_label']} "
        f"xstest_written={xstest_probe_counts['written']}"
    )
    print(f"UNIFIED: {output_path}")
    print(f"METADATA: {metadata_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
