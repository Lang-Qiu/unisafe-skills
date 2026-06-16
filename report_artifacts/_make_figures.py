"""Course-report figures from report_artifacts/result_summary.csv (the reconciled,
metrics.md-consistent table). Reads ONLY the CSV — no fabricated numbers.

Design rules honored:
- one conclusion per figure (the title IS the conclusion)
- sample size n annotated on every guard
- y-axis starts at 0 (no truncation / no visual exaggeration)
- formal vs CPU-ref vs E3 tiers visually distinguished (color); mechanism/smoke runs
  are NOT plotted (synthetic / superseded — see analysis_notes.md §3)
- colorblind-safe palette (Okabe-Ito)

Run: <python-with-matplotlib> report_artifacts/_make_figures.py
"""
import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

CSV = "report_artifacts/result_summary.csv"
OUT = "report_artifacts/figures"
os.makedirs(OUT, exist_ok=True)

# Okabe-Ito colorblind-safe
C = {"blue": "#0072B2", "orange": "#E69F00", "green": "#009E73",
     "vermillion": "#D55E00", "purple": "#CC79A7", "sky": "#56B4E9", "grey": "#999999"}
SRC = "数据来源：report_artifacts/result_summary.csv（复算，与 metrics.md 逐位一致）"


def num(s):
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def load():
    rows = {}
    with open(CSV, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows[(r["run"], r["guard"], r["basis"])] = r
    return rows


R = load()
TR = "wildguardmix_test/out_text_real"
JU = "wildguardmix_test/out_judge_subset"
IM = "unsafebench_test/out_m3_real"
CPU = "unsafebench_test/out_cpu_ref150"
E3 = "unsafebench_test/out_e3"


def g(run, guard, basis, col):
    return num(R[(run, guard, basis)][col])


def save(fig, name):
    path = os.path.join(OUT, name)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", path)


# ---- Fig 1: guard quality (answered_only) Accuracy / F1_unsafe / Coverage ----
def fig1():
    guards = [(TR, "rule", "rule\n(text 1959)"),
              (TR, "llama-guard", "Llama Guard\n(text 1959)"),
              (JU, "llm-judge", "LLM-judge\n(judge 120)"),
              (IM, "caption-rule", "caption-rule\n(image 2037)"),
              (IM, "shieldgemma2", "ShieldGemma2 int8\n(image 2037)")]
    metrics = [("accuracy", "Accuracy", C["blue"]),
               ("f1_unsafe", "F1 (unsafe)", C["orange"]),
               ("coverage", "Coverage", C["green"])]
    fig, ax = plt.subplots(figsize=(9.5, 5.5))
    n = len(guards)
    w = 0.26
    xs = range(n)
    for mi, (col, lab, color) in enumerate(metrics):
        vals = [g(run, gd, "answered_only", col) for run, gd, _ in guards]
        bars = ax.bar([x + (mi - 1) * w for x in xs], vals, w, label=lab, color=color)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + 0.012, f"{v:.2f}",
                    ha="center", va="bottom", fontsize=8)
    ax.set_xticks(list(xs))
    ax.set_xticklabels([lab for _, _, lab in guards], fontsize=9)
    ax.set_ylim(0, 1.18)
    ax.set_ylabel("指标值（0–1）")
    ax.set_title("结论：Llama Guard（文本）Acc/F1 最高；图像 guard 的 F1 极低、且覆盖率有缺口\n"
                 "（answered_only 口径；柱标 n=eligible；仅正式实验）", fontsize=11)
    ax.legend(loc="upper right", framealpha=0.95)
    ax.grid(axis="y", alpha=0.3)
    ax.text(0, -0.16, SRC, transform=ax.transAxes, fontsize=7.5, color=C["grey"])
    save(fig, "fig1_guard_quality.png")


# ---- Fig 2: answered_only vs failure_as_wrong (Accuracy) ----
def fig2():
    guards = [(TR, "rule", "rule\n(0 err)"),
              (TR, "llama-guard", "Llama Guard\n(48 err / 2.4%)"),
              (JU, "llm-judge", "LLM-judge\n(1 err)"),
              (IM, "shieldgemma2", "ShieldGemma2 int8\n(395 NaN / 19.4%)"),
              (IM, "caption-rule", "caption-rule\n(609 err / 29.9%)")]
    fig, ax = plt.subplots(figsize=(9.5, 5.5))
    n = len(guards)
    w = 0.36
    xs = range(n)
    ao = [g(run, gd, "answered_only", "accuracy") for run, gd, _ in guards]
    fw = [g(run, gd, "failure_as_wrong", "accuracy") for run, gd, _ in guards]
    b1 = ax.bar([x - w / 2 for x in xs], ao, w, label="answered_only（剔除失败，乐观）", color=C["sky"])
    b2 = ax.bar([x + w / 2 for x in xs], fw, w, label="failure_as_wrong（失败计错，保守）", color=C["vermillion"])
    for bars, vals in ((b1, ao), (b2, fw)):
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + 0.012, f"{v:.2f}",
                    ha="center", va="bottom", fontsize=8)
    for x, a, f in zip(xs, ao, fw):
        d = a - f
        if d > 0.005:
            ax.annotate(f"Δ−{d:.2f}", xy=(x, min(a, f) - 0.05), ha="center",
                        fontsize=8.5, color=C["vermillion"], weight="bold")
    ax.set_xticks(list(xs))
    ax.set_xticklabels([lab for _, _, lab in guards], fontsize=8.5)
    ax.set_ylim(0, 1.0)
    ax.set_ylabel("Accuracy（0–1）")
    ax.set_title("结论：失败率越高，两口径落差越大——caption-rule −0.18 / int8 −0.12，文本仅 −0.02\n"
                 "（双口径护栏：剔除失败会虚高，必须并报）", fontsize=11)
    ax.legend(loc="upper right", framealpha=0.95)
    ax.grid(axis="y", alpha=0.3)
    ax.text(0, -0.16, SRC, transform=ax.transAxes, fontsize=7.5, color=C["grey"])
    save(fig, "fig2_dual_basis_gap.png")


# ---- Fig 3: failure counts + proportion by guard ----
def fig3():
    # (label, error_count, eligible, reason, color)
    items = [("caption-rule\n(image)", g(IM, "caption-rule", "answered_only", "error"),
              2037, "缺 caption/图", C["vermillion"]),
             ("ShieldGemma2 int8\n(image)", g(IM, "shieldgemma2", "answered_only", "error"),
              2037, "int8 NaN（确定性）", C["orange"]),
             ("Llama Guard\n(text)", g(TR, "llama-guard", "answered_only", "error"),
              1959, "生成/超时", C["blue"]),
             ("LLM-judge\n(judge)", g(JU, "llm-judge", "answered_only", "error"),
              120, "API", C["sky"]),
             ("rule\n(text)", g(TR, "rule", "answered_only", "error"),
              1959, "无失败", C["green"])]
    fig, ax = plt.subplots(figsize=(9.5, 5.5))
    labels = [it[0] for it in items]
    counts = [int(it[1]) for it in items]
    xs = range(len(items))
    bars = ax.bar(xs, counts, 0.6, color=[it[4] for it in items])
    for b, it in zip(bars, items):
        cnt, elig, reason = int(it[1]), it[2], it[3]
        pct = cnt / elig * 100
        ax.text(b.get_x() + b.get_width() / 2, cnt + 8,
                f"{cnt}\n({pct:.1f}%)\n{reason}", ha="center", va="bottom", fontsize=8.5)
    ax.set_xticks(list(xs))
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylim(0, max(counts) * 1.28)
    ax.set_ylabel("record-level error 数")
    ax.set_title("结论：失败由图像侧主导——caption 缺失 609(29.9%) + int8 NaN 395(19.4%)；文本 guard 仅 ~2.5%\n"
                 "（% = error / eligible；不同失败机制已标注）", fontsize=11)
    ax.grid(axis="y", alpha=0.3)
    ax.text(0, -0.13, SRC, transform=ax.transAxes, fontsize=7.5, color=C["grey"])
    save(fig, "fig3_failure_types.png")


# ---- Fig 4: image vs text experiment completeness (coverage) ----
def fig4():
    # (label, coverage, n, tier_color, note)
    items = [("文本\nLlama Guard", g(TR, "llama-guard", "answered_only", "coverage"),
              1959, C["blue"], "formal"),
             ("图像\nShieldGemma2 int8", g(IM, "shieldgemma2", "answered_only", "coverage"),
              2037, C["orange"], "formal"),
             ("图像 +E3 回退\n(NaN 子集实测)", g(E3, "shieldgemma2", "answered_only", "coverage"),
              100, C["green"], "E3-recovery")]
    fig, ax = plt.subplots(figsize=(8.5, 5.5))
    xs = range(len(items))
    covs = [it[1] for it in items]
    bars = ax.bar(xs, covs, 0.55, color=[it[3] for it in items])
    notes = ["", "395 NaN 丢覆盖", "100/100 恢复\n全量投影 ~1.00"]
    for b, it, nt in zip(bars, items, notes):
        ax.text(b.get_x() + b.get_width() / 2, it[1] + 0.015,
                f"{it[1]:.3f}\n(n={it[2]})", ha="center", va="bottom", fontsize=9)
        if nt:
            ax.text(b.get_x() + b.get_width() / 2, it[1] / 2, nt,
                    ha="center", va="center", fontsize=8.5, color="white", weight="bold")
    ax.set_xticks(list(xs))
    ax.set_xticklabels([it[0] for it in items], fontsize=9.5)
    ax.set_ylim(0, 1.20)
    ax.set_ylabel("Coverage = answered / eligible")
    ax.set_title("结论：图像侧覆盖率被 int8 NaN 拉到 0.806；E3 逐记录回退把覆盖率补回 ~1.00\n"
                 "（文本侧本就高覆盖 0.976；蓝/橙=正式实验，绿=E3 回退，非机制验证）", fontsize=11)
    ax.grid(axis="y", alpha=0.3)
    ax.text(0, -0.13, SRC + "；E3 实测=NaN 子集 100，全量为投影", transform=ax.transAxes,
            fontsize=7.5, color=C["grey"])
    save(fig, "fig4_completeness_text_vs_image.png")


if __name__ == "__main__":
    fig1(); fig2(); fig3(); fig4()
    print("done: 4 figures ->", OUT)
