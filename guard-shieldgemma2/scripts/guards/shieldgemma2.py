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
  - is_unsafe = max(yes_p) >= threshold (default 0.30 = M3.6 E1 int8 recall@FPR<=0.1
    calibration, references/calibration-notes.md; 0.5 = old model-card default);
    confidence = max(yes_p) (unsafe-direction, native [0,1]);
  - risk_categories = mapped policies with yes_p >= threshold (M0 section 4 via
    references/category_mapping.json 'shieldgemma2', which carries both the M0
    display names and the discovery-verified runtime keys);
  - unmapped policy names are NEVER guessed: unknown_policy_count is a
    NAME-LEVEL audit — the count of distinct unmapped policy names seen this
    run, threshold-independent (surfaced as
    run_metadata.warnings.unknown_policy_count, plan AD-8); the raw scores stay
    in raw_output.policy_scores on every row; unsafe with no mapped category
    falls back to general_harm (M0 section 4);
  - NaN probabilities -> record-level error row (defensive: the 4-bit failure
    shape observed in task 4) UNLESS nan_fallback is enabled (M3.7 E3): on int8
    NaN, re-score that single image with a non-quantized fallback model
    (auto=fp16-GPU then CPU bf16, or gpu/cpu); recovered rows carry
    raw_output.quant="int8->{gpu-fp16|cpu-bf16}" + prediction.warnings
    ["nan_fallback_recovered"]; nan_fallback="none" (default) preserves the old
    error-row behavior exactly. NOTE the recovered score is bf16/fp16 under the
    int8-calibrated 0.30 threshold (same [0,1] yes-prob space, better-ranked) —
    E3 recovers COVERAGE, it does not fix the int8 quality drift (notes §6.1a);
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
DEFAULT_THRESHOLD = 0.30  # M3.6 E1: int8 recall@FPR<=0.1 calibration point
# (references/calibration-notes.md; was 0.5 model-card default). Override via
# --threshold / config["threshold"]; 0.5 reproduces the old behavior.

FIX_DEPS = ("FIX: install the torch build that matches your CUDA/CPU first "
            "(see https://pytorch.org/get-started/locally/), then run "
            "`pip install -r requirements-shieldgemma.txt` for transformers/"
            "accelerate/bitsandbytes/pillow. torch is intentionally not pinned "
            "in that file.")
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
        # M3.7 E3: per-record NaN fallback precision. none(default)|auto|gpu|cpu.
        self.nan_fallback: str = config.get("nan_fallback") or "none"
        self.model_revision: Optional[str] = None  # W1: resolved commit hash after load
        self._unknown_policy_names: set = set()  # name-level audit backing store
        self._nan_fallback_recovered: int = 0  # E3: count of int8-NaN rows recovered
        self._fallback_models: Dict[str, Any] = {}  # E3: lazily-loaded fallback models
        self._model = None
        self._processor = None
        self._device: Optional[str] = None
        self._policy_keys: List[str] = []
        self._mapping: Dict[str, List[str]] = load_category_mapping().get("shieldgemma2", {})

    @property
    def unknown_policy_count(self) -> int:
        """Distinct unmapped policy names seen this run (name-level audit, AD-8;
        threshold-independent — read by main.py into run_metadata.warnings)."""
        return len(self._unknown_policy_names)

    @property
    def nan_fallback_recovered(self) -> int:
        """E3: count of int8-NaN rows recovered via the non-quantized fallback
        this run — read by main.py into run_metadata.warnings (mirrors
        unknown_policy_count)."""
        return self._nan_fallback_recovered

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
        # W1: resolved revision from the cached config (offline-friendly, no network)
        self.model_revision = getattr(self._model.config, "_commit_hash", None)

    # ------------------------------------------------------------- inference
    def _run_forward(self, model, inputs):
        """Threaded forward with soft timeout; returns the model output or raises.

        CUDA steps cannot be interrupted — a late result is discarded (TimeoutError).
        """
        import torch

        holder: Dict[str, Any] = {}

        def worker():
            try:
                with torch.no_grad():
                    holder["out"] = model(**inputs)
            except Exception as exc:
                holder["error"] = exc

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        thread.join(self.timeout_s)
        if thread.is_alive():
            raise TimeoutError(f"soft timeout after {self.timeout_s}s (result discarded)")
        if "error" in holder:
            raise holder["error"]
        return holder["out"]

    def _probs_from_output(self, out) -> List[Tuple[str, float]]:
        rows = out.probabilities.float().cpu().tolist()
        keys = self._policy_keys or [f"policy_{i}" for i in range(len(rows))]
        return [(key, float(row[0])) for key, row in zip(keys, rows)]

    def _forward_probs(self, image) -> List[Tuple[str, float]]:
        """One batched forward on the primary (int8) model; [(policy_key, yes_prob)].

        Seam for offline tests: everything torch-side lives here.
        """
        inputs = self._processor(images=[image], return_tensors="pt").to(self._device)
        return self._probs_from_output(self._run_forward(self._model, inputs))

    def _ensure_fallback_loaded(self, mode: str) -> Tuple[Any, str]:
        """E3: lazily load a non-quantized fallback model. gpu=fp16 on cuda:0,
        cpu=bf16 on cpu (reuses the clean CPU baseline). Cached per mode."""
        if mode in self._fallback_models:
            return self._fallback_models[mode]
        import torch
        from transformers import ShieldGemma2ForImageClassification

        auth = {"token": self.hf_token} if self.hf_token else {}
        if mode == "gpu":
            model = ShieldGemma2ForImageClassification.from_pretrained(
                self.model_id, torch_dtype=torch.float16,
                device_map="cuda:0", **auth).eval()
            device = "cuda:0"
        else:  # cpu bf16, no quantization (the §6.1a truth reference)
            model = ShieldGemma2ForImageClassification.from_pretrained(
                self.model_id, torch_dtype=torch.bfloat16,
                attn_implementation="eager", **auth).eval()
            device = "cpu"
        self._fallback_models[mode] = (model, device)
        return model, device

    def _fallback_forward(self, image, mode: str) -> List[Tuple[str, float]]:
        """E3: re-score one image on a non-quantized fallback model. Torch seam."""
        model, device = self._ensure_fallback_loaded(mode)
        inputs = self._processor(images=[image], return_tensors="pt").to(device)
        return self._probs_from_output(self._run_forward(model, inputs))

    def _attempt_fallback(self, image):
        """E3: first mode that yields a non-NaN score wins. Returns (scored, via)
        or None. auto = fp16-GPU then CPU bf16 (covers CUDA OOM and gpu-NaN)."""
        plan = {"auto": (("gpu", "gpu-fp16"), ("cpu", "cpu-bf16")),
                "gpu": (("gpu", "gpu-fp16"),),
                "cpu": (("cpu", "cpu-bf16"),)}.get(self.nan_fallback, ())
        for mode, via in plan:
            try:
                scored = self._fallback_forward(image, mode)
            except Exception:
                continue  # OOM / load failure / timeout -> next mode
            if scored and not any(math.isnan(yes) for _key, yes in scored):
                return scored, via
        return None

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

        recovered_via: Optional[str] = None
        if any(math.isnan(yes) for _key, yes in scored):
            fb = self._attempt_fallback(image) if self.nan_fallback != "none" else None
            if fb is None:
                extra = ("" if self.nan_fallback == "none"
                         else f"; nan_fallback={self.nan_fallback} did not recover")
                return self.make_result(
                    record, is_unsafe=None, device=self._device or "cpu",
                    latency_ms=(time.perf_counter() - start) * 1000.0,
                    raw_output={"policy_scores": {k: v for k, v in scored},
                                "quant": getattr(self, "_quant", None)},
                    error=("nan_probabilities: quantized forward returned NaN "
                           "(known 4-bit failure shape; see references/shieldgemma2-notes.md)"
                           + extra))
            scored, recovered_via = fb  # E3: recovered on a non-quantized model
            self._nan_fallback_recovered += 1

        quant_tag = f"int8->{recovered_via}" if recovered_via else getattr(self, "_quant", None)
        max_yes = max(yes for _key, yes in scored) if scored else 0.0
        is_unsafe = max_yes >= self.threshold
        categories: List[str] = []
        for key, yes in scored:
            if key not in self._mapping:
                # never guess a mapping (M3_SPEC section 5); name-level audit,
                # threshold-independent — an unknown name is a model property
                self._unknown_policy_names.add(key)
                continue
            if yes < self.threshold:
                continue
            for category in self._mapping[key]:
                if category not in categories:
                    categories.append(category)
        if is_unsafe and not categories:
            categories = ["general_harm"]  # unsafe with no mapped category (M0 section 4)
        if not is_unsafe:
            categories = []

        result = self.make_result(
            record,
            is_unsafe=is_unsafe,
            risk_categories=categories,
            severity=None,
            confidence=max(0.0, min(1.0, max_yes)),
            raw_output={"policy_scores": {k: round(v, 6) for k, v in scored},
                        "policy_order": [k for k, _ in scored],
                        "threshold": self.threshold,
                        "quant": quant_tag},
            latency_ms=(time.perf_counter() - start) * 1000.0,
            device=self._device or "cpu",
        )
        if recovered_via:  # E3: surface the recovery on the row (mirrors main.py warning landing)
            result["prediction"].setdefault("warnings", []).append("nan_fallback_recovered")
        return result
