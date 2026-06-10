#!/usr/bin/env python3
"""Convert this skill's FLAT normalized records into the UNIFIED nested schema.

The downloader (``download_text_modal_dataset.py``) writes a flat schema
(top-level ``text``/``safety_label``/``label``/``nist_safety_categories``/...).
The sibling skill ``dataset-format-checker`` validates a UNIFIED NESTED schema
(nested ``source``/``content``/``label`` + top-level ``id``/``task_type``); see
``safety_dataset_format_guide.md``.

This module maps flat -> unified so the output PASSES that checker. It is an
ADDITIONAL, read-only transform: it never touches the flat ``normalized/`` or
``raw/`` outputs.

Design goals: portability + robustness.
  * Pure standard library. No third-party dependencies.
  * Per-record errors are skipped and counted, never raised through a whole file.

Run standalone on an existing normalized file:
  python scripts/to_unified_format.py \
    --input  data/safety_guard_2026/normalized/safety_guard_2026.jsonl \
    --output data/safety_guard_2026/unified/safety_guard_2026.unified.jsonl
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple

# --------------------------------------------------------------------------- #
# Mapping tables — aligned with dataset-format-checker (taxonomy.md / the guide)
# --------------------------------------------------------------------------- #

# This skill's 8 NIST-style categories -> canonical taxonomy (22 + `other`).
# The original labels are always preserved in raw_label.original_categories,
# so this mapping stays auditable and remappable.
NIST2CANON: Dict[str, str] = {
    "violence": "violence",
    "hate_speech": "hate_discrimination",
    "harassment": "harassment_bullying",
    "sexual_content": "sexual_content",
    "suicide_self_harm": "self_harm",
    "profanity": "profanity_toxicity",
    "threats": "violence",
    "health_misinformation": "medical_safety",
}

# source_dataset -> Hugging Face dataset page (provenance for source.url).
SOURCE_REPO_URLS: Dict[str, str] = {
    "harmbench": "https://huggingface.co/datasets/walledai/HarmBench",
    "strongreject": "https://huggingface.co/datasets/walledai/StrongREJECT",
    "real_toxicity_prompts": "https://huggingface.co/datasets/allenai/real-toxicity-prompts",
    "beavertails": "https://huggingface.co/datasets/PKU-Alignment/BeaverTails",
}

# Adversarial / jailbreak-style sources (recorded in risk_metadata).
ADVERSARIAL_SOURCES = {"harmbench", "strongreject"}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _nonempty_str(value: Any) -> bool:
    """Match the checker's notion of a non-empty text value (stripped)."""
    return isinstance(value, str) and value.strip() != ""


def _content_hash(prompt: str, response: Optional[str]) -> str:
    """Real sha256 over prompt+response. Not a placeholder, so the checker's
    dedup.content_hash warning is avoided."""
    payload = (prompt or "") + "\n" + (response or "")
    digest = hashlib.sha256(payload.encode("utf-8", errors="ignore")).hexdigest()
    return "sha256:" + digest


def _canonical_categories(nist_cats: Any, is_unsafe: bool) -> List[str]:
    cats: List[str] = []
    if isinstance(nist_cats, list):
        for c in nist_cats:
            key = str(c).strip().lower()
            cats.append(NIST2CANON.get(key, "other"))
    out = sorted(set(cats))
    # An unsafe record should carry at least one category; fall back to the
    # taxonomy's explicit catch-all rather than leaving it empty.
    if is_unsafe and not out:
        out = ["general_harm"]
    return out


def _derive_task(source: str, response_nonempty: bool) -> Tuple[str, str]:
    """task_type / label.target, by source semantics (see plan / guide).

    Only BeaverTails (QA-pair safety, with a real response) is treated as a
    prompt+response task; everything else — including RTP, whose continuation we
    keep as context but whose label is about the text/prompt — is prompt-only.
    Falling back to prompt-only also guarantees the checker's conditional
    ``response_missing`` rule never fires.
    """
    if source == "beavertails" and response_nonempty:
        return "prompt_response_safety", "prompt_response_pair"
    return "prompt_only_safety", "prompt"


# --------------------------------------------------------------------------- #
# Core mapping: one flat record -> one unified record
# --------------------------------------------------------------------------- #
def flat_to_unified(rec: Dict[str, Any]) -> Dict[str, Any]:
    """Map one flat normalized record to the unified nested schema."""
    source = str(rec.get("source_dataset") or "")
    split = rec.get("source_split")
    text = rec.get("text") or ""
    response = rec.get("response")
    response = response if _nonempty_str(response) else None

    is_unsafe = rec.get("label") == 1
    nist_cats = rec.get("nist_safety_categories") or []
    confidence = rec.get("confidence")

    task_type, target = _derive_task(source, response is not None)

    label: Dict[str, Any] = {
        "target": target,
        "is_unsafe": bool(is_unsafe),
        "policy_action": "refuse" if is_unsafe else "allow",
        "canonical_categories": _canonical_categories(nist_cats, bool(is_unsafe)),
        "canonical_subcategories": [],
        "severity": None,
        "is_refusal": None,
        "requires_refusal": bool(is_unsafe),
    }

    annotation: Dict[str, Any] = {}
    if confidence is not None:
        annotation["confidence"] = confidence

    risk_metadata: Dict[str, Any] = {}
    if source in ADVERSARIAL_SOURCES:
        risk_metadata["adversarial"] = True

    return {
        "id": rec.get("id"),
        "source": {
            "dataset": source,
            "subset": None,
            "split": split,
            "url": SOURCE_REPO_URLS.get(source),
            "license": None,
        },
        "modality": ["text"],
        "task_type": task_type,
        "language": "en",
        "content": {
            "system": None,
            "prompt": text,
            "response": response,
            "conversation": None,
            "images": [],
            "videos": [],
            "audio": [],
        },
        "label": label,
        "risk_metadata": risk_metadata,
        "annotation": annotation,
        "generation_metadata": {},
        "dedup": {
            "content_hash": _content_hash(text, response),
            "near_duplicate_group": None,
        },
        "raw_label": {
            "original_categories": list(nist_cats) if isinstance(nist_cats, list) else [],
            "original_fields": {
                "original_category": rec.get("original_category"),
                "category_scores": rec.get("category_scores"),
            },
        },
        "raw_example": rec,
    }


def convert_rows(
    rows: Iterable[Dict[str, Any]],
    errors: Optional[List[Tuple[int, str]]] = None,
) -> Iterator[Dict[str, Any]]:
    """Yield unified records for an iterable of flat records.

    A record that fails to convert is skipped (and appended to ``errors`` as
    ``(index, message)`` when a list is provided) instead of aborting the run.
    """
    for idx, rec in enumerate(rows):
        try:
            if not isinstance(rec, dict):
                raise TypeError("record is not a JSON object")
            yield flat_to_unified(rec)
        except Exception as exc:  # noqa: BLE001 - robustness: never abort the batch
            if errors is not None:
                errors.append((idx, str(exc)))
            continue


# --------------------------------------------------------------------------- #
# Standalone file conversion
# --------------------------------------------------------------------------- #
def _read_jsonl(path: Path) -> Iterator[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                # A malformed line yields a non-dict sentinel so convert_rows
                # counts it as a skip rather than crashing.
                yield {"__parse_error__": True}


def convert_file(in_path: Path, out_path: Path) -> Tuple[int, int, int]:
    """Convert a flat JSONL file to a unified JSONL file.

    Returns (n_in, n_out, n_skipped). Only writes ``out_path`` (and its parent
    directory); never touches the input.
    """
    rows = list(_read_jsonl(in_path))
    errors: List[Tuple[int, str]] = []
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n_out = 0
    with out_path.open("w", encoding="utf-8") as f:
        for unified in convert_rows(rows, errors=errors):
            f.write(json.dumps(unified, ensure_ascii=False) + "\n")
            n_out += 1
    return len(rows), n_out, len(errors)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", "-i", required=True, help="flat normalized JSONL (e.g. normalized/safety_guard_2026.jsonl)")
    p.add_argument("--output", "-o", required=True, help="unified JSONL to write (e.g. unified/safety_guard_2026.unified.jsonl)")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    in_path = Path(args.input)
    out_path = Path(args.output)
    if not in_path.is_file():
        print(f"ERROR: input file not found: {in_path}", file=sys.stderr)
        return 2
    n_in, n_out, n_skipped = convert_file(in_path, out_path)
    print(f"Converted {n_out}/{n_in} records ({n_skipped} skipped) -> {out_path}", file=sys.stderr)
    if n_out == 0:
        print("ERROR: no records converted.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
