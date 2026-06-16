# M3.6 Plan — 判别效果优化（E1 默认阈值校准 + E2 栈升级隔离 spike）

> 契约：[`../M3.6_SPEC.md`](../M3.6_SPEC.md)。前置：M3.5 已交付（`56a8a94`）；`calibrate.py` 两侧已在（M3.5 commit `4a6b213`）。
> 路径：无前缀相对仓库根；`llama/`=guard-llama-guard、`sg2/`=guard-shieldgemma2。
> 原则：纯效果优化、`--threshold 0.5` 永远复现旧行为；E2 隔离不动主 env；现有 **llama 100 / sg2 99** 套件保持绿；真数据派生逐例产物 gitignore，committed 只放聚合。
> ⛔ 放行点：本计划经用户确认前不开工。

## 架构决策（落点已勘）

- **AD-1（关键，需确认）— llama 无阈值旋钮**：`llama_guard.predict` 是 **argmax 判定**（`is_unsafe` = 模型生成的 safe/unsafe token，llama_guard.py:187-189），confidence（归一化 `p_unsafe/(p_unsafe+p_safe)`）是事后算的。**E1 对 llama 不是改常量，而是加阈值机制**：`is_unsafe = (confidence >= threshold)`，confidence 不可得时回退 argmax（鲁棒）。`threshold=0.5` ≈ argmax 等价（argmax-unsafe ⟺ 归一化 p_unsafe>0.5），故 `--threshold 0.5` 复现旧行为。默认=calibrate 选出的 **0.55**。→ 这是 verdict-path 变更（不是"阈值以外"的逻辑变更，仍在 E1 授权内），但比 sg2 重。**OQ-1 已同意（2026-06-16）**。
- **AD-2 — sg2 改常量即可**：`shieldgemma2.py` 有 `DEFAULT_THRESHOLD=0.5`，`is_unsafe = max_yes >= self.threshold`（:213）。E1 改 `DEFAULT_THRESHOLD` 为 int8 生产校准值（build 时定）。
- **AD-3 — sweep 复用 `calibrate.py`**：sweep 表=calibrate 现有产物（calibration.md）；**flip analysis 是新计算**（无现成脚本），build 期一次性分析脚本从同一 predictions 的 confidence 在 0.5/新阈值下比对（产物即弃）。
- **AD-4 — 生产精度**：sg2 用 **int8 全量预测**（`out_m3_real`，80.6% 非 NaN）校准；llama 用本身生产分（`out_text_real`）。**不照搬 CPU 的 0.10**（§3A）。
- **AD-5 — 测试翻转**：sg2 `test_shieldgemma2` 的 `_patched_guard` 默认 0.5 判定会随默认变翻转 → 显式传 `threshold=0.5`；llama 新增阈值机制的离线判定测试（mock confidence）。caption-rule/rule（关键词,无阈值）不受影响。

## 依赖图

```
T1 sweep(两侧生产精度)+选 max_macro_f1 ─┬─► T3 应用默认(sg2 常量 + llama 阈值机制) ─► T4 flip analysis + before→after 矩阵
T2 llama 阈值机制(TDD, AD-1) ───────────┘                                            │
T5 E2 隔离 spike (并行,互不依赖) ──────────────────────────────────────────────────┤
                                                                                     ▼
                                                    Cγ(M3.6 交付门) ─► T6 best-known-config + M3.6_summary + push
```

## Phase A · E1（默认阈值校准落地）

### T1（E1a）生产精度 threshold sweep + 选点
**描述**：两侧跑 `calibrate.py`——sg2 对 int8 全量预测、llama 对本身预测——出 sweep 表（threshold × Acc/Macro-F1/Recall/FPR/coverage）；选 `max_macro_f1` 点为新默认候选。sweep 表写 `references/calibration-notes.md`（聚合）+ 运行产物 `out*/calibration/`。
**验收**：① 两侧 sweep 表存在；② 默认可追溯到选点——**llama=max_macro_f1 0.55、sg2(int8)=recall@FPR≤0.1 0.30**（OQ-2 已实跑定，§9-2）；③ calibration-notes 落库（聚合，含 max_macro_f1 与高召回两备选档）。
**验证**：跑 calibrate；读 calibration.md 确认 max_macro_f1 行。
**文件**：`*/references/calibration-notes.md`。**依赖**：无（数据在盘）。**规模**：S。

### T2（E1-llama 阈值机制，TDD · AD-1）
**描述**：给 `llama_guard` 加 `threshold` 配置：`is_unsafe = (confidence >= threshold)`，confidence 为 None 时回退 argmax verdict；默认取 T1 的 0.55。先写失败测试（mock confidence 在阈值两侧 + 回退路径 + `threshold=0.5` ≈ argmax）再实现。
**验收**：① mock confidence 0.6 vs 0.5 在 threshold 0.55 下判定正确；② confidence=None → 回退 argmax；③ `threshold=0.5` 与历史 argmax 判定一致（边界等价）；④ `--threshold` 可覆盖。
**验证**：`unittest`（新增 llama 阈值测试绿 + 全套绿）。
**文件**：`llama/scripts/guards/llama_guard.py`、`llama/tests/test_llama_threshold.py`（新）。**依赖**：T1（取值）。**规模**：M。

### T3（E1-应用默认）
**描述**：sg2 `DEFAULT_THRESHOLD` = **0.30**（int8 recall@FPR≤0.1）；llama adapter 默认 threshold = **0.55**；`--threshold` 覆盖保留 + config 回显；**测试翻转处置**（AD-5：sg2 判定用例显式 `threshold=0.5` + 新增"默认=校准值"断言）；黄金 `metrics.sample.json`/`output.sample` 若翻转则双路核算重锁。
**验收**：① 两侧默认=校准值；② `--threshold 0.5` 复现旧行为；③ 套件全绿（翻转用例显式化 + 默认断言）；④ 黄金重锁（如翻转）。
**验证**：`unittest` 两侧全绿；跑一条 `--threshold 0.5` 对照旧黄金。
**文件**：`sg2/scripts/guards/shieldgemma2.py`、`llama/scripts/guards/llama_guard.py`、两侧 tests + golden samples、`*/SKILL.md`、`*/references/io-contract.md`。**依赖**：T1、T2。**规模**：M。

### T4（E1-flip + before→after 矩阵）
**描述**：flip analysis（0.5→新默认）——聚合（总翻转/safe→unsafe/unsafe→safe/TP recovered/FP introduced/FP removed/FN introduced/borderline）落 `calibration-notes.md` 的 `Threshold Flip Analysis` 小节；逐例（id/truth/old/new/score/category）落 gitignored `reports/calibration/flip_analysis.{md,csv}`。新默认 vs 0.5 的 Acc/Macro-F1/Recall/FPR **before→after 对照表**（两侧，metrics.py 在两阈值下各跑）。
**验收**：① flip 聚合表存在且能解释 Macro-F1 变化来源；② before→after 对照表存在（llama 0.779→0.793、sg2 实测）；③ 逐例产物在 gitignore 路径。
**验证**：跑 metrics @0.5 与 @新值对照；核 flip 计数与 Macro-F1 变化自洽。
**文件**：`*/references/calibration-notes.md`、`reports/calibration/`（gitignore）。**依赖**：T3。**规模**：M。

## Phase B · E2（栈升级隔离 spike，与 Phase A 并行）

### T5（E2 spike）
**描述**：建隔离 conda env（`pytorch_dl_26`，torch≥2.6 + transformers≥4.53 + 匹配 bnb）；固定 **N=20 probe set**（合成 safe fixtures + 真 UnsafeBench 小样本覆盖 safe/violence/sexual/general_harm + 优先含历史 int8 NaN 样本；真图不可用则合成+M3 smoke 并标 limitation；记 id/生成方式，真图不入库）；**三向对照**（旧主 env int8 / 新 env int8 / CPU bf16）测 NaN rate / label agreement / confidence drift / coverage；结论 `fixed/not_fixed/blocked` + 数字落 `shieldgemma2-notes.md`。**主 env/requirements/代码零改动**。
**验收**：① spike env 隔离（主 env 套件仍 llama 100/sg2 99 绿）；② 四项 alignment 数字落库；③ 三选一结论 + 数字；④ 真图不入库。
**验证**：主 env 套件复跑绿；读 notes 的 E2 结论段。
**文件**：`sg2/references/shieldgemma2-notes.md`（结论）；probe/对照产物 gitignore。**依赖**：无（隔离）。**规模**：M。

## ☐ Checkpoint Cγ（M3.6 交付门）
E1：sweep 表 + flip analysis + 默认=max_macro_f1 + before→after 对照 + `--threshold 0.5` 可复现 + calibration caveats 入文档 + 黄金重锁 + 套件绿；E2：固定 probe + 四项 alignment + `fixed/not_fixed/blocked` 结论落 notes（**不要求修复成功，要求有据结论**）；leak 净。

## Phase C · 交付

### T6 best-known-config + M3.6_summary + push
**描述**：两侧 `references/best-known-config.md`（§3B YAML）；`root/M3.6_summary.md`（before→after 对照 + flip analysis + E2 spike 结论 + **仍存结构上限定位**：三策略天花板/judge 对抗鲁棒明确未解）；`.gitignore` 加 `reports/`；spec §10 全勾 sweep；泄漏自查（凭证/权重/真数据零命中）；push（直连 main，待用户点头）。
**验收**：§10 全勾或 N/A；best-known-config 两侧 + summary 汇总；leak 净。**依赖**：T1-T5 终态。**规模**：M。

## 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| AD-1 llama 改 argmax→阈值，连累 verdict 测试 | 中 | TDD 锁 `threshold=0.5`≈argmax 等价；confidence=None 回退 argmax；`--threshold 0.5` 兜底 |
| 默认翻转连累黄金/判定测试 | 中 | AD-5 显式传 0.5 解耦 + 双路核算重锁黄金 |
| sg2 int8 阈值在 19.4% NaN 数据上校准（NaN 行无 conf 被排除）| 低 | 仅在非 NaN 子集校准（calibrate 本就只用有 conf 行）；caveat §3A 注明 |
| E2 新 env 装不起来/版本冲突 | 中 | 限时；`blocked` 是合法结论；主 env 零改动兜底 |
| 逐例 flip 含真数据 id/label 误入库 | 中（泄漏） | committed 只放聚合；逐例落 gitignored `reports/`；交付前 git grep |

## 开放问题（✅ 已解决，2026-06-16）

- **OQ-1（AD-1）→ 同意**：llama 加阈值机制 `is_unsafe = confidence>=threshold`（conf=None 回退 argmax），默认 **0.55**、`--threshold 0.5`≈argmax。
- **OQ-2 → 看数字后定 sg2=0.30**：plan 阶段实跑 sg2 int8 sweep——max_macro_f1 落 thr=0.05/**FPR 0.383**（38% 误报，弃）；用户选 **recall@FPR≤0.1 @ 0.30**（Recall 0.125→0.198、FPR 0.051→0.089、Macro-F1 0.480→0.523）。详见 M3.6_SPEC §9-2。

## 非目标（M3.6 不做）

E3 NaN 回退（后续，§3C）；升主 env（E2 采纳需另 Ask-first）；SKILL 瘦身；M4 报告/打包。
