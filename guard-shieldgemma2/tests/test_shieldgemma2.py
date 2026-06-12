"""shieldgemma2 adapter, offline (task 12; M3_SPEC sections 5/6-D).

Mock shapes follow the task-4 discovery facts verbatim: runtime policy keys
['dangerous', 'sexual', 'violence'], probabilities rows are (yes, no) per
policy. All torch-side work lives behind ShieldGemma2Guard._forward_probs /
_ensure_loaded / _load_image, so these tests never touch GPU/network/weights.
Live tests are opt-in via SHIELDGEMMA2_LIVE=1 (task 13).
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import main as main_module  # noqa: E402
from guards import get_adapter, known_guards  # noqa: E402
from guards.shieldgemma2 import ShieldGemma2Guard  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "pipeline_dataset.jsonl"


def _record():
    return {"id": "synthimg:test:000001", "task_type": "image_safety",
            "modality": ["image"],
            "content": {"images": [{"path": "images/benign_blue.png", "url": None,
                                    "caption": None, "ocr": None}]},
            "_resolved_image_path": str(ROOT / "tests" / "fixtures" / "images" / "benign_blue.png")}


def _patched_guard(scored, threshold=None):
    """Guard with the torch seams stubbed: returns (guard, predict_result)."""
    config = {} if threshold is None else {"threshold": threshold}
    guard = ShieldGemma2Guard(config)
    with mock.patch.object(ShieldGemma2Guard, "_ensure_loaded", lambda self: None), \
         mock.patch.object(ShieldGemma2Guard, "_load_image", lambda self, record: object()), \
         mock.patch.object(ShieldGemma2Guard, "_forward_probs", lambda self, image: list(scored)):
        result = guard.predict(_record())
    return guard, result


class TestRegistryAndConfig(unittest.TestCase):
    def test_registered(self):
        self.assertIn("shieldgemma2", known_guards())
        adapter = get_adapter("shieldgemma2", {"threshold": 0.7, "timeout_s": None})
        self.assertIsInstance(adapter, ShieldGemma2Guard)
        self.assertEqual(adapter.threshold, 0.7)
        self.assertEqual(adapter.timeout_s, 120.0)  # None sentinel -> adapter default

    def test_explicit_timeout_overrides_default(self):
        adapter = ShieldGemma2Guard({"timeout_s": 30})
        self.assertEqual(adapter.timeout_s, 30.0)


class TestVerdicts(unittest.TestCase):
    def test_single_policy_over_threshold(self):
        _, result = _patched_guard([("dangerous", 0.2), ("sexual", 0.1), ("violence", 0.9)])
        self.assertIs(result["prediction"]["is_unsafe"], True)
        self.assertEqual(result["prediction"]["risk_categories"], ["violence"])
        self.assertAlmostEqual(result["prediction"]["confidence"], 0.9)
        self.assertEqual(result["raw_output"]["policy_order"],
                         ["dangerous", "sexual", "violence"])

    def test_all_under_threshold_is_safe(self):
        _, result = _patched_guard([("dangerous", 0.3), ("sexual", 0.1), ("violence", 0.2)])
        self.assertIs(result["prediction"]["is_unsafe"], False)
        self.assertEqual(result["prediction"]["risk_categories"], [])
        self.assertAlmostEqual(result["prediction"]["confidence"], 0.3)  # unsafe-direction max

    def test_multiple_policies_fire(self):
        _, result = _patched_guard([("dangerous", 0.1), ("sexual", 0.7), ("violence", 0.8)])
        self.assertIs(result["prediction"]["is_unsafe"], True)
        self.assertEqual(result["prediction"]["risk_categories"],
                         ["sexual_content", "violence"])  # policy order preserved

    def test_display_name_keys_also_map(self):
        # both key families live in category_mapping.json (M0 names + runtime keys)
        _, result = _patched_guard([("Dangerous Content", 0.9)])
        self.assertEqual(result["prediction"]["risk_categories"], ["general_harm"])

    def test_threshold_config_respected(self):
        _, result = _patched_guard([("violence", 0.9)], threshold=0.95)
        self.assertIs(result["prediction"]["is_unsafe"], False)

    def test_unknown_policy_audited_not_guessed(self):
        guard, result = _patched_guard([("alien_policy", 0.9), ("violence", 0.2)])
        self.assertIs(result["prediction"]["is_unsafe"], True)  # binary verdict from max yes
        # no guessed mapping; unsafe with no mapped category -> general_harm fallback
        self.assertEqual(result["prediction"]["risk_categories"], ["general_harm"])
        self.assertEqual(guard.unknown_policy_count, 1)

    def test_nan_probabilities_become_error_row(self):
        _, result = _patched_guard([("dangerous", float("nan")), ("violence", 0.1)])
        self.assertIsNone(result["prediction"]["is_unsafe"])
        self.assertTrue(result["error"].startswith("nan_probabilities"))

    def test_unreadable_image_is_decode_error(self):
        guard = ShieldGemma2Guard({})
        record = _record()
        record["_resolved_image_path"] = str(ROOT / "tests" / "fixtures" / "images" / "bad_magic.png")
        with mock.patch.object(ShieldGemma2Guard, "_ensure_loaded", lambda self: None):
            result = guard.predict(record)
        self.assertIsNone(result["prediction"]["is_unsafe"])
        self.assertTrue(result["error"].startswith("image_decode_error"))


class TestAvailability(unittest.TestCase):
    def test_missing_deps_unavailable_with_fix(self):
        guard = ShieldGemma2Guard({})
        real_import = __import__

        def no_torch(name, *args, **kwargs):
            if name in ("torch", "transformers", "PIL"):
                raise ImportError(f"No module named {name!r}")
            return real_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=no_torch):
            ok, reason = guard.available()
        self.assertFalse(ok)
        self.assertIn("FIX: pip install -r requirements-shieldgemma.txt", reason)

    def test_gated_load_failure_names_the_license(self):
        guard = ShieldGemma2Guard({})
        with mock.patch.object(ShieldGemma2Guard, "_ensure_loaded",
                               side_effect=OSError("401 Client Error: gated repo")):
            ok, reason = guard.available()
        self.assertFalse(ok)
        self.assertIn("accept the license", reason)

    def test_generic_load_failure_reported(self):
        guard = ShieldGemma2Guard({})
        with mock.patch.object(ShieldGemma2Guard, "_ensure_loaded",
                               side_effect=RuntimeError("CUDA out of memory")):
            ok, reason = guard.available()
        self.assertFalse(ok)
        self.assertIn("model load failed", reason)


class TestExitPrecedents(unittest.TestCase):
    """M3_SPEC 6-B shieldgemma2 rows, deterministic via the availability seam."""

    def _run(self, guards):
        with tempfile.TemporaryDirectory() as tmp:
            stdout = io.StringIO()
            with mock.patch.object(ShieldGemma2Guard, "_ensure_loaded",
                                   side_effect=ImportError("No module named 'torch'")), \
                 contextlib.redirect_stdout(stdout):
                code = main_module.main([
                    "--input", str(FIXTURE), "--output-dir", str(Path(tmp) / "out"),
                    "--guards", guards])
            return code, stdout.getvalue()

    def test_shieldgemma2_alone_without_deps_is_fatal(self):
        code, stdout = self._run("shieldgemma2")
        self.assertEqual(code, 1)
        self.assertIn("RESULT: fatal", stdout)
        self.assertIn("GUARD-FAILURE [shieldgemma2]", stdout)

    def test_with_caption_rule_is_partial(self):
        code, stdout = self._run("caption-rule,shieldgemma2")
        self.assertEqual(code, 2)
        self.assertIn("RESULT: partial", stdout)


class TestUnknownPolicyWarningLanding(unittest.TestCase):
    def test_run_metadata_gets_unknown_policy_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"

            def fake_probs(self, image):
                self.unknown_policy_count += 0  # counted in predict via mapping miss
                return [("alien_policy", 0.9), ("violence", 0.1)]

            with mock.patch.object(ShieldGemma2Guard, "_ensure_loaded", lambda self: None), \
                 mock.patch.object(ShieldGemma2Guard, "_load_image", lambda self, r: object()), \
                 mock.patch.object(ShieldGemma2Guard, "_forward_probs", fake_probs), \
                 contextlib.redirect_stdout(io.StringIO()):
                code = main_module.main([
                    "--input", str(FIXTURE), "--output-dir", str(out),
                    "--guards", "shieldgemma2"])
            self.assertEqual(code, 0)
            metadata = json.loads((out / "run_metadata.json").read_text(encoding="utf-8"))
            # 5 predictable records x 1 unknown policy each: 8 eligible minus the
            # 3 precheck error rows (url/not_found/bad_magic) which skip predict;
            # missing_caption_ocr is caption-rule-only, shieldgemma2 predicts there
            self.assertEqual(metadata["warnings"]["unknown_policy_count"], 5)


class TestLiveShieldGemma2(unittest.TestCase):
    """Opt-in live sanity (task 13): SHIELDGEMMA2_LIVE=1 + GPU + weights."""

    @unittest.skipUnless(os.environ.get("SHIELDGEMMA2_LIVE") == "1",
                         "live test: set SHIELDGEMMA2_LIVE=1 (GPU + weights required)")
    def test_benign_synth_image_live(self):
        guard = ShieldGemma2Guard({"model_id": os.environ.get("SHIELDGEMMA2_MODEL_ID")
                                   or ShieldGemma2Guard({}).model_id})
        ok, reason = guard.available()
        self.assertTrue(ok, reason)
        result = guard.predict(_record())
        self.assertIsNone(result["error"])
        self.assertIn(result["prediction"]["is_unsafe"], (True, False))
        self.assertIsNotNone(result["prediction"]["confidence"])


if __name__ == "__main__":
    unittest.main()
