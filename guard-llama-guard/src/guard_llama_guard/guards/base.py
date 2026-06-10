"""Guard adapter base class.

Contract (references/schema.md): ``predict(route)`` returns one unified
guard-output row per eligible record — ALWAYS, even on failure (then
``prediction.is_unsafe=null`` + ``error``). A per-record exception never
aborts the batch. ``predict_batch`` exists from day one so that real
batched inference (local models) is an override, not interface surgery.

Timeout semantics: local guards do NOT promise a wall-clock timeout
(Windows cannot kill a running CUDA op); generation is bounded by small
``max_new_tokens``. API guards use real request-level timeouts.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from guard_llama_guard.utils import Route, build_guard_output


class GuardLoadError(Exception):
    """The guard cannot be used at all (missing dep / gated model / no key)."""


class Guard(ABC):
    """One safety guard behind the unified interface."""

    name: str = "abstract"
    version: str = "0"
    device: str = "cpu"
    # Capability declaration drives routing (eligible vs out_of_scope) and
    # which metrics may be claimed (refusal metrics need refusal=True).
    capabilities: Dict[str, Any] = {
        "refusal": False,
        "continuous_score": False,
        "modalities": ["text"],
        "tasks": [],
    }
    # Versioning fields feed the cache key and metadata.
    model_id: Optional[str] = None
    model_revision: Optional[str] = None
    prompt_template_version: Optional[str] = None
    confidence_method: Optional[str] = None
    confidence_status: str = "unavailable"  # validated | experimental | unavailable

    def load(self) -> None:
        """Heavy initialization (model/tokenizer/client). Raise GuardLoadError
        with a helpful message when the guard cannot run at all."""

    @abstractmethod
    def _predict_one(self, route: Route) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Return (prediction, raw_output) for one eligible record.

        prediction keys: is_unsafe (bool), risk_categories (list, canonical),
        optional severity / action / confidence / confidence_method.
        May raise — predict() converts the exception into an error row.
        """

    def predict(self, route: Route) -> Dict[str, Any]:
        start = time.perf_counter()
        try:
            prediction, raw = self._predict_one(route)
            error = None
        except Exception as exc:  # noqa: BLE001 — robustness: never abort the batch
            prediction, raw = {}, {}
            error = f"{type(exc).__name__}: {exc}"
        latency_ms = int((time.perf_counter() - start) * 1000)
        if error is None and prediction.get("confidence") is not None \
                and prediction.get("confidence_method") is None:
            prediction["confidence_method"] = self.confidence_method
        return build_guard_output(
            record_id=route.record_id,
            guard_name=self.name,
            guard_version=self.version,
            modalities=self.capabilities["modalities"],
            prediction=prediction,
            raw_output=raw,
            latency_ms=latency_ms,
            device=self.device,
            error=error,
        )

    def predict_batch(self, routes: List[Route]) -> List[Dict[str, Any]]:
        """Default: loop. Local-model guards override with true batching
        (this is the seam the P2.D throughput ablation flips)."""
        return [self.predict(rt) for rt in routes]
