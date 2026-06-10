"""Rule-keyword baseline guard (pure stdlib, no downloads, no keys).

The Core-Minimal tracer bullet: crude lowercase substring matching against
config/category_mapping.json ``rule_keyword_map``. Deliberately includes
homonym-prone keywords so the baseline demonstrates keyword over-flagging
on safe probes (unsafe_fpr_on_safe_probe).

No continuous score by default (AUROC honestly N/A). ``score_mode=True``
(CLI: --rule-score) opts into a PSEUDO score — saturating keyword-hit count
k/(k+2) — labeled ``rule_keyword_score_experimental``: it is a ranking
heuristic, NOT a probability, and is excluded from headline AUROC.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

if __package__ in (None, ""):  # direct-path run without install
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from guard_llama_guard.guards.base import Guard, GuardLoadError
from guard_llama_guard.utils import Route, load_config


class RuleGuard(Guard):
    name = "rule"
    version = "0.1.0"
    device = "cpu"
    capabilities = {
        "refusal": False,           # keyword matching cannot detect refusals
        "continuous_score": False,  # pseudo score is experimental opt-in only
        "modalities": ["text"],
        "tasks": ["prompt_only_safety", "prompt_response_safety"],
    }
    prompt_template_version = "rule-v1"

    def __init__(self, score_mode: bool = False):
        self.score_mode = score_mode
        self._keyword_map: Dict[str, List[str]] = {}

    def load(self) -> None:
        try:
            cfg = load_config()
            self._keyword_map = {
                cat: [kw.lower() for kw in kws]
                for cat, kws in cfg["rule_keyword_map"].items()
            }
        except Exception as exc:
            raise GuardLoadError(f"cannot load rule_keyword_map: {exc}") from exc
        if self.score_mode:
            self.confidence_method = "rule_keyword_score_experimental"
            self.confidence_status = "experimental"

    def _predict_one(self, route: Route) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        # Crude by design: pairs are scanned as prompt+response concatenation,
        # so an unsafe-looking prompt can flag a safely-refused pair (a known,
        # documented weakness of keyword baselines).
        text = " ".join(t for t in (route.prompt, route.response) if t).lower()
        matched: Dict[str, List[str]] = {}
        for cat, keywords in self._keyword_map.items():
            hits = [kw for kw in keywords if kw in text]
            if hits:
                matched[cat] = hits
        is_unsafe = bool(matched)
        prediction: Dict[str, Any] = {
            "is_unsafe": is_unsafe,
            "risk_categories": sorted(matched),
            "confidence": None,
        }
        if self.score_mode:
            k = sum(len(hits) for hits in matched.values())
            prediction["confidence"] = k / (k + 2)
            prediction["confidence_method"] = self.confidence_method
        return prediction, {"matched_keywords": matched}


def _self_test() -> int:
    from guard_llama_guard.utils import SKILL_DIR, load_valid_records, route

    guard = RuleGuard()
    guard.load()
    records, _ = load_valid_records(SKILL_DIR / "examples" / "tiny_unified.jsonl")
    ok = True
    for rec in records:
        rt = route(rec, guard.capabilities)
        if rt is None:
            print(f"{rec['id']}: out_of_scope")
            continue
        row = guard.predict(rt)
        pred = row["prediction"]
        print(f"{rec['id']}: is_unsafe={pred['is_unsafe']} cats={pred['risk_categories']} "
              f"truth={rec['label']['is_unsafe']}")
        ok = ok and row["error"] is None
    print("SELF-TEST:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(_self_test())
