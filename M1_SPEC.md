# M1 Spec：`guard-llama-guard`（方向 B 主 Skill）规格与路线图

> 状态：**待评审**。本文档是 M1 阶段的实施契约——按 spec-driven 流程，评审通过前不动手写实现代码。
> 推导依据：`作业说明/README.md`（最新标准 Skill 结构 + 评分标准）、`团队分工计划.md`（方向 B + 共同任务 + 里程碑）、`M0_接口约定.md`（双边契约）、`InfoSec-example-skills`（dataset-format-checker / download-text-modal-dataset 两个示例的设计模式）。**未参考旧计划**（避免锚定）。

---

## 0. 假设声明（ASSUMPTIONS — 不同意请先纠正）

1. **M1 主 Skill 就是 `guard-llama-guard`**。分工计划 M1 = "文本核心 E2E：WildGuardMix→checker PASS→Llama Guard 出第一版指标"；`dataset-wildguardmix` 归甲，乙在 M1 的唯一交付物即本 skill。
2. **运行环境**：开发机有 GPU + HF 账号 + OpenAI API（已具备）；但 skill 必须在"无 GPU、无 token、无网络"的机器上仍能跑通最小闭环（评分者环境不可控，这正是可复现性 30% 的得分点）。
3. **评测数据**：M1 先用 `M0_dataset_unified_sample.jsonl`（5 条 text + 2 条 image）解耦开发；甲的 WildGuardTest unified 输出就绪后接入，**接口不变**。
4. **OpenAI Moderation 完整对比属 M2**（分工计划 M2 = 多 Guard 对比），M1 只交付适配器（Plus 层）。
5. Guard 输出的**文件布局**在 M0 契约中未定义（M0 §7 只定义了数据集侧），本 spec §5.4 给出定义，需作为 **M0 契约补充**开 PR 通知甲。（**状态 2026-06-11**：已写入 `M0_接口约定.md` §5，默认接受制生效中，否决窗口与其余甲侧事项见 `M1_待甲确认.md`）

---

## 1. 分层目标

### L0 · Core-Minimal —— M1 必须完成，决定 M1 是否交付

| 项 | 内容 |
|---|---|
| 包含 | 统一 JSONL 读入与 task 路由；**规则关键词基线 Guard**（纯 stdlib）；统一 guard-result JSONL 输出；`validate.py` 自校验；`metrics.py`（Accuracy / Recall / FPR / Macro-F1 / AUROC，纯 stdlib 实现）；`SKILL.md`；examples + tests + fixtures；**`M1_summary.md`（含追溯表）**；**smoke 运行截图** |
| 为什么在这层 | 这是作业 B 五项要求（①输入接口 ②Guard 调用 ③输出解析 ④标签映射 ⑤评测兼容）的最小完整覆盖，且**零安装**——任何 Python ≥3.9 不联网即可复现，托底可复现性 30% |
| 成功标准 | 在 `examples/input.sample.jsonl` 上：`main.py --guards rule` exit 0 → `validate.py` exit 0 → `metrics.py` 产出全部 5 项指标；`python -m unittest discover -s tests` 全绿；全程无第三方依赖、无网络、< 60 秒；smoke 终端截图已存档 |
| 失败降级 | 无降级空间——这层失败即 M1 失败，必须修复 |
| 影响交付 | **是**，阻塞项 |

### L1 · Core-Full —— 依赖（GPU/gated/网络）具备时必须完成

| 项 | 内容 |
|---|---|
| 包含 | **Llama Guard 3-1B 适配器**：本地推理、S1–S14 → 22 类映射、unsafe token 概率 → `confidence`、超时/重试/空输出处理、gated 401 可读修复提示；在真实 unified 数据（甲的输出或 M0 样本）上产出**第一版指标矩阵** |
| 为什么在这层 | 是 M1 里程碑的本体（"Llama Guard 出第一版指标"），但依赖 GPU + HF gated 授权 + torch/transformers，不能让环境问题阻塞最小闭环 |
| 成功标准 | M0 样本 5 条 text 记录 ≥4 条产出非 error 预测；AUROC 可计算（confidence 非 null）；gated 未授权时打印 FIX 三步提示并 exit 2（部分成功），规则基线结果仍正常落盘 |
| 失败降级 | GPU 不可用 → `--device cpu`（1B 模型 CPU 可推理，慢但可行）；模型完全不可得 → 降到 L0 闭环交付 + 在报告中如实说明，M1 演示用规则基线，Llama Guard 顺延 |
| 影响交付 | 影响"第一版指标"质量，**不阻塞** skill 本身验收 |

### L2 · Plus —— 强烈建议，不阻塞验收

| 项 | 内容 |
|---|---|
| 包含 | OpenAI Moderation 适配器（`category_scores` → confidence）；Over-refusal Rate 支线（metrics 对 `over_refusal_probe=true` 子集算 FPR，M0 样本已含 1 条 XSTest 探针可测）；`templates/report-section.md`；`examples/metrics.sample.json`；trigger eval（§8）跑一轮并记录 |
| 为什么在这层 | OpenAI 对比与 over-refusal 是 M2 主战场，M1 把接口和最小实现铺好可让 M2 零返工；report 模板直接喂共同任务的小组报告 |
| 成功标准 | OpenAI 适配器无 key 时优雅失败（exit 2 + 提示）、有 key 时 M0 样本跑通；metrics 输出含 `over_refusal_rate` 字段（探针数 <30 时标注 `low_sample_warning`） |
| 失败降级 | 任何一项做不完 → 移入 M2 首日任务，不影响 M1 |
| 影响交付 | 否 |

### L3 · Extension —— 只留设计与接口，M1 明确不实现

| 项 | 内容 | 留的接口 |
|---|---|---|
| 全量 XSTest over-refusal 评测 | M2 | metrics 的探针分桶已支持，只差数据 |
| 对抗/普通分桶 + 按类别 Macro-F1 | M2 | `metrics.py --adversarial-split --by-category` 旗标预留（M1 可不实现旗标逻辑，报 `not implemented` + exit 1） |
| 图像模态（ShieldGemma 2） | M3，属 `guard-shieldgemma2` skill | 本 skill 对 image 记录 = out-of-scope skip 并计数；输出 schema 与 M3 共用 |
| 批量缓存 / 断点续跑增强、阈值扫描、prompt 模板消融 | 后续可选（§8） | `--resume` 旗标 + 逐行 append 写盘已天然支持粗粒度续跑 |

---

## 2. 主线任务

- **一句话目标**：把"统一安全数据集 → 文本 Guard 判断 → 统一结果 → 指标报告"做成一个零安装可闭环、GPU 就绪即出真指标、能被 Claude Code 自动发现调用的标准结构 Skill。
- **主要使用者**：① 评分老师/助教（装进 `.claude/skills` 后用自然语言触发）；② 同学乙（开发与 M2 复用）；③ 同学甲（交叉 review 指标公式）；④ 统一实验平台（按作业愿景被发现/调用/组合）。
- **解决方向 B 的核心问题**：作业 B 全部五项——统一输入接口（①）、Guard 调用含异常处理（②）、输出解析为统一字段（③）、标签映射到 22 类（④）、评测指标兼容（⑤）。M1 在规则基线上五项全闭环，在 Llama Guard 上做实②③④。
- **支持的共同任务**：端到端集成（直接消费甲的 unified 输出，产出截图素材）；交叉 review（`references/metrics-definitions.md` 给甲核对"正类=unsafe"）；小组报告（`templates/report-section.md` + metrics.md 直接进报告）。
- **输入**：unified JSONL 文件或目录（已过 dataset-format-checker 的数据，或 M0 样本）。
- **输出**：`predictions/<guard>.predictions.jsonl`（每行一条 M0 §5 schema 记录）+ `metrics/metrics.{json,md}` + `run_metadata.json`。
- **最小可运行链路**：`examples/input.sample.jsonl → main.py --guards rule → validate.py → metrics.py`，零依赖零网络。
- **只留接口不实现**：见 §1 L3 表。

---

## 3. 标准目录设计

```
guard-llama-guard/
├── SKILL.md
├── README.md
├── requirements.txt
├── scripts/
│   ├── main.py
│   ├── metrics.py
│   ├── validate.py
│   ├── utils.py
│   └── guards/
│       ├── __init__.py
│       ├── base.py
│       ├── rule_based.py
│       ├── llama_guard.py
│       └── openai_moderation.py
├── schemas/
│   ├── guard_output.schema.json
│   └── metrics.schema.json
├── references/
│   ├── io-contract.md
│   ├── category_mapping.json
│   ├── metrics-definitions.md
│   ├── llama-guard-notes.md
│   └── trigger-eval.md
├── templates/
│   └── report-section.md
├── examples/
│   ├── input.sample.jsonl
│   ├── output.sample.jsonl
│   └── metrics.sample.json
├── tests/
│   ├── test_rule_guard.py
│   ├── test_metrics.py
│   ├── test_validate.py
│   └── fixtures/
│       ├── mini_unified.jsonl
│       └── mini_predictions.jsonl
└── assets/
    └── rule_keywords.json
```

| 文件 | 职责 | M1 必需 | 层级 | 影响验收 |
|---|---|---|---|---|
| `SKILL.md` | 模型入口：触发、TL;DR、快捷命令、契约摘要、排障（设计见 §4） | ✅ | Core-Minimal | ✅ 结构+质量双验收 |
| `README.md` | 给人看：Guard 来源论文链接、复现步骤（提交硬性要求） | ✅ | Core-Minimal | ✅（提交内容第 1 条点名） |
| `requirements.txt` | 仅 Llama Guard/OpenAI 路径的依赖（torch、transformers、openai），注明"核心闭环零依赖" | ✅ | Core-Full | ⭕ 可复现性加分 |
| `scripts/main.py` | CLI 编排：读入→路由→调 Guard→落盘 predictions + run_metadata | ✅ | Core-Minimal | ✅ smoke 验收主体 |
| `scripts/metrics.py` | 独立 CLI：join 真值→指标矩阵→metrics.{json,md} | ✅ | Core-Minimal | ✅ |
| `scripts/validate.py` | guard-result JSONL 结构校验 + 与输入 id join 核对 | ✅ | Core-Minimal | ✅ |
| `scripts/utils.py` | JSONL 流式读写（UTF-8）、id 解析、映射加载、计时 | ✅ | Core-Minimal | ⭕ 间接 |
| `scripts/guards/__init__.py` | 适配器注册表；**按需 import**（不装 torch 也能 import rule） | ✅ | Core-Minimal | ✅ 降级路径关键 |
| `scripts/guards/base.py` | `GuardAdapter` 协议：`name/version/modality`、`predict(record)→dict`、`available()→(bool,reason)` | ✅ | Core-Minimal | ✅ |
| `scripts/guards/rule_based.py` | 关键词/正则基线；确定性；`confidence=null` | ✅ | Core-Minimal | ✅ |
| `scripts/guards/llama_guard.py` | 3-1B 推理、S1–S14 解析、token 概率、超时/重试/gated 提示 | GPU 就绪则✅ | Core-Full | ⭕ 不阻塞 |
| `scripts/guards/openai_moderation.py` | API 调用、scores→confidence、退避重试 | ❌ | Plus | ❌ |
| `schemas/guard_output.schema.json` | 单条预测记录的 JSON Schema（draft 2020-12） | ✅ | Core-Minimal | ✅ |
| `schemas/metrics.schema.json` | metrics.json 的结构约束 | ❌ | Plus | ❌ |
| `references/io-contract.md` | 输入输出契约全文（§5 落库版）：错误分级、计数语义、文件布局 | ✅ | Core-Minimal | ✅ |
| `references/category_mapping.json` | S1–S14 / OpenAI / 规则类别 → 22 类（与 M0 §4 一致，甲乙共审） | ✅ | Core-Minimal | ✅ |
| `references/metrics-definitions.md` | 公式、正类=unsafe、AUROC 算法（秩统计）、真值字段对齐表 | ✅ | Core-Minimal | ✅ 交叉 review 载体 |
| `references/llama-guard-notes.md` | prompt 模板、S1–S14 全表、token 概率提取法、gated 三步授权 | GPU 就绪则✅ | Core-Full | ⭕ |
| `references/trigger-eval.md` | 触发评测协议与记录（§8） | ❌ | Plus | ❌ |
| `templates/report-section.md` | 报告"Guard 方法+结果"章节模板，留指标占位符 | ❌ | Plus | ❌ |
| `examples/input.sample.jsonl` | 从 M0 样本截取：5 text + 1 image（演示 out-of-scope skip） | ✅ | Core-Minimal | ✅ |
| `examples/output.sample.jsonl` | rule 基线在上述输入的**黄金输出**（与实跑字段级一致以便自动比对；error 记录示例放 fixtures） | ✅ | Core-Minimal | ✅ smoke 比对基准 |
| `examples/metrics.sample.json` | 对应的指标输出示例 | ❌ | Plus | ❌ |
| `tests/test_rule_guard.py` | 规则基线在 fixtures 上的确定性断言 | ✅ | Core-Minimal | ✅ |
| `tests/test_metrics.py` | 手算混淆矩阵/AUROC/over-refusal 对照断言 | ✅ | Core-Minimal | ✅ |
| `tests/test_validate.py` | 合法/非法 fixtures 的 PASS/FAIL 断言 | ✅ | Core-Minimal | ✅ |
| `tests/fixtures/mini_unified.jsonl` | 6–8 条手工微型数据（覆盖 §7 examples 矩阵） | ✅ | Core-Minimal | ✅ |
| `tests/fixtures/mini_predictions.jsonl` | 已知混淆矩阵的预测集（含 null/error 条目） | ✅ | Core-Minimal | ✅ |
| `assets/rule_keywords.json` | 规则基线词表（数据而非文档，故放 assets） | ✅ | Core-Minimal | ✅ |

不建 `manifest.yaml`、`pyproject.toml`、`src/`。

---

## 4. SKILL.md 设计

**总约束**：≤ 250 行 / ≤ 12KB（对齐两个示例 skill 的体量）；模型每次执行只读这一个文件就能干活，细节全部指针到 `references/`。

### frontmatter

```yaml
---
name: guard-llama-guard
description: Run text safety guards (Llama Guard 3, keyword rule baseline, OpenAI
  Moderation) over unified safety JSONL records and emit unified guard-result JSONL
  plus evaluation metrics (Accuracy, Macro-F1, Recall, FPR, AUROC, Over-refusal).
  Use this skill when the user asks to run, evaluate, or benchmark a guard or
  moderation model on a unified safety dataset, score guard predictions, or compute
  guard safety metrics. Not for building or converting datasets (use dataset-*
  skills) and not for checking dataset format (use dataset-format-checker).
---
```

设计要点：动词触发词（run/evaluate/benchmark/score）+ 名词锚点（unified safety JSONL、Llama Guard、metrics）+ **显式负触发**（两个兄弟 skill 的职责排除）。

### 章节大纲（按序）

| # | 章节 | 内容要点 |
|---|---|---|
| 1 | 标题 + 一段定位 | 读 unified JSONL → 路由 → Guard → 统一结果 + 指标；**read-only 保证**（绝不修改输入数据集，借鉴 checker） |
| 2 | When to use | 4–5 条用户原话式触发（"run llama guard on this dataset" / "评测 guard 在统一数据上的指标"…） |
| 3 | When NOT to use | 转换数据集→`dataset-wildguardmix`；查格式→`dataset-format-checker`；图像→`guard-shieldgemma2`（M3） |
| 4 | TL;DR for the agent | 5 条实战失败模式：① 判结果看 **exit code + `RESULT:` 行**，禁 `\| tail`；② 正类=unsafe，FPR 别算反；③ gated 401 → 三步授权（web 同意→`hf auth login`→重跑），期间规则基线照常出结果（exit 2=部分成功≠崩溃）；④ 无 GPU/无 token 时先跑零依赖 smoke（rule guard）；⑤ `prediction.is_unsafe=null` 是合法的 error 记录，剔除指标并计数，不要"修" |
| 5 | Quick workflow | 两段式：**Smoke（零安装）** `main.py --input examples/input.sample.jsonl --output-dir out_smoke --guards rule` → `validate.py out_smoke/predictions` → `metrics.py --predictions out_smoke/predictions --dataset examples/input.sample.jsonl`；**Full** 加 `--guards rule,llama-guard` + venv 安装步骤。给 bash 与 PowerShell 双版本（Windows 兼容是实测痛点） |
| 6 | 输入格式 | 3 行说明 + 指针：unified JSONL（checker PASS 的数据）；M1 只消费 text 记录，image 记录跳过计数；字段读取表 → `references/io-contract.md` |
| 7 | 输出格式 | 单条 JSON 示例（M0 §5 同款）+ 文件布局 3 行 + 指针 `schemas/guard_output.schema.json` |
| 8 | 执行步骤 | 编号步骤：确认输入路径→选 guards→跑 main→读 exit code→validate→metrics→把 metrics.md 给用户 |
| 9 | 失败处理 | exit code 表（0/1/2 语义）；guard 级失败 vs 记录级 error vs out-of-scope skip 三分法（各 1 行 + 指针） |
| 10 | Sanity check | 预期数字表：sample 输入 → rule guard 5 条预测 0 error、image 1 条 skip；黄金输出 `examples/output.sample.jsonl` 字段级一致（latency 除外）；实现后回填 Llama Guard 在 M0 样本的预期指标区间 |
| 11 | Good response pattern | 模型答复用户时必含：跑的命令、exit code、预测/error/skip 三计数、指标表、输出路径（借鉴 download 示例的 6 点模式） |
| 12 | Troubleshooting | 表格 6–8 行：401/403 gated、`No module named torch`、CUDA OOM（→`--device cpu` 或 `--limit`）、PowerShell 通配符不展开（→传目录不传 glob）、AUROC=null（规则基线无连续分，预期行为）、超时率高（→调 `--timeout-s`） |
| 13 | Safety & limitation | 数据含有害内容仅限防御性评测；Guard 判断非真值，存在误判；遵守模型/数据 license |

### 明确不放进 SKILL.md 的内容（→ references/）

S1–S14 × 22 类完整映射表（→ `category_mapping.json`）；指标公式推导与 AUROC 秩统计细节（→ `metrics-definitions.md`）；Llama Guard prompt 模板原文与 token 概率提取代码说明（→ `llama-guard-notes.md`）；错误分级的完整判定表（→ `io-contract.md`）；触发评测记录（→ `trigger-eval.md`）。SKILL.md 里每处只留 1 行摘要 + 相对路径指针，实现懒加载。

---

## 5. 输入输出契约

### 5.1 输入

| 项 | 约定 |
|---|---|
| 形态 | 单个 `.jsonl` 文件或目录（目录则发现 `*.jsonl`，跳过 `metadata.json` 等裸对象文件，对齐 checker 行为） |
| 前置 | 数据应已过 dataset-format-checker；本 skill **不重复做全量格式校验**，只防御性读取 |
| 消费字段 | `id`；`task_type`；`modality`；`content.prompt` / `content.response`；真值仅 metrics 读：`label.is_unsafe`、`label.prompt_is_unsafe`、`label.response_is_unsafe`、`risk_metadata.over_refusal_probe`、`risk_metadata.adversarial`（M2） |
| M1 范围 | `task_type ∈ {prompt_only_safety, prompt_response_safety}` 且 `modality=["text"]`；其余 → out-of-scope skip |

### 5.2 输出记录（= M0 §5，零偏离）

每行一条：`id`（与输入逐字一致，join 键）、`guard{name,version,modality}`、`prediction{is_unsafe, risk_categories, severity, action, confidence}`、`raw_output`（Guard 原始输出，原值保留）、`runtime{latency_ms, cost, device}`、`error`。

### 5.3 错误三分法（判定规则）

| 级别 | 触发条件 | 处理 | exit code 影响 |
|---|---|---|---|
| **Fatal** | 输入路径不存在；0 条可解析记录；输出目录不可写；`--guards` 全部未知；schema 文件缺失 | 打印原因，立即终止 | `1` |
| **Guard 级失败** | 某 guard `available()=false`（gated 401、缺依赖、无 API key、模型加载失败） | 跳过该 guard，打印 `FIX:` 提示；其余 guard 照常 | 有≥1 guard 成功 → `2`（部分成功）；全失败 → `1` |
| **记录级 error** | 单条推理超时（默认 30s）/重试后仍空输出/解析失败 | `prediction.is_unsafe=null` + `error` 字符串，**照常写入输出行**，计入 `counts.errors`，metrics 剔除 | 不影响 |
| **Out-of-scope skip** | image/video/conversation 模态或任务；该任务必需的 content 字段为空 | 不写输出行，计入 `counts.skipped{out_of_scope, missing_content}` | 不影响 |

### 5.4 文件布局与 run_metadata（已写入 M0 §5；甲否决式确认中，见 `M1_待甲确认.md` #1）

```
<output_dir>/
├── predictions/<guard-name>.predictions.jsonl
├── metrics/metrics.json
├── metrics/metrics.md
└── run_metadata.json
```

`run_metadata.json` 字段：`run_id`、`timestamp`、`input{path, n_records}`、`guards{requested, completed, failed:{name: reason}}`、`counts{total, predicted, errors, skipped:{out_of_scope, missing_content}}`、`config`（CLI 参数回显，含 seed/timeout/batch）、`env{python, platform, torch?, cuda?, model_revision?}`、`duration_s`。守恒式：`total = predicted + errors之外仍写行(errors含在predicted行内,is_unsafe=null) + skipped合计`，即 **输出行数 = total − skipped**，其中 error 行 `is_unsafe=null`。

### 5.5 校验方式

- `validate.py`：结构校验（必填键、类型、`is_unsafe ∈ {true,false,null}`、`risk_categories ⊆ 22类+other`、error/null 联动约束："`is_unsafe=null` ⇔ `error≠null`"）；`--against <input.jsonl>` 时核对 join 覆盖率 = 100%（输出 id ⊆ 输入 id 且无重复）。纯 stdlib 实现 schema 子集；环境装了 `jsonschema` 则额外跑全量 schema（可选增强）。
- exit：`0` PASS / `1` FAIL / `2` 用法或 IO 错。

### 5.6 对 M2/M3 的可用性保证

id join 键不变；schema 与 `guard-shieldgemma2`（M3）完全共用；metrics.py 按 `guard.name` 分组天然支持多 Guard 对比（M2）；探针/对抗分桶只是真值侧过滤器，predictions 无需重跑。

---

## 6. scripts 设计

### `main.py`（必需，Core-Minimal）

```
python scripts/main.py --input <file|dir> --output-dir <dir>
  [--guards rule,llama-guard,openai]   # 默认 rule
  [--limit N] [--device auto|cuda|cpu] [--timeout-s 30] [--retries 1]
  [--batch-size 8] [--model-id meta-llama/Llama-Guard-3-1B]
  [--hf-token TOKEN] [--seed 42] [--resume] [--dry-run]
```

- `--dry-run`：只做读入+路由+计数，不调 Guard（快速检查输入）。
- `--resume`：输出文件已存在时跳过已有 id（逐行 append 写盘使粗粒度断点续跑天然成立）。
- exit：`0` 全部请求的 guard 成功；`2` 部分成功；`1` fatal。
- stdout 末行打印 `RESULT: ok|partial|fatal  predicted=N errors=N skipped=N`（对齐 checker 的 `RESULT:` 行模式）。

### `metrics.py`（必需，Core-Minimal）

```
python scripts/metrics.py --predictions <dir|file...> --dataset <unified file|dir>
  --output-dir <dir> [--by-category] [--adversarial-split]   # 两旗标 M1 预留
```

- 按 M0 §3 真值对齐表路由：头部二分类用 `label.is_unsafe`；prompt 任务桶用 `prompt_is_unsafe`；pair 桶用 `response_is_unsafe`。
- AUROC 用**秩统计（Mann–Whitney，ties 取平均秩）**纯 stdlib 实现；`confidence=null` 的预测仅从 AUROC 剔除（其余指标保留）；`is_unsafe=null` 从全部指标剔除。
- 输出 `metrics.json`（机器读）+ `metrics.md`（Guard × 任务 × 指标表，直接可截图/进报告）。
- exit：`0` 成功 / `1` 无可 join 记录或参数错。

### `validate.py`（必需，Core-Minimal）— 见 §5.5。

### `utils.py`（必需）

JSONL 流式 reader/writer（`encoding="utf-8"`、写时 `newline="\n"`）、`pathlib` 全程（Windows 兼容）、id 工具、`references/category_mapping.json` 加载器、计时器。

### `guards/` 适配器

- `base.py`：`GuardAdapter` 协议（`available() -> tuple[bool, str]`、`predict(record) -> dict`、可选 `predict_batch`）。
- `rule_based.py`：词表（`assets/rule_keywords.json`）+ 大小写无关词边界正则；类别由词表分组直接给出 canonical 类；`confidence=null`（诚实不参与 AUROC）。
- `llama_guard.py`：懒 import torch/transformers；chat template 构造（prompt-only 与 pair 两种）；贪心解码 + 固定 max_new_tokens；首 token logits 提取 `unsafe_token_prob` → confidence；输出文本解析 S 码 → 22 类；单条超时（线程级看门狗）+ 重试 `--retries` 次；401/403 → `FIX:` 三步提示。
- `openai_moderation.py`（Plus）：`omni-moderation-latest`；指数退避重试；`max(category_scores)` → confidence；无 `OPENAI_API_KEY` → `available()=false`。

**零安装/轻依赖**：`main.py --guards rule`、`metrics.py`、`validate.py`、全部 tests 仅 stdlib；torch/transformers/openai 全部懒 import，`requirements.txt` 仅服务 Core-Full/Plus 路径。
**Windows 兼容**：`pathlib`、显式 UTF-8、CLI 接受**目录**而非依赖 shell glob（PowerShell 不为 python 展开 `*.jsonl`）、SKILL.md 给双 shell 命令。

---

## 7. schemas / references / templates / examples / tests / assets 规划

| 目录 | 内容 | M1 必需 |
|---|---|---|
| `schemas/` | `guard_output.schema.json`（必需）：完整约束 §5.2 记录，含 "`is_unsafe=null` ⇔ `error` 非空" 的条件逻辑；`metrics.schema.json`（Plus） | ✅ / ❌ |
| `references/` | `io-contract.md`（必需，§5 落库）；`category_mapping.json`（必需，与 M0 §4 一字不差，含 S1–S14、OpenAI、规则词表类别三段）；`metrics-definitions.md`（必需，公式 + 正类声明 + AUROC 算法 + 真值对齐表，交叉 review 用）；`llama-guard-notes.md`（Core-Full）；`trigger-eval.md`（Plus） | 见左 |
| `templates/` | `report-section.md`（Plus）：报告 Guard 章节骨架，指标表/误判案例占位符 | ❌ |
| `examples/` | **覆盖矩阵**（必需）：unsafe prompt-only ✓、safe prompt-only ✓、safe pair（拒答）✓、unsafe pair ✓、XSTest 探针 ✓、image 记录（演示 skip）✓ —— 即 M0 样本 6 条裁剪；`output.sample.jsonl` 为 rule 基线黄金输出（**不含** error 行，保证与实跑可逐字段比对；error 记录示例见 `tests/fixtures/mini_predictions.jsonl`）；`metrics.sample.json`（Plus） | ✅ |
| `tests/` | `test_rule_guard.py`：fixtures 上预测序列逐字段断言（确定性）；`test_metrics.py`：手算对照（固定 8 条预测：TP=3 FP=1 TN=3 FN=1 → Acc=0.75、Recall=0.75、FPR=0.25，AUROC 手算值，含 null 剔除与探针 FPR 用例）；`test_validate.py`：合法文件 PASS、缺键/字符串 is_unsafe/孤儿 error 各 FAIL；stdlib `unittest`（零依赖，pytest 兼容） | ✅ |
| `assets/` | `rule_keywords.json`：分类别词组表（数据资产）；不需要图片/表格类资源 | ✅ |

---

## 8. 性能优化策略

"性能" = 触发准确性 + 输出稳定性 + 可复现性 + 工程效率。借鉴自示例 skill 的模式已内化到 §4–§6（TL;DR 失败模式前置、exit-code 三态、`FIX:` 提示、`RESULT:` 行、预期计数 sanity 表、read-only 保证、零依赖 stdlib 核心）。

### M1 必做

| 手段 | 落点 |
|---|---|
| 触发优化：description 动词+名词锚点+负触发 | §4 frontmatter；与两个 dataset skill、checker 的 description 互斥分工 |
| SKILL.md 短而强 | ≤250 行硬约束；每节带 references 指针，长内容懒加载 |
| 确定性下沉到代码 | 模型只编排命令，所有转换/解析/计算在 scripts；规则基线 100% 确定 |
| 输出防漂移 | schema + validate 强制门 + 黄金输出比对（`examples/output.sample.jsonl`） |
| 可复现 | `--seed`、贪心解码、`run_metadata` 记录 model revision/env、requirements 锁版本、`--limit` smoke 路径 |
| 工程效率底线 | 逐行 append 写盘（崩溃不丢已算结果）、`--resume`、latency_ms 逐条记录、单条 timeout 不拖垮批 |
| 回归防护 | tests 三件套 + fixtures 进 git；验收清单含 smoke 计时上限 |

### M1 强烈建议

| 手段 | 落点 |
|---|---|
| **可度量 trigger eval** | `references/trigger-eval.md`：≥8 正例（"run llama guard on …"、"评测这个数据集上的 guard"…）+ ≥6 负例（"转换 WildGuardMix"、"检查数据格式"、"下载数据集"…）；协议=每条开新会话提问，记录是否触发本 skill；达标线：正例 ≥7/8 触发，负例 0 误触；记录日期与模型版本；无法实跑时**退化为文档化判定**（逐条写预期是否触发及依据，标注"未实测"），不删项 |
| batch 推理 | `--batch-size`，1B 模型 GPU 下 8–16；记录吞吐进 run_metadata |
| fp16/bf16 | cuda 路径默认 bf16，省显存提速 |
| OpenAI 退避重试 + 限速 | Plus 适配器内置 |

### 后续可选（M2+ 消融实验素材，正好喂报告"分析"章节）

prompt 模板 ×2 对比（官方 chat template vs 简化模板）；解析方式消融（token 概率 vs 文本正则）对 AUROC 的影响；OpenAI score 阈值扫描（0.3/0.5/0.7）对 FPR/Recall 曲线；batch size {1,4,8,16} 延迟曲线；`--resume` 缓存命中下的重跑耗时；依赖体积/导入耗时对比（stdlib 核心 vs 全量）；错误注入演练（中途 kill → resume 完整性）。

---

## 9. 评测与验收（全部可打勾）

**全局规则：验收项只可标记，不可删除。** 任何做不到的项保留原文并标 `N/A + 原因 + 顺延里程碑`，记入 `M1_summary.md`；禁止静默砍范围。

### 9.0 验收总览（层 × 降级）

| 档 | 内容 | M1 要求 | 通过含义 | 失败降级 |
|---|---|---|---|---|
| **Core-Minimal** | §1-L0 全部（含 `M1_summary.md` 追溯表、smoke 截图） | **必过** | 下文 A/B/C/E/F/G/H/I/L 中非 Plus 标注项全勾 | 无降级——修复为止，否则 M1 失败 |
| **Core-Full** | + Llama Guard 3-1B 第一版指标 | 授权+算力具备时应过 | J 两项全勾 | 降回 Core-Minimal，写入 limitations；**非 Core 失败** |
| **Plus** | OpenAI 适配器、over-refusal、report 模板、trigger eval | 否（强烈建议） | K 及各处 Plus 标注项勾 | 逐项 N/A+原因；trigger eval 退化为文档化判定（§8） |
| **Extension** | 对抗/按类别分桶、全量 XSTest、图像（M3） | 否 | 接口存在且**响亮拒绝**（M） | 不实现即合规，静默错误实现才算失败 |

### 9.1 分维度清单

**A. 文件结构**
- [ ] `SKILL.md` 存在，frontmatter 含合法 `name` + `description`；无 `manifest.yaml`/`pyproject.toml`/`src/`
- [ ] §3 表中所有 Core-Minimal 文件存在且非空；目录名与标准结构一致

**B. SKILL.md 质量**
- [ ] ≤250 行；含 §4 大纲全部 13 节；所有 references 指针路径真实存在
- [ ] Quick workflow 的每条命令复制粘贴即可运行（bash + PowerShell 双版本）

**C. 方向 B 任务覆盖**
- [ ] ①读 unified JSONL ②≥2 类 Guard（规则+本地模型）且处理超时/空输出/gated ③统一字段输出 ④22 类映射含显式 `other` ⑤五项指标 —— 逐项有代码与测试对应

**D. 共同任务覆盖**
- [ ] 用甲的 unified 输出（或 M0 样本）端到端跑通并截图；`metrics-definitions.md` 已请甲 review 签字（PR approve 即可）

**E. I/O 契约**
- [ ] 输出每行过 `validate.py`；`--against` join 覆盖率 100%；`run_metadata.counts` 守恒式成立（输出行数 = total − skipped）
- [ ] M0 §5 字段零偏离；文件布局 PR 已开给甲

**F. schema/validate**
- [ ] `guard_output.schema.json` 能拒绝：缺 `id`、字符串 `"unsafe"`、`is_unsafe=null` 而 `error=null` 的孤儿记录
- [ ] `validate.py` 三态 exit code 与文档一致

**G. examples**
- [ ] `input.sample.jsonl` 覆盖 §7 六种情形；`output.sample.jsonl` 与实际 rule 输出字段级一致（latency 除外），由测试固化

**H. tests**
- [ ] `python -m unittest discover -s tests` exit 0；≥3 个测试文件；fixtures 已入 git；test_metrics 含手算对照（混淆矩阵 + AUROC + null 剔除 + 探针 FPR）

**I. smoke run（零依赖机器可执行）**
- [ ] 干净环境（无 torch/无网络）：`main.py --guards rule` → exit 0；predictions 5 行；skip 1（image）；validate exit 0；metrics 产出 5 指标（AUROC=null 标注原因）；全程 <60s
- [ ] smoke 运行终端截图已存档（**第一张提交截图**，不等 E2E/Core-Full）

**J. Core-Full（环境就绪时）**
- [ ] Llama Guard 在 M0 样本 5 条 text ≥4 条非 error；confidence 非 null；AUROC 可算；metrics.md 出 Guard×任务表
- [ ] 拔掉 HF token 重跑 → exit 2 + `FIX:` 三步提示 + rule 结果完好

**K. 性能优化**
- [ ] description 含负触发；SKILL.md 行数达标；trigger eval 跑过一轮且正例 ≥7/8、负例 0 误触（Plus，未做则记录顺延理由）

**L. 报告/总结**
- [ ] README.md 含 Guard 论文与模型链接（Llama Guard 3 论文/卡片）、复现三步；metrics.md 可直接贴报告
- [ ] 仓库根目录 `M1_summary.md` 存在，含**追溯表**（作业 B 五项要求 × 层级 × 实现文件 × 测试 × §9 验收项的映射）+ N/A 项记录（项、原因、顺延里程碑）+ 已知限制

**M. 非目标边界**
- [ ] image 记录被 skip 且计数，**不报错**；`--by-category`/`--adversarial-split` 未实现时给出明确 `not implemented` 退出而非静默错误结果

**N. 降级路径**
- [ ] 无 GPU：`--device cpu` 可跑（`--limit 5` 验证）；无任何重依赖：L0 闭环完整；llama-guard 失败不影响 rule 输出落盘（exit 2 验证）

---

## 10. 任务依赖图（DAG）

```
P0 契约与骨架（半天）
  T0.1 schemas/guard_output.schema.json ─┐
  T0.2 references/io-contract.md ────────┼──► C0
  T0.3 examples/input.sample.jsonl ──────┤
  T0.4 M0 契约补充（§5.4 布局）✅ 已落 M0 §5 + M1_待甲确认.md（待 push 通知甲） ┘

P1 Core-Minimal 闭环（1–2 天，C0 后）
  T1.1 utils.py ──► T1.2 guards/base.py + rule_based.py + assets/rule_keywords.json
                          │
  T1.3 main.py(rule) ◄────┘     T1.4 validate.py     T1.5 metrics.py
        [T1.3 依赖 T1.2；T1.4/T1.5 仅依赖 T0.1/T0.2，可与 T1.1–T1.3 并行]
  T1.6 tests + fixtures（随各模块同步写）──► C1

P2 Core-Full（1–2 天，C1 后）          P3 Plus（与 P2 并行，C1 后）
  T2.1 llama_guard.py                    T3.1 openai_moderation.py
  T2.2 gated 授权 + GPU 联调              T3.2 report-section.md + metrics.sample.json
  T2.3 真实数据第一版指标（--limit 200）──► C2   T3.3 trigger-eval 跑一轮
                                          [P3 任何任务可顺延 M2，不阻塞]
P4 验收打磨（半天，C2 后）
  T4.1 SKILL.md 终稿（回填实测 sanity 数字）
  T4.2 M1_summary.md（追溯表 + N/A 项 + 已知限制）
  T4.3 §9 验收清单全勾 + E2E 截图 ──► C3 = M1 交付
```

| Checkpoint | 成功条件 | 失败处理 |
|---|---|---|
| **C0** | schema/契约/样例三件套评审通过（自审 + 发甲）；PR 已开 | 契约有分歧 → 当天和甲对齐后再动代码（接口先行原则） |
| **C1** | 验收 §9-I smoke 全绿（含截图存档）+ §9-H tests 全绿 | 阻塞修复，不进 P2；超 1 天 → 削减 rule 词表范围保闭环 |
| **C2** | §9-J 两项通过；metrics.md 出第一版指标 | gated/GPU 受阻 → 降级预案（§1 L1）：CPU 或顺延，M1 以 L0+文档交付 |
| **C3** | §9 清单 A–N 中除 Plus 项外全勾；`M1_summary.md` 追溯表完整 | 未勾项按全局"不删项"规则标 N/A+原因+顺延里程碑，写入 `M1_summary.md` 与 README 已知限制 |

**Core-Minimal 阻塞链**：T0.1/T0.2 → T1.1 → T1.2 → T1.3 → C1。其余均有并行或顺延空间。

---

## 11. 工程规范（Commands / Code Style / Boundaries）

**Commands 速查**

```bash
# Smoke（零依赖）
python scripts/main.py --input examples/input.sample.jsonl --output-dir out_smoke --guards rule
python scripts/validate.py out_smoke/predictions --against examples/input.sample.jsonl
python scripts/metrics.py --predictions out_smoke/predictions --dataset examples/input.sample.jsonl --output-dir out_smoke/metrics
# Full（GPU + gated 就绪）
python -m venv .venv && .venv/Scripts/activate && python -m pip install -r requirements.txt
python scripts/main.py --input <unified_dir> --output-dir out --guards rule,llama-guard --batch-size 8
# Tests
python -m unittest discover -s tests -v
```

**Code style**（对齐示例 skill 的 `validate_output.py` 风格）：stdlib `argparse` + `pathlib` + 类型标注；常量表大写置顶；`main() -> int` + `raise SystemExit(main())`；错误信息带 `file:line` 或 `id` 定位；打印 `FIX:` 可执行修复提示；不捕获后静默。

**Boundaries**
- **Always**：产出 predictions 后立即 validate；以 exit code 判结果；正类=unsafe；记录级失败写 error 不抛异常；UTF-8 显式编码；契约文件改动与 `M0_接口约定.md` 同步并通知甲。
- **Ask first**：改任何 M0 契约字段；新增 torch/transformers/openai 之外的依赖；提交 >1MB 文件；改共享的 `category_mapping.json` 语义。（OpenAI 调用量**不设上限**——2026-06-11 用户确认 token 充足，已移出 Ask-first）
- **Never**：提交 HF token / API key / 模型权重 / 数据集 dump；让 `is_unsafe` 输出为字符串；绕过 validate 直接交付；修改甲的 dataset 目录或输入数据（read-only 保证）。

---

## 12. 不确定项（Open Questions）

### 12.1 需要甲确认（契约/协作）——**已整理为 `M1_待甲确认.md`，默认接受制（2026-06-11 推送）**

1. §5.4 Guard 输出布局（M0 契约补充）→ 已写入 M0 §5，**48h 否决窗口**（待甲确认 #1）。
2. WildGuardTest unified 就绪时间 → 默认"M0 样本顶替联调/截图、提交前真实数据重截"（待甲确认 #2）。
3. trigger eval 负例盲测 → 默认愿意，C1 后执行（待甲确认 #3）；另含 metrics 公式交叉 review（待甲确认 #4，对应 §9-D，无默认须实际动作）。

### 12.2 已决事项（2026-06-11 用户拍板）

4. ✅ `out*/` 已加入 `.gitignore`（截图与 metrics.md 手动挑选入库）。
5. ✅ M1 演示用 `--limit 200` 子集；全量 1,725 条留 M2（DAG T2.3 已同步）。
6. ✅ OpenAI 调用**不设配额上限**（用户 token 充足；§11 Ask-first 已移除该项）。
7. ✅ `M1_summary.md` 放仓库根目录，与 `M0_*` 并列。
8. ✅ 最低 Python 版本承诺 **3.9**。

### 12.3 实现期技术风险（在对应任务内解决，不阻塞 spec 评审）

9. **unsafe 概率提取细节**（T2.1）：Llama Guard 3 输出首 token 的 tokenizer 切分需实测——"unsafe" 可能切成多子词，届时取首子词 logit 或对比 safe/unsafe 两 token 概率归一化；结论落 `references/llama-guard-notes.md`。
10. **超时语义在 Windows/CUDA 下的限制**（T2.1）：CUDA 推理无法安全中断，看门狗只能"标记超时、算完丢弃"，`--timeout-s` 不能精确止损；SKILL.md 的 flag 说明须如实描述为软超时。
11. **HF gated 审批状态未验证**（T2.2 前置）：分工计划 M0 要求已点同意 Llama Guard 3，需实际跑一次确认 401 已消除，否则按降级路径走。
12. **规则基线在 XSTest 探针上的高 FPR 是设计性的**（T1.2）：关键词法必然误伤 "kill a process" 类安全 prompt——报告中作为"规则 vs 模型"对比叙事的素材，不当缺陷修。
