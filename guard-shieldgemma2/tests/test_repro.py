"""W1 reproducibility (sg2 edition): run_metadata.env carries model_revision +
lib versions. Controlled-copy sibling of guard-llama-guard/tests/test_repro.py;
the model guard here is `shieldgemma2`, baseline `caption-rule` has no weights.
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
        env = main_module._probe_env(["shieldgemma2"],
                                     {"shieldgemma2": "deadbeef", "caption-rule": None})
        self.assertEqual(env["model_revision"], "deadbeef")
        self.assertEqual(env["model_revisions"],
                         {"shieldgemma2": "deadbeef", "caption-rule": None})
        self.assertIn("transformers", env["lib_versions"])

    def test_no_model_guard_means_null_revision_and_empty_libs(self):
        env = main_module._probe_env(["caption-rule"], {"caption-rule": None})
        self.assertIsNone(env["model_revision"])
        self.assertEqual(env["lib_versions"], {})

    def test_revisions_arg_is_optional_backward_compat(self):
        env = main_module._probe_env(["caption-rule"])
        self.assertIsNone(env["model_revision"])
        self.assertEqual(env["model_revisions"], {})


class TestAdapterExposesRevision(unittest.TestCase):
    def test_shieldgemma2_has_revision_attr_default_none(self):
        from guards.shieldgemma2 import ShieldGemma2Guard
        self.assertIsNone(ShieldGemma2Guard({}).model_revision)


if __name__ == "__main__":
    unittest.main()
