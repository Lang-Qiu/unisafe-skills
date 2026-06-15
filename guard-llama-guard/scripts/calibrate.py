"""Threshold calibration / ROC operating points for guard predictions.

Separate concern from metrics.py (which evaluates at a *fixed* threshold): given
predictions carrying a continuous `prediction.confidence` plus gold labels, sweep
thresholds and recommend operating points. Positive class = **unsafe**, same
definitions as references/metrics-definitions.md (FPR = FP/(FP+TN); answered
records only; null confidence excluded — identical population to the AUROC
bucket). Guards without a continuous score (e.g. the keyword `rule` baseline)
are reported as not-calibratable rather than silently dropped.

Why this exists (M2/M3 finding, 2026-06-15): on real data, moving llama-guard's
threshold along its ROC curve strictly dominated an OR-ensemble with the weak
rule guard (higher recall at lower FPR), so the actionable lever is a *calibrated
operating point*, not a fixed 0.5. This tool makes that selection reproducible.

CLI:
  python calibrate.py --predictions <f.jsonl ...> --dataset <gold> \
      --output-dir <dir> [--fpr-budget 0.1] [--thresholds 0.1,0.2,...]
Exit: 0 ok; 2 usage/IO (no predictions, no dataset, nothing calibratable).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from metrics import auroc, _load_dataset, _load_predictions, _truth  # reuse exact defns

DEFAULT_GRID: List[float] = [round(0.05 * i, 2) for i in range(1, 20)]  # 0.05..0.95


def _point(scored: List[Tuple[float, bool]], thr: float) -> Dict[str, Any]:
    """One operating point at `thr` (predict unsafe iff confidence >= thr)."""
    tp = fp = tn = fn = 0
    for conf, truth in scored:
        pred = conf >= thr
        if pred and truth:
            tp += 1
        elif pred and not truth:
            fp += 1
        elif (not pred) and truth:
            fn += 1
        else:
            tn += 1
    n = tp + fp + tn + fn

    def div(num: int, den: int) -> Optional[float]:
        return num / den if den else None

    def f1(p: Optional[float], r: Optional[float]) -> Optional[float]:
        if p is None or r is None:
            return None
        return 2 * p * r / (p + r) if (p + r) > 0 else 0.0

    prec_u, rec_u = div(tp, tp + fp), div(tp, tp + fn)
    prec_s, rec_s = div(tn, tn + fn), div(tn, tn + fp)
    f1_u, f1_s = f1(prec_u, rec_u), f1(prec_s, rec_s)
    macro = (f1_u + f1_s) / 2 if (f1_u is not None and f1_s is not None) else None
    return {
        "threshold": thr, "n": n, "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "accuracy": div(tp + tn, n), "recall": rec_u, "fpr": div(fp, fp + tn),
        "precision": prec_u, "f1_unsafe": f1_u, "macro_f1": macro,
    }


def operating_points(scored: List[Tuple[float, bool]],
                     grid: Optional[List[float]] = None,
                     fpr_budget: float = 0.1) -> Dict[str, Any]:
    """Sweep `grid`; return table + recommended operating points.

    Recommendations: default_0.5 (current behaviour), max_macro_f1, max_f1_unsafe,
    and recall_at_fpr_budget (highest recall among points with FPR <= budget).
    """
    grid = grid if grid is not None else DEFAULT_GRID
    table = [_point(scored, thr) for thr in grid]

    def best(metric: str) -> Optional[Dict[str, Any]]:
        cand = [row for row in table if row[metric] is not None]
        return max(cand, key=lambda row: row[metric]) if cand else None

    within = [row for row in table if row["fpr"] is not None and row["fpr"] <= fpr_budget]
    recommended = {
        "default_0.5": next((r for r in table if abs(r["threshold"] - 0.5) < 1e-9), None)
        or _point(scored, 0.5),
        "max_macro_f1": best("macro_f1"),
        "max_f1_unsafe": best("f1_unsafe"),
        "recall_at_fpr_budget": max(within, key=lambda r: (r["recall"] or 0.0), default=None),
    }
    return {"n_scored": len(scored), "auroc": auroc(list(scored)),
            "fpr_budget": fpr_budget, "table": table, "recommended": recommended}


def _scored_for_guard(dataset: Dict[str, Dict[str, Any]],
                      predictions: List[Dict[str, Any]]) -> List[Tuple[float, bool]]:
    """(confidence, truth_is_unsafe) for answered records with a non-null score."""
    scored: List[Tuple[float, bool]] = []
    for pred in predictions:
        record = dataset.get(pred.get("id"))
        if record is None:
            continue
        block = pred.get("prediction") or {}
        conf = block.get("confidence")
        truth = _truth(record, "is_unsafe")
        if block.get("is_unsafe") is None or conf is None or truth is None:
            continue
        scored.append((float(conf), truth))
    return scored


def _fmt(value: Optional[float]) -> str:
    return "-" if value is None else f"{value:.4f}"


def render_markdown(report: Dict[str, Any]) -> str:
    lines = ["# Threshold calibration (ROC operating points)", "",
             "Positive class = **unsafe**. Population = answered records with a non-null "
             "confidence (same as the AUROC bucket). `rule`-style guards without a "
             "continuous score are not calibratable.", ""]
    for guard, block in report["guards"].items():
        lines.append(f"## guard: `{guard}`")
        if not block.get("calibratable"):
            lines.append(f"- not calibratable: {block.get('reason')}")
            lines.append("")
            continue
        data = block["operating_points"]
        lines.append(f"AUROC = **{_fmt(data['auroc'])}** (n_scored = {data['n_scored']}); "
                     f"FPR budget = {data['fpr_budget']}")
        lines.append("")
        lines.append("| threshold | Acc | Recall | FPR | Precision | F1(unsafe) | Macro-F1 |")
        lines.append("|---|---|---|---|---|---|---|")
        for row in data["table"]:
            lines.append(f"| {row['threshold']:.2f} | {_fmt(row['accuracy'])} | "
                         f"{_fmt(row['recall'])} | {_fmt(row['fpr'])} | {_fmt(row['precision'])} | "
                         f"{_fmt(row['f1_unsafe'])} | {_fmt(row['macro_f1'])} |")
        lines.append("")
        lines.append("Recommended operating points:")
        lines.append("| point | threshold | Recall | FPR | F1(unsafe) | Macro-F1 |")
        lines.append("|---|---|---|---|---|---|")
        for name, row in data["recommended"].items():
            if row is None:
                lines.append(f"| {name} | - | - | - | - | - |")
                continue
            lines.append(f"| {name} | {row['threshold']:.2f} | {_fmt(row['recall'])} | "
                         f"{_fmt(row['fpr'])} | {_fmt(row['f1_unsafe'])} | {_fmt(row['macro_f1'])} |")
        lines.append("")
    return "\n".join(lines) + "\n"


def build_report(dataset: Dict[str, Dict[str, Any]],
                 by_guard: Dict[str, List[Dict[str, Any]]],
                 grid: Optional[List[float]], fpr_budget: float) -> Dict[str, Any]:
    guards: Dict[str, Any] = {}
    for guard, preds in sorted(by_guard.items()):
        scored = _scored_for_guard(dataset, preds)
        if not scored:
            guards[guard] = {"calibratable": False,
                             "reason": "no answered record carries a continuous confidence"}
            continue
        guards[guard] = {"calibratable": True,
                         "operating_points": operating_points(scored, grid, fpr_budget)}
    return {"guards": guards}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Threshold calibration / ROC operating points.")
    parser.add_argument("--predictions", nargs="+", required=True,
                        help="prediction .jsonl file(s) or directory(ies)")
    parser.add_argument("--dataset", required=True, help="unified dataset file or directory (gold)")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--fpr-budget", type=float, default=0.1,
                        help="recall_at_fpr_budget caps FPR at this value (default 0.1)")
    parser.add_argument("--thresholds", default=None,
                        help="comma-separated thresholds (default 0.05..0.95 step 0.05)")
    args = parser.parse_args(argv)

    grid = ([round(float(x), 4) for x in args.thresholds.split(",")]
            if args.thresholds else None)
    dataset = _load_dataset(Path(args.dataset))
    if not dataset:
        print("ERROR: no eligible gold records found", file=sys.stderr)
        return 2
    by_guard = _load_predictions([Path(p) for p in args.predictions])
    if not by_guard:
        print("ERROR: no predictions found", file=sys.stderr)
        return 2

    report = build_report(dataset, by_guard, grid, args.fpr_budget)
    if not any(b.get("calibratable") for b in report["guards"].values()):
        print("ERROR: nothing calibratable (no guard has continuous confidence)", file=sys.stderr)
        return 2

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "calibration.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (out / "calibration.md").write_text(render_markdown(report), encoding="utf-8")
    print(f"wrote {out / 'calibration.json'} and {out / 'calibration.md'}")
    for guard, block in report["guards"].items():
        if block.get("calibratable"):
            rec = block["operating_points"]["recommended"]["recall_at_fpr_budget"]
            mf1 = block["operating_points"]["recommended"]["max_macro_f1"]
            print(f"RECOMMEND [{guard}] max_macro_f1@thr={mf1['threshold']:.2f} "
                  f"(macroF1 {_fmt(mf1['macro_f1'])}); "
                  f"recall@FPR<={args.fpr_budget}: thr="
                  f"{rec['threshold']:.2f} recall {_fmt(rec['recall'])}" if rec else
                  f"RECOMMEND [{guard}] max_macro_f1@thr={mf1['threshold']:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
