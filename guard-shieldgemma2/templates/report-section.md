# 报告模板 — 图像 Guard 章节（guard-shieldgemma2，M3）

> 占位符约定：`{{...}}` 由实跑结果填充；数据来源一律标注 `out_*/metrics/metrics.{json,md}` 与
> `references/shieldgemma2-notes.md`。引用任何数字前先读文末 Metric Caveats。

## 方法（图像侧）

- Guard：ShieldGemma 2 4B（`{{model_id}}`，量化口径 **int8**——4-bit 在实测环境全 NaN，见 notes §2）
  + caption-rule（caption/OCR 关键词，**pipeline 基线**，不读像素）。
- 判定：3 内置策略（dangerous/sexual/violence）逐策略 yes 概率；`is_unsafe = max(yes) ≥ {{threshold}}`
  （默认 0.5 = 模型卡默认，未校准）；`confidence = max(yes)`（unsafe 方向原生概率）。
- 类别映射：3 策略 → 22 类 canonical（M0 §4；粗细不对称见"分歧分析"）。

## 结果表占位

### 双 Guard comparison（head_binary，双口径）

{{粘贴 out_*/metrics/metrics.md 的 comparison 表；标注数据档状态：full_shieldgemma2 / partial_shieldgemma2_n / baseline_only / fallback_only}}

### 按类别 + taxonomy 分歧

{{粘贴 by-category 表；重点叙事：3 策略 vs 22 类的粗细不对称 —— divergence 计数与纯 FP 类别（如 dangerous→general_harm vs 真值 violence）}}

### 阈值敏感性（消融）

{{threshold sweep 表（任务 14）；案例：OOD 合成纹理在 0.5 判限下 FP、0.7 判限下 safe}}

### 量化口径（消融）

{{int8 vs CPU bf16 子集对照：判定翻转数 / confidence 漂移 / 延迟；附 4-bit NaN 实录结论}}

## 误判案例占位（3–5 例）

{{案例 1：棋盘格合成图 → dangerous 0.637（OOD 误报，阈值敏感）}}
{{案例 2–5：真实 UnsafeBench 数据到位后补}}

## Metric Caveats（引用数字前必读）

1. **数据档状态**：`{{result_tier}}`（四态取一）——fallback/合成数据仅做机制验证，不可作为最终结论；
   提交前以甲的真实 UnsafeBench 数据重跑。
2. **量化扰动**：int8 概率 ≠ 校准概率；跨 guard AUROC 对比须注明量化口径；阈值 0.5 未在评测集校准。
3. **caption-rule 是文本替身基线**：不读像素；其数字不得与图像模型混排无注记；caption/OCR 缺失即 error
   （在真实数据上 coverage 可能显著低于模型档——这本身是发现，不是噪声）。
4. **小样本**：≤500 张评测均为 low_sample/low_support 量级，只作趋势与机制验证，不作强结论。
