"""Guard adapter registry with lazy imports.

Derived from guard-llama-guard@8fa8fedcafb5b788bbdac0923ac07514e150d52f
scripts/guards/__init__.py. Image adaptation: registry entries only —
caption-rule (zero-dep pipeline baseline) + shieldgemma2 (Core-Full).

Importing this package must never require third-party dependencies; each
adapter module is only imported when requested (so `get_adapter('caption-rule')`
works on a clean stdlib-only environment even if torch is missing).
"""
from __future__ import annotations

import importlib
from typing import List

_REGISTRY = {
    "caption-rule": ("guards.caption_rule", "CaptionRuleGuard"),
    "shieldgemma2": ("guards.shieldgemma2", "ShieldGemma2Guard"),
}


def known_guards() -> List[str]:
    return sorted(_REGISTRY)


def get_adapter(name: str, config=None):
    """config: CLI-derived dict (device/timeout_s/threshold/model_id/hf_token...);
    adapters take what they need and ignore the rest."""
    if name not in _REGISTRY:
        raise KeyError(
            f"unknown guard {name!r}; known guards: {', '.join(known_guards())}"
        )
    module_name, class_name = _REGISTRY[name]
    module = importlib.import_module(module_name)
    return getattr(module, class_name)(config)
