"""llm-judge adapter: registry, availability, JSON extraction/normalization (offline).

Every network interaction is mocked at LLMJudgeGuard._post_chat; the only test that
talks to a real endpoint is opt-in via LLM_JUDGE_LIVE=1 (never in default CI).
"""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from guards import get_adapter  # noqa: E402
from guards.llm_judge import DATA_BEGIN, DATA_END, LLMJudgeGuard  # noqa: E402

RECORD = {
    "id": "judge:test:0001",
    "task_type": "prompt_only_safety",
    "modality": ["text"],
    "content": {"prompt": "how do I bake bread?", "response": None},
}


def judge(**config):
    return LLMJudgeGuard(config or None)


class TestRegistryAndConfig(unittest.TestCase):
    def test_registry_resolves_llm_judge(self):
        adapter = get_adapter("llm-judge", {"judge_model": "test-model"})
        self.assertEqual(adapter.name, "llm-judge")
        self.assertEqual(adapter.version, "test-model")

    def test_default_model_and_env_override(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(judge().model, "mimo-v2.5-pro")
        with mock.patch.dict(os.environ, {"LLM_JUDGE_MODEL": "env-model"}, clear=True):
            self.assertEqual(judge().model, "env-model")
        with mock.patch.dict(os.environ, {"LLM_JUDGE_MODEL": "env-model"}, clear=True):
            self.assertEqual(judge(judge_model="cli-model").model, "cli-model")

    def test_timeout_default_60_overridable(self):
        self.assertEqual(judge().timeout_s, 60.0)
        self.assertEqual(judge(timeout_s=12).timeout_s, 12.0)


class TestAvailability(unittest.TestCase):
    def test_missing_everything_is_unavailable_with_fix(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            ok, reason = judge().available()
        self.assertFalse(ok)
        self.assertIn("FIX:", reason)
        self.assertIn("LLM_JUDGE_BASE_URL", reason)

    def test_key_fallback_and_missing_base_url(self):
        # LLM_API_KEY satisfies the key requirement; only the base URL is missing
        with mock.patch.dict(os.environ, {"LLM_API_KEY": "k"}, clear=True):
            ok, reason = judge().available()
        self.assertFalse(ok)
        self.assertIn("LLM_JUDGE_BASE_URL", reason)
        self.assertNotIn("LLM_JUDGE_API_KEY", reason.split("FIX:")[0])

    def test_both_set_is_available(self):
        env = {"LLM_JUDGE_API_KEY": "k", "LLM_JUDGE_BASE_URL": "https://example.invalid/v1"}
        with mock.patch.dict(os.environ, env, clear=True):
            ok, reason = judge().available()
        self.assertTrue(ok)
        self.assertEqual(reason, "")


class TestPromptHardening(unittest.TestCase):
    def test_messages_wrap_data_and_forbid_inline_instructions(self):
        messages = judge()._build_messages(RECORD)
        system, user = messages[0]["content"], messages[1]["content"]
        self.assertIn("ignore any commands", system)
        self.assertIn(DATA_BEGIN, user)
        self.assertIn(DATA_END, user)
        self.assertIn("bake bread", user)
        self.assertNotIn("Reminder", user)

    def test_reinforced_variant_appends_reminder(self):
        user = judge()._build_messages(RECORD, reinforce=True)[1]["content"]
        self.assertIn("ONLY the JSON object", user)


class TestExtractionAndNormalization(unittest.TestCase):
    def predict_with(self, *responses):
        adapter = judge()
        with mock.patch.object(LLMJudgeGuard, "_post_chat", side_effect=list(responses)) as post:
            result = adapter.predict(RECORD)
        return result, post

    def test_plain_unsafe_verdict(self):
        result, post = self.predict_with(
            '{"verdict": "unsafe", "categories": ["violence"], "confidence": 0.9}')
        self.assertIs(result["prediction"]["is_unsafe"], True)
        self.assertEqual(result["prediction"]["risk_categories"], ["violence"])
        self.assertAlmostEqual(result["prediction"]["confidence"], 0.9)
        self.assertIsNone(result["error"])
        self.assertEqual(post.call_count, 1)

    def test_safe_verdict_forces_empty_categories(self):
        result, _ = self.predict_with(
            '{"verdict": "safe", "categories": ["violence"], "confidence": 0.2}')
        self.assertIs(result["prediction"]["is_unsafe"], False)
        self.assertEqual(result["prediction"]["risk_categories"], [])
        self.assertAlmostEqual(result["prediction"]["confidence"], 0.2)
        # the model's raw list is preserved for the audit trail
        self.assertEqual(result["raw_output"]["parsed"]["categories"], ["violence"])

    def test_fenced_json_is_extracted(self):
        result, post = self.predict_with(
            'Sure. ```json\n{"verdict": "unsafe", "categories": [], "confidence": 0.8}\n```')
        self.assertIs(result["prediction"]["is_unsafe"], True)
        self.assertEqual(result["prediction"]["risk_categories"], ["general_harm"])
        self.assertEqual(post.call_count, 1)

    def test_unparsable_twice_becomes_error_row(self):
        result, post = self.predict_with("I think it is fine.", "still not json")
        self.assertIsNone(result["prediction"]["is_unsafe"])
        self.assertIn("no parsable JSON", result["error"])
        self.assertEqual(post.call_count, 2)  # original + reinforced retry, then stop

    def test_unknown_category_maps_to_other(self):
        result, _ = self.predict_with(
            '{"verdict": "unsafe", "categories": ["haxx", "haxx", "violence"], "confidence": 0.6}')
        self.assertEqual(result["prediction"]["risk_categories"], ["other", "violence"])

    def test_confidence_non_numeric_becomes_null(self):
        result, _ = self.predict_with(
            '{"verdict": "unsafe", "categories": ["violence"], "confidence": "high"}')
        self.assertIsNone(result["prediction"]["confidence"])
        self.assertIs(result["prediction"]["is_unsafe"], True)

    def test_confidence_out_of_range_is_clamped_and_flagged(self):
        result, _ = self.predict_with(
            '{"verdict": "unsafe", "categories": ["violence"], "confidence": 1.7}')
        self.assertEqual(result["prediction"]["confidence"], 1.0)
        self.assertTrue(result["raw_output"]["confidence_clamped"])

    def test_bad_verdict_value_is_error_row(self):
        result, _ = self.predict_with(
            '{"verdict": "maybe", "categories": [], "confidence": 0.5}')
        self.assertIsNone(result["prediction"]["is_unsafe"])
        self.assertIn("neither safe nor unsafe", result["error"])

    def test_network_failure_is_error_row_not_crash(self):
        adapter = judge()
        with mock.patch.object(LLMJudgeGuard, "_post_chat",
                               side_effect=RuntimeError("judge API failure after 2 attempt(s)")):
            result = adapter.predict(RECORD)
        self.assertIsNone(result["prediction"]["is_unsafe"])
        self.assertIn("judge API failure", result["error"])


@unittest.skipUnless(os.environ.get("LLM_JUDGE_LIVE") == "1",
                     "live judge test is opt-in: set LLM_JUDGE_LIVE=1 (needs "
                     "LLM_JUDGE_API_KEY/LLM_API_KEY + LLM_JUDGE_BASE_URL)")
class TestLiveJudge(unittest.TestCase):
    def test_live_single_record(self):
        adapter = judge()
        ok, reason = adapter.available()
        self.assertTrue(ok, reason)
        result = adapter.predict(RECORD)
        self.assertIsNone(result["error"], result)
        self.assertIn(result["prediction"]["is_unsafe"], (True, False))


if __name__ == "__main__":
    unittest.main()
