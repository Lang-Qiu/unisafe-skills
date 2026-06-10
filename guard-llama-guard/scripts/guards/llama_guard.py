"""Llama Guard 3-1B adapter (Core-Full). Lazy-imports torch/transformers.

Method notes + spike findings: references/llama-guard-notes.md.

Key decisions (documented there):
  - available() performs the full tokenizer+model load: gated 401/403 and
    missing deps are guard-level failures with an actionable FIX hint, never
    record-level errors.
  - confidence = two-way normalized first-verdict-token probability:
    p(unsafe) / (p(unsafe) + p(safe)) at the generation step whose argmax is
    the safe/unsafe token (robust if the verdict word ever splits or shifts).
  - soft timeout: generation runs in a watchdog thread; CUDA steps cannot be
    interrupted, so on timeout the eventual result is discarded and the
    record gets an error row (--timeout-s is a soft bound, SKILL.md says so).
"""
from __future__ import annotations

import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from guards.base import GuardAdapter
from utils import load_category_mapping

DEFAULT_MODEL_ID = "meta-llama/Llama-Guard-3-1B"
MAX_NEW_TOKENS = 24
S_CODE_PATTERN = re.compile(r"S(\d{1,2})")

FIX_GATED = (
    "FIX: gated model access missing. Three steps: (1) open "
    "https://huggingface.co/{model_id} and accept the license; "
    "(2) run `hf auth login` with a token of that account; (3) re-run."
)
FIX_DEPS = "FIX: pip install -r requirements-llama.txt (torch/transformers are not installed)"


class LlamaGuard(GuardAdapter):
    name = "llama-guard"
    version = "3-1b"
    modality = ["text"]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        config = config or {}
        self.model_id: str = config.get("model_id") or DEFAULT_MODEL_ID
        self.device_pref: str = config.get("device") or "auto"
        self.timeout_s: float = float(config.get("timeout_s") or 30.0)
        self.retries: int = int(config.get("retries") if config.get("retries") is not None else 1)
        self.hf_token: Optional[str] = config.get("hf_token")
        self._tokenizer = None
        self._model = None
        self._device: Optional[str] = None
        self._verdict_ids: Optional[Tuple[int, int]] = None  # (safe_id, unsafe_id)
        self._mapping = load_category_mapping().get("llama_guard", {})

    @property
    def capabilities(self) -> Dict[str, Any]:
        return {
            "supports_batch": True,
            "returns_confidence": True,
            "modalities": list(self.modality),
        }

    # ------------------------------------------------------------------ load
    def available(self) -> Tuple[bool, str]:
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401

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
        from transformers import AutoModelForCausalLM, AutoTokenizer

        if self.device_pref == "auto":
            self._device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self._device = self.device_pref
        dtype = torch.bfloat16 if self._device == "cuda" else torch.float32
        auth = {"token": self.hf_token} if self.hf_token else {}
        self._tokenizer = AutoTokenizer.from_pretrained(self.model_id, **auth)
        if self._tokenizer.pad_token_id is None:
            self._tokenizer.pad_token = self._tokenizer.eos_token
        self._tokenizer.padding_side = "left"  # decoder-only generation
        self._model = AutoModelForCausalLM.from_pretrained(
            self.model_id, torch_dtype=dtype, **auth
        ).to(self._device).eval()

        def first_id(word: str) -> int:
            ids = self._tokenizer.encode(word, add_special_tokens=False)
            return ids[0]  # spike: single token in the Llama 3 tokenizer

        self._verdict_ids = (first_id("safe"), first_id("unsafe"))

    # ------------------------------------------------------------- inference
    def _conversation(self, record: Dict[str, Any]) -> List[Dict[str, Any]]:
        content = record.get("content") or {}
        conversation = [{"role": "user",
                         "content": [{"type": "text", "text": content.get("prompt") or ""}]}]
        response = content.get("response")
        if isinstance(response, str) and response.strip():
            conversation.append({"role": "assistant",
                                 "content": [{"type": "text", "text": response}]})
        return conversation

    def _encode_batch(self, records: List[Dict[str, Any]]):
        texts = []
        for record in records:
            try:
                text = self._tokenizer.apply_chat_template(
                    self._conversation(record), tokenize=False
                )
            except Exception:
                # fallback for templates that want plain-string content
                conv = [{"role": m["role"], "content": m["content"][0]["text"]}
                        for m in self._conversation(record)]
                text = self._tokenizer.apply_chat_template(conv, tokenize=False)
            texts.append(text)
        return self._tokenizer(texts, return_tensors="pt", padding=True,
                               add_special_tokens=False).to(self._device)

    def _generate(self, encoded) -> Tuple[Any, Any]:
        import torch

        with torch.no_grad():
            out = self._model.generate(
                **encoded,
                max_new_tokens=MAX_NEW_TOKENS,
                do_sample=False,
                temperature=None,
                top_p=None,
                return_dict_in_generate=True,
                output_scores=True,
                pad_token_id=self._tokenizer.pad_token_id,
            )
        return out.sequences[:, encoded["input_ids"].shape[1]:], out.scores

    def _generate_with_watchdog(self, encoded):
        """Soft timeout: join the worker; a late CUDA result is discarded."""
        holder: Dict[str, Any] = {}

        def worker():
            try:
                holder["result"] = self._generate(encoded)
            except Exception as exc:
                holder["error"] = exc

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        thread.join(self.timeout_s)
        if thread.is_alive():
            raise TimeoutError(f"soft timeout after {self.timeout_s}s (result discarded)")
        if "error" in holder:
            raise holder["error"]
        return holder["result"]

    def _parse_one(self, token_ids, scores, batch_index: int, latency_ms: float,
                   record: Dict[str, Any]) -> Dict[str, Any]:
        import torch

        text = self._tokenizer.decode(token_ids, skip_special_tokens=True).strip()
        if not text:
            return self.make_result(record, is_unsafe=None, device=self._device,
                                    latency_ms=latency_ms,
                                    raw_output={"model_response": text},
                                    error="empty model output")
        lowered = text.lower()
        if "unsafe" in lowered:
            is_unsafe = True
        elif "safe" in lowered:
            is_unsafe = False
        else:
            return self.make_result(record, is_unsafe=None, device=self._device,
                                    latency_ms=latency_ms,
                                    raw_output={"model_response": text},
                                    error=f"unparseable verdict: {text[:80]!r}")

        safe_id, unsafe_id = self._verdict_ids
        confidence = None
        for step, step_scores in enumerate(scores):
            if step >= token_ids.shape[0]:
                break
            argmax_id = int(token_ids[step])
            if argmax_id in (safe_id, unsafe_id):
                probs = torch.softmax(step_scores[batch_index].float(), dim=-1)
                p_safe = float(probs[safe_id])
                p_unsafe = float(probs[unsafe_id])
                if p_safe + p_unsafe > 0:
                    confidence = p_unsafe / (p_safe + p_unsafe)
                break

        categories: List[str] = []
        for number in S_CODE_PATTERN.findall(text):
            for mapped in self._mapping.get(f"S{int(number)}", ["other"]):
                if mapped not in categories:
                    categories.append(mapped)
        if is_unsafe and not categories:
            categories = ["general_harm"]  # unsafe with no category -> fallback (M0 section 4)
        if not is_unsafe:
            categories = []

        return self.make_result(
            record,
            is_unsafe=is_unsafe,
            risk_categories=categories,
            severity=None,
            confidence=confidence,
            raw_output={"label": "unsafe" if is_unsafe else "safe",
                        "model_response": text,
                        "unsafe_token_prob": confidence},
            latency_ms=latency_ms,
            device=self._device or "cpu",
        )

    def _predict_chunk(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        start = time.perf_counter()
        last_error: Optional[Exception] = None
        for _attempt in range(self.retries + 1):
            try:
                encoded = self._encode_batch(records)
                generated, scores = self._generate_with_watchdog(encoded)
                latency_ms = (time.perf_counter() - start) * 1000.0 / max(len(records), 1)
                return [
                    self._parse_one(generated[i], scores, i, latency_ms, record)
                    for i, record in enumerate(records)
                ]
            except Exception as exc:
                last_error = exc
        reason = f"{type(last_error).__name__}: {last_error}"
        return [
            self.make_result(record, is_unsafe=None, device=self._device or "cpu",
                             latency_ms=(time.perf_counter() - start) * 1000.0,
                             error=f"failed after {self.retries + 1} attempt(s): {reason}")
            for record in records
        ]

    def predict(self, record: Dict[str, Any]) -> Dict[str, Any]:
        self._ensure_loaded()
        return self._predict_chunk([record])[0]

    def predict_batch(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        self._ensure_loaded()
        return self._predict_chunk(records)
