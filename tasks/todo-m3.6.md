# M3.6 Todo — 判别效果优化（v1）

> 详细验收/验证见 [`plan-m3.6.md`](plan-m3.6.md)；契约见 [`../M3.6_SPEC.md`](../M3.6_SPEC.md)。
> 路径：无前缀相对仓库根；`llama/`=guard-llama-guard、`sg2/`=guard-shieldgemma2。
> 标记：完成打 `x`；做不到的项**不删**，标 `N/A(原因→顺延)`。
> 交付底线：**Cγ 硬依赖 T1-T4(E1) + T5(E2 有据结论) + 套件绿 + leak净**；`--threshold 0.5` 永远复现旧行为。
> ⛔ **执行放行点：本 todo 在用户放行前不开工**；**OQ-1/OQ-2 需先定**（见 plan）。

## Phase A · E1（默认阈值校准落地）

- [x] 任务 1（E1a）生产精度 sweep（commit `a6947b1`）：sg2 int8（AUROC 0.6133）+ llama（AUROC 0.8881）sweep 表落各自 `references/calibration-notes.md`；选点 **llama=max_macro_f1 0.55 / sg2(int8)=recall@FPR≤0.1 0.30**（实测定，不照搬 CPU 0.10、不取 sg2 max_macro_f1=0.05/FPR38%）；max_macro_f1 与高召回两备选档留档
- [x] 任务 2（E1-llama 阈值机制，TDD · AD-1）：`llama_guard` 加 `_apply_threshold`（`is_unsafe=confidence>=threshold`，conf=None 回退 argmax）+ `DEFAULT_THRESHOLD=0.55` + `_parse_one` 调用 + main `--threshold`（default None→adapter 0.55）+ config 回显；**5 测试绿**（默认 0.55/覆盖/阈值两侧/回退/0.5≈argmax）；llama 105 全绿无回归（M · 依赖 T1）
- [x] 任务 3（E1-应用默认）：sg2 `DEFAULT_THRESHOLD` 0.5→**0.30** + sg2 main `--threshold` default 0.5→None（adapter 拥有默认）+ docstring/SKILL/io 注；唯一翻转用例 `test_all_under_threshold_is_safe` 显式 `threshold=0.5` + 新增 `test_default_threshold_is_calibrated_030`；**黄金未翻**（caption-rule 基线无阈值，无需重锁）；llama 默认 0.55（T2 已落）+ SKILL 注；`--threshold 0.5` 复现旧行为；**sg2 100/llama 105 全绿**（M · 依赖 T1,T2）
- [ ] 任务 4（E1-flip + 对照）：flip analysis（0.5→新）聚合（总翻转/safe↔unsafe/TP recovered/FP intro/FP removed/FN intro/borderline）落 calibration-notes，逐例落 **gitignored** `reports/calibration/`；新默认 vs 0.5 的 Acc/MacroF1/Recall/FPR **before→after** 对照表（M · 依赖 T3）

## Phase B · E2（栈升级隔离 spike，并行）

- [ ] 任务 5（E2 spike）：隔离 `pytorch_dl_26`（torch≥2.6/transformers≥4.53/bnb）；固定 **N=20 probe**（合成+真小样本覆盖 safe/violence/sexual/general_harm+历史 NaN 样本优先；真图不入库记 id/生成方式）；三向对照（旧 int8/新 int8/CPU bf16）测 NaN rate·label agreement·confidence drift·coverage；结论 `fixed/not_fixed/blocked`+数字落 `shieldgemma2-notes.md`；**主 env 零改动**（M · 依赖无）

### ☐ Checkpoint Cγ（M3.6 交付门）：E1 sweep+flip+默认=maxF1+before→after+`--threshold 0.5`复现+caveats入档+黄金重锁+套件绿；E2 固定probe+四项alignment+三选一结论；leak净

## Phase C · 交付

- [ ] 任务 6：两侧 `references/best-known-config.md`（§3B YAML）+ `root/M3.6_summary.md`（before→after + flip + E2 结论 + **仍存结构上限定位**）+ `.gitignore` 加 `reports/` + spec §10 全勾 + 泄漏自查 + push（M · 依赖 T1-T5 终态）

## 开放问题（✅ 已解决 2026-06-16）

- **OQ-1 → 同意**：llama 加阈值机制（conf≥threshold，conf=None 回退 argmax），默认 **0.55**。
- **OQ-2 → sg2 默认 0.30**：实跑 int8 sweep，max_macro_f1=0.05/FPR 38% 弃；选 **recall@FPR≤0.1 @ 0.30**（Recall 0.125→0.198、FPR 0.051→0.089、Macro-F1 0.480→0.523）。

## 非目标（登记防漏）

E3 NaN 回退（后续 §3C）；升主 env（E2 采纳另 Ask-first）；SKILL 瘦身；M4 报告/打包。
