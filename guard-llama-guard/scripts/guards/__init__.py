"""Guard adapter registry with lazy imports.

Importing this package must never require third-party dependencies; each
adapter module is only imported when requested (so `get_adapter('rule')`
works on a clean stdlib-only environment even if torch is missing).
"""
from __future__ import annotations

import importlib
from typing import List

# name -> (module, class). llama-guard lands in task 11, openai in task 14.
_REGISTRY = {
    "rule": ("guards.rule_based", "RuleGuard"),
}


def known_guards() -> List[str]:
    return sorted(_REGISTRY)


def get_adapter(name: str):
    if name not in _REGISTRY:
        raise KeyError(
            f"unknown guard {name!r}; known guards: {', '.join(known_guards())}"
        )
    module_name, class_name = _REGISTRY[name]
    module = importlib.import_module(module_name)
    return getattr(module, class_name)()
