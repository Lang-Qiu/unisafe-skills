# guard-llama-guard

Guard Skill（方向 B，文本主 Guard）。在统一 JSONL 上运行三个文本 Guard 并输出统一判断 + 指标。

**状态**：scaffold（M0）。实现见 M1，分支 `feat/guard-llama-guard`。

- Guard：[Llama Guard 3-1B](https://huggingface.co/meta-llama/Llama-Guard-3-1B)（本地, MLCommons S1-S14）+ 规则关键词基线（stdlib）+ [OpenAI Moderation](https://developers.openai.com/api/docs/guides/moderation)（API）。
- 指标：Accuracy / Macro-F1 / Recall / FPR / AUROC / Over-refusal Rate。
- 接口/映射/指标定义：见 [`../M0_接口约定.md`](../M0_接口约定.md) §3、§4、§5、§6。
- 先用根目录 [`M0_dataset_unified_sample.jsonl`](../M0_dataset_unified_sample.jsonl) 开发；目标输出形如 [`M0_guard_output_sample.jsonl`](../M0_guard_output_sample.jsonl)。

## 待办（M1）

- [ ] `scripts/guards/`：llama_guard / rule_based / openai_moderation 三个适配器
- [ ] 异常/超时/空输出 → `error` 字段 + 计入 metadata，不崩
- [ ] 标签映射 S1-S14 / OpenAI → 22 类（`references/category_mapping.json`）
- [ ] `scripts/metrics.py`：多 Guard × 多任务对比 + 对抗分桶 + over-refusal
- [ ] AUROC 用连续分（Llama Guard token 概率 / OpenAI scores）；规则基线无 AUROC
