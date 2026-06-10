"""Keyword rule baseline guard (Core-Minimal). Stdlib only, fully deterministic.

Word lists live in assets/rule_keywords.json, grouped directly by canonical
category (identity mapping; see references/category_mapping.json ->
rule_baseline). No continuous score: confidence is always null, so this guard
is excluded from AUROC by design.

Known design property (M1_SPEC section 12.3-12): keyword matching necessarily
misfires on safe homonym prompts such as "kill a Python process" -> high FPR
on XSTest over-refusal probes. This is kept as report material, not fixed.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from guards.base import GuardAdapter
from utils import SKILL_ROOT, canonical_categories, record_text

KEYWORDS_PATH = SKILL_ROOT / "assets" / "rule_keywords.json"


class RuleGuard(GuardAdapter):
    name = "rule"
    version = "1.0"
    modality = ["text"]

    def __init__(self, keywords_path: Optional[Path] = None):
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
                print(f"WARNING: rule_keywords.json category {category!r} "
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
            return False, "rule keyword table is empty or unreadable"
        return True, ""

    def predict(self, record: Dict[str, Any]) -> Dict[str, Any]:
        start = time.perf_counter()
        text = record_text(record)
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
            raw_output={"engine": "keyword-regex-v1", "matched": matched},
            latency_ms=(time.perf_counter() - start) * 1000.0,
            device="cpu",
        )
