# guard-shieldgemma2

Guard Skill（方向 B，多模态亮点）。在统一 image_safety JSONL 上运行图像 Guard 并输出统一判断 + 指标。

**状态**：scaffold（M0）。实现见 M3，分支 `feat/guard-shieldgemma2`。

- Guard：[ShieldGemma 2-4B](https://huggingface.co/google/shieldgemma-2-4b-it)（本地，gated，3 策略：性/暴力血腥/危险内容）+ OpenAI omni-moderation（图像，API 交叉验证）。
- 指标：Accuracy / Macro-F1 / Recall / FPR（含 Safe 样本）。
- 与文本 Guard **完全相同**的统一输出 schema → 证明接口跨模态零改动。
- 接口/映射/指标：见 [`../M0_接口约定.md`](../M0_接口约定.md) §4、§5、§6。

## 待办（M3）

- [ ] ShieldGemma 2 逐策略推理；per-policy 概率 → `confidence`
- [ ] OpenAI omni 图像交叉验证
- [ ] 3 策略 → 22 类映射；小样本（200–500 张）
