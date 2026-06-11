# Implementation Plan：guard-llama-guard M2（v1，2026-06-11）

> 来源契约：[`root/M2_SPEC.md`](../M2_SPEC.md)（评审通过、七条修订已落；本计划**不改 spec、不实现代码、不进执行阶段**）。
> 背景契约：[`root/M1_SPEC.md`](../M1_SPEC.md)（exit code 三态、错误三分法、双口径、GuardAdapter 协议、Plus/API 隔离、不删项规则——全部继承，不复述）。
> 现状基线：M1 C3 已交付（[`root/M1_summary.md`](../M1_summary.md)）；本计划基于对 `scripts/main.py`、`scripts/metrics.py`、`scripts/guards/*`、`tests/*`、`examples/*`、`SKILL.md` 的实读编排。

## 路径约定（全局）

**除非带 `root/` 前缀，所有路径相对 `guard-llama-guard/`**。本计划自身与 todo 位于 `root/tasks/plan-m2.md`、`root/tasks/todo-m2.md`（M1 的 `plan.md`/`todo.md` 保持原位不动——`M1_summary.md` 与 `references/io-contract.md` 均有指向它们的既有链接）。

## Overview

把 M2_SPEC 拆为 **20 个 XS/S/M 档任务、5 个阶段、4 个 checkpoint**。垂直切片：每个 L0 任务交付"定义→实现→fixtures 手算对照→落盘可见"的完整链路。**M2 技术交付（C3）只硬依赖 C1（Core-Minimal）+ 任务 19/20（文档与总结）**；C2（judge）是网络可用即应过的软门；P3 与全量数据档按"有则纳入、无则 N/A"吸收（spec §7：P4 交付硬依赖 C1、软吸收 C2/P3/G）。

**Scope Note（继承 M1 原则）**：Plus 不阻塞交付，未完成项 N/A+原因+顺延写入 `root/M2_summary.md`；Extension（WildGuard/vLLM/图像/官方权重切回/Anthropic 协议 judge）只留接口不展开，去向见 M2_SPEC §1 L3。

## Architecture Decisions（编排层执行决策，不改 spec）

- **AD-1 comparison 触发条件 = joined guards ≥ 2**：单 guard 运行不输出 `comparison` 节 → 既有单 guard 黄金样例（`examples/metrics.sample.json`，rule-only）天然逐字段不变，§6-A 兼容锁直接成立。spec 未规定触发条件，此为**默认解释（默认接受制）**——不作为人工阻塞；用户如反对，再调整 comparison 输出策略。登记 R1。
- **AD-2 旗标节按需输出，且无空占位**：`by_category` / `adversarial_split` 仅在对应旗标给出时出现在 metrics.json（spec "只增不改"的实现方式）；`comparison` 与探针对比行同理**不输出空占位节**——comparison 仅在 ≥2 guards 时出现，探针行仅在探针 `eligible_total ≥ 1` 时进入 comparison（M1 既有 bucket 内的零探针输出行为不变，受黄金锁保护）。所有新节只在条件满足时存在，绝不出现空骨架。无旗标输出与 M1 完全一致。
- **AD-3 黄金样例策略**："更新"实现为**新增** `examples/metrics.sample.m2.json`（多 guard + 双旗标，源自 category fixtures 实跑后人工核对固化）；既有 `metrics.sample.json` 一字节不动，本身就是兼容断言。登记 R3。
- **AD-4 `--timeout-s` 改 None 哨兵**：argparse 默认从 `30.0` 改为 `None`；各适配器自给默认（rule 无关 / llama、openai 30 / judge 60），显式给值则全体覆盖——这是实现 spec §5"`--timeout-s` 显式给出时覆盖 judge 的 60"的唯一干净方式。M1 行为不变（None → llama/openai 仍 30）；`run_metadata.config.timeout_s` 回显原始 CLI 值（可为 null）+ 新增 `timeout_s_effective` 按 guard 记录。需同步 SKILL.md/io-contract 默认值文案（任务 19），登记 R2。
- **AD-5 fixtures 用两个合成 guard**（`fixture-guard-a` 带 confidence、`fixture-guard-b` 仿 rule 无 confidence），不依赖任何真实 guard——comparison 的 Δ 列、AUROC null 注记、`--baseline` 切换全部离线可测。二者**仅作为 fixtures 数据中的 `guard.name` 值存在，不注册进 `guards/__init__.py`、不可被 `main.py` 调用**，只服务 metrics 测试。
- **AD-6 P1 内部执行序（串行落盘）**：任务 3/4/5 逻辑独立但同改 `scripts/metrics.py` 与 `tests/test_metrics.py`，**实现与提交顺序固定为 3 → 4 → 5**（禁止多 agent 并发落盘同一文件）；comparison 渲染（任务 5）先于 over-refusal 正式化（任务 6）——探针桶"进对比透视"依赖 comparison 骨架存在。spec DAG 画作并行，此为编排细化。
- **AD-7 judge 纯 stdlib urllib**（spec §5 已定）：`requirements*.txt` 零改动；live 测试与 openai 适配器同模式（`mock.patch.dict` 离线 + opt-in 环境变量）。
- **AD-8 metrics-definitions v2 发甲方式**：在 `root/M1_待甲确认.md` #4 条目追加一行"v2 增补段已就绪，并入同一 review"，不新开确认文件（spec §6-H"并入 #4 review 线程"的最小实现）。

## 与 spec / 现状的冲突与解释登记（只登记，不改 spec）

| # | 类型 | 内容 | 处置 |
|---|---|---|---|
| R1 | 解释 | comparison 何时输出 spec 未定义；若总是输出则破坏 §6-A 兼容锁 | AD-1（≥2 guards）**默认接受制生效**：不设人工确认阻塞；用户反对再调整输出策略 |
| R2 | 实现冲突 | spec §5 要求 judge 超时 60 且"`--timeout-s` 显式给出时覆盖"，但现状 `--timeout-s` 恒有默认 30，适配器无法区分"显式/默认" | AD-4 None 哨兵；io-contract §6 / SKILL.md 的默认值文案在任务 19 同步（一行措辞，非契约语义变化） |
| R3 | 解释 | spec §3 写 `metrics.sample.json`"更新"，§6-A 又要求无旗标输出与 M1 黄金逐字段一致 | AD-3：原文件不动 = 兼容断言；新增 `.m2.json` 黄金 |
| R4 | 解释 | spec §4.2"其余桶样本量够才出"无量化 | 定为 `eligible_total ≥ 1` 即输出指标；**n=0 的桶不输出具体指标**（至多留计数）；每桶 n<30 标 `low_sample_warning`；不设隐藏门槛 |
| R5 | 数据风险 | 甲数据 `adversarial`/`canonical_categories` 实际覆盖率未知；fallback 数据二字段几乎全缺 → `unknown` 桶与审计计数可能很大 | 设计即如实暴露（spec §4.1/4.2 的 warning 与计数），不修数据；进 M2_summary Metric Caveats |
| R6 | 外部风险 | MiMo 端点对 `temperature=0`/`max_tokens` 的兼容性、JSON 输出纪律未实测 | 四步提取策略已设防（spec §5）；任务 11 live 联调首验，失败按记录级 error 路径走 |
| R7 | 性能风险 | judge 串行 HTTP 跑 1,725 条**可能耗时数小时**（端点延迟未实测，不作乐观估计） | `--resume` 分段续跑（M1 消融 E 实证）；**允许 partial 全量**——judge 未跑完时如实标记 partial（任务 18）；**不引入并发**（spec 未授权，列为 M3+ 可选优化，Ask-first） |
| R8 | 编排决策 | M1 的 `tasks/plan.md`/`todo.md` 被两处文档链接引用 | M2 计划落 `plan-m2.md`/`todo-m2.md`，零链接破坏 |
| R9 | 文档同步 | `metrics.py` docstring、io-contract §7、SKILL.md 失败处理/旗标表述、README 中"旗标未实现 → loud refusal"相关文字在实现后过期 | 任务 5 改 docstring（随实现文件本身）；io-contract、SKILL.md、README 三处措辞同步归任务 19 |

---

## Phase 0 · 定义先行（≈半天；零依赖）

### 任务 1：`references/metrics-definitions.md` v2 增补段（S）
- **描述**：把 M2_SPEC §4.1–§4.4 的实质内容落为正式定义文档：by-category 全部计数与公式（support / binary_recall / category_recall / taxonomy_divergence / precision / F1 / macro 排除规则 / low_support_warning<10）、缺失/异常类别三规则与 `category_audit.*` 审计、adversarial 三态分桶、over-refusal 正式化（双口径公式 + error→FP）、comparison 列结构（计数四列 + ao 五指标 + fw Acc/Macro-F1 + Δ 规则）。v1 内容一字不动，v2 为追加节。
- **验收**：v2 节覆盖 spec §4 全部要素且无一处与 v1 冲突；by-category 明确标注"仅 answered_only 口径"及理由。
- **验证**：人工对照 spec §4 逐条勾；`git diff` 确认 v1 区域零改动。
- **依赖**：无。**文件**：`references/metrics-definitions.md`。

### 任务 2：category/adversarial/probe fixtures + 手算答案钥（M）
- **描述**：新建 `tests/fixtures/category_dataset.jsonl`（约 12–14 条 text eligible 记录）与 `tests/fixtures/category_predictions.jsonl`（两个合成 guard，AD-5）。**覆盖矩阵（spec §3 fixtures 行全项）**：多类别真值（≥1 条双类别）；类别命中；二分类命中但类别错（分歧，phishing→S1 型）；adversarial true/false/缺失 三态；探针 ≥3 条（其中 1 条预测为 error 行 → fw 探针用例）；真值 unsafe 缺类别（`unsafe_missing_category`）；未知类别值（→other + 审计）；真值 safe 带类别 + 预测 safe 带类别（双审计）；非探针 error 行（unsafe 真值→fw FN、safe 真值→fw FP 各 ≥1）。**手算答案钥**：全部预期数字（每类别五量、macro、三审计计数、两桶双口径、comparison Δ）落成**可追踪文件 `tests/fixtures/category_expected.json`**（结构与 metrics.json 新节对齐，附 `_notes` 字段记录推导依据），两次独立手算一致后入库；后续测试一律引用/对照该文件，不散落 docstring。
- **验收**：覆盖矩阵逐项有对应记录 id；`category_expected.json` 两次独立手算一致且可 `json.loads`。
- **验证**：`validate.py` 跑 predictions fixture 结构 PASS（错误行合法）；记录数与矩阵对照表一致。
- **依赖**：任务 1。**文件**：`tests/fixtures/category_dataset.jsonl`、`tests/fixtures/category_predictions.jsonl`、`tests/fixtures/category_expected.json`（本阶段不建测试文件）。

### ☑ Checkpoint C0
- **成功条件**：v2 定义自审通过；`tests/fixtures/category_expected.json` 定稿；`M1_待甲确认.md` #4 已追加 v2 一行（AD-8）。（AD-1/R1 走默认接受制，**不设人工阻塞**；用户反对再调整 comparison 输出策略。）
- **失败处理**：定义有分歧 → 修订任务 1 后再进 P1（接口先行）。

---

## Phase 1 · Core-Minimal（≈1–2 天；C0 后；全程零第三方依赖）

> 实现均落 `scripts/metrics.py`（现状 294 行，函数级落点已勘察：`compute_bucket` 复用、`build_metrics` 内加分节、`render_markdown` 加表、`main()` 解除 246–252 行响亮拒绝）。

### 任务 3：`--by-category` 实现 + 测试（M）
- **描述**：新增 `compute_by_category(joined)`：仅 answered∩eligible；真值类别取 `label.canonical_categories`；按任务 1 定义产出 `results[guard]["by_category"] = {categories: {...}, macro: {...}, unsafe_missing_category, unknown_category_values, category_audit: {...}, basis_note}`；仅旗标给出时挂节（AD-2）；解除该旗标的响亮拒绝；markdown 渲染按类别表（support 降序，截断显示 + 全量进 json）。测试新建 `TestByCategory`（对照 `tests/fixtures/category_expected.json` 逐项断言 + 审计计数不污染指标断言）。
- **验收**：spec §6-B 四个勾全绿；无旗标运行 metrics.json 无 `by_category` 键。
- **验证**：`python -m unittest tests.test_metrics -v`；fixtures 上带/不带旗标各跑一次 CLI 对照。
- **依赖**：任务 2。**文件**：`scripts/metrics.py`、`tests/test_metrics.py`。

### 任务 4：`--adversarial-split` 实现 + 测试（S）
- **描述**：三态切片（true/false/缺失或非布尔→unknown）；前两桶各对标准四桶复用 `compute_bucket`（head_binary 必出，其余 `eligible_total ≥ 1` 才出，R4）；每桶挂 `low_sample_warning`（n<30）；unknown 仅 `{eligible_total}`；仅旗标时挂节；解除响亮拒绝。测试 `TestAdversarialSplit`（对照 `category_expected.json` 的三态计数与两桶双口径 + 与全集 head_binary 的分片守恒：两桶 eligible 之和 + unknown = 全集）。
- **验收**：spec §6-C 两勾全绿；分片守恒断言通过。
- **验证**：同任务 3 模式。
- **依赖**：任务 2；**提交序在任务 3 之后**（AD-6 串行落盘）。**文件**：同任务 3。

### 任务 5：comparison 渲染 + `--baseline`（M）
- **描述**：新增顶层 `comparison` 节（AD-1：joined guards ≥2 才输出）：按 bucket 透视，行=guard；列三组=计数四列（eligible_total/answered_total/coverage/error_rate）+ ao 五指标 + fw Acc/Macro-F1；`delta_vs_baseline` 覆盖 ao 与 fw 列（基线默认 `rule`，`--baseline` 可换；基线不在 joined guards 中 → 无 Δ + 一行 note，不报错）。markdown 渲染对比表。**顺带**：更新 metrics.py 模块 docstring 的 exit code 注释（R9 前半）。测试 `TestComparison`（对照 `category_expected.json` 的 Δ 值、含 error 行的 ao/fw 分叉防虚高、baseline 切换、单 guard 无 comparison）。
- **验收**：spec §6-D 两勾全绿。
- **验证**：同上；另跑单 guard CLI 确认无 comparison 键。
- **依赖**：任务 2；**提交序在任务 4 之后**（AD-6 串行落盘）。**文件**：同任务 3。

### 任务 6：over-refusal 对比正式化 + 测试（S）
- **描述**：探针识别与桶内计算复用 M1 既有路径；M2 新增双口径输出的正式核验与 comparison 透视（over_refusal_rate 双口径列 + Δ）。**字段名兼容检查**：核对 M1 实际输出字段名（现状为 `over_refusal_probe` 桶 + `over_refusal_rate.{answered_only,failure_as_wrong}`）与 v2 定义/spec 用名（如 `unsafe_fpr_on_safe_probe` 类表述）是否一致；如有出入**只加兼容别名**（新名与旧名同值并存），不改不删 M1 既有字段（黄金锁保证）。测试 `TestOverRefusalFormal`：fw 口径含 error 探针（error 行计 FP）的手算用例、低样本 warning、探针行在 comparison 中数值与 bucket 一致性断言、别名一致性断言（若引入）。
- **验收**：spec §6-O 两勾全绿。
- **验证**：同上。
- **依赖**：任务 5（AD-6）。**文件**：同任务 3。

### 任务 7：黄金样例 + 向后兼容锁（S）
- **描述**：`examples/metrics.sample.m2.json` 固化（category fixtures + 双旗标 + 双合成 guard 实跑 → 人工核对 → 锁定）；新测试 `TestMetricsSampleM2Golden`（实跑≡黄金）+ `TestBackwardCompat`（无旗标单 guard 实跑 ≡ 既有 `metrics.sample.json`，即 M1 黄金锁在 M2 代码上重申）；确认 M1 现有测试全集零修改全绿。
- **验收**：spec §6-A 两勾全绿；新旧黄金双锁定。
- **验证**：`python -m unittest discover -s tests -v` 全绿；干净 venv（零第三方包）复跑一遍。
- **依赖**：任务 3,4,5,6。**文件**：`examples/metrics.sample.m2.json`、`tests/test_metrics.py`。

### ☑ Checkpoint C1（M2 唯一硬门的技术半）
- **成功条件**：spec §6-A/B/C/D/O 全勾；unittest 全绿且零第三方依赖（pip freeze 复证）；fixtures CLI 全链路（带旗标 main→metrics）exit 0。
- **失败处理**：阻塞修复，不进 P2。

---

## Phase 2 · Core-Full：LLM-as-judge（C2 软门；C1 后；仅依赖网络 + 运行时 key）

### 任务 8：`llm_judge.py` 适配器 + 离线测试（M）
- **描述**：新建 `scripts/guards/llm_judge.py`（GuardAdapter；纯 stdlib urllib；spec §5 契约全项：env 凭证/端点缺一即 unavailable+FIX、默认模型 `mimo-v2.5-pro`、temperature=0、max_tokens=256、request_timeout_s=60、退避 min(2**attempt,8)、四步 JSON 提取、safe→categories=[] 规范化+审计、confidence 缺失/非数字→null+计数、越界→clamp+计数、注入防护分隔符 prompt、raw_output 全文、cost=null）；注册表加 `"llm-judge"`。新建 `tests/test_llm_judge.py`（注册表；`mock.patch.dict` 清 env → unavailable+FIX；罐头响应解析 ≥5 例：unsafe 正常/safe 带多余类别/带代码栅栏的 JSON/坏 JSON 两次→error/confidence 越界与非数字；prompt 构造含分隔符断言——全部离线）。
- **验收**：spec §6-E 第一勾全绿；`get_adapter("llm-judge")` 在零第三方环境可取（urllib 属 stdlib）。
- **验证**：`python -m unittest tests.test_llm_judge -v` 离线全绿。
- **依赖**：C1。**文件**：`scripts/guards/llm_judge.py`、`scripts/guards/__init__.py`、`tests/test_llm_judge.py`。

### 任务 9：`main.py` 接线：`--judge-model` + timeout 哨兵（S）
- **描述**：`--judge-model`（默认 None → 适配器自取 env `LLM_JUDGE_MODEL` → 再缺省 `mimo-v2.5-pro`）入 adapter_config；AD-4 的 `--timeout-s` None 哨兵改造（llama/openai 适配器内补默认 30，judge 60）；run_metadata.config 回显 judge_model 与原始 timeout_s。
- **验收**：M1 全部既有测试不变绿（哨兵改造无行为回归）；`--timeout-s` 缺省时 run_metadata 回显 `timeout_s: null` 且 **`timeout_s_effective` 按 guard 展开**（llama/openai=30、judge=60）；llama/openai 默认 30 行为逐项确认不回归（缺省与显式 `--timeout-s 30` 行为一致）。
- **验证**：unittest 全绿 + dry-run/smoke CLI 各一次对照 run_metadata（含 null 与 effective 两字段）。
- **依赖**：任务 8。**文件**：`scripts/main.py`、`scripts/guards/llama_guard.py`、`scripts/guards/openai_moderation.py`（各一行默认值处理）。

### 任务 10：`references/llm-judge-notes.md`（XS）
- **描述**：prompt 模板原文、注入防护设计与已知残余风险（对抗样本可操纵裁决——报告素材）、自报 confidence 非校准告诫、协议与环境变量说明（只写变量名，URL/key 永不落文件）、与 OpenAI Moderation 的隔离关系。
- **验收**：spec §5 每行契约在 notes 有对应说明；`git grep` 无端点 URL/key。
- **验证**：人工对照 + git grep。
- **依赖**：任务 8。**文件**：`references/llm-judge-notes.md`。

### 任务 11：live 联调（S；需用户 session 注入 env）
- **描述**：`LLM_JUDGE_LIVE=1` opt-in 测试 + 样本实跑：`main.py --guards llm-judge --input examples/input.sample.jsonl`（5 条 text 全非 error、categories 合法）→ `validate.py --against` PASS；无 key 复跑验证 exit 1（单独）/exit 2（与 rule 同跑）判例——**两判例只针对显式 `--guards` 含 `llm-judge` 的命令；smoke（`--guards rule`）与默认 CI 永不运行 llm-judge，无 key 不影响其 exit 0**（Plus/API 隔离原则）；交付前 `git grep` key/URL 自查。
- **验收**：spec §6-E 后两勾全绿。
- **验证**：exit code + RESULT 行 + validate PASS + git grep 零命中。
- **依赖**：任务 8,9,10 + 用户提供 env（key/base-url 已在用户手中）。**文件**：无新文件（notes 回填实测数字）。

### 任务 12：三 Guard 对比矩阵（顶替数据）（S）
- **描述**：rule + llama-guard + llm-judge 在 M1 顶替数据集（examples+fixtures，10 eligible）上全链路 → comparison 表含三行 + judge 的 AUROC（自报分）→ 截图素材；llm-judge-notes 回填首批观测（判定分布、与 llama 分歧样本、延迟）。
- **验收**：metrics.md 对比表三 guard 齐；judge 行 over_refusal 探针有数。
- **验证**：main exit 0（三 guard 全成）或如实记录 partial；metrics RESULT: ok guards=3。
- **依赖**：任务 11（+ M1 已就绪的 llama 镜像权重环境）。**文件**：`out_*`（gitignored）+ notes 回填。

### ☑ Checkpoint C2（软门）
- **成功条件**：spec §6-E 全勾；三 Guard 矩阵存在。
- **失败处理**：端点不可用 → live 档 N/A+原因，对比退回两 Guard，**不阻塞 C3**。

---

## Phase 3 · Plus（C1 后与 P2 并行；逐项可 N/A）

> 引用纪律（任务 13/14/15 通用）：对"M1 已证"类结论，`references/ablations.md` / `references/llama-guard-notes.md` 已有记录数字的才可引用且须标注来源；M1 未记录的不直接断言，做轻量 sanity 复测后再引用。

### 任务 13：消融 A+B（模板×2；token 概率 vs 文本解析 AUROC）（M；GPU）
- **描述**：A：typed-content 官方模板 vs plain-string fallback 两版在同一数据上对比 Recall/FPR（适配器已有双路径）；B：同一轮生成下 token 双向归一 confidence vs 文本解析（confidence=null）对 AUROC 的影响。回填 `references/ablations.md` A/B 节（替换 N/A，保留原 N/A 行迹）。
- **验收**：两节各一张数字表 + 一句结论；复现命令齐。
- **验证**：表中数字可由记录的命令重出。
- **依赖**：C1（GPU + 镜像权重即 M1 现状）。**文件**：`references/ablations.md`。

### 任务 14：消融 D（batch {1,4,8,16} 吞吐/延迟）（S；GPU）
- **描述**：同一输入扫 4 档 batch-size，记录吞吐、单条延迟、判定一致性（batch/单条 verdict 一致与 conf 漂移 ≤0.018 在 `llama-guard-notes.md` 有 M1 记录——引用并标注来源；本轮扫描若观察到不一致则如实记录并复测，不沿用旧结论）。回填 D 节。
- **验收/验证/文件**：同任务 13 模式。**依赖**：C1。

### 任务 15：消融 C（阈值扫描；先 llama 单源，judge 后补）（S）
- **描述**：llama confidence 上扫 0.3/0.5/0.7 出 FPR/Recall 曲线表（已决事项 2：先单源）；C2 过后追加 judge 自报分第二源（标注非校准）。回填 C 节。
- **验收/验证/文件**：同上。**依赖**：C1（单源）；任务 12（第二源，可后补）。

### 任务 16：trigger eval 实测档（S；人工配合）
- **描述**：与甲 #3 合并一轮（已决事项 3）：乙侧 8 正例自测 + 甲侧 6 负例盲测，全新会话逐条，结果分别回填 `references/trigger-eval.md`（达标线：正例 ≥7/8、负例 0 误触；判官 skill 描述未变，M1 文档化判定作 baseline 对照）。
- **验收**：实测档表格替换"未实测"标注；达标或如实记录未达标+分析。
- **验证**：记录会话日期/模型版本。
- **依赖**：C1 后任意；外部=甲配合。**文件**：`references/trigger-eval.md`。

### 任务 17：report 模板 v2（XS）
- **描述**：`templates/report-section.md` 增补 comparison 透视/by-category/adversarial/Metric Caveats 占位符（与 metrics.json 新节字段一一对应）。
- **验收**：占位符 ↔ 字段映射表齐；不破坏 v1 占位符。
- **验证**：人工对照新 metrics.json 键。
- **依赖**：C1。**文件**：`templates/report-section.md`。

### 任务 18：全量 1,725 条结果档（S 执行 + 等待；数据依赖）
- **描述**：甲数据 checker exit 0 后：三 guard（或可用集）全量 + 双旗标 + comparison → 真实指标矩阵 + E2E 截图；judge 段用 `--resume` 分段跑（R7，可能耗时数小时）；**partial 全量规则**：若 rule/llama 全量完成而 judge 未完成，结果档与 `root/M2_summary.md` 必须标记 **partial（两 Guard 全量 + judge 部分/缺席）**，不得声称三 Guard 全量完成；`M1_待甲确认.md` #2 状态同步。
- **验收**：spec §6-G 勾或按 M1 #2 模式标"顶替+提交前重跑"；partial 时 M2_summary 标记如实。
- **验证**：run_metadata 守恒式 + validate PASS + metrics RESULT 行。
- **依赖**：C1 + C2（judge 行可选）+ **甲 #2 数据**。**文件**：`out_*`（gitignored）+ 截图归档。

---

## Phase 4 · 交付（硬依赖 C1；软吸收 C2/P3/任务 18）

### 任务 19：文档同步终稿（S）
- **描述**：SKILL.md（两旗标解禁示例、guards 表/Quick workflow/sanity 表/troubleshooting 各加 llm-judge 行、`--timeout-s` 默认值文案改"按 guard：llama/openai 30s、judge 60s"、测试计数行改"现有测试全集"措辞；**≤250 行红线**）；`references/io-contract.md` §6/§7 两处措辞同步（R2/R9）；README guards 表加 judge 行（注明非校准 confidence）。
- **验收**：spec §6-H 第一勾；SKILL.md 行数达标、指针全有效。
- **验证**：行数统计 + 指针逐一存在性检查 + 命令复制粘贴可跑。
- **依赖**：C1（内容随 C2/P3 实际达成情况回填，N/A 项如实标注）。**文件**：`SKILL.md`、`references/io-contract.md`、`README.md`。

### 任务 20：`root/M2_summary.md` + 验收 sweep + push（S）
- **描述**：追溯表（M2 范围 × 层级 × 文件 × 测试 × spec §6 验收项）、N/A 表（候选：judge live 若端点故障、消融逐项、trigger eval、全量档）、已知限制、Extension Backlog（L3 五行 + R7 并发优化）、**Metric Caveats 四条**（by-category 仅 answered_only；judge confidence 非校准；low_support 不作强结论；fallback 数据不可作最终结果）；spec §6 全清单 sweep；`M1_待甲确认.md` 相关条目状态同步；push。
- **验收**：spec §6-H 第二勾；§6 各项勾或 N/A 无遗漏。
- **验证**：对照 spec §6 逐字母核对；git push 成功。
- **依赖**：任务 19；吸收 8–18 实际状态。**文件**：`root/M2_summary.md`、`root/M1_待甲确认.md`。

### ☑ Checkpoint C3 = M2 技术交付
- **成功条件**：spec §6-H 全勾；A/B/C/D/O 全勾（C1 已保证）；E/F/G 各项勾或 N/A+原因+顺延。
- **失败处理**：未勾项按不删项规则入 M2_summary；Core-Minimal 未过则 M2 失败（无降级）。

---

## 并行化与关键路径

- **关键路径**：任务 1 → 2 → 3 → 4 → 5 → 6 → 7 → C1 → 19 → 20（纯 L0 链；3/4/5 逻辑独立但同文件**串行落盘**，AD-6；全程无外部依赖，估 2–3 天）。
- **可并行**：C1 后 P2（8→9→10→11→12）与 P3（13/14/15/17 互独立；16/18 等外部）两线并行。
- **外部依赖跟踪**：① judge env（key/base-url/model 已在用户手中，任务 11 时 session 注入）；② GPU 窗口（任务 13–15，M1 环境现成）；③ 甲 #2 数据（任务 18）；④ 甲 #3 + 人工新会话（任务 16）。

## 任务规模一览

| 档 | 任务 |
|---|---|
| XS | 10, 17 |
| S | 1, 4, 6, 7, 9, 11, 12, 14, 15, 16, 18, 19, 20 |
| M | 2, 3, 5, 8, 13 |

无 L/XL；每任务触文件 ≤5；每任务自带验证命令。
