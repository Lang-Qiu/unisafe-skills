"""GuardAdapter protocol (M1_SPEC section 6 + tasks/plan.md task 6).

Adapters must be import-safe without their heavy dependencies installed:
defer torch/transformers/openai imports to available()/predict().
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


class GuardAdapter:
    """Base class for guard adapters.

    Contract:
      - available() -> (bool, reason): cheap capability probe; False means
        guard-level failure (exit-code contract row 2), reason is user-facing.
      - predict(record) -> dict: one guard_output.schema.json record. Must not
        raise for record-level problems; return an error record instead.
      - predict_batch(records): default = loop over predict; real batching
        adapters (Llama Guard) override and set capabilities.supports_batch.
    """

    name: str = "base"
    version: Optional[str] = None
    modality: List[str] = ["text"]

    @property
    def capabilities(self) -> Dict[str, Any]:
        return {
            "supports_batch": False,
            "returns_confidence": False,
            "modalities": list(self.modality),
        }

    def available(self) -> Tuple[bool, str]:
        return True, ""

    def predict(self, record: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def predict_batch(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [self.predict(record) for record in records]

    def make_result(
        self,
        record: Dict[str, Any],
        *,
        is_unsafe: Optional[bool],
        risk_categories: Optional[List[str]] = None,
        severity: Optional[int] = None,
        action: Optional[str] = None,
        confidence: Optional[float] = None,
        raw_output: Optional[Dict[str, Any]] = None,
        latency_ms: float = 0.0,
        device: str = "cpu",
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Assemble one schema-conformant output record (single source of shape)."""
        if action is None:
            if is_unsafe is None:
                action = "uncertain"
            else:
                action = "refuse" if is_unsafe else "allow"
        return {
            "id": record.get("id"),
            "guard": {
                "name": self.name,
                "version": self.version,
                "modality": list(self.modality),
            },
            "prediction": {
                "is_unsafe": is_unsafe,
                "risk_categories": list(risk_categories or []),
                "severity": severity,
                "action": action,
                "confidence": confidence,
            },
            "raw_output": raw_output if raw_output is not None else {},
            "runtime": {
                "latency_ms": round(float(latency_ms), 3),
                "cost": None,
                "device": device,
            },
            "error": error,
        }
