# dataset-wildguardmix

Dataset Skill（方向 A，文本主数据集）。把 [WildGuardMix](https://huggingface.co/datasets/allenai/wildguardmix) 转成统一 JSONL，通过 `dataset-format-checker`。

**状态**：scaffold（M0）。实现见 M1，分支 `feat/dataset-wildguardmix`。

- 源数据集：`allenai/wildguardmix`（gated，odc-by）。论文：WildGuard (NeurIPS 2024)。
- 评测集用 WildGuardTest（1,725 条）。
- 字段映射与约定：见 [`../M0_接口约定.md`](../M0_接口约定.md) §2、§4。
- 输出样例：见根目录 [`M0_dataset_unified_sample.jsonl`](../M0_dataset_unified_sample.jsonl) 的 `wildguardmix:*` 记录。

## 待办（M1）

- [ ] `scripts/main.py`：`load_dataset` + gated 认证失败提示（仿示例 `explain_load_error`）+ exit 2
- [ ] flat→unified 映射；null 标签跳过计数；编码 `errors="ignore"`
- [ ] `references/category_mapping.json`：dump subcategory unique 值后补全 → 22 类
- [ ] `metadata.json`：样本数、标签比例、按类别/对抗分布、skipped、load_errors
- [ ] `tests/test_validate.py`（+ `fixtures/` 微型样本）+ 自跑 checker = exit 0
