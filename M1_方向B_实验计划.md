# 方向 B 实验计划：多 Guard 统一安全基准对比

> 来源：experiment-agent `plan` 模式（代码实验路径），消费 ARS Stage 1（RQ Brief + Methodology Blueprint）+ [`M0_接口约定.md`](M0_接口约定.md)。
> 本文件只设计、不执行。执行见衔接步骤。

## Material Passport

```yaml
passport_id: dirB-guard-eval-plan-v1
artifact_type: code_experiment_plan
pipeline_stage: experiment-agent / plan (code path)
upstream: [ARS Stage1 RQ-Brief + Methodology-Blueprint, M0_接口约定.md]
created_at: 2026-06-09
created_by: experiment-agent (plan mode)
status: DESIGN-COMPLETE (not yet executed)
reproducibility: {seed: 42, version_pinning: required, deterministic_decode: true}
produces: [guard_output JSONL ×6, metrics_tables, plots, run metadata.json]
constraint: 展现实验流程优先；结论保守（图像侧为抽样）
```

---

## 1. 研究问题与假设

- **主 RQ**：Llama Guard 3 / WildGuard / 规则基线 / OpenAI Moderation / ShieldGemma 2 在统一基准上的设计、taxonomy 与评测表现异同（见 Stage 1 Brief）。
- **工作假设（待检验，非预设结论）**：
  - H1：学习型 Guard（Llama/WildGuard/OpenAI）在 Recall 上显著高于规则基线。
  - H2：各 Guard 在 over-refusal（XSTest）上存在差异，规则基线 FPR 最高。
  - H3：主场模型 WildGuard 在 WildGuardTest 上优于客场 Guard，但优势随任务变化。

## 2. 变量

| 类别 | 内容 |
|---|---|
| 自变量 IV | Guard(6) × 任务(prompt/response/refusal/image) × 样本类型(对抗/普通) |
| 因变量 DV | Accuracy、Macro-F1、AUROC、Recall、FPR、Over-refusal Rate、latency_ms |
| 控制变量 | 同批样本、每 Guard 固定官方 prompt 模板、seed=42、同一 GPU、统一阈值策略、temperature=0 |
| 效度威胁 | taxonomy 映射分歧、prompt 模板敏感性、阈值选择、类别不平衡、图像抽样代表性 |

## 3. 实验设计

**配对式跨模型基准对比**（observational benchmark，非干预）。同一批样本喂给所有 Guard → 支持配对统计（McNemar）。

## 4. 实验矩阵

| Guard | 模态 | prompt 危害 | response 危害 | 拒答检测 | over-refusal | 图像 | AUROC 连续分来源 |
|---|---|---|---|---|---|---|---|
| Llama Guard 3-1B | text | ✓ | ✓ | — | ✓ | — | unsafe-token 概率 |
| WildGuard 7B | text | ✓ | ✓ | ✓ 原生 | ✓ | — | yes/no token logit（无则标 N/A） |
| 规则基线 | text | ✓ | (可选) | — | ✓ | — | 无 → AUROC N/A（诚实标注） |
| OpenAI Moderation | text+img | ✓ | ✓ | — | ✓ | ✓ | category_scores 最大值 |
| ShieldGemma 2-4B | image | — | — | — | — | ✓ | 逐策略 yes-prob 取最大 |

> 第 6 个 Guard 为 OpenAI omni-moderation（图像），与文本侧 OpenAI 同源、跨模态复用。

## 5. 数据与样本（seed=42，分层抽样）

| 数据集 | 规模 | 真值字段 | 用途 |
|---|---|---|---|
| WildGuardTest | 全 1,725 | prompt_is_unsafe / response_is_unsafe / is_refusal / adversarial / subcategory | 主评测（三任务+对抗分桶+按类别） |
| XSTest | 全 450（250 safe + 200 unsafe） | over_refusal_probe | Over-refusal 专测 |
| UnsafeBench | 抽 1,000（Safe/Unsafe 均衡） | is_unsafe / category | 图像安全（含 FPR） |

数据由方向 A 的 `dataset-*` 产出统一 JSONL；阻塞时先用 [`M0_dataset_unified_sample.jsonl`](M0_dataset_unified_sample.jsonl) 联调。

## 6. 评测协议

- **真值对齐**：严格按 [`M0_接口约定.md`](M0_接口约定.md) §3 表（prompt 任务读 `prompt_is_unsafe`，response 任务读 `response_is_unsafe`，拒答读 `is_refusal`，图像读 `is_unsafe`）。
- **prompt 模板**：每个 Guard 用其**官方模板**（Llama Guard 官方 category 模板 / WildGuard 官方指令格式 / ShieldGemma 官方 policy 提示），固定并记录。
- **阈值策略**：二分指标（Acc/F1/Recall/FPR）用 Guard **原生决策**；AUROC 用连续分（来源见矩阵末列）；附**阈值敏感性曲线**（0.1–0.9 扫描）。
- **taxonomy 映射**：Guard 原生标签 → 22 类，用各自 `config/category_mapping.json`（与 §4 映射表一致），原值留 `raw_output`。

## 7. 指标与统计分析

- **指标定义**：正类=unsafe；FPR=FP/(FP+TN)；Macro-F1=safe/unsafe 两类 F1 均值；Over-refusal=XSTest safe 子集上的 FPR。
- **点估计 + bootstrap 95% CI**（每指标每 Guard，重采样 1000 次，seed 固定）。
- **配对显著性**：Guard 两两 McNemar 检验（同批样本），**Holm 多重比较校正**。
- **按类别 Macro-F1**：WildGuardTest `subcategory` 桶 + UnsafeBench `category` 桶，**附 taxonomy 分歧注释**（如 phishing 在 Llama Guard 归 S2/illicit、数据集归 cyber）。
- **对抗 vs 普通**：WildGuardTest 按 `adversarial` 分桶分别报指标。
- **产出表**：Guard × 任务 主指标矩阵 + per-category 表 + 对抗分桶表 + over-refusal 排行 + latency 表。

## 8. 运行环境与依赖

GPU（本地 Llama Guard 1B / WildGuard 7B / ShieldGemma2 4B）+ HF（可 `HF_ENDPOINT=https://hf-mirror.com`）+ OpenAI API。**版本钉死**：`torch`/`transformers`/`datasets`/`openai` SDK 版本 + 各模型 commit hash，写入 `metadata.json`。

## 9. 可复现性与鲁棒性（对应评分 30%）

- `seed=42` 贯穿抽样与 bootstrap；生成式 Guard `do_sample=False`。
- **异常处理**：本地超时（默认 30s/样本）、API 重试（指数退避，最多 3 次）、空/不可解析输出 → `prediction.is_unsafe=null` + `error` 字段，**剔除出指标并计入 `metadata.errors`**（见 [`M0_guard_output_sample.jsonl`](M0_guard_output_sample.jsonl) 第 4 条）。
- **断点续跑**：逐样本结果缓存（按 `id`），重跑不重复推理。
- **gated 失败**：仿示例 `explain_load_error` 给可复制修复提示，exit code 规范（0/2）。
- `metadata.json`：样本数、各 Guard 成功/失败/uncertain 计数、版本、命令、耗时。

## 10. 执行步骤（命令骨架，先 smoke test）

```bash
# 0) 联调：先用手写样本验证管线
python guard-llama-guard/src/main.py --input M0_dataset_unified_sample.jsonl \
  --guards llama_guard,rule,openai --out runs/smoke/ --max-samples 7

# 1) 文本全量（4 Guard × prompt/response/refusal + XSTest）
python guard-llama-guard/src/main.py --input data/unified/wildguardtest.jsonl \
  --guards llama_guard,wildguard,rule,openai --seed 42 --out runs/text/
python guard-llama-guard/src/main.py --input data/unified/xstest.jsonl \
  --guards llama_guard,wildguard,rule,openai --task over_refusal --out runs/xstest/

# 2) 图像（ShieldGemma2 + OpenAI omni，UnsafeBench 1000）
python guard-shieldgemma2/src/main.py --input data/unified/unsafebench_1k.jsonl \
  --guards shieldgemma2,openai_omni --seed 42 --out runs/image/

# 3) 指标 + CI + McNemar + 图
python guard-llama-guard/src/metrics.py --runs runs/ --out reports/metrics/
```

## 11. 预期产出物

6 份 `guard_output*.jsonl`、指标矩阵（CSV/MD）、阈值曲线/对比图、`metadata.json`、报告用图表。

## 12. 风险与缓解

| 风险 | 缓解 |
|---|---|
| WildGuard 无干净连续分 | AUROC 用 yes/no logit；不可得则标 N/A，不硬凑 |
| 图像为抽样 → 泛化受限 | 结论限定“1k 子样本上”；措辞保守 |
| OpenAI 速率/成本 | 批处理 + 退避 + 缓存；moderation 免费但限速 |
| taxonomy 分歧污染按类别指标 | 同一映射下比较 + 显式注释，作为分析点而非缺陷 |
| prompt 模板敏感 | 固定官方模板并记录，作为已知局限 |

## 13. 算力/时间预估（粗略）

Llama Guard 1B 几分钟；WildGuard 7B 约几十分钟；ShieldGemma2 1k 图中等；OpenAI ~5k 调用数分钟。**总计数小时内可完成全量。**

## 14. 与作业评分对齐

- **结构 40%**：Guard 输出严格符合统一格式 + 完整 skill 结构。
- **可复现 30%**：§9 全部到位 + smoke test + metadata + 断点续跑。
- **结果报告 30%**：§7 多 Guard × 多任务矩阵 + CI + 配对检验 + over-refusal + 误判案例 → 远超“展现流程”的下限。

---

## 衔接步骤

1. **M1 实现**：在 `feat/guard-llama-guard` 上把上述协议写成 `guard-llama-guard`（含 `src/guards/`、`metrics.py`）。
2. **执行**：用 experiment-agent **`run` 模式**跑命令骨架 + 实时监控。
3. **核验**：用 experiment-agent **`validate` 模式**做统计解读 + 11 类谬误扫描 + 可复现性重跑。
