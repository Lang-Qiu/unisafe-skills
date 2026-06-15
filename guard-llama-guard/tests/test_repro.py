"""W1 reproducibility: run_metadata.env carries model_revision + lib versions.

_probe_env is pure/offline (no weights, no network): revision is threaded in
from the loaded adapters by main.py; lib versions come from package metadata
(importlib.metadata, no heavy import). model_revision is the first non-null
revision among model guards; rule/llm-judge (no weights) stay null.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import main as main_module  # noqa: E402


class TestEnvReproducibility(unittest.TestCase):
    def test_revision_threaded_and_lib_versions(self):
        env = main_module._probe_env(["llama-guard"],
                                     {"llama-guard": "abc123", "rule": None})
        self.assertEqual(env["model_revision"], "abc123")
        self.assertEqual(env["model_revisions"], {"llama-guard": "abc123", "rule": None})
        self.assertIn("transformers", env["lib_versions"])  # probed when model guard requested

    def test_no_model_guard_means_null_revision_and_empty_libs(self):
        env = main_module._probe_env(["rule"], {"rule": None})
        self.assertIsNone(env["model_revision"])
        self.assertEqual(env["lib_versions"], {})

    def test_revisions_arg_is_optional_backward_compat(self):
        env = main_module._probe_env(["rule"])
        self.assertIsNone(env["model_revision"])
        self.assertEqual(env["model_revisions"], {})


class TestAdapterExposesRevision(unittest.TestCase):
    def test_llama_guard_has_revision_attr_default_none(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        from guards.llama_guard import LlamaGuard
        self.assertIsNone(LlamaGuard({}).model_revision)  # null until _ensure_loaded


if __name__ == "__main__":
    unittest.main()
