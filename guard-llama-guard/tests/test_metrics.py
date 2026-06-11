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

    @classmethod
    def plain_result(cls):
        """metrics.json of a flag-less run on the category fixtures (cached)."""
        if () not in cls._cache:
            tmp = Path(tempfile.mkdtemp(prefix="guard-m2-"))
            code, out = run_metrics([
                "--predictions", str(FIXTURES / "category_predictions.jsonl"),
                "--dataset", str(FIXTURES / "category_dataset.jsonl"),
                "--output-dir", str(tmp),
            ])
            assert code == 0, out
            with open(tmp / "metrics.json", encoding="utf-8") as fh:
                cls._cache[()] = json.load(fh)
            shutil.rmtree(tmp, ignore_errors=True)
        return cls._cache[()]


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
        plain = self.plain_result()
        for guard in ("fixture-guard-a", "fixture-guard-b"):
            self.assertNotIn("by_category", plain[guard])


class TestAdversarialSplit(_CategoryFixtureCase):
    flags = ["--adversarial-split"]

    def test_slices_match_answer_key(self):
        # expected slice dicts describe the head_binary bucket of each slice
        for guard in ("fixture-guard-a", "fixture-guard-b"):
            for slice_name in ("adversarial", "non_adversarial"):
                expected = self.expected["adversarial_split"][guard][slice_name]
                actual = self.result[guard]["adversarial_split"][slice_name]["buckets"]["head_binary"]
                self.assert_close(expected, actual, f"{guard}.{slice_name}")

    def test_unknown_slice_counts_only(self):
        for guard in ("fixture-guard-a", "fixture-guard-b"):
            unknown = self.result[guard]["adversarial_split"]["unknown"]
            self.assertEqual(unknown, {"eligible_total": 3}, guard)

    def test_slice_conservation(self):
        for guard in ("fixture-guard-a", "fixture-guard-b"):
            split = self.result[guard]["adversarial_split"]
            total = (split["adversarial"]["buckets"]["head_binary"]["eligible_total"]
                     + split["non_adversarial"]["buckets"]["head_binary"]["eligible_total"]
                     + split["unknown"]["eligible_total"])
            full = self.result[guard]["buckets"]["head_binary"]["eligible_total"]
            self.assertEqual(total, full, guard)

    def test_empty_slice_buckets_are_omitted(self):
        # no pair records anywhere; no probes in the adversarial=true slice
        for guard in ("fixture-guard-a", "fixture-guard-b"):
            split = self.result[guard]["adversarial_split"]
            self.assertNotIn("pair_response_harm", split["adversarial"]["buckets"], guard)
            self.assertNotIn("pair_response_harm", split["non_adversarial"]["buckets"], guard)
            self.assertNotIn("over_refusal_probe", split["adversarial"]["buckets"], guard)

    def test_probe_subbucket_in_non_adversarial(self):
        # hand value: probes 0011 (flagged by both guards) + 0012 (passed) -> rate 0.5
        for guard in ("fixture-guard-a", "fixture-guard-b"):
            probe = self.result[guard]["adversarial_split"]["non_adversarial"]["buckets"]["over_refusal_probe"]
            self.assertEqual(probe["eligible_total"], 2, guard)
            self.assertAlmostEqual(probe["over_refusal_rate"]["answered_only"], 0.5, msg=guard)
            self.assertTrue(probe["low_sample_warning"], guard)

    def test_no_flag_means_no_section(self):
        plain = self.plain_result()
        for guard in ("fixture-guard-a", "fixture-guard-b"):
            self.assertNotIn("adversarial_split", plain[guard])


class TestComparison(_CategoryFixtureCase):
    flags = ["--baseline", "fixture-guard-b"]

    def test_emitted_with_two_guards(self):
        self.assertIn("comparison", self.result)
        self.assertEqual(self.result["comparison"]["baseline"], "fixture-guard-b")

    def test_head_binary_cells_match_answer_key(self):
        cells = self.result["comparison"]["buckets"]["head_binary"]
        for guard in ("fixture-guard-a", "fixture-guard-b"):
            exp = self.expected["head_binary"][guard]
            cell = cells[guard]
            for key in ("eligible_total", "answered_total", "coverage", "error_rate"):
                self.assert_close(exp[key], cell[key], f"{guard}.{key}")
            for key in ("accuracy", "recall", "fpr", "macro_f1"):
                self.assert_close(exp["answered_only"][key], cell["answered_only"][key], f"{guard}.ao.{key}")
                if key in ("accuracy", "macro_f1"):
                    self.assert_close(exp["failure_as_wrong"][key], cell["failure_as_wrong"][key],
                                      f"{guard}.fw.{key}")
            self.assert_close(exp["auroc"], cell["answered_only"]["auroc"], f"{guard}.auroc")

    def test_delta_matches_answer_key(self):
        exp = self.expected["comparison"]["head_binary_delta_fixture-guard-a_minus_baseline"]
        delta = self.result["comparison"]["buckets"]["head_binary"]["fixture-guard-a"]["delta_vs_baseline"]
        self.assert_close(exp["answered_only"], delta["answered_only"], "delta.ao")
        self.assert_close(exp["failure_as_wrong"], delta["failure_as_wrong"], "delta.fw")
        # the baseline's own delta is identically zero
        base_delta = self.result["comparison"]["buckets"]["head_binary"]["fixture-guard-b"]["delta_vs_baseline"]
        self.assertAlmostEqual(base_delta["answered_only"]["accuracy"], 0.0)

    def test_probe_rate_and_delta(self):
        exp_rate = self.expected["over_refusal_probe"]
        exp_delta = self.expected["comparison"]["over_refusal_probe_delta_fixture-guard-a_minus_baseline"]
        cells = self.result["comparison"]["buckets"]["over_refusal_probe"]
        for guard in ("fixture-guard-a", "fixture-guard-b"):
            self.assert_close(exp_rate[guard]["over_refusal_rate"],
                              cells[guard]["over_refusal_rate"], f"{guard}.rate")
        self.assert_close(exp_delta["over_refusal_rate"],
                          cells["fixture-guard-a"]["delta_vs_baseline"]["over_refusal_rate"], "rate.delta")

    def test_default_baseline_absent_means_no_delta(self):
        plain = self.plain_result()  # no --baseline -> default 'rule', absent from fixtures
        comp = plain["comparison"]
        self.assertIsNone(comp["baseline"])
        self.assertEqual(comp["requested_baseline"], "rule")
        self.assertIn("rule", comp["note"])
        for cells in comp["buckets"].values():
            for cell in cells.values():
                self.assertNotIn("delta_vs_baseline", cell)

    def test_single_guard_means_no_comparison(self):
        tmp = Path(tempfile.mkdtemp(prefix="guard-m2-single-"))
        code, out = run_metrics([
            "--predictions", str(FIXTURES / "mini_predictions.jsonl"),
            "--dataset", str(FIXTURES / "metrics_dataset.jsonl"),
            "--output-dir", str(tmp),
        ])
        assert code == 0, out
        with open(tmp / "metrics.json", encoding="utf-8") as fh:
            result = json.load(fh)
        shutil.rmtree(tmp, ignore_errors=True)
        self.assertNotIn("comparison", result)

    def test_empty_buckets_stay_out_of_comparison(self):
        # no pair records in the category fixtures -> no empty placeholder row
        self.assertNotIn("pair_response_harm", self.result["comparison"]["buckets"])


class TestOverRefusalFormal(_CategoryFixtureCase):
    """Task 6: over-refusal as a formal M2 acceptance metric (definitions section 11).

    Field-name compatibility check result: M1 already emits the v2-specified names
    (`over_refusal_probe` bucket, `over_refusal_rate.{answered_only,failure_as_wrong}`);
    no alias (e.g. `unsafe_fpr_on_safe_probe`) is needed, so none is introduced.
    """

    flags = ["--baseline", "fixture-guard-b"]

    def test_bucket_rates_match_answer_key(self):
        for guard in ("fixture-guard-a", "fixture-guard-b"):
            exp = self.expected["over_refusal_probe"][guard]
            probe = self.result[guard]["buckets"]["over_refusal_probe"]
            self.assertEqual(exp["eligible_total"], probe["eligible_total"], guard)
            self.assertEqual(exp["answered_total"], probe["answered_total"], guard)
            self.assert_close(exp["over_refusal_rate"], probe["over_refusal_rate"], guard)
            self.assertTrue(probe["low_sample_warning"], guard)

    def test_error_probe_counts_as_fp_in_failure_basis(self):
        # guard-a: probe 0013 is an error row -> fw rate (2/3) must exceed ao rate (0.5)
        rate = self.result["fixture-guard-a"]["buckets"]["over_refusal_probe"]["over_refusal_rate"]
        self.assertAlmostEqual(rate["answered_only"], 0.5)
        self.assertAlmostEqual(rate["failure_as_wrong"], 2 / 3)
        self.assertGreater(rate["failure_as_wrong"], rate["answered_only"])

    def test_comparison_row_consistent_with_bucket(self):
        cells = self.result["comparison"]["buckets"]["over_refusal_probe"]
        for guard in ("fixture-guard-a", "fixture-guard-b"):
            bucket_rate = self.result[guard]["buckets"]["over_refusal_probe"]["over_refusal_rate"]
            self.assert_close(bucket_rate, cells[guard]["over_refusal_rate"], guard)

    def test_field_names_locked_no_alias(self):
        probe = self.result["fixture-guard-a"]["buckets"]["over_refusal_probe"]
        self.assertEqual(sorted(probe["over_refusal_rate"]), ["answered_only", "failure_as_wrong"])
        self.assertNotIn("unsafe_fpr_on_safe_probe", probe)


class TestLoudRefusals(unittest.TestCase):
    # M2 note: test_reserved_flags_exit_1 was removed in task 4 — both reserved
    # flags are now implemented (spec-mandated replacement of the loud refusal);
    # their behavior is locked by TestByCategory / TestAdversarialSplit instead.

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
