"""Llama Guard 3-1B adapter (Core-Full; local, gated: meta-llama/Llama-Guard-3-1B).

Official chat template, two input modes (schema.md §2):
  prompt_only_safety      -> single user turn (classify the user prompt)
  prompt_response_safety  -> user + assistant turns (classify the response)

Continuous score for AUROC: softmax over the {safe, unsafe} token logits at
the decision position of the generated output (single forward pass via
``generate(output_scores=True)``). Reliability gating (plan C7):

- ``validate_token_ids``: if "safe"/"unsafe" are not single tokens, the first
  sub-token is used and confidence is demoted to ``experimental``.
- logit-vs-generated label agreement is tracked across the run; < 99%
  agreement demotes ``confidence_status`` to ``experimental`` (AUROC then is
  not a headline result).

No wall-clock timeout for local inference (Windows cannot kill a CUDA op);
generation is bounded by small ``max_new_tokens`` and ``do_sample=False``.
Heavy deps (torch/transformers) are imported lazily inside ``load()``.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

if __package__ in (None, ""):  # direct-path run without install
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from guard_llama_guard.guards.base import Guard, GuardLoadError
from guard_llama_guard.utils import Route, load_config

MODEL_ID = "meta-llama/Llama-Guard-3-1B"


# ---- pure helpers (model-free, unit-tested) -------------------------------- #
def parse_output(text: str) -> Tuple[bool, List[str]]:
    """Parse Llama Guard generation: 'safe' or 'unsafe\\nS1,S2'."""
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    if not lines:
        raise ValueError("empty guard output")
    verdict = lines[0].lower()
    if verdict == "safe":
        return False, []
    if verdict == "unsafe":
        codes: List[str] = []
        if len(lines) > 1:
            codes = [c.strip().upper() for c in lines[1].split(",") if c.strip()]
        return True, codes
    raise ValueError(f"unparseable guard output: {text!r}")


def map_s_codes(codes: List[str]) -> List[str]:
    mapping = load_config()["llama_guard_s_to_canonical"]
    out: List[str] = []
    for code in codes:
        out.extend(mapping.get(code, ["other"]))
    return sorted(set(out))


def build_messages(route: Route) -> List[Dict[str, str]]:
    """Official conversation format; the chat template asks the model to
    classify the LAST turn — user turn for prompts, assistant turn for pairs."""
    messages = [{"role": "user", "content": route.prompt or ""}]
    if route.task_type == "prompt_response_safety" and route.response is not None:
        messages.append({"role": "assistant", "content": route.response})
    return messages


# ---- adapter ---------------------------------------------------------------- #
class LlamaGuard(Guard):
    name = "llama_guard"
    version = "3-1b"
    capabilities = {
        "refusal": False,            # Llama Guard does not emit refusal labels
        "continuous_score": True,
        "modalities": ["text"],
        "tasks": ["prompt_only_safety", "prompt_response_safety"],
    }
    model_id = MODEL_ID
    prompt_template_version = "llama-guard-3-official-chat-template-v1"
    confidence_method = "unsafe_token_softmax"

    def __init__(self, hf_token: Optional[str] = None, cache_dir: Optional[str] = None,
                 max_new_tokens: int = 20, batch_size: int = 8):
        self.hf_token = hf_token
        self.cache_dir = cache_dir
        self.max_new_tokens = max_new_tokens
        self.batch_size = batch_size
        self._tok = None
        self._model = None
        self._safe_ids: List[int] = []
        self._unsafe_ids: List[int] = []
        self._agree = 0
        self._compared = 0

    # -- loading ------------------------------------------------------------- #
    def load(self) -> None:
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as exc:
            raise GuardLoadError(
                f"missing dependency for {self.name}: {exc}. "
                "Install with: pip install -r requirements-llama.txt") from exc
        try:
            kwargs: Dict[str, Any] = {}
            if self.hf_token:
                kwargs["token"] = self.hf_token
            if self.cache_dir:
                kwargs["cache_dir"] = self.cache_dir
            self._tok = AutoTokenizer.from_pretrained(MODEL_ID, **kwargs)
            use_cuda = torch.cuda.is_available()
            self._model = AutoModelForCausalLM.from_pretrained(
                MODEL_ID,
                torch_dtype=torch.bfloat16 if use_cuda else torch.float32,
                device_map="auto" if use_cuda else None,
                **kwargs)
            self._model.eval()
            self.device = "cuda" if use_cuda else "cpu"
        except Exception as exc:
            raise GuardLoadError(f"cannot load {MODEL_ID}: {exc}") from exc
        self.model_revision = getattr(self._model.config, "_commit_hash", None)
        self._validate_token_ids()
        self.confidence_status = "validated"  # may be demoted below / at runtime

    def _validate_token_ids(self) -> None:
        """Single-token check for 'safe'/'unsafe' (plan C7). Multi-token ->
        use the first sub-token and demote confidence to experimental."""
        self._safe_ids = self._tok.encode("safe", add_special_tokens=False)
        self._unsafe_ids = self._tok.encode("unsafe", add_special_tokens=False)
        if len(self._safe_ids) != 1 or len(self._unsafe_ids) != 1:
            self.confidence_method = "unsafe_token_softmax_first_subtoken_experimental"
            self.confidence_status = "experimental"

    # -- runtime reliability tracking ----------------------------------------- #
    @property
    def logit_label_agreement(self) -> Optional[float]:
        return self._agree / self._compared if self._compared else None

    def _track_agreement(self, generated_unsafe: bool, p_unsafe: Optional[float]) -> None:
        if p_unsafe is None:
            return
        self._compared += 1
        if (p_unsafe > 0.5) == generated_unsafe:
            self._agree += 1
        agreement = self._agree / self._compared
        if self._compared >= 5 and agreement < 0.99 and self.confidence_status == "validated":
            self.confidence_status = "experimental"

    # -- inference ------------------------------------------------------------ #
    def _generate(self, routes: List[Route]):
        import torch

        tok, model = self._tok, self._model
        prompts = [tok.apply_chat_template(build_messages(rt), tokenize=False)
                   for rt in routes]
        if tok.pad_token_id is None:
            tok.pad_token = tok.eos_token
        enc = tok(prompts, return_tensors="pt", padding=True).to(model.device)
        with torch.no_grad():
            out = model.generate(
                **enc, max_new_tokens=self.max_new_tokens, do_sample=False,
                output_scores=True, return_dict_in_generate=True,
                pad_token_id=tok.pad_token_id)
        gen_ids = out.sequences[:, enc["input_ids"].shape[1]:]
        results = []
        safe_id, unsafe_id = self._safe_ids[0], self._unsafe_ids[0]
        for b in range(gen_ids.shape[0]):
            text = tok.decode(gen_ids[b], skip_special_tokens=True)
            p_unsafe = None
            for step in range(min(len(out.scores), gen_ids.shape[1])):
                tok_id = int(gen_ids[b, step])
                if tok_id in (safe_id, unsafe_id):
                    pair = torch.tensor([out.scores[step][b, safe_id],
                                         out.scores[step][b, unsafe_id]])
                    p_unsafe = float(torch.softmax(pair.float(), dim=0)[1])
                    break
            results.append((text, p_unsafe))
        return results

    def _predict_from_generation(self, text: str, p_unsafe: Optional[float]):
        is_unsafe, codes = parse_output(text)
        self._track_agreement(is_unsafe, p_unsafe)
        prediction = {
            "is_unsafe": is_unsafe,
            "risk_categories": map_s_codes(codes) if is_unsafe else [],
            "confidence": p_unsafe,
            "confidence_method": self.confidence_method,
        }
        raw = {"model_response": text, "s_codes": codes, "unsafe_token_prob": p_unsafe}
        return prediction, raw

    def _predict_one(self, route: Route):
        text, p_unsafe = self._generate([route])[0]
        return self._predict_from_generation(text, p_unsafe)

    def predict_batch(self, routes: List[Route]) -> List[Dict[str, Any]]:
        """True batching in chunks of ``batch_size`` (P2.D ablation seam);
        falls back to per-record predict() for a failed chunk so one bad
        record cannot poison its neighbours."""
        rows: List[Dict[str, Any]] = []
        for i in range(0, len(routes), self.batch_size):
            chunk = routes[i:i + self.batch_size]
            try:
                generations = self._generate(chunk)
            except Exception:  # noqa: BLE001 — chunk-level fallback
                rows.extend(self.predict(rt) for rt in chunk)
                continue
            for rt, (text, p_unsafe) in zip(chunk, generations):
                import time
                start = time.perf_counter()
                try:
                    prediction, raw = self._predict_from_generation(text, p_unsafe)
                    error = None
                except Exception as exc:  # noqa: BLE001
                    prediction, raw, error = {}, {"model_response": text}, \
                        f"{type(exc).__name__}: {exc}"
                from guard_llama_guard.utils import build_guard_output
                rows.append(build_guard_output(
                    record_id=rt.record_id, guard_name=self.name,
                    guard_version=self.version,
                    modalities=self.capabilities["modalities"],
                    prediction=prediction, raw_output=raw,
                    latency_ms=int((time.perf_counter() - start) * 1000),
                    device=self.device, error=error))
        return rows


def _self_test() -> int:
    """Integration self-test (needs GPU/CPU + gated access + deps installed)."""
    from guard_llama_guard.utils import SKILL_DIR, load_valid_records, route

    guard = LlamaGuard()
    try:
        guard.load()
    except GuardLoadError as exc:
        print(f"LOAD FAILED (expected without deps/token): {exc}")
        return 2
    print(f"loaded {MODEL_ID} rev={guard.model_revision} device={guard.device}")
    print(f"token ids: safe={guard._safe_ids} unsafe={guard._unsafe_ids} "
          f"status={guard.confidence_status}")
    records, _ = load_valid_records(SKILL_DIR / "examples" / "tiny_unified.jsonl")
    routes = [rt for rt in (route(r, guard.capabilities) for r in records) if rt]
    for row in guard.predict_batch(routes):
        p = row["prediction"]
        print(f"{row['id']}: is_unsafe={p['is_unsafe']} conf={p['confidence']} "
              f"cats={p['risk_categories']} err={row['error']}")
    print(f"logit_label_agreement={guard.logit_label_agreement} "
          f"confidence_status={guard.confidence_status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test())
