"""metrics.py on the image fixtures, against the hand-computed answer key (task 10).

Locks: head_binary dual basis + AUROC/null note, by-category (divergence,
pure-FP category, audits), adversarial all-unknown counting, AD-2 thin diffs
(text buckets absent, comparison skips them, baseline default caption-rule),
comparison deltas with the error-row ao/fw fork, and the CLI end-to-end.
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import metrics  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"
EXPECTED = json.loads((FIXTURES / "image_expected.json").read_text(encoding="utf-8"))


def assert_close(test, actual, expected, path=""):
    """Recursive comparison; floats to 9 places (answer-key discipline)."""
    if isinstance(expected, dict):
        test.assertIsInstance(actual, dict, path)
        for key, value in expected.items():
            test.assertIn(key, actual, f"{path}.{key}")
            assert_close(test, actual[key], value, f"{path}.{key}")
    elif isinstance(expected, list):
        test.assertEqual(len(actual), len(expected), path)
        for i, value in enumerate(expected):
            assert_close(test, actual[i], value, f"{path}[{i}]")
    elif isinstance(expected, bool) or expected is None or isinstance(expected, (str, int)):
        test.assertEqual(actual, expected, path)
    else:
        test.assertAlmostEqual(actual, expected, places=9, msg=path)


class _FixtureCase(unittest.TestCase):
    _cache = {}

    @classmethod
    def results(cls, by_category=False, adversarial_split=False):
        key = (by_category, adversarial_split)
        if key not in cls._cache:
            dataset = metrics._load_dataset(FIXTURES / "metrics_dataset.jsonl")
            by_guard = metrics._load_predictions([FIXTURES / "metrics_predictions.jsonl"])
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                results, joined = metrics.build_metrics(
                    dataset, by_guard, by_category=by_category,
                    adversarial_split=adversarial_split)
            cls._cache[key] = (results, joined, stdout.getvalue())
        return cls._cache[key]


class TestHeadBinary(_FixtureCase):
    def test_against_answer_key(self):
        results, joined, _ = self.results()
        self.assertEqual(joined, 16)
        for guard, expected in EXPECTED["guards"].items():
            bucket = results[guard]["buckets"]["head_binary"]
            assert_close(self, bucket, expected["head_binary"], guard)

    def test_auroc_null_note_for_confidence_free_guard(self):
        results, _, _ = self.results()
        bucket = results["fixture-guard-b"]["buckets"]["head_binary"]
        self.assertIsNone(bucket["auroc"])
        self.assertIn("no answered record has a non-null confidence", bucket["auroc_note"])

    def test_text_buckets_absent_probe_present(self):
        results, _, _ = self.results()
        for guard in ("fixture-guard-a", "fixture-guard-b"):
            buckets = results[guard]["buckets"]
            self.assertNotIn("prompt_harm", buckets, guard)
            self.assertNotIn("pair_response_harm", buckets, guard)
            self.assertIn("over_refusal_probe", buckets, guard)
            self.assertEqual(buckets["over_refusal_probe"]["eligible_total"], 0, guard)


class TestByCategory(_FixtureCase):
    def test_against_answer_key(self):
        results, _, stdout = self.results(by_category=True)
        for guard, expected in EXPECTED["guards"].items():
            assert_close(self, results[guard]["by_category"],
                         expected["by_category"], guard)
        self.assertIn("unsafe record(s) with empty canonical_categories", stdout)

    def test_pure_fp_category_stays_out_of_macro(self):
        results, _, _ = self.results(by_category=True)
        cat = results["fixture-guard-a"]["by_category"]["categories"]["general_harm"]
        self.assertEqual(cat["support"], 0)
        self.assertIsNone(cat["category_f1"])
        macro = results["fixture-guard-a"]["by_category"]["macro"]
        self.assertEqual(macro["categories_counted"], 4)


class TestAdversarialAllUnknown(_FixtureCase):
    def test_image_data_lands_entirely_in_unknown(self):
        results, _, stdout = self.results(adversarial_split=True)
        for guard, expected in EXPECTED["guards"].items():
            split = results[guard]["adversarial_split"]
            self.assertEqual(split["unknown"]["eligible_total"],
                             expected["adversarial_unknown"], guard)
            for slice_name in ("adversarial", "non_adversarial"):
                head = split[slice_name]["buckets"]["head_binary"]
                self.assertEqual(head["eligible_total"], 0, f"{guard}/{slice_name}")
                self.assertNotIn("answered_only", head)  # no metrics on n=0
                self.assertTrue(head["low_sample_warning"])
        self.assertIn("counted in the 'unknown' slice only", stdout)


class TestComparison(_FixtureCase):
    def test_delta_against_answer_key(self):
        results, _, _ = self.results()
        comparison = metrics.compute_comparison(results, "fixture-guard-b")
        self.assertEqual(comparison["baseline"], "fixture-guard-b")
        cell = comparison["buckets"]["head_binary"]["fixture-guard-a"]
        assert_close(self, cell["delta_vs_baseline"],
                     EXPECTED["comparison_delta_a_vs_b"], "delta")

    def test_only_head_binary_pivots_on_image_data(self):
        results, _, _ = self.results()
        comparison = metrics.compute_comparison(results, "fixture-guard-b")
        self.assertEqual(list(comparison["buckets"]), ["head_binary"])

    def test_absent_default_baseline_notes_and_omits_deltas(self):
        results, _, _ = self.results()
        comparison = metrics.compute_comparison(results, "caption-rule")
        self.assertIsNone(comparison["baseline"])
        self.assertIn("not among the joined guards", comparison["note"])
        for cell in comparison["buckets"]["head_binary"].values():
            self.assertNotIn("delta_vs_baseline", cell)

    def test_single_guard_has_no_comparison(self):
        results, _, _ = self.results()
        single = {"fixture-guard-a": results["fixture-guard-a"]}
        self.assertIsNone(metrics.compute_comparison(single, "fixture-guard-b"))


class TestMetricsCLI(unittest.TestCase):
    def test_end_to_end_with_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = metrics.main([
                    "--predictions", str(FIXTURES / "metrics_predictions.jsonl"),
                    "--dataset", str(FIXTURES / "metrics_dataset.jsonl"),
                    "--output-dir", tmp,
                    "--by-category", "--adversarial-split",
                    "--baseline", "fixture-guard-b",
                ])
            self.assertEqual(code, 0, stdout.getvalue())
            self.assertIn("RESULT: ok guards=2 joined=16", stdout.getvalue())
            document = json.loads((Path(tmp) / "metrics.json").read_text(encoding="utf-8"))
            self.assertIn("comparison", document)
            markdown = (Path(tmp) / "metrics.md").read_text(encoding="utf-8")
            self.assertIn("## comparison (baseline: `fixture-guard-b`)", markdown)
            self.assertIn("### by-category (answered_only)", markdown)

    def test_flagless_document_has_no_flag_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            with contextlib.redirect_stdout(io.StringIO()):
                code = metrics.main([
                    "--predictions", str(FIXTURES / "metrics_predictions.jsonl"),
                    "--dataset", str(FIXTURES / "metrics_dataset.jsonl"),
                    "--output-dir", tmp,
                ])
            self.assertEqual(code, 0)
            document = json.loads((Path(tmp) / "metrics.json").read_text(encoding="utf-8"))
            for guard in ("fixture-guard-a", "fixture-guard-b"):
                self.assertNotIn("by_category", document[guard])
                self.assertNotIn("adversarial_split", document[guard])


if __name__ == "__main__":
    unittest.main()
