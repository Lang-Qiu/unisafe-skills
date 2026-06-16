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
import types
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


def _nan_scored():
    return [("dangerous", float("nan")), ("sexual", float("nan")), ("violence", float("nan"))]


def _patched_guard_fb(primary_scored, fallback_fn, config):
    """E3: primary int8 forward + a stubbed _fallback_forward(self, image, mode)."""
    guard = ShieldGemma2Guard(config)
    with mock.patch.object(ShieldGemma2Guard, "_ensure_loaded", lambda self: None), \
         mock.patch.object(ShieldGemma2Guard, "_load_image", lambda self, record: object()), \
         mock.patch.object(ShieldGemma2Guard, "_forward_probs",
                           lambda self, image: list(primary_scored)), \
         mock.patch.object(ShieldGemma2Guard, "_fallback_forward", fallback_fn):
        result = guard.predict(_record())
    return guard, result


@contextlib.contextmanager
def _fake_runtime_deps():
    """Let available() reach the model-loading seam without real heavy deps."""
    torch = types.ModuleType("torch")
    torch.no_grad = object()
    modules = {
        "torch": torch,
        "transformers": types.ModuleType("transformers"),
        "PIL": types.ModuleType("PIL"),
    }
    with mock.patch.dict(sys.modules, modules):
        yield


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

    def test_default_threshold_is_calibrated_030(self):
        # M3.6 E1: int8 recall@FPR<=0.1 point (references/calibration-notes.md);
        # NOT max_macro_f1 (=0.05/FPR 0.383). Override via --threshold / config.
        self.assertEqual(ShieldGemma2Guard({}).threshold, 0.30)


class TestVerdicts(unittest.TestCase):
    def test_single_policy_over_threshold(self):
        _, result = _patched_guard([("dangerous", 0.2), ("sexual", 0.1), ("violence", 0.9)])
        self.assertIs(result["prediction"]["is_unsafe"], True)
        self.assertEqual(result["prediction"]["risk_categories"], ["violence"])
        self.assertAlmostEqual(result["prediction"]["confidence"], 0.9)
        self.assertEqual(result["raw_output"]["policy_order"],
                         ["dangerous", "sexual", "violence"])

    def test_all_under_threshold_is_safe(self):
        # explicit threshold=0.5 decouples this logic test from the default (M3.6 E1
        # moved the default to 0.30, under which dangerous 0.3 would flip to unsafe)
        _, result = _patched_guard([("dangerous", 0.3), ("sexual", 0.1), ("violence", 0.2)],
                                   threshold=0.5)
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

    def test_unknown_policy_audited_even_below_threshold(self):
        # name-level audit is threshold-independent: an unknown name is a model
        # property, not a verdict property
        guard, result = _patched_guard([("alien_policy", 0.1), ("violence", 0.9)])
        self.assertEqual(result["prediction"]["risk_categories"], ["violence"])
        self.assertEqual(guard.unknown_policy_count, 1)

    def test_nan_probabilities_become_error_row(self):
        # default nan_fallback="none" (E3): NaN stays a record-level error row
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


class TestNanFallback(unittest.TestCase):
    """E3: int8 NaN -> per-record non-quantized fallback (recover coverage)."""

    def test_default_nan_fallback_is_none(self):
        self.assertEqual(ShieldGemma2Guard({}).nan_fallback, "none")
        self.assertEqual(ShieldGemma2Guard({}).nan_fallback_recovered, 0)

    def test_nan_fallback_cpu_recovers(self):
        def fb(self, image, mode):
            return [("dangerous", 0.1), ("sexual", 0.1), ("violence", 0.8)]
        guard, result = _patched_guard_fb(_nan_scored(), fb, {"nan_fallback": "cpu"})
        self.assertIs(result["prediction"]["is_unsafe"], True)  # 0.8 >= 0.30
        self.assertIsNone(result["error"])
        self.assertEqual(result["raw_output"]["quant"], "int8->cpu-bf16")
        self.assertIn("nan_fallback_recovered", result["prediction"].get("warnings", []))
        self.assertEqual(guard.nan_fallback_recovered, 1)

    def test_nan_fallback_auto_gpu_oom_then_cpu(self):
        def fb(self, image, mode):
            if mode == "gpu":
                raise RuntimeError("CUDA out of memory")
            return [("dangerous", 0.1), ("sexual", 0.1), ("violence", 0.9)]
        guard, result = _patched_guard_fb(_nan_scored(), fb, {"nan_fallback": "auto"})
        self.assertIs(result["prediction"]["is_unsafe"], True)
        self.assertEqual(result["raw_output"]["quant"], "int8->cpu-bf16")  # gpu OOM -> cpu
        self.assertEqual(guard.nan_fallback_recovered, 1)

    def test_nan_fallback_gpu_recovers(self):
        def fb(self, image, mode):
            self_assert = ("violence", 0.7)
            return [("dangerous", 0.1), ("sexual", 0.1), self_assert]
        guard, result = _patched_guard_fb(_nan_scored(), fb, {"nan_fallback": "gpu"})
        self.assertEqual(result["raw_output"]["quant"], "int8->gpu-fp16")
        self.assertEqual(guard.nan_fallback_recovered, 1)

    def test_nan_fallback_also_nan_is_error(self):
        def fb(self, image, mode):
            return _nan_scored()
        guard, result = _patched_guard_fb(_nan_scored(), fb, {"nan_fallback": "cpu"})
        self.assertIsNone(result["prediction"]["is_unsafe"])
        self.assertTrue(result["error"].startswith("nan_probabilities"))
        self.assertEqual(guard.nan_fallback_recovered, 0)

    def test_nan_fallback_none_never_calls_fallback(self):
        def fb(self, image, mode):
            raise AssertionError("fallback must not run when nan_fallback=none")
        guard, result = _patched_guard_fb(_nan_scored(), fb, {"nan_fallback": "none"})
        self.assertIsNone(result["prediction"]["is_unsafe"])
        self.assertTrue(result["error"].startswith("nan_probabilities"))
        self.assertEqual(guard.nan_fallback_recovered, 0)


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
        self.assertIn("install the torch build", reason)
        self.assertIn("requirements-shieldgemma.txt", reason)

    def test_gated_load_failure_names_the_license(self):
        guard = ShieldGemma2Guard({})
        with _fake_runtime_deps(), \
             mock.patch.object(ShieldGemma2Guard, "_ensure_loaded",
                               side_effect=OSError("401 Client Error: gated repo")):
            ok, reason = guard.available()
        self.assertFalse(ok)
        self.assertIn("accept the license", reason)

    def test_generic_load_failure_reported(self):
        guard = ShieldGemma2Guard({})
        with _fake_runtime_deps(), \
             mock.patch.object(ShieldGemma2Guard, "_ensure_loaded",
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
                return [("alien_policy", 0.9), ("violence", 0.1)]

            with _fake_runtime_deps(), \
                 mock.patch.object(ShieldGemma2Guard, "_ensure_loaded", lambda self: None), \
                 mock.patch.object(ShieldGemma2Guard, "_load_image", lambda self, r: object()), \
                 mock.patch.object(ShieldGemma2Guard, "_forward_probs", fake_probs), \
                 contextlib.redirect_stdout(io.StringIO()):
                code = main_module.main([
                    "--input", str(FIXTURE), "--output-dir", str(out),
                    "--guards", "shieldgemma2"])
            self.assertEqual(code, 0)
            metadata = json.loads((out / "run_metadata.json").read_text(encoding="utf-8"))
            # name-level audit: ONE distinct unknown policy name ('alien_policy'),
            # however many records it appears on (5 predictable records here)
            self.assertEqual(metadata["warnings"]["unknown_policy_count"], 1)

    def test_run_metadata_gets_nan_fallback_recovered(self):
        # E3: --nan-fallback cpu, every int8 forward NaN, fallback valid ->
        # all 5 predictable records recovered, surfaced in run_metadata.warnings
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"

            def nan_probs(self, image):
                return [("dangerous", float("nan")), ("violence", float("nan"))]

            def fb(self, image, mode):
                return [("dangerous", 0.1), ("violence", 0.9)]

            with _fake_runtime_deps(), \
                 mock.patch.object(ShieldGemma2Guard, "_ensure_loaded", lambda self: None), \
                 mock.patch.object(ShieldGemma2Guard, "_load_image", lambda self, r: object()), \
                 mock.patch.object(ShieldGemma2Guard, "_forward_probs", nan_probs), \
                 mock.patch.object(ShieldGemma2Guard, "_fallback_forward", fb), \
                 contextlib.redirect_stdout(io.StringIO()):
                code = main_module.main([
                    "--input", str(FIXTURE), "--output-dir", str(out),
                    "--guards", "shieldgemma2", "--nan-fallback", "cpu"])
            self.assertEqual(code, 0)
            metadata = json.loads((out / "run_metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["warnings"]["nan_fallback_recovered"], 5)
            self.assertEqual(metadata["config"]["nan_fallback"], "cpu")

    def test_nan_fallback_none_leaves_no_warning_key(self):
        # default none: NaN -> error rows, no recovery key in run_metadata.warnings
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"

            def nan_probs(self, image):
                return [("dangerous", float("nan")), ("violence", float("nan"))]

            with _fake_runtime_deps(), \
                 mock.patch.object(ShieldGemma2Guard, "_ensure_loaded", lambda self: None), \
                 mock.patch.object(ShieldGemma2Guard, "_load_image", lambda self, r: object()), \
                 mock.patch.object(ShieldGemma2Guard, "_forward_probs", nan_probs), \
                 contextlib.redirect_stdout(io.StringIO()):
                main_module.main([
                    "--input", str(FIXTURE), "--output-dir", str(out),
                    "--guards", "shieldgemma2"])
            metadata = json.loads((out / "run_metadata.json").read_text(encoding="utf-8"))
            self.assertNotIn("nan_fallback_recovered", metadata.get("warnings", {}))


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
