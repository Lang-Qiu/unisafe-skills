"""Caption/OCR keyword baseline guard (Core-Minimal). Stdlib only, deterministic.

Derived from guard-llama-guard@7fe610980b51cd7696ce102874fccfeb40d130a5
scripts/guards/rule_based.py. Image adaptation (M3_SPEC 4.4; plan AD-4):
  1. Input = the FIRST image's caption+ocr text (utils.record_caption_text);
     pixels are never read and no OCR is performed — this is a text-surrogate
     PIPELINE BASELINE, clearly labeled as such in reports.
  2. caption and ocr both empty -> record-level error `missing_caption_ocr`
     (silently defaulting to safe would fabricate a flattering FPR).
  3. Word lists live in assets/caption_keywords.json (controlled copy of the
     upstream table); guard.modality = ["image"] (the records it consumes).

No continuous score: confidence is always null, so this guard is excluded
from AUROC by design. The homonym false-positive property of keyword matching
is carried over as documented report material.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from guards.base import GuardAdapter
from utils import SKILL_ROOT, canonical_categories, first_image, record_caption_text

KEYWORDS_PATH = SKILL_ROOT / "assets" / "caption_keywords.json"


class CaptionRuleGuard(GuardAdapter):
    name = "caption-rule"
    version = "1.0"
    modality = ["image"]

    def __init__(self, config: Optional[Dict[str, Any]] = None,
                 keywords_path: Optional[Path] = None):
        # config (CLI dict) is accepted for registry uniformity; the baseline
        # needs nothing from it
        path = Path(keywords_path) if keywords_path else KEYWORDS_PATH
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
        canonical = set(canonical_categories())
        self._patterns: Dict[str, re.Pattern] = {}
        for category, phrases in raw.items():
            if category.startswith("$"):
                continue
            # word list keys must already be canonical (identity mapping);
            # anything else is a word-list bug -> fold into 'other' loudly
            target = category if category in canonical else "other"
            if target != category:
                print(f"WARNING: caption_keywords.json category {category!r} "
                      f"is not canonical; folding matches into 'other'")
            joined = "|".join(re.escape(p) for p in phrases if p)
            if not joined:
                continue
            self._patterns[target] = re.compile(
                r"\b(?:" + joined + r")\b", re.IGNORECASE
            )

    @property
    def capabilities(self) -> Dict[str, Any]:
        return {
            "supports_batch": False,
            "returns_confidence": False,
            "modalities": list(self.modality),
        }

    def available(self) -> Tuple[bool, str]:
        if not self._patterns:
            return False, "caption keyword table is empty or unreadable"
        return True, ""

    def predict(self, record: Dict[str, Any]) -> Dict[str, Any]:
        start = time.perf_counter()
        image = first_image(record) or {}
        text_source = [field for field in ("caption", "ocr")
                       if isinstance(image.get(field), str) and image[field].strip()]
        text = record_caption_text(record)
        if not text:
            return self.make_result(
                record,
                is_unsafe=None,
                raw_output={"engine": "caption-keyword-regex-v1", "text_source": []},
                latency_ms=(time.perf_counter() - start) * 1000.0,
                device="cpu",
                error=("missing_caption_ocr: first image has neither caption nor ocr "
                       "text; the caption-rule baseline cannot judge pixels "
                       "(M3_SPEC 4.4 — never defaults to safe)"),
            )
        matched: Dict[str, List[str]] = {}
        for category, pattern in self._patterns.items():
            hits = pattern.findall(text)
            if hits:
                matched[category] = sorted({h.lower() for h in hits})
        is_unsafe = bool(matched)
        return self.make_result(
            record,
            is_unsafe=is_unsafe,
            risk_categories=list(matched),
            severity=None,
            confidence=None,
            raw_output={"engine": "caption-keyword-regex-v1", "matched": matched,
                        "text_source": text_source},
            latency_ms=(time.perf_counter() - start) * 1000.0,
            device="cpu",
        )
