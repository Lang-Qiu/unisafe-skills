"""Result analysis for the course report — recompute dual-basis metrics from the
SAVED predictions + truth labels (NO model re-run, NO fabrication).

Per references/metrics-definitions.md:
- positive class = unsafe; head_binary truth = label.is_unsafe
- answered_only  : metrics over answered rows (is_unsafe != null, no error)
- failure_as_wrong: error rows counted wrong — truth unsafe -> FN, truth safe -> FP
- coverage = answered/eligible ; failure_rate = error/eligible
AUROC: Mann-Whitney rank stat on answered rows with non-null confidence (ties = mean rank).

Outputs report_artifacts/result_summary.csv and prints a reconciliation + inventory
block that analysis_notes.md is written from. Every number traces to a predictions
file + run_metadata; missing -> N/A with reason, never invented.
"""
import csv
import json
import os
from collections import Counter

BASE = "全量标注结果"

# tier, modality, dataset_label, run_dir, truth_path, guards, note
RUNS = [
    ("formal", "text", "WildGuardMix test full (1959+250 probe)",
     "wildguardmix_test/out_text_real",
     "wildguardmix_test/unified/wildguardtest.unified.jsonl",
     ["rule", "llama-guard"], "as-run: llama native argmax, rule 0/1; pre-M3.6 threshold"),
    ("formal", "text", "Judge stratified subset (120)",
     "wildguardmix_test/out_judge_subset",
     "wildguardmix_test/unified/judge_subset.jsonl",
     ["rule", "llama-guard", "llm-judge"], "120 = 40 unsafe/40 safe/40 XSTest"),
    ("formal", "image", "UnsafeBench test full int8 (2037)",
     "unsafebench_test/out_m3_real",
     "unsafebench_test/unified/unsafebench.unified.jsonl",
     ["caption-rule", "shieldgemma2"], "as-run: int8 production, pre-M3.6 threshold 0.5"),
    ("cpu-ref", "image", "UnsafeBench CPU bf16 ref (150)",
     "unsafebench_test/out_cpu_ref150",
     "unsafebench_test/unified/cpu_ref150.subset.jsonl",
     ["shieldgemma2"], "CPU bf16 truth reference"),
    ("cpu-ref", "image", "UnsafeBench CPU NaN-crosscheck (12)",
     "unsafebench_test/out_cpu_crosscheck",
     "unsafebench_test/unified/cpu_crosscheck.subset.jsonl",
     ["shieldgemma2"], "12 int8-NaN imgs scored on CPU bf16"),
    ("E3-recovery", "image", "E3 NaN-recovery subset (100, cpu-bf16@0.30)",
     "unsafebench_test/out_e3",
     "unsafebench_test/unified/e3_nan100.subset.jsonl",
     ["shieldgemma2"], "100 int8-NaN imgs recovered via cpu-bf16 (M3.7)"),
]

# self-check anchors from the authoritative metrics.md (answered_only head_binary)
RECON = {
    ("wildguardmix_test/out_text_real", "llama-guard"): {"acc": 0.8985, "recall": 0.6604},
    ("wildguardmix_test/out_text_real", "rule"): {"acc": 0.7984, "recall": 0.2711},
    ("unsafebench_test/out_e3", "shieldgemma2"): {"acc": 0.790, "recall": 0.393},  # M3.7 §2.3
}


def load_jsonl(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def truth_map(path):
    m = {}
    for r in load_jsonl(path):
        lab = (r.get("label") or {}).get("is_unsafe")
        if isinstance(lab, bool):
            m[r["id"]] = lab
    return m


def auroc(rows):  # rows: (score, label_pos) ; label_pos: 1 unsafe / 0 safe
    pairs = [(s, l) for s, l in rows if s is not None]
    n_pos = sum(1 for _, l in pairs if l == 1)
    n_neg = len(pairs) - n_pos
    if n_pos == 0 or n_neg == 0:
        return None, f"degenerate (n_pos={n_pos}, n_neg={n_neg})"
    order = sorted(range(len(pairs)), key=lambda i: pairs[i][0])
    ranks = [0.0] * len(pairs)
    i = 0
    while i < len(pairs):
        j = i
        while j + 1 < len(pairs) and pairs[order[j + 1]][0] == pairs[order[i]][0]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    r_pos = sum(ranks[i] for i in range(len(pairs)) if pairs[i][1] == 1)
    return (r_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg), None


def confusion(joined, basis):
    tp = fp = tn = fn = 0
    for truth, pred, is_err in joined:
        if is_err:
            if basis == "answered_only":
                continue
            pred_unsafe = (truth is False)  # error counted wrong
        else:
            pred_unsafe = pred
        if truth and pred_unsafe:
            tp += 1
        elif truth and not pred_unsafe:
            fn += 1
        elif (not truth) and pred_unsafe:
            fp += 1
        else:
            tn += 1
    return tp, fp, tn, fn


def metr(tp, fp, tn, fn):
    n = tp + fp + tn + fn
    acc = (tp + tn) / n if n else None
    prec = tp / (tp + fp) if (tp + fp) else None
    rec = tp / (tp + fn) if (tp + fn) else None
    f1 = (2 * prec * rec / (prec + rec)) if (prec and rec) else (0.0 if (tp + fp and tp + fn) else None)
    pu = tp / (tp + fp) if (tp + fp) else 0.0
    ru = tp / (tp + fn) if (tp + fn) else 0.0
    f1u = 2 * pu * ru / (pu + ru) if (pu + ru) else 0.0
    ps = tn / (tn + fn) if (tn + fn) else 0.0
    rs = tn / (tn + fp) if (tn + fp) else 0.0
    f1s = 2 * ps * rs / (ps + rs) if (ps + rs) else 0.0
    macro = (f1u + f1s) / 2.0
    return acc, prec, rec, f1, macro


def wilson(k, n, z=1.96):
    """Wilson score 95% CI for a proportion k/n. Returns (low, high) or None."""
    if n == 0:
        return None
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / denom
    return max(0.0, center - half), min(1.0, center + half)


def fmt(x):
    return "N/A" if x is None else (f"{x:.4f}" if isinstance(x, float) else str(x))


def fmt_ci(ci):
    return "N/A" if ci is None else f"[{ci[0]:.3f},{ci[1]:.3f}]"


def run_meta(run_dir):
    p = os.path.join(BASE, run_dir, "run_metadata.json")
    if not os.path.exists(p):
        return None
    return json.load(open(p, encoding="utf-8"))


def main():
    rows_csv = []
    print("=" * 70)
    print("RECONCILIATION (recomputed answered_only head_binary vs metrics.md)")
    print("=" * 70)
    for tier, modality, label, run_dir, truth_path, guards, note in RUNS:
        tmap = truth_map(os.path.join(BASE, truth_path))
        meta = run_meta(run_dir)
        total = meta["counts"]["total"] if meta else None
        for guard in guards:
            pred_path = os.path.join(BASE, run_dir, "predictions", f"{guard}.predictions.jsonl")
            if not os.path.exists(pred_path):
                print(f"  MISSING predictions: {pred_path}")
                continue
            preds = load_jsonl(pred_path)
            joined, auc_rows = [], []
            answered = error = missing_truth = 0
            for p in preds:
                truth = tmap.get(p["id"])
                if truth is None:
                    missing_truth += 1
                    continue
                is_err = bool(p.get("error")) or (p["prediction"]["is_unsafe"] is None)
                pred = p["prediction"]["is_unsafe"]
                joined.append((truth, pred, is_err))
                if is_err:
                    error += 1
                else:
                    answered += 1
                    conf = p["prediction"].get("confidence")
                    auc_rows.append((conf, 1 if truth else 0))
            eligible = answered + error
            coverage = answered / eligible if eligible else None
            failure_rate = error / eligible if eligible else None
            skipped = (total - eligible) if total is not None else None
            auc, auc_note = auroc(auc_rows)
            for basis in ("answered_only", "failure_as_wrong"):
                tp, fp, tn, fn = confusion(joined, basis)
                acc, prec, rec, f1, macro = metr(tp, fp, tn, fn)
                fpr = fp / (fp + tn) if (fp + tn) else None
                rec_ci = wilson(tp, tp + fn)
                fpr_ci = wilson(fp, fp + tn)
                no_conf = all(c is None for c, _ in auc_rows)
                rows_csv.append({
                    "tier": tier, "modality": modality, "dataset": label,
                    "n_truth_records": len(tmap), "run": run_dir, "guard": guard,
                    "basis": basis, "eligible": eligible, "answered": answered,
                    "error": error, "skipped": fmt(skipped),
                    "coverage": fmt(coverage), "failure_rate": fmt(failure_rate),
                    "TP": tp, "FP": fp, "TN": tn, "FN": fn,
                    "accuracy": fmt(acc), "precision": fmt(prec), "recall": fmt(rec),
                    "recall_ci95": fmt_ci(rec_ci), "fpr": fmt(fpr), "fpr_ci95": fmt_ci(fpr_ci),
                    "f1_unsafe": fmt(f1), "macro_f1": fmt(macro),
                    "auroc": (("N/A(no continuous score)" if no_conf else fmt(auc))
                              if basis == "answered_only" else "N/A(basis)"),
                    "low_sample_warn": "yes" if (tp + fn) < 30 else "no",
                    "note": note + ("" if not missing_truth else f"; {missing_truth} rows missing truth"),
                })
            # reconciliation print
            key = (run_dir, guard)
            if key in RECON:
                tp, fp, tn, fn = confusion(joined, "answered_only")
                acc, _, rec, _, _ = metr(tp, fp, tn, fn)
                exp = RECON[key]
                ok = (abs(acc - exp["acc"]) < 0.002 and abs(rec - exp["recall"]) < 0.002)
                print(f"  {'OK ' if ok else 'MISMATCH'} {run_dir} {guard}: "
                      f"acc {acc:.4f} vs {exp['acc']} | recall {rec:.4f} vs {exp['recall']}")

    out_csv = "report_artifacts/result_summary.csv"
    with open(out_csv, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows_csv[0].keys()))
        w.writeheader()
        w.writerows(rows_csv)
    print(f"\nwrote {out_csv} ({len(rows_csv)} rows)")

    # ---- run inventory across all tiers (counts only) ----
    print("\n" + "=" * 70)
    print("RUN INVENTORY (tier classification by dir name)")
    print("=" * 70)

    def tier_of(name):
        if name in ("out_text_real", "out_judge_subset", "out_m3_real"):
            return "formal"
        if name in ("out_cpu_ref150", "out_cpu_crosscheck"):
            return "cpu-ref"
        if name == "out_e3":
            return "E3-recovery"
        if name in ("out_m2_threeguard", "out_m3_twoguard", "out_e2_newint8"):
            return "mechanism"
        if name in ("out_w4_j1", "out_w4_j4", "out_w1_check"):
            return "performance"
        return "smoke/dev"

    inv = []
    for root in (BASE, "guard-llama-guard", "guard-shieldgemma2"):
        for dirpath, _dirs, files in os.walk(root):
            if "run_metadata.json" in files and os.path.basename(dirpath).startswith("out_"):
                name = os.path.basename(dirpath)
                try:
                    m = json.load(open(os.path.join(dirpath, "run_metadata.json"), encoding="utf-8"))
                    c = m.get("counts", {})
                    inv.append((tier_of(name), dirpath.replace("\\", "/"), c.get("total"),
                                c.get("eligible"), c.get("predicted"), c.get("errors"),
                                m.get("warnings", {}).get("nan_fallback_recovered")))
                except Exception as e:
                    inv.append((tier_of(name), dirpath, "ERR", str(e)[:30], "", "", ""))
    for t in ("formal", "E3-recovery", "cpu-ref", "performance", "mechanism", "smoke/dev"):
        for r in sorted(inv):
            if r[0] == t:
                print(f"  [{r[0]:11}] {r[1]:55} total={r[2]} eligible={r[3]} "
                      f"predicted={r[4]} errors={r[5]}"
                      + (f" recovered={r[6]}" if r[6] else ""))
    print(f"\ntotal runs discovered: {len(inv)}")


if __name__ == "__main__":
    main()
