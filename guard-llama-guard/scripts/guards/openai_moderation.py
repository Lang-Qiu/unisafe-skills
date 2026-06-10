"""OpenAI Moderation API baseline (Plus layer). Lazy-imports `openai`.

Isolation principle (tasks/plan.md / io-contract.md section 7): this guard is
never part of the Core-Minimal smoke or default CI. Without OPENAI_API_KEY it
reports itself unavailable (guard-level failure) — by the rulings table that
is exit 1 when requested alone, exit 2 alongside a succeeding guard, and
never an M1 failure.

confidence = max(category_scores) (M0 section 5), so AUROC is computable.
"""
from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional, Tuple

from guards.base import GuardAdapter
from utils import load_category_mapping, record_text

DEFAULT_MODEL = "omni-moderation-latest"
FIX_KEY = ("FIX: set the OPENAI_API_KEY environment variable "
           "(PowerShell: $env:OPENAI_API_KEY = '<key>') and re-run; "
           "deps: pip install -r requirements-api.txt")


class OpenAIModerationGuard(GuardAdapter):
    name = "openai-moderation"
    version = DEFAULT_MODEL
    modality = ["text"]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        config = config or {}
        self.timeout_s: float = float(config.get("timeout_s") or 30.0)
        self.retries: int = int(config.get("retries") if config.get("retries") is not None else 1)
        self._client = None
        self._mapping = load_category_mapping().get("openai_moderation", {})

    @property
    def capabilities(self) -> Dict[str, Any]:
        return {
            "supports_batch": False,
            "returns_confidence": True,
            "modalities": list(self.modality),
        }

    def available(self) -> Tuple[bool, str]:
        try:
            import openai  # noqa: F401
        except ImportError:
            return False, f"openai package not installed. {FIX_KEY}"
        if not os.environ.get("OPENAI_API_KEY"):
            return False, f"OPENAI_API_KEY is not set. {FIX_KEY}"
        return True, ""

    def _ensure_client(self):
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(timeout=self.timeout_s)
        return self._client

    def predict(self, record: Dict[str, Any]) -> Dict[str, Any]:
        start = time.perf_counter()
        client = self._ensure_client()
        text = record_text(record)
        last_error: Optional[Exception] = None
        for attempt in range(self.retries + 1):
            try:
                response = client.moderations.create(model=self.version, input=text)
                return self._parse(record, response,
                                   latency_ms=(time.perf_counter() - start) * 1000.0)
            except Exception as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(min(2 ** attempt, 8))  # exponential backoff
        return self.make_result(
            record, is_unsafe=None, device="api",
            latency_ms=(time.perf_counter() - start) * 1000.0,
            error=f"API failure after {self.retries + 1} attempt(s): "
                  f"{type(last_error).__name__}: {last_error}",
        )

    def _parse(self, record: Dict[str, Any], response: Any, latency_ms: float) -> Dict[str, Any]:
        result = response.results[0]
        categories: Dict[str, bool] = result.categories.model_dump(by_alias=True)
        scores: Dict[str, float] = result.category_scores.model_dump(by_alias=True)
        flagged = bool(result.flagged)

        mapped: List[str] = []
        for key, hit in categories.items():
            if not hit:
                continue
            for canonical in self._mapping.get(key, ["other"]):
                if canonical not in mapped:
                    mapped.append(canonical)
        if flagged and not mapped:
            mapped = ["general_harm"]  # unsafe with no mappable category (M0 section 4)
        if not flagged:
            mapped = []

        numeric_scores = [v for v in scores.values() if isinstance(v, (int, float))]
        confidence = max(numeric_scores) if numeric_scores else None
        if confidence is not None:
            confidence = min(max(float(confidence), 0.0), 1.0)

        return self.make_result(
            record,
            is_unsafe=flagged,
            risk_categories=mapped,
            severity=None,
            confidence=confidence,
            raw_output={
                "flagged": flagged,
                "categories": {k: v for k, v in categories.items() if v},
                "category_scores": scores,
            },
            latency_ms=latency_ms,
            device="api",
        )
