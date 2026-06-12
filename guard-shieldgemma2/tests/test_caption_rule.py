"""caption-rule baseline guard (M3_SPEC 4.4; plan AD-4).

Contract under test: reads ONLY the first image's caption/ocr text (no pixels,
no OCR), keyword verdicts mirror the upstream rule baseline, and caption+ocr
both empty yields a missing_caption_ocr error row — never a silent safe.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from guards import get_adapter, known_guards  # noqa: E402
from guards.caption_rule import CaptionRuleGuard  # noqa: E402


def _record(caption=None, ocr=None, path="images/benign_blue.png"):
    return {
        "id": "synthimg:test:000001",
        "task_type": "image_safety",
        "modality": ["image"],
        "content": {"images": [{"path": path, "url": None, "caption": caption, "ocr": ocr}]},
    }


class TestRegistry(unittest.TestCase):
    def test_caption_rule_registered(self):
        self.assertIn("caption-rule", known_guards())
        adapter = get_adapter("caption-rule", {})
        self.assertIsInstance(adapter, CaptionRuleGuard)
        ok, reason = adapter.available()
        self.assertTrue(ok, reason)


class TestCaptionRuleVerdicts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.guard = CaptionRuleGuard({})

    def test_benign_caption_is_safe(self):
        result = self.guard.predict(_record(caption="a golden retriever playing in a park"))
        self.assertIs(result["prediction"]["is_unsafe"], False)
        self.assertEqual(result["prediction"]["risk_categories"], [])
        self.assertIsNone(result["error"])

    def test_caption_keyword_hit_is_unsafe(self):
        result = self.guard.predict(_record(caption="poster showing how to build a bomb"))
        self.assertIs(result["prediction"]["is_unsafe"], True)
        self.assertIn("violence", result["prediction"]["risk_categories"])

    def test_ocr_only_hit_is_unsafe(self):
        result = self.guard.predict(_record(ocr="GUNS FOR SALE: cheap rifle and ammunition"))
        self.assertIs(result["prediction"]["is_unsafe"], True)
        self.assertIn("weapons", result["prediction"]["risk_categories"])
        self.assertEqual(result["raw_output"]["text_source"], ["ocr"])

    def test_homonym_false_positive_is_design_property(self):
        # documented upstream property carried over: keyword matching misfires
        # on safe homonyms; report material, not a bug (rule_keywords comment)
        result = self.guard.predict(_record(caption="tutorial on how to kill a Python process"))
        self.assertIs(result["prediction"]["is_unsafe"], True)

    def test_missing_caption_and_ocr_is_error_not_safe(self):
        result = self.guard.predict(_record(caption=None, ocr=None))
        self.assertIsNone(result["prediction"]["is_unsafe"])
        self.assertTrue(result["error"].startswith("missing_caption_ocr"))

    def test_output_shape(self):
        result = self.guard.predict(_record(caption="a dog"))
        self.assertEqual(result["guard"]["name"], "caption-rule")
        self.assertEqual(result["guard"]["modality"], ["image"])
        self.assertIsNone(result["prediction"]["confidence"])  # no continuous score
        self.assertEqual(result["raw_output"]["engine"], "caption-keyword-regex-v1")
        self.assertEqual(result["raw_output"]["text_source"], ["caption"])


if __name__ == "__main__":
    unittest.main()
