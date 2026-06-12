"""ShieldGemma 2 image safety adapter (Core-Full). Lazy-imports torch/transformers.

Quantization basis: **8-bit int8 on CUDA** (M3_SPEC 9-3 said 4-bit NF4; deviation
registered — on this stack (bitsandbytes 0.48.2 + torch 2.5.1 + Gemma3/Windows)
the 4-bit path returns all-NaN probabilities while CPU bf16 is clean, so the
weights are innocent and 8-bit is the measured working baseline: peak 5.95GB,
~2.4-3.4 s/image, benign synth image judged safe with yes<=0.008). CPU device
uses bf16 without quantization. Discovery facts (M3 task 4, 2026-06-12):
processor.policy_definitions keys = ['dangerous', 'sexual', 'violence']
(snake_case, NOT the M0 display names); output.probabilities shape =
(n_policies, 2) as (yes, no) per policy.

Contract (M3_SPEC section 5):
  - is_unsafe = max(yes_p) >= threshold (default 0.5, model-card default,
    not calibrated); confidence = max(yes_p) (unsafe-direction, native [0,1]);
  - risk_categories = mapped policies with yes_p >= threshold (M0 section 4 via
    references/category_mapping.json 'shieldgemma2', which carries both the M0
    display names and the discovery-verified runtime keys);
  - unmapped policy names are NEVER guessed: counted in unknown_policy_count
    (surfaced as run_metadata.warnings.unknown_policy_count, plan AD-8) and the
    raw scores stay in raw_output.policy_scores; unsafe with no mapped category
    falls back to general_harm (M0 section 4);
  - NaN probabilities -> record-level error row (defensive: the 4-bit failure
    shape observed in task 4);
  - soft timeout default 120s (vision inference; CUDA steps cannot be
    interrupted — late results are discarded, same pattern as the text guards).
"""
from __future__ import annotations

import math
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from guards.base import GuardAdapter
from utils import first_image, load_category_mapping

DEFAULT_MODEL_ID = "google/shieldgemma-2-4b-it"
DEFAULT_TIMEOUT_S = 120.0
DEFAULT_THRESHOLD = 0.5

FIX_DEPS = ("FIX: pip install -r requirements-shieldgemma.txt "
            "(torch/transformers/bitsandbytes/pillow are required for shieldgemma2)")
FIX_GATED = ("FIX: gated model access missing. Three steps: (1) open "
             "https://huggingface.co/{model_id} and accept the license; "
             "(2) run `hf auth login` with a token of that account; (3) re-run "
             "(or pass an accessible mirror via --model-id).")


class ShieldGemma2Guard(GuardAdapter):
    name = "shieldgemma2"
    version = None  # set to the actual model id at load time
    modality = ["image"]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        config = config or {}
        self.model_id: str = config.get("model_id") or DEFAULT_MODEL_ID
        self.device_pref: str = config.get("device") or "auto"
        self.timeout_s: float = float(config.get("timeout_s") or DEFAULT_TIMEOUT_S)
        self.retries: int = int(config.get("retries") if config.get("retries") is not None else 1)
        self.threshold: float = float(config.get("threshold")
                                      if config.get("threshold") is not None else DEFAULT_THRESHOLD)
        self.hf_token: Optional[str] = config.get("hf_token")
        self.unknown_policy_count = 0  # run-level audit, read by main.py (AD-8)
        self._model = None
        self._processor = None
        self._device: Optional[str] = None
        self._policy_keys: List[str] = []
        self._mapping: Dict[str, List[str]] = load_category_mapping().get("shieldgemma2", {})

    @property
    def capabilities(self) -> Dict[str, Any]:
        return {
            "supports_batch": False,  # processor already batches the 3 policies per image
            "returns_confidence": True,
            "modalities": list(self.modality),
        }

    # ------------------------------------------------------------------ load
    def available(self) -> Tuple[bool, str]:
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401
            import PIL  # noqa: F401

            if not hasattr(torch, "no_grad"):
                raise ImportError("broken torch installation (namespace remnants)")
        except ImportError as exc:
            return False, f"missing/broken dependency: {exc}. {FIX_DEPS}"
        try:
            self._ensure_loaded()
        except Exception as exc:  # gated, network, OOM at load, ...
            message = str(exc)
            if any(marker in message for marker in ("gated", "401", "403")):
                return False, ("model is gated and this account has no access. "
                               + FIX_GATED.format(model_id=self.model_id))
            return False, f"model load failed: {type(exc).__name__}: {message[:300]}"
        return True, ""

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        import torch
        from transformers import (AutoProcessor, BitsAndBytesConfig,
                                  ShieldGemma2ForImageClassification)

        if self.device_pref == "auto":
            self._device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self._device = self.device_pref
        auth = {"token": self.hf_token} if self.hf_token else {}
        self._processor = AutoProcessor.from_pretrained(self.model_id, **auth)
        self._policy_keys = list(getattr(self._processor, "policy_definitions", {}) or {})
        if self._device == "cuda":
            # measured working baseline on 8GB VRAM (see module docstring)
            self._model = ShieldGemma2ForImageClassification.from_pretrained(
                self.model_id, quantization_config=BitsAndBytesConfig(load_in_8bit=True),
                device_map="cuda:0", **auth).eval()
            self._quant = "int8"
        else:
            self._model = ShieldGemma2ForImageClassification.from_pretrained(
                self.model_id, torch_dtype=torch.bfloat16,
                attn_implementation="eager", **auth).eval()
            self._quant = "none-bf16"
        self.version = self.model_id

    # ------------------------------------------------------------- inference
    def _forward_probs(self, image) -> List[Tuple[str, float]]:
        """One batched forward (all policies); returns [(policy_key, yes_prob)].

        Seam for offline tests: everything torch-side lives here.
        """
        import torch

        inputs = self._processor(images=[image], return_tensors="pt").to(self._device)
        holder: Dict[str, Any] = {}

        def worker():
            try:
                with torch.no_grad():
                    holder["out"] = self._model(**inputs)
            except Exception as exc:
                holder["error"] = exc

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        thread.join(self.timeout_s)
        if thread.is_alive():
            raise TimeoutError(f"soft timeout after {self.timeout_s}s (result discarded)")
        if "error" in holder:
            raise holder["error"]
        rows = holder["out"].probabilities.float().cpu().tolist()
        keys = self._policy_keys or [f"policy_{i}" for i in range(len(rows))]
        return [(key, float(row[0])) for key, row in zip(keys, rows)]

    def _load_image(self, record: Dict[str, Any]):
        from PIL import Image

        path = record.get("_resolved_image_path") or (first_image(record) or {}).get("path")
        if not path:
            raise FileNotFoundError("no resolvable image path on record")
        return Image.open(path).convert("RGB")

    def predict(self, record: Dict[str, Any]) -> Dict[str, Any]:
        self._ensure_loaded()
        start = time.perf_counter()
        try:
            image = self._load_image(record)
        except Exception as exc:
            return self.make_result(
                record, is_unsafe=None, device=self._device or "cpu",
                latency_ms=(time.perf_counter() - start) * 1000.0,
                error=f"image_decode_error: {type(exc).__name__}: {str(exc)[:200]}")

        last_error: Optional[Exception] = None
        for _attempt in range(self.retries + 1):
            try:
                scored = self._forward_probs(image)
                break
            except Exception as exc:
                last_error = exc
        else:
            return self.make_result(
                record, is_unsafe=None, device=self._device or "cpu",
                latency_ms=(time.perf_counter() - start) * 1000.0,
                error=(f"failed after {self.retries + 1} attempt(s): "
                       f"{type(last_error).__name__}: {last_error}"))

        if any(math.isnan(yes) for _key, yes in scored):
            return self.make_result(
                record, is_unsafe=None, device=self._device or "cpu",
                latency_ms=(time.perf_counter() - start) * 1000.0,
                raw_output={"policy_scores": {k: v for k, v in scored},
                            "quant": getattr(self, "_quant", None)},
                error=("nan_probabilities: quantized forward returned NaN "
                       "(known 4-bit failure shape; see references/shieldgemma2-notes.md)"))

        max_yes = max(yes for _key, yes in scored) if scored else 0.0
        is_unsafe = max_yes >= self.threshold
        categories: List[str] = []
        for key, yes in scored:
            if yes < self.threshold:
                continue
            mapped = self._mapping.get(key)
            if mapped is None:
                # never guess a mapping (M3_SPEC section 5); audited run-level
                self.unknown_policy_count += 1
                continue
            for category in mapped:
                if category not in categories:
                    categories.append(category)
        if is_unsafe and not categories:
            categories = ["general_harm"]  # unsafe with no mapped category (M0 section 4)
        if not is_unsafe:
            categories = []

        return self.make_result(
            record,
            is_unsafe=is_unsafe,
            risk_categories=categories,
            severity=None,
            confidence=max(0.0, min(1.0, max_yes)),
            raw_output={"policy_scores": {k: round(v, 6) for k, v in scored},
                        "policy_order": [k for k, _ in scored],
                        "threshold": self.threshold,
                        "quant": getattr(self, "_quant", None)},
            latency_ms=(time.perf_counter() - start) * 1000.0,
            device=self._device or "cpu",
        )
