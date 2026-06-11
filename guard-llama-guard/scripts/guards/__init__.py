"""Guard adapter registry with lazy imports.

Importing this package must never require third-party dependencies; each
adapter module is only imported when requested (so `get_adapter('rule')`
works on a clean stdlib-only environment even if torch is missing).
"""
from __future__ import annotations

import importlib
from typing import List

_REGISTRY = {
    "rule": ("guards.rule_based", "RuleGuard"),
    "llama-guard": ("guards.llama_guard", "LlamaGuard"),
    "openai": ("guards.openai_moderation", "OpenAIModerationGuard"),
    "llm-judge": ("guards.llm_judge", "LLMJudgeGuard"),
}


def known_guards() -> List[str]:
    return sorted(_REGISTRY)


def get_adapter(name: str, config=None):
    """config: CLI-derived dict (device/timeout_s/retries/model_id/hf_token...);
    adapters take what they need and ignore the rest."""
    if name not in _REGISTRY:
        raise KeyError(
            f"unknown guard {name!r}; known guards: {', '.join(known_guards())}"
        )
    module_name, class_name = _REGISTRY[name]
    module = importlib.import_module(module_name)
    return getattr(module, class_name)(config)
