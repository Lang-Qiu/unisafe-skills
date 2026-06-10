# I/O Contract — guard-llama-guard

> 本文件是 `M1_SPEC.md` §5 的库内落地版，与 `M0_接口约定.md` §5（含 2026-06-11 文件布局补充块）零冲突。
> 单条输出记录的机器可读约束：[`../schemas/guard_output.schema.json`](../schemas/guard_output.schema.json)。
> 指标公式与双口径定义：[`metrics-definitions.md`](metrics-definitions.md)。

## 1. 输入

| 项 | 约定 |
|---|---|
| 形态 | 单个 `.jsonl` 文件或目录（目录则发现 `*.jsonl`，跳过 `metadata.json` 等裸对象文件，对齐 dataset-format-checker 行为） |
| 前置 | 数据应已通过 dataset-format-checker（exit 0）；本 skill **不重复做全量格式校验**，只防御性读取 |
| 消费字段 | `id`；`task_type`；`modality`；`content.prompt` / `content.response`。真值字段仅 `metrics.py` 读取：`label.is_unsafe`、`label.prompt_is_unsafe`、`label.response_is_unsafe`、`risk_metadata.over_refusal_probe`、`risk_metadata.adversarial`（M2 预留） |
| M1 范围 | `task_type ∈ {prompt_only_safety, prompt_response_safety}` 且 `modality == ["text"]`；其余 → out-of-scope skip |
| Read-only 保证 | 绝不修改输入数据集（任何文件、任何字段） |

## 2. eligible 定义（覆盖率与指标的统一分母）

**eligible** := 输入中按路由规则 in-scope 的记录集合。一条记录 eligible 当且仅当同时满足：

1. `task_type ∈ {prompt_only_safety, prompt_response_safety}`；
2. `modality == ["text"]`；
3. 该任务必需的 content 字段非空——`prompt_only_safety` 要求 `content.prompt`；`prompt_response_safety` 要求 `content.prompt` **且** `content.response`。

不满足 1 或 2 → 计入 `counts.skipped.out_of_scope`；满足 1、2 但 3 缺失 → 计入 `counts.skipped.missing_content`。两类 skip 记录**均不写输出行**。

**predictions 文件对每条 eligible 记录恰好写一行**（记录级 error 行也写，见 §4）。由此得守恒式：

```
每个 completed guard 的 predictions 行数 = eligible = total − skipped.out_of_scope − skipped.missing_content
```

`validate.py --against <input>` 的覆盖率核对即以本节 eligible 集合为基准：predictions ids 与 eligible ids **双向一致**（无缺失、无多余、无重复）。

## 3. 输出记录 schema（= M0 §5，零偏离）

每行一条 JSON：`id`（与输入逐字一致，join 键）、`guard{name, version, modality}`、`prediction{is_unsafe, risk_categories, severity, action, confidence}`、`raw_output`（Guard 原始输出，原值保留）、`runtime{latency_ms, cost, device}`、`error`。

关键约束（schema 强制）：

- `prediction.is_unsafe ∈ {true, false, null}`，**禁止字符串**；`null` ⇔ `error` 为非空字符串（双向）。
- `prediction.risk_categories ⊆ 22 类 + other`（枚举与 `category_mapping.json` 同源）；原始类别标签留在 `raw_output`。
- `prediction.confidence ∈ [0,1] ∪ {null}`；`null`（如规则基线）仅从 AUROC 剔除。

示例见 [`../examples/output.sample.jsonl`](../examples/output.sample.jsonl)（黄金输出，无 error 行）与 `tests/fixtures/mini_predictions.jsonl`（含 error 行示例）。

## 4. 错误三分法（判定规则）

| 级别 | 触发条件 | 处理方式 | exit code 影响 |
|---|---|---|---|
| **Fatal** | 输入路径不存在；0 条可解析记录；输出目录不可写；`--guards` 全部未知；schema 文件缺失 | 打印原因，立即终止 | `1` |
| **Guard 级失败** | 某 guard `available()=false`（gated 401、缺依赖、无 API key、模型加载失败） | 跳过该 guard，打印 `FIX:` 可执行修复提示；其余 guard 照常 | ≥1 guard 成功 → `2`（部分成功）；**全部**请求的 guard 失败 → `1` |
| **记录级 error** | 单条推理超时（默认 30s）/ 重试后仍空输出 / 解析失败 | `prediction.is_unsafe=null` + `error` 字符串，**照常写输出行**，计入 `counts.errors`；指标按双口径处理（见 metrics-definitions.md §3） | 不影响 |
| **Out-of-scope skip** | 非 M1 范围的模态/任务（§2 条件 1/2）；必需 content 字段为空（§2 条件 3） | **不写输出行**，计入 `counts.skipped{out_of_scope, missing_content}` | 不影响 |

## 5. 输出文件布局（M0 §5 补充块，2026-06-11 默认接受制生效中）

```
<output_dir>/
├── predictions/<guard-name>.predictions.jsonl   # 每行一条 §3 记录；id 与数据集记录逐字一致（join 键）
├── metrics/metrics.json                          # 指标矩阵（机器可读，双口径并列）
├── metrics/metrics.md                            # 同内容人读表格（可直接贴报告）
└── run_metadata.json                             # 见 §6
```

## 6. run_metadata.json 字段

| 字段 | 内容 |
|---|---|
| `run_id` | 本次运行唯一标识（时间戳派生） |
| `timestamp` | ISO 8601 |
| `input` | `{path, n_records}` |
| `guards` | `{requested: [...], completed: [...], failed: {name: reason}}` |
| `counts` | `{total, eligible, predicted, errors, skipped: {out_of_scope, missing_content}}`——`predicted` = `is_unsafe` 非 null 的行数，`errors` = error 行数；多 guard 时 `predicted`/`errors` 为各 completed guard 之和，守恒式对**每个** guard 的 predictions 文件分别成立 |
| `resume_hits` / `resume_misses` / `resume_hit_rate` | 断点续跑计数（消融 17-E 数据源）：`hits` = 因输出中已存在而跳过重算的 eligible id 数；`misses` = 本次实际新预测数；`hit_rate = hits/(hits+misses)`（分母为 0 时取 0.0）。**始终写出**；未启用 `--resume` 时 `hits=0` |
| `config` | CLI 参数回显（guards、limit、device、timeout_s、retries、batch_size、model_id、seed、resume、dry_run） |
| `env` | `{python, platform, torch?, cuda?, model_revision?}`（未安装/不适用置 null） |
| `duration_s` | 总耗时（秒） |

## 7. 全局 Exit Code Contract（库内权威副本）

所有脚本与文档的 exit code 语义**以本表为准**（与 `tasks/plan.md` 全局 contract 一字不差）：

| code | 全局语义 | `main.py` | `validate.py` | `metrics.py` |
|---|---|---|---|---|
| **0** | 完全成功 | 请求的 guard 全部成功 | PASS（结构合法 + 覆盖率达标） | 指标完整产出 |
| **1** | 失败（数据或致命） | fatal：输入不可用 / 输出不可写 / **全部** guard 失败 | FAIL：结构违规、eligible 覆盖率不达标、计数不吻合 | fatal：无可 join 记录 / 参数错 / 未实现旗标（响亮拒绝） |
| **2** | 非数据性降级 | 部分成功：≥1 guard 成功且 ≥1 guard 级失败（gated/缺依赖/缺 key） | 用法/IO 错：目标路径不存在、无可校验文件 | 用法/IO 错 |

判读一律看 **exit code + `RESULT:` 行**（`RESULT: ok|partial|fatal predicted=N errors=N skipped=N`），禁止 `| tail`（管道吞 exit code）。

**判例（消除边界歧义）**

| 场景 | 判定 | exit |
|---|---|---|
| `--guards llama-guard` 且无 HF token | 唯一请求的 guard 失败 = **全部** guard 失败 | **1** |
| `--guards rule,llama-guard` 且 llama-guard 无 token | rule 成功 → 部分成功 | **2** |
| C1 smoke（固定只跑 `--guards rule`） | 不涉及 Plus/API guard，缺 token/key 不影响 | **0** |

**Plus/API guard 隔离原则**：Plus 层 guard（OpenAI 等）不进入 Core-Minimal smoke，也不进入默认 CI——`python -m unittest discover` 不依赖任何 key，无 key 用例 `skipIf` 自动跳过。无 key 状态只在**显式 Plus 命令**（用户主动 `--guards ...,openai`）中按 guard 级失败记录，不影响 C1/C3。

## 8. 对 M2/M3 的可用性保证

`id` join 键不变；输出 schema 与 `guard-shieldgemma2`（M3）完全共用（`guard.modality` 字段已支持 image）；`metrics.py` 按 `guard.name` 分组天然支持多 Guard 对比（M2）；探针/对抗分桶只是真值侧过滤器，predictions 无需重跑。
