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


class TestLoudRefusals(unittest.TestCase):
    def test_reserved_flags_exit_1(self):
        for flag in ("--by-category", "--adversarial-split"):
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
