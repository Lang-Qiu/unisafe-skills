# UniSafe Skills

> Skill-Native 统一安全实验平台 — 期末作业（方向 A 数据集 + 方向 B Guard 配套）。

本仓库实现 4 个可复用 Skill，把 **内容安全数据集 → 统一 JSONL → Guard 安全判断 → 评测指标** 做成一条可被统一平台**发现、调用、组合、复现**的流水线。文本为评分主干，图文多模态为亮点章节，二者共用同一套统一 schema 与 Guard 结果接口——证明该抽象可跨模态泛化。

## 🧭 导航

| 文档 | 用途 |
|---|---|
| [团队分工计划.md](团队分工计划.md) | 角色归属、A/B 任务清单、里程碑、贡献度、风险 |
| [M0_接口约定.md](M0_接口约定.md) | **接口契约**：统一 schema、字段读取、22 类 taxonomy 映射表、Guard 输出 schema、指标定义 |
| [M0_dataset_unified_sample.jsonl](M0_dataset_unified_sample.jsonl) | 7 条统一数据样本（text+image），已实跑 `dataset-format-checker` = PASS |
| [M0_guard_output_sample.jsonl](M0_guard_output_sample.jsonl) | Guard 输出目标样本（含超时/空输出异常处理示例） |

## 流水线

```
原始安全数据集 ──[Dataset Skill]──> 统一 JSONL ──[Guard Skill]──> 统一判断 ──> 指标(Acc/Macro-F1/AUROC/Recall/FPR/Over-refusal)
                          ↑ 必须通过 dataset-format-checker (exit 0)
```

## Skills

| Skill | 方向 | 模态 | 负责人 | 分支 | 状态 |
|---|---|---|---|---|---|
| [`dataset-wildguardmix`](dataset-wildguardmix/) | A · 数据集 | 文本 | 同学甲 | `feat/dataset-wildguardmix` | 🟡 scaffold (M1) |
| [`dataset-unsafebench`](dataset-unsafebench/) | A · 数据集 | 图像 | 同学甲 | `feat/dataset-unsafebench` | 🟡 scaffold (M3) |
| [`guard-llama-guard`](guard-llama-guard/) | B · Guard | 文本 | 同学乙 | `feat/guard-llama-guard` | 🟡 scaffold (M1) |
| [`guard-shieldgemma2`](guard-shieldgemma2/) | B · Guard | 图像 | 同学乙 | `feat/guard-shieldgemma2` | 🟡 scaffold (M3) |

`guard-llama-guard` 内含规则基线与 OpenAI Moderation 两个对比 Guard。

## 数据与模型（不入库）

`.gitignore` 已排除示例 skill、数据集、模型权重、图片缓存——**不要把数据集或权重提交进 git**。请从原始来源获取：

- WildGuardMix — https://huggingface.co/datasets/allenai/wildguardmix （gated, odc-by）
- XSTest — https://huggingface.co/datasets/walledai/XSTest
- UnsafeBench — https://huggingface.co/datasets/yiting/UnsafeBench
- Llama Guard 3 — https://huggingface.co/meta-llama/Llama-Guard-3-1B （gated）
- ShieldGemma 2 — https://huggingface.co/google/shieldgemma-2-4b-it （gated）
- OpenAI Moderation — https://developers.openai.com/api/docs/guides/moderation

## 分支策略

- `main` = 共享基线（M0 文档 + 接口契约 + scaffold）。
- 两人按里程碑开 feature 分支，独立开发、PR 合回 `main`。
- ⚠️ **`M0_接口约定.md` 一旦改动，立即开 PR 并通知对方** —— 这是数据集与 Guard 之间唯一契约，避免接口漂移。

## 里程碑

M0 接口契约 ✅ → M1 文本核心 E2E → M2 多 Guard 对比+over-refusal → M3 多模态亮点 → M4 报告+截图+打包。

## 安全声明

数据集可能含有害/冒犯内容，仅用于安全研究、审核基准与防御性评测；请遵守各源数据集与模型的 license 与访问条款。
