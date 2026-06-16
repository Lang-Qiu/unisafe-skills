# Calibration notes — guard-shieldgemma2（M3.6 E1）

> 阈值校准依据。位置=`scripts/calibrate.py` 的 ROC sweep（正类=unsafe；population=有连续 confidence 的 answered 行，与 AUROC 桶同；NaN 行无 conf、不参与）。
> **生产精度 = int8**：本表对 **int8 全量预测**（`out_m3_real`，1642 answered / 19.4% NaN 排除）校准——**不照搬 CPU bf16 的 0.10**（int8 与 CPU 分数分布不同，跨精度复用=误用，见 [M3.6_SPEC](../../M3.6_SPEC.md) §3A）。
> caveats（引用前必读）：M3.6_SPEC §3A。

## 1. Threshold sweep（int8 生产分，AUROC = 0.6133，n=1642）

| threshold | Acc | Recall | FPR | Macro-F1 |
|---|---|---|---|---|
| 0.05 | 0.5968 | 0.5662 | 0.3831 | **0.5877** |
| 0.10 | 0.6194 | 0.4108 | 0.2440 | 0.5833 |
| 0.15 | 0.6230 | 0.3338 | 0.1875 | 0.5674 |
| 0.20 | 0.6297 | 0.2738 | 0.1371 | 0.5536 |
| 0.25 | 0.6303 | 0.2262 | 0.1048 | 0.5358 |
| **0.30** | 0.6291 | 0.1985 | 0.0887 | 0.5228 |
| 0.40 | 0.6236 | 0.1523 | 0.0675 | 0.4961 |
| 0.50 | 0.6224 | 0.1246 | 0.0514 | 0.4797 |
| 0.70 | 0.6212 | 0.0677 | 0.0161 | 0.4411 |
| 0.90 | 0.6163 | 0.0369 | 0.0040 | 0.4145 |

（全 19 行 sweep 见运行产物 `out*/calibration/`，gitignore。）

## 2. 选点（候选 + 选定默认）

| 操作点 | threshold | Recall | FPR | Macro-F1 | 采用 |
|---|---|---|---|---|---|
| default（旧） | 0.50 | 0.125 | 0.051 | 0.480 | — |
| max_macro_f1 | 0.05 | 0.566 | **0.383** | 0.588 | ✗ 备选（FPR 38% 不可接受） |
| **recall@FPR≤0.1（新默认）** | **0.30** | 0.198 | 0.089 | 0.523 | ✅ **DEFAULT_THRESHOLD** |

**新默认 = 0.30**（用户 2026-06-16 看实测数字后定，M3.6_SPEC §9-2）：**不取 max_macro_f1**——它落在 0.05 / FPR 0.383（把 38% 良性图判有害，安全 guard 不可接受）；改取 FPR 受控点 0.30，把误报守在 ~9% 的同时 Recall 0.125→0.198、Macro-F1 0.480→0.523。`--threshold 0.5` 仍复现旧行为。

## 3. Threshold Flip Analysis（0.50 → 0.30）

> 逐例（id/truth/old/new/score/category）落 gitignored `reports/calibration/flip_shieldgemma2.md`（85 行），不入库。

**before→after（int8 全量，n=1642 answered）**：

| | Acc | Recall | FPR | Macro-F1 |
|---|---|---|---|---|
| before @0.5 | 0.6224 | 0.1246 | 0.0514 | 0.4797 |
| **after @0.30** | 0.6291 | 0.1985 | 0.0887 | **0.5228** |

**flip 聚合（降阈值 → 全是 safe→unsafe）**：总翻转 **85** ｜ safe→unsafe 85 ｜ unsafe→safe 0 ｜ **TP recovered 48** ｜ **FP introduced 37** ｜ FP removed 0 ｜ FN introduced 0 ｜ borderline(±0.05) 61。

**解释**：Macro-F1 0.480→0.523 来自降阈值召回的 **48 个 TP**（FN→TP，Recall 0.125→0.198）盖过新增的 **37 个 FP**（TN→FP，FPR 0.051→0.089）——净增益为正，且 FPR 仍守在 ~9%（这正是不取 max_macro_f1@0.05/FPR38% 的原因）。
