"""calibrate.py — threshold sweep / ROC operating points (answer-key locked).

The hand-computed key uses scored = [(0.9,T),(0.7,T),(0.6,F),(0.4,T),(0.2,F)]
(positive=unsafe). At thr=0.5: tp=2 fp=1 tn=1 fn=1 -> Acc 0.6, Recall 2/3,
FPR 0.5, Precision 2/3, F1_unsafe 2/3, Macro-F1 0.5833. AUROC = 5 concordant /
6 pairs = 0.8333. Best Macro-F1 is at thr=0.65 (tp=2 fp=0 tn=2 fn=1 -> 0.8).
recall_at_FPR<=0.1 is first reached at thr=0.65 (FPR 0, recall 2/3).
"""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import calibrate  # noqa: E402

SCORED = [(0.9, True), (0.7, True), (0.6, False), (0.4, True), (0.2, False)]


class TestPoint(unittest.TestCase):
    def test_point_at_half(self):
        p = calibrate._point(SCORED, 0.5)
        self.assertEqual((p["tp"], p["fp"], p["tn"], p["fn"]), (2, 1, 1, 1))
        self.assertAlmostEqual(p["accuracy"], 0.6)
        self.assertAlmostEqual(p["recall"], 2 / 3)
        self.assertAlmostEqual(p["fpr"], 0.5)
        self.assertAlmostEqual(p["precision"], 2 / 3)
        self.assertAlmostEqual(p["f1_unsafe"], 2 / 3)
        self.assertAlmostEqual(p["macro_f1"], (2 / 3 + 0.5) / 2)

    def test_point_high_threshold_no_positives(self):
        p = calibrate._point(SCORED, 0.95)
        self.assertEqual((p["tp"], p["fp"]), (0, 0))
        self.assertIsNone(p["precision"])     # no positive predictions
        self.assertIsNone(p["f1_unsafe"])     # undefined precision -> None


class TestOperatingPoints(unittest.TestCase):
    def setUp(self):
        self.report = calibrate.operating_points(SCORED, fpr_budget=0.1)

    def test_auroc(self):
        self.assertAlmostEqual(self.report["auroc"], 5 / 6)

    def test_default_half_row(self):
        row = self.report["recommended"]["default_0.5"]
        self.assertAlmostEqual(row["threshold"], 0.5)
        self.assertAlmostEqual(row["recall"], 2 / 3)
        self.assertAlmostEqual(row["fpr"], 0.5)

    def test_max_macro_f1_at_065(self):
        row = self.report["recommended"]["max_macro_f1"]
        self.assertAlmostEqual(row["threshold"], 0.65)
        self.assertAlmostEqual(row["macro_f1"], 0.8)

    def test_recall_at_fpr_budget(self):
        row = self.report["recommended"]["recall_at_fpr_budget"]
        self.assertLessEqual(row["fpr"], 0.1)
        self.assertAlmostEqual(row["threshold"], 0.65)  # first point reaching FPR<=0.1
        self.assertAlmostEqual(row["recall"], 2 / 3)

    def test_table_covers_default_grid(self):
        self.assertEqual(len(self.report["table"]), 19)  # 0.05..0.95


def _gold_record(rid, is_unsafe):
    return {"id": rid, "task_type": "prompt_only_safety", "modality": ["text"],
            "content": {"prompt": "x", "response": None, "conversation": None,
                        "images": [], "videos": [], "audio": []},
            "label": {"target": "prompt", "is_unsafe": is_unsafe,
                      "canonical_categories": []}}


def _pred_record(rid, guard, is_unsafe, conf):
    return {"id": rid, "guard": {"name": guard},
            "prediction": {"is_unsafe": is_unsafe, "confidence": conf,
                           "risk_categories": []}, "error": None}


class TestCli(unittest.TestCase):
    def test_cli_writes_calibration_and_skips_non_scored(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            gold = [(f"t:{i:03d}", i % 2 == 0) for i in range(6)]
            (tmp / "gold.jsonl").write_text(
                "\n".join(json.dumps(_gold_record(r, u)) for r, u in gold) + "\n",
                encoding="utf-8")
            # llama-guard has confidences; rule has null confidence -> not calibratable
            preds = []
            for i, (rid, u) in enumerate(gold):
                preds.append(_pred_record(rid, "llama-guard", u, 0.9 if u else 0.1))
                preds.append(_pred_record(rid, "rule", u, None))
            (tmp / "p.jsonl").write_text(
                "\n".join(json.dumps(p) for p in preds) + "\n", encoding="utf-8")
            out = tmp / "out"
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = calibrate.main(["--predictions", str(tmp / "p.jsonl"),
                                       "--dataset", str(tmp / "gold.jsonl"),
                                       "--output-dir", str(out)])
            self.assertEqual(code, 0)
            report = json.loads((out / "calibration.json").read_text(encoding="utf-8"))
            self.assertTrue(report["guards"]["llama-guard"]["calibratable"])
            self.assertFalse(report["guards"]["rule"]["calibratable"])
            self.assertIn("not calibratable", (out / "calibration.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
