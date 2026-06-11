"""metrics.py: hand-computed confusion matrix / AUROC / dual basis / probes.

Fixture design (tests/fixtures/{metrics_dataset,mini_predictions}.jsonl):
truth: 5 unsafe + 5 safe. answered 8: TP=3 FP=1 TN=3 FN=1; errors 2 (1 unsafe,
1 safe truth). Hand-computed targets:
  answered_only    Acc=0.75 Recall=0.75 FPR=0.25 Macro-F1=0.75
  failure_as_wrong Acc=0.60 Recall=0.60 FPR=0.40 Macro-F1=0.60
  coverage=0.8 error_rate=0.2
  AUROC: pos {0.9,0.8,0.7,0.4} neg {0.6,0.3,0.2,0.1} -> R_pos=25 -> 15/16=0.9375
"""
import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

import metrics  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
EXAMPLES = SKILL_ROOT / "examples"


def run_metrics(argv):
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = metrics.main(argv)
    return code, buffer.getvalue()


class TestAuroc(unittest.TestCase):
    def test_hand_computed_no_ties(self):
        pairs = [(0.9, True), (0.8, True), (0.7, True), (0.4, True),
                 (0.6, False), (0.3, False), (0.2, False), (0.1, False)]
        self.assertAlmostEqual(metrics.auroc(pairs), 0.9375)

    def test_hand_computed_with_ties(self):
        # 0.4 appears for one positive and one negative -> average rank 4.5
        pairs = [(0.9, True), (0.8, True), (0.7, True), (0.4, True),
                 (0.4, False), (0.3, False), (0.2, False), (0.1, False)]
        self.assertAlmostEqual(metrics.auroc(pairs), 15.5 / 16)

    def test_degenerate_returns_none(self):
        self.assertIsNone(metrics.auroc([(0.5, True), (0.6, True)]))
        self.assertIsNone(metrics.auroc([]))


class TestMetricsEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="guard-metrics-"))
        code, out = run_metrics([
            "--predictions", str(FIXTURES / "mini_predictions.jsonl"),
            "--dataset", str(FIXTURES / "metrics_dataset.jsonl"),
            "--output-dir", str(cls.tmp),
        ])
        assert code == 0, out
        with open(cls.tmp / "metrics.json", encoding="utf-8") as fh:
            cls.result = json.load(fh)["fixture-guard"]
        cls.head = cls.result["buckets"]["head_binary"]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_count_fields(self):
        self.assertEqual(self.head["eligible_total"], 10)
        self.assertEqual(self.head["answered_total"], 8)
        self.assertAlmostEqual(self.head["coverage"], 0.8)
        self.assertAlmostEqual(self.head["error_rate"], 0.2)

    def test_answered_only_basis(self):
        m = self.head["answered_only"]
        self.assertEqual((m["tp"], m["fp"], m["tn"], m["fn"]), (3, 1, 3, 1))
        self.assertAlmostEqual(m["accuracy"], 0.75)
        self.assertAlmostEqual(m["recall"], 0.75)
        self.assertAlmostEqual(m["fpr"], 0.25)
        self.assertAlmostEqual(m["macro_f1"], 0.75)

    def test_failure_as_wrong_basis(self):
        m = self.head["failure_as_wrong"]
        self.assertEqual((m["tp"], m["fp"], m["tn"], m["fn"]), (3, 2, 3, 2))
        self.assertAlmostEqual(m["accuracy"], 0.60)
        self.assertAlmostEqual(m["recall"], 0.60)
        self.assertAlmostEqual(m["fpr"], 0.40)
        self.assertAlmostEqual(m["macro_f1"], 0.60)

    def test_auroc_hand_value(self):
        self.assertAlmostEqual(self.head["auroc"], 0.9375)

    def test_probe_bucket_over_refusal(self):
        probe = self.result["buckets"]["over_refusal_probe"]
        self.assertEqual(probe["eligible_total"], 2)
        self.assertAlmostEqual(probe["over_refusal_rate"]["answered_only"], 0.5)
        self.assertAlmostEqual(probe["over_refusal_rate"]["failure_as_wrong"], 0.5)
        self.assertTrue(probe["low_sample_warning"])
        # both scored probes are truth-safe -> AUROC degenerate
        self.assertIsNone(probe["auroc"])
        self.assertIn("degenerate", probe["auroc_note"])

    def test_metrics_md_written(self):
        text = (self.tmp / "metrics.md").read_text(encoding="utf-8")
        self.assertIn("fixture-guard", text)
        self.assertIn("failure_as_wrong", text)


class TestRuleGuardAuroc(unittest.TestCase):
    def test_confidence_null_guard_has_null_auroc_with_reason(self):
        tmp = Path(tempfile.mkdtemp(prefix="guard-metrics-rule-"))
        try:
            code, out = run_metrics([
                "--predictions", str(EXAMPLES / "output.sample.jsonl"),
                "--dataset", str(EXAMPLES / "input.sample.jsonl"),
                "--output-dir", str(tmp),
            ])
            self.assertEqual(code, 0, out)
            with open(tmp / "metrics.json", encoding="utf-8") as fh:
                head = json.load(fh)["rule"]["buckets"]["head_binary"]
            self.assertIsNone(head["auroc"])
            self.assertIn("confidence", head["auroc_note"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestMetricsSampleGolden(unittest.TestCase):
    """examples/metrics.sample.json is the frozen metrics output for the
    golden rule predictions on examples/input.sample.jsonl. Metrics are fully
    deterministic, so the lock is exact."""

    def test_sample_matches_fresh_run(self):
        tmp = Path(tempfile.mkdtemp(prefix="guard-metrics-sample-"))
        try:
            code, out = run_metrics([
                "--predictions", str(EXAMPLES / "output.sample.jsonl"),
                "--dataset", str(EXAMPLES / "input.sample.jsonl"),
                "--output-dir", str(tmp),
            ])
            self.assertEqual(code, 0, out)
            with open(tmp / "metrics.json", encoding="utf-8") as fh:
                fresh = json.load(fh)
            with open(EXAMPLES / "metrics.sample.json", encoding="utf-8") as fh:
                frozen = json.load(fh)
            self.assertEqual(fresh, frozen)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_sample_probe_fields(self):
        with open(EXAMPLES / "metrics.sample.json", encoding="utf-8") as fh:
            probe = json.load(fh)["rule"]["buckets"]["over_refusal_probe"]
        self.assertAlmostEqual(probe["over_refusal_rate"]["answered_only"], 1.0)
        self.assertTrue(probe["low_sample_warning"])
        for key in ("eligible_total", "answered_total", "coverage", "error_rate"):
            self.assertIn(key, probe)


class _CategoryFixtureCase(unittest.TestCase):
    """Shared runner for the M2 category fixtures (tests/fixtures/category_*).

    All expected numbers come from tests/fixtures/category_expected.json — the
    hand-computed answer key (two independent computations, see its _notes).
    """

    flags = []
    _cache = {}

    @classmethod
    def setUpClass(cls):
        key = tuple(cls.flags)
        if key not in cls._cache:
            tmp = Path(tempfile.mkdtemp(prefix="guard-m2-"))
            code, out = run_metrics([
                "--predictions", str(FIXTURES / "category_predictions.jsonl"),
                "--dataset", str(FIXTURES / "category_dataset.jsonl"),
                "--output-dir", str(tmp), *cls.flags,
            ])
            assert code == 0, out
            with open(tmp / "metrics.json", encoding="utf-8") as fh:
                result = json.load(fh)
            shutil.rmtree(tmp, ignore_errors=True)
            cls._cache[key] = result
        cls.result = cls._cache[key]
        with open(FIXTURES / "category_expected.json", encoding="utf-8") as fh:
            cls.expected = json.load(fh)

    def assert_close(self, expected, actual, path=""):
        """Recursive numeric-tolerant comparison (floats: 9 places)."""
        if isinstance(expected, dict):
            for k, v in expected.items():
                self.assertIn(k, actual, f"missing key {path}.{k}")
                self.assert_close(v, actual[k], f"{path}.{k}")
        elif isinstance(expected, float):
            self.assertAlmostEqual(expected, actual, places=9, msg=path)
        else:
            self.assertEqual(expected, actual, path)


class TestByCategory(_CategoryFixtureCase):
    flags = ["--by-category"]

    def test_categories_match_answer_key(self):
        for guard in ("fixture-guard-a", "fixture-guard-b"):
            expected = self.expected["by_category"][guard]["categories"]
            actual = self.result[guard]["by_category"]["categories"]
            self.assertEqual(sorted(expected), sorted(actual), guard)
            self.assert_close(expected, actual, guard)

    def test_macro_excludes_zero_support(self):
        for guard in ("fixture-guard-a", "fixture-guard-b"):
            self.assert_close(self.expected["by_category"][guard]["macro"],
                              self.result[guard]["by_category"]["macro"], guard)

    def test_audit_counters_match_answer_key(self):
        for guard in ("fixture-guard-a", "fixture-guard-b"):
            exp, act = self.expected["by_category"][guard], self.result[guard]["by_category"]
            self.assertEqual(exp["unsafe_missing_category"], act["unsafe_missing_category"])
            self.assertEqual(exp["unknown_category_values"], act["unknown_category_values"])
            self.assert_close(exp["category_audit"], act["category_audit"], guard)

    def test_audit_rows_do_not_pollute_binary_metrics(self):
        # safe-with-categories rows must still count as plain TN/TP in head_binary
        for guard in ("fixture-guard-a", "fixture-guard-b"):
            exp = self.expected["head_binary"][guard]
            head = self.result[guard]["buckets"]["head_binary"]
            self.assert_close(exp["answered_only"], head["answered_only"], guard)
            self.assert_close(exp["failure_as_wrong"], head["failure_as_wrong"], guard)

    def test_no_flag_means_no_section(self):
        plain = type(self)._cache.get(())
        if plain is None:
            tmp = Path(tempfile.mkdtemp(prefix="guard-m2-"))
            code, out = run_metrics([
                "--predictions", str(FIXTURES / "category_predictions.jsonl"),
                "--dataset", str(FIXTURES / "category_dataset.jsonl"),
                "--output-dir", str(tmp),
            ])
            assert code == 0, out
            with open(tmp / "metrics.json", encoding="utf-8") as fh:
                plain = json.load(fh)
            shutil.rmtree(tmp, ignore_errors=True)
            type(self)._cache[()] = plain
        for guard in ("fixture-guard-a", "fixture-guard-b"):
            self.assertNotIn("by_category", plain[guard])


class TestLoudRefusals(unittest.TestCase):
    def test_reserved_flags_exit_1(self):
        # M2 note: --by-category is implemented (task 3) and left this list;
        # only still-reserved flags must keep refusing loudly.
        for flag in ("--adversarial-split",):
            code, out = run_metrics([
                "--predictions", str(FIXTURES / "mini_predictions.jsonl"),
                "--dataset", str(FIXTURES / "metrics_dataset.jsonl"),
                "--output-dir", str(FIXTURES),  # never written
                flag,
            ])
            self.assertEqual(code, 1, flag)
            self.assertIn("not implemented", out)

    def test_unjoinable_ids_exit_1(self):
        code, out = run_metrics([
            "--predictions", str(FIXTURES / "mini_predictions.jsonl"),
            "--dataset", str(FIXTURES / "mini_unified.jsonl"),  # disjoint ids
            "--output-dir", str(FIXTURES),
        ])
        self.assertEqual(code, 1)
        self.assertIn("no prediction record joins", out)


if __name__ == "__main__":
    unittest.main()
