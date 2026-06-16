# Calibration notes — guard-llama-guard（M3.6 E1）

> 阈值校准依据。位置=`scripts/calibrate.py` 的 ROC sweep（正类=unsafe；population=有连续 confidence 的 answered 行）。
> **生产精度 = 本身（非量化）**：本表对 llama-guard 全量预测（`out_text_real`，1911 answered）校准。
> **机制说明**：llama-guard 原生是 **argmax 判定**（生成 safe/unsafe token）；M3.6 E1 给 adapter 加阈值旋钮 `is_unsafe = (confidence ≥ threshold)`（confidence=None 回退 argmax），`threshold=0.5` ≈ argmax 等价。
> caveats：M3.6_SPEC §3A。

## 1. Threshold sweep（生产分，AUROC = 0.8881，n=1911）

| threshold | Acc | Recall | FPR | Macro-F1 |
|---|---|---|---|---|
| 0.05 | 0.6813 | 0.8830 | 0.3512 | 0.6063 |
| 0.10 | 0.7535 | 0.8566 | 0.2631 | 0.6641 |
| 0.20 | 0.8179 | 0.7925 | 0.1780 | 0.7165 |
| 0.30 | 0.8540 | 0.7472 | 0.1288 | 0.7490 |
| 0.40 | 0.8734 | 0.7132 | 0.1009 | 0.7670 |
| 0.45 | 0.8823 | 0.6830 | 0.0857 | 0.7736 |
| 0.50 | 0.8885 | 0.6642 | 0.0753 | 0.7788 |
| **0.55** | 0.9016 | 0.6377 | 0.0559 | **0.7928** |
| 0.60 | 0.9042 | 0.6113 | 0.0486 | 0.7919 |
| 0.70 | 0.9063 | 0.5698 | 0.0395 | 0.7871 |
| 0.90 | 0.9011 | 0.3811 | 0.0152 | 0.7308 |

（全 19 行 sweep 见运行产物 `out*/calibration/`，gitignore。）

## 2. 选点（候选 + 选定默认）

| 操作点 | threshold | Recall | FPR | Macro-F1 | 采用 |
|---|---|---|---|---|---|
| default（旧，≈argmax） | 0.50 | 0.664 | 0.075 | 0.779 | — |
| **max_macro_f1（新默认）** | **0.55** | 0.638 | 0.056 | **0.793** | ✅ **默认 threshold** |
| recall@FPR≤0.1 | 0.45 | 0.683 | 0.086 | 0.774 | 备选（高召回档） |

**新默认 = 0.55**（max_macro_f1，温和无争议）：FPR 0.075→**0.056**（误报反降）、Macro-F1 0.779→**0.793**、Recall 0.664→0.638（小降）。`--threshold 0.5` 复现旧 argmax 行为。高召回档（0.45）留备选。

## 3. Threshold Flip Analysis（0.50 → 0.55）

> 聚合见下（T4 填）；逐例（id/truth/old/new/score/category）落 gitignored `reports/calibration/`，不入库。

_（T4 落地后填：总翻转 / safe→unsafe / unsafe→safe / TP recovered / FP introduced / FP removed / FN introduced / borderline，并解释 Macro-F1 0.779→0.793 来源。）_
