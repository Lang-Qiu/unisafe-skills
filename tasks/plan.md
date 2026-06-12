# Implementation Plan：guard-llama-guard M1（v2，2026-06-11 review 修订）

> 来源契约：[`root/M1_SPEC.md`](../M1_SPEC.md)（未改动）。本计划**只做任务编排，不改 spec、不实现代码**。
> v2 修订：吸收 12 条 review 意见——Phase 4 与 C2 解耦、全局 exit code contract、`--against` 覆盖率重定义（eligible 口径）、metrics 双口径防虚高、GuardAdapter 协议增强、requirements 三分层、新增性能消融任务（任务 17）、OpenAI 定位为 API baseline、路径根约定、category_mapping 位置说明、M0/甲数据 fallback 规则、人工审阅移出技术验收。任务总数 19 → **20**。
> v2.1 终轮小修：exit code 判例与 Plus 隔离原则、validate `--metadata` 可选参数、消融 E 项改 resume/idempotence（含 resume 计数字段）、requirements.txt 纯注释合法性、M1_summary 增 Extension Backlog 表。

## 路径约定（全局）

**除非带 `root/` 前缀，本计划所有路径一律相对 `guard-llama-guard/`**。例：`scripts/main.py` = `guard-llama-guard/scripts/main.py`；`root/M1_summary.md` = 仓库根目录文件。

## Overview

把 `guard-llama-guard`（方向 B 的 M1 主 Skill）按垂直切片拆为 **20 个 S/M 档任务、4 个阶段、4 个 checkpoint**。每个任务交付一条可独立运行验证的链路。**M1 最终交付（C3）只以 Core-Minimal（C1）为必需条件**；Core-Full（C2）与 Plus 未达成项按"不删项"规则以 N/A+原因+顺延里程碑进入 `root/M1_summary.md`，不阻塞交付。

## 完成确认（2026-06-11）

- [x] **C0 契约就绪**：schema、I/O contract、category mapping、input sample 均已落库并通过解析/一致性核对。
- [x] **C1 Core-Minimal 已通过**：rule smoke 全链路 main → validate → metrics exit 0；`python -m unittest discover -s tests -v` 为 41 tests OK，1 个 live OpenAI opt-in skip；`phase1smoke.png` 已存档。
- [x] **C2 Core-Full 已通过（fallback 数据 + 镜像权重）**：`out_task13_e2e_v3` 两 guard E2E 已跑通，main `RESULT: ok predicted=20 errors=0 skipped=3`，validate `RESULT: PASS files=2 records=20`，metrics `RESULT: ok guards=2 joined=20`；`C3截图.png` 已存档。
- [x] **C3 M1 技术交付已完成**：20 个任务均已处置；Core-Minimal 必需项全勾；Core-Full/Plus 未完全实测项按 N/A + 原因 + 顺延里程碑记录在 `root/M1_summary.md`。
- [x] **外部/人工项不阻塞 M1**：甲侧 #2 数据日期、#3 trigger eval 盲测、#4 metrics review 签字，以及用户终审，转为交付后人工审阅/M2 跟踪项。

**Scope Note：Plus / Extension 处理原则**

本 implementation plan 以 M1 可交付闭环为主，Core-Minimal 与 Core-Full 是 M1 主线。

Plus 任务在本计划中只保留 M1 最有价值的轻量增强项，包括 API baseline、over-refusal 指标和 trigger eval。Plus 不阻塞 C3，未完成项按 N/A + 原因 + 顺延里程碑写入 M1_summary.md，可整体顺延到 M2。

Extension 任务不在本 implementation plan 中展开。它们保留在 M1_SPEC.md / 后续 Extension plan 中，包括但不限于：
- LLM-as-judge 适配器；
- WildGuard 适配器；
- 多模态 image safety 路径；
- vLLM / 高吞吐后端；
- 更完整的性能消融实验。

M1 阶段只需要在接口、文件结构、metrics 字段和 M1_summary.md 中为 Extension 留出追踪入口，不要求实现。

## Architecture Decisions（编排层，spec 之外的执行决策）

- **垂直切片重组**：spec DAG 的 P1 水平分层重组为四条链路切片：dry-run 链路（任务 5）→ rule 预测链路（6–7）→ 校验链路（8）→ 指标链路（9），每条链路自带测试。
- **Phase 4 与 C2 解耦**：交付阶段的硬前置只有 C1；C2/P3 的产物"有则纳入、无则 N/A"。理由：评分 40%+30% 的底盘在 Core-Minimal 的可发现/可跑通/可复现，Core-Full 是质量增益而非交付条件（与 spec §9.0 总览表的降级语义一致）。
- **测试嵌入切片**：测试与 fixtures 在各切片任务内完成，checkpoint 统一跑 `python -m unittest discover -s tests`。
- **SKILL.md v1 提前**到 C1 前（任务 10），终稿（任务 18）仅回填实测数字。
- **黄金文件模式**：`examples/output.sample.jsonl` 任务 7 人工核对后固化，测试锁定防回归。
- **风险 spike 前置**：token 切分与软超时两个风险在任务 11 第一步实测，失败立即触发降级。
- **`category_mapping.json` 保留在 `references/`（不挪 `assets/`）**：该文件是甲乙**双边契约工件**（M0 §4 明文约定路径"各自 `references/category_mapping.json`，内容须一致"，已推送生效），且兼具"标签政策/字段规范"的文档属性（作业模板将 label-policy 类放 references/）。机器可读不妨碍其规范地位；挪动需重开契约变更，收益不抵成本。`assets/` 仅放纯运行数据（`rule_keywords.json`）。
- **fallback 规则（全局）**：Core-Minimal 链路（任务 5–10）**只依赖 skill 内文件**（`examples/` + `tests/fixtures/`）。所有引用 `root/M0_*` 或甲侧数据的任务均为只读、且必须声明 skill 内 fallback；甲数据缺位永不阻塞任何 checkpoint。
- **与 spec 的差异登记**（C3 时决定是否回写 spec，本轮不改 spec）：① spec §10 P4 写"依赖 C2"，本计划解耦；② spec §3 单一 `requirements.txt` 细化为三文件分层；③ GuardAdapter 协议新增 `capabilities`/`predict_batch`；④ metrics 新增双口径与四个计数字段；⑤ 消融从"后续可选"升格为 Plus 任务 17。

## 全局 Exit Code Contract（单一权威定义）

所有脚本、README、SKILL.md 的 exit code 章节**必须引用本表**（任务 10/18 有对应验收项），不得各写各的：

| code | 全局语义 | `main.py` | `validate.py` | `metrics.py` |
|---|---|---|---|---|
| **0** | 完全成功 | 请求的 guard 全部成功 | PASS（结构合法 + 覆盖率达标） | 指标完整产出 |
| **1** | 失败（数据或致命） | fatal：输入不可用 / 输出不可写 / **全部** guard 失败 | FAIL：结构违规、eligible 覆盖率不达标、计数不吻合 | fatal：无可 join 记录 / 参数错 / 未实现旗标（响亮拒绝） |
| **2** | 非数据性降级 | 部分成功：≥1 guard 成功且 ≥1 guard 级失败（gated/缺依赖/缺 key） | 用法/IO 错：目标路径不存在、无可校验文件 | 用法/IO 错 |

语义与 spec §5.3/§6 一致；本表是唯一集中表述。判读一律 exit code + `RESULT:` 行，禁 `| tail`。

**判例（消除边界歧义）**

| 场景 | 判定 | exit |
|---|---|---|
| `--guards llama-guard` 且无 HF token | 唯一请求的 guard 失败 = **全部** guard 失败 | **1** |
| `--guards rule,llama-guard` 且 llama-guard 无 token | rule 成功 → 部分成功 | **2** |
| C1 smoke | **固定只跑 `--guards rule`**，不涉及 Plus/API guard，缺 token/key 不可能影响 C1 | 0 |

**Plus/API guard 隔离原则**：Plus 层 guard（OpenAI 等）**不进入 Core-Minimal smoke，也不进入默认 CI**——`python -m unittest discover` 不依赖任何 key，无 key 用例 `skipIf` 自动跳过。无 key 状态只在**显式 Plus 命令**（用户主动 `--guards ...,openai`）中按 guard 级失败记 N/A，不影响 C1/C3。

---

## Task List

### Phase 0 · 契约与骨架（对应 spec P0；全部可并行）

---

#### 任务 1：guard 输出 JSON Schema

**Description**：编写 `schemas/guard_output.schema.json`（draft 2020-12），完整约束 spec §5.2 单条预测记录，含条件逻辑 "`prediction.is_unsafe=null` ⇔ `error≠null`"、`risk_categories ⊆ 22 类+other` 枚举。

**Acceptance criteria**
- [x] schema 可被 `json.load` 解析，`$schema`/`required`/枚举齐全
- [x] 能表达三类非法：缺 `id`、`is_unsafe` 为字符串、孤儿 error——表达力由任务 8 的 test_validate 兑现
- [x] 22 类枚举与 `references/category_mapping.json`（任务 3）同源一致

**Verification**
- [x] `python -m json.tool schemas/guard_output.schema.json` exit 0
- [x] 对 `root/M0_guard_output_sample.jsonl` 4 条逐条人工比对：每条都应合法

**Dependencies**：None ｜ **Files**：`schemas/guard_output.schema.json` ｜ **Scope**：XS
**映射**：spec T0.1；验收 §9-A/F

---

#### 任务 2：I/O 契约文档

**Description**：把 spec §5 落库为 `references/io-contract.md`：消费字段表、错误三分法判定表、文件布局、run_metadata 字段、守恒式，并**内嵌全局 Exit Code Contract 表**（本计划上文为源，文档为库内权威副本）。

**Acceptance criteria**
- [x] 与 spec §5 及 `root/M0_接口约定.md` §5 补充块零冲突（人工 diff）
- [x] 错误三分法含触发条件、处理方式、exit code 影响三列；exit 表与全局 contract 一字不差
- [x] 明确 eligible 定义：按路由规则 in-scope 的记录集合（任务 8/9 的覆盖率与指标分母依据）

**Verification**
- [x] 自审 + 对照 M0 §5 逐行核对

**Dependencies**：None ｜ **Files**：`references/io-contract.md` ｜ **Scope**：XS
**映射**：spec T0.2；验收 §9-E

---

#### 任务 3：共享映射表 + 指标定义

**Description**：`references/category_mapping.json`（S1–S14 / OpenAI / rule 词表类别 → 22 类，与 M0 §4 一字不差；位置理由见 Architecture Decisions）+ `references/metrics-definitions.md`（公式、正类=unsafe、AUROC 秩统计、真值字段对齐表、**双口径定义**：answered-only 与 failure-as-wrong，及 `eligible_total / answered_total / coverage / error_rate` 四计数字段——甲交叉 review 的载体）。

**Acceptance criteria**
- [x] mapping 三段齐全；S6 双映射、`other` 兜底显式
- [x] metrics 文档含 5 项公式 + 双口径语义（answered-only=剔除 error；failure-as-wrong=error 计为错判的保守口径）+ 剔除规则 + over-refusal 定义 + 四计数字段公式（coverage=answered/eligible、error_rate=errors/eligible）

**Verification**
- [x] `python -m json.tool` exit 0；与 M0 §4 表逐行 diff 一致

**Dependencies**：None ｜ **Files**：`references/category_mapping.json`、`references/metrics-definitions.md` ｜ **Scope**：S
**映射**：spec T0.2/§7；验收 §9-C④/D

---

#### 任务 4：输入样例（覆盖矩阵；M0 的 skill 内 fallback）

**Description**：从 `root/M0_dataset_unified_sample.jsonl`（只读）裁剪 6 条为 `examples/input.sample.jsonl`：unsafe prompt-only、safe prompt-only、safe pair（拒答）、unsafe pair、XSTest 探针、image 记录（演示 skip）。**裁剪入库后，后续所有任务只依赖 `examples/`，不再读取 `root/M0_*`**（fallback 规则落地）。

**Acceptance criteria**
- [x] 6 条覆盖矩阵齐全；每行可 `json.loads`；id 保持 M0 原值
- [x] Core-Minimal 链路（任务 5–10）声明的输入均指向本文件而非 root/M0_*

**Verification**
- [x] `python -c "import json;[json.loads(l) for l in open('examples/input.sample.jsonl',encoding='utf-8')]"` exit 0

**Dependencies**：None ｜ **Files**：`examples/input.sample.jsonl` ｜ **Scope**：XS
**映射**：spec T0.3；验收 §9-G

---

### ✅ Checkpoint C0：契约就绪

- [x] 任务 1–4 产物存在且全部可解析（json.tool exit 0；6 条样例逐行 json.loads 通过；jsonschema 实测：M0 4 条样本全 VALID，缺 id/字符串 is_unsafe/孤儿 error/反向孤儿全 REJECTED）
- [x] `category_mapping.json` ↔ M0 §4 人工 diff 一致（S1–S14 14 键、OpenAI 13 键、S6 双映射、other/general_harm 双兜底）；schema 22 类枚举与之同源（程序断言通过）
- [x] io-contract 内的 exit 表与本计划全局 contract 一致（含判例与 Plus 隔离原则）
- [x] 甲侧事项已推送（`root/待甲确认.md`，commit 7c7450e ✅）
- **失败处理**：契约有分歧 → 当天与甲对齐再动代码；自审不过 → 修复后再进 P1

---

### Phase 1 · Core-Minimal 垂直闭环（对应 spec P1；只依赖 skill 内文件）

---

#### 任务 5：dry-run 链路（读入→路由→计数→run_metadata）

**Description**：`scripts/utils.py`（UTF-8 流式 JSONL 读写、pathlib、id 工具、mapping 加载器、计时）+ `scripts/main.py` 骨架：`--input/--output-dir/--dry-run/--limit`，按 io-contract 路由并计数（eligible / out_of_scope / missing_content），写 `run_metadata.json`，打印 `RESULT:` 行，exit 语义按全局 contract。

**Acceptance criteria**
- [x] `main.py --input examples/input.sample.jsonl --output-dir out_dry --dry-run` → exit 0；计数 total=6、eligible=5、skipped.out_of_scope=1
- [x] run_metadata 含 spec §5.4 全部字段 + `eligible` 计数（guards 为空列表可）
- [x] 输入路径不存在 / 0 条可解析 → exit 1 + 可读原因（contract 第 1 行语义）

**Verification**
- [x] 上述命令 + exit code 三态实测；人工查看 run_metadata.json 字段

**Dependencies**：任务 2、4 ｜ **Files**：`scripts/utils.py`、`scripts/main.py` ｜ **Scope**：M
**映射**：spec T1.1+T1.3 前半；验收 §9-E

---

#### 任务 6：guards 框架 + 规则基线适配器

**Description**：`scripts/guards/base.py`（`GuardAdapter` 协议：`available() -> (bool, reason)`、`predict(record) -> dict`、**`capabilities` 属性**（`supports_batch / returns_confidence / modalities`）、**`predict_batch(records)` 默认实现 = 循环调用 `predict`**——为 Llama Guard 批推理与任务 17 消融预留接口）、`__init__.py`（注册表 + 懒 import）、`rule_based.py`（词边界正则、大小写无关、类别→canonical、`confidence=null`、`supports_batch=False`）、`assets/rule_keywords.json` 词表 v1、`tests/test_rule_guard.py` + `tests/fixtures/mini_unified.jsonl`（6–8 条手工微型数据，**不依赖 root/M0_***）。

**Acceptance criteria**
- [x] rule adapter 对 fixtures 的预测序列逐字段确定（test 断言锁定）
- [x] 协议测试：默认 `predict_batch` 与逐条 `predict` 结果完全一致；`capabilities` 字段齐全
- [x] 词表按 canonical 类别分组；探针误伤行为如实保留（spec §12.3-12）
- [x] 不装任何第三方包时 `get_adapter('rule')` 可用

**Verification**
- [x] `python -m unittest tests.test_rule_guard -v` 全绿；干净 venv import 冒烟

**Dependencies**：任务 3 ｜ **Files**：`scripts/guards/{__init__,base,rule_based}.py`、`assets/rule_keywords.json`、`tests/test_rule_guard.py`、`tests/fixtures/mini_unified.jsonl` ｜ **Scope**：M（6 文件，逻辑集中在 2 个）
**映射**：spec T1.2 + T1.6 部分；验收 §9-C②

---

#### 任务 7：rule 预测链路落盘 + 黄金输出

**Description**：main.py 接入注册表：`--guards rule` → `predictions/rule.predictions.jsonl` 逐行 append、`--resume`、guard 级失败 exit 2 语义、error 记录写行规则。跑 `examples/input.sample.jsonl`，人工逐条核对后固化 `examples/output.sample.jsonl` 黄金文件。

**Acceptance criteria**
- [x] predictions 5 行；id 与输入逐字一致；`RESULT: ok predicted=5 errors=0 skipped=1`
- [x] 重跑 `--resume` → 0 新增、exit 0；run_metadata 记录 `resume_hits / resume_misses / resume_hit_rate`（任务 17-E 的数据源）；exit 三态符合全局 contract
- [x] 黄金文件与实跑字段级一致（latency/timestamp 除外），不含 error 行（error 示例归 fixtures）

**Verification**
- [x] smoke 命令 + exit code 核对；test_rule_guard 黄金比对用例全绿

**Dependencies**：任务 5、6 ｜ **Files**：`scripts/main.py`、`examples/output.sample.jsonl`、`tests/test_rule_guard.py`（追加） ｜ **Scope**：S
**映射**：spec T1.3 后半；验收 §9-E/G/I

---

#### 任务 8：校验链路（validate.py）

**Description**：`scripts/validate.py`：纯 stdlib schema 子集结构校验 + 覆盖率核对，exit 按全局 contract；有 `jsonschema` 则额外全量校验（可选增强）。CLI 两个核对参数：**`--against <input>`** —— 以 **eligible 集合**（输入按 io-contract 路由后的 in-scope 记录）为基准，校验 predictions ids 与 eligible ids **双向一致**（无缺失、无多余、无重复）= 100%；out_of_scope/image skip **不要求** prediction。**`--metadata <run_metadata.json>`（可选）** —— 提供时**额外**校验 `skipped/out_of_scope` 计数与输入实际 skip 数吻合；不提供时只做 ids 覆盖关系校验。`tests/test_validate.py` + 非法 fixtures（缺 id / 字符串 `"unsafe"` / 孤儿 error）。

**Acceptance criteria**
- [x] 黄金输出 → PASS exit 0；三类非法各 FAIL exit 1 且报错带行号
- [x] `--against examples/input.sample.jsonl`：eligible 5/5 双向一致通过；人为删一行（缺失）→ FAIL；人为加幽灵 id（多余）→ FAIL
- [x] 提供 `--metadata` 且 skip 计数不吻合（篡改 run_metadata）→ FAIL；**不提供 `--metadata` 时不校验计数**；image 记录无 prediction 不报错

**Verification**
- [x] `python -m unittest tests.test_validate -v` 全绿；CLI 三态 exit 实测

**Dependencies**：任务 1、7 ｜ **Files**：`scripts/validate.py`、`tests/test_validate.py`、`tests/fixtures/`（非法样本） ｜ **Scope**：S
**映射**：spec T1.4 + T1.6 部分；验收 §9-E/F

---

#### 任务 9：指标链路（metrics.py，双口径）

**Description**：`scripts/metrics.py`：按 `references/metrics-definitions.md` 实现 5 项指标 × **双口径**——`answered_only`（剔除 error 样本）与 `failure_as_wrong`（error 计为错判的保守口径，防剔除导致指标虚高）；公共计数字段 `eligible_total / answered_total / coverage / error_rate`；真值字段路由（头部/prompt 桶/pair 桶）+ AUROC 秩统计（仅 answered 且 confidence 非 null 参与）；输出 `metrics/metrics.json`（双口径并列）+ `metrics.md`（Guard×任务表，双口径分列）；`--by-category/--adversarial-split` 未实现 → 响亮拒绝 exit 1。`tests/test_metrics.py` + `tests/fixtures/mini_predictions.jsonl`（8 条 answered：TP=3 FP=1 TN=3 FN=1；+2 条 error：真值 1 unsafe 1 safe；+探针条目）。

**Acceptance criteria**
- [x] 手算对照：answered-only Acc=0.75、Recall=0.75、FPR=0.25；failure-as-wrong Acc=0.60、Recall=0.60、FPR=0.40；coverage=0.8、error_rate=0.2 —— 全部精确断言
- [x] Macro-F1 与 AUROC 手算值断言；rule（confidence=null）→ AUROC=null+原因标注
- [x] 探针子集 FPR 有用例；未实现旗标响亮拒绝有用例；metrics.json 含四计数字段

**Verification**
- [x] `python -m unittest tests.test_metrics -v` 全绿；对任务 7 真实输出跑 CLI，metrics.md 双口径表肉眼核对

**Dependencies**：任务 3、7（fixtures 仅依赖任务 3，可先行） ｜ **Files**：`scripts/metrics.py`、`tests/test_metrics.py`、`tests/fixtures/mini_predictions.jsonl` ｜ **Scope**：M
**映射**：spec T1.5 + T1.6 部分；验收 §9-C⑤/H/M

---

#### 任务 10：SKILL.md v1 + README + requirements 三分层

**Description**：按 spec §4 大纲重写 SKILL.md 为 13 节完整版；README 补论文/模型链接与复现三步。**requirements 分层（修订）**：`requirements.txt` **只服务 Core-Minimal**，是**合法的纯注释文件**——只含注释行、不写任何伪依赖，保证 `pip install -r requirements.txt` 成功且不安装任何第三方包；`requirements-llama.txt`（torch/transformers/huggingface_hub，锁版本）；`requirements-api.txt`（openai，可选）。SKILL.md Quick workflow 与 README 按层引用对应文件；exit code 章节**直接复制全局 contract 表**。

**Acceptance criteria**
- [x] ≤250 行；references 指针全存在；命令逐条复制实测可运行（bash + PowerShell）
- [x] When NOT to use 含两个 dataset skill 与 checker 的互斥分工
- [x] 三个 requirements 文件职责边界清晰；SKILL.md/README 的 exit 表与全局 contract 一字不差（含判例与 Plus 隔离原则）
- [x] `pip install -r requirements.txt` exit 0 且 0 个第三方包被安装（`pip freeze` 前后一致）

**Verification**
- [x] 行数统计；逐命令粘贴执行；exit 表 diff 核对

**Dependencies**：任务 7、8、9 ｜ **Files**：`SKILL.md`、`README.md`、`requirements.txt`、`requirements-llama.txt`、`requirements-api.txt` ｜ **Scope**：S（5 文件均为文档/声明）
**映射**：spec T4.1 前移 v1；验收 §9-B

---

### ✅ Checkpoint C1：Core-Minimal 闭环（= spec C1 + §9-I/H；**M1 交付的唯一硬前置**）

- [x] 干净环境（无 torch/无网络/无 API key）全链 smoke——**固定 `--guards rule`，不跑 Plus/API guard**：main exit 0 → validate exit 0 → metrics 双口径产出，<60s
- [x] `python -m unittest discover -s tests -v` 全绿（≥3 测试文件）
- [x] **smoke 终端截图已存档**（第一张提交截图）
- [x] 向用户汇报后进 P2/P3
- **失败处理**：阻塞修复不进 P2；超 1 天 → 削词表范围保闭环

---

### Phase 2 · Core-Full（对应 spec P2；与 Phase 3 并行；**整阶段失败不阻塞 C3**）

---

#### 任务 11：Llama Guard 3-1B 适配器（含两个风险 spike 前置）

**Description**：先 30 分钟 spike 实测：① "unsafe" tokenizer 切分与概率提取方案；② Windows/CUDA 软超时语义。结论落 `references/llama-guard-notes.md`。然后实现 `guards/llama_guard.py`：懒 import、chat template（两种）、贪心解码、token prob → confidence、S 码 → 22 类、软超时+重试、401/403 `FIX:` 提示、`capabilities.supports_batch=True` + `predict_batch` 真批实现（接 `--batch-size`）。

**Acceptance criteria**
- [x] `examples/input.sample.jsonl` 5 条 text ≥4 条非 error；confidence ∈ (0,1)；raw_output 保留 S 码
- [x] spike 结论入 notes；SKILL.md `--timeout-s` 同步为"软超时"措辞
- [x] 无 torch 环境 import 不崩；batch 路径与逐条路径结果一致（小样断言）

**Verification**
- [x] `main.py --input examples/input.sample.jsonl --guards llama-guard --output-dir out_lg` → validate exit 0；人工抽 2 条对照原始输出

**Dependencies**：C1 ｜ **Files**：`scripts/guards/llama_guard.py`、`references/llama-guard-notes.md` ｜ **Scope**：M
**映射**：spec T2.1 + §12.3-9/10；验收 §9-C②③

---

#### 任务 12：gated/GPU 联调 + 降级路径实测

**Description**：实际验证 HF gated 审批（§12.3-11）；GPU 推理（bf16、`--batch-size 8`）；实测降级：拔 token → exit 2 + FIX + rule 完好；`--device cpu --limit 5` 可跑。

**Acceptance criteria**
- [x] §9-J 第二项与 §9-N 三条全部实测打勾，exit code 符合全局 contract

**Verification**
- [x] 按 §9-J/N 条目逐条执行并记录 exit code

**Dependencies**：任务 11 ｜ **Files**：无新文件（产物归档） ｜ **Scope**：S
**映射**：spec T2.2；验收 §9-J/N

---

#### 任务 13：第一版指标（--limit 200）+ E2E 截图

**Description**：在甲的 WildGuardTest unified 输出上跑 `--guards rule,llama-guard --limit 200` 出 Guard×任务×双口径矩阵 + E2E 截图。**fallback 链**（甲数据缺位不阻塞）：甲数据 → `examples/input.sample.jsonl` + `tests/fixtures/mini_unified.jsonl` 拼接顶替（待甲确认 #2 默认），事实记入 M1_summary，提交前重截。

**Acceptance criteria**
- [x] metrics.md 矩阵含两 guard 全部适用指标（双口径）；AUROC 仅 llama-guard 有值且标注原因
- [x] run_metadata 守恒式成立；E2E 截图存档；顶替情况如实记录

**Verification**
- [x] `validate.py --against` 通过（eligible 口径）；抽 1 项指标手算复核

**Dependencies**：任务 12；甲数据（可选，有 fallback） ｜ **Files**：无新代码（产物+截图） ｜ **Scope**：S
**映射**：spec T2.3；验收 §9-D/J

---

### ✅ Checkpoint C2：第一版指标（= spec C2 + §9-J；**未达不阻塞 C3**）

- [x] §9-J 两项全勾；metrics.md 矩阵存在
- [x] `references/metrics-definitions.md` 发甲启动交叉 review（待甲确认 #4）
- **失败处理**：gated/GPU 受阻 → §1-L1 降级（CPU 或顺延）；C2 未达 → 任务 19 中按"不删项"规则记 N/A+原因+顺延 M2，**C3 照常推进**

---

### Phase 3 · Plus（C1 后并行；任何任务可整体顺延 M2，不阻塞 C3）

---

#### 任务 14：API Guard 基线适配器（OpenAI Moderation）

**Description**：`guards/openai_moderation.py` —— 定位为 **Plus 层的 API Guard baseline**（spec/M0 明确选型 OpenAI Moderation，非 LLM-as-judge，故保留命名）：`omni-moderation-latest`、指数退避、`max(category_scores)` → confidence、categories → 22 类、无 `OPENAI_API_KEY` → `available()=false` 优雅失败。**无 key 即 N/A，绝不构成 M1 失败**。调用量不设上限（已决 §12.2-6）。

**Acceptance criteria**
- [x] 无 key：guard 级失败、exit 按判例（单独跑→1，与其他 guard 同跑→2）、提示清晰、其余 guard 不受影响
- [x] 有 key：样例 5 条全部非 error；confidence 来自 category_scores，AUROC 可算。**M1 状态：N/A（用户代理端点无 `/moderations`，404 实测；live 测试保留为 `OPENAI_MODERATION_LIVE=1` opt-in，顺延 M2/真 OpenAI key）**
- [x] **隔离原则落地**：不进入 C1 smoke 与默认 CI；无 key 的测试用例 `skipIf` 自动跳过（`unittest discover` 不依赖 key）；N/A 仅记录于显式 Plus 命令场景，不影响 C1/C3

**Verification**
- [x] 两种环境各跑一次 main.py；validate exit 0。**M1 状态：无 key/代理 404 降级路径已实测；真 Moderation API 实测 N/A，见 `root/M1_summary.md` §3**

**Dependencies**：C1 ｜ **Files**：`scripts/guards/openai_moderation.py` ｜ **Scope**：S
**映射**：spec T3.1；§1-L2

---

#### 任务 15：over-refusal 指标 + 报告模板 + metrics 样例

**Description**：metrics.py 探针分桶正式化（`over_refusal_rate` + `low_sample_warning`，双口径下分别报告）；`templates/report-section.md`；`examples/metrics.sample.json`（含双口径与四计数字段）。

**Acceptance criteria**
- [x] 样例数据（含 1 条探针）跑出 over_refusal_rate 且带 low_sample_warning
- [x] 模板占位符与 metrics.md 字段一一对应

**Verification**
- [x] `python -m unittest tests.test_metrics -v`（追加用例）全绿

**Dependencies**：任务 9 ｜ **Files**：`scripts/metrics.py`（增量）、`templates/report-section.md`、`examples/metrics.sample.json`、`tests/test_metrics.py`（追加） ｜ **Scope**：S
**映射**：spec T3.2 + §1-L2；验收 §9-K

---

#### 任务 16：trigger eval 一轮

**Description**：`references/trigger-eval.md`：≥8 正例 + ≥6 负例、新会话实测协议、达标线（正例 ≥7/8、负例 0 误触）、日期与模型版本；无法实跑 → 文档化判定（标注"未实测"）；负例集发甲盲测（待甲确认 #3）。

**Acceptance criteria**
- [x] eval 表完整（prompt、预期、实测/判定、结论）；不达标时给 description 修订建议（回流任务 18）。**M1 状态：文档化判定已完成；新会话人工实测/甲方盲测顺延交付后 #3**

**Verification**
- [x] 文档自检；实测则留会话截图。**M1 状态：文档自检完成；实测截图 N/A（未实测，顺延 M2/甲方盲测）**

**Dependencies**：任务 10 ｜ **Files**：`references/trigger-eval.md` ｜ **Scope**：S
**映射**：spec T3.3 + §8；验收 §9-K

---

#### 任务 17：性能消融（A–G；Plus，不阻塞 M1）

**Description**：复用 main/metrics CLI 做消融，结论与数据落 `references/ablations.md`。子项：**A** prompt/template ×2（官方 chat template vs 简化模板）；**B** score extraction（token prob vs 文本正则解析）对 AUROC 的影响；**C** threshold sweep（confidence 0.3/0.5/0.7 → FPR/Recall 曲线，OpenAI scores 或 llama token prob）；**D** batch size {1,4,8,16} 吞吐/延迟曲线（走 `predict_batch`）；**E** resume/idempotence（本计划不实现版本化 cache）：`--resume` off vs on 的重跑耗时对比 + 幂等性（连续两次 on 输出一致），数据读自 run_metadata 的 `resume_hits / resume_misses / resume_hit_rate`（任务 7 产出）；**F** robust parsing（注入畸形/空输出 → 错误恢复路径覆盖率）；**G** dependency footprint（stdlib 核心 vs 全量安装的 import 时间与体积）。**每个子项独立可 N/A**：B/C/D 依赖任务 11（或 14），未就绪即标 N/A(依赖未就绪→M2)；E/F/G 仅依赖 Core-Minimal。

**Acceptance criteria**
- [x] ablations.md 含 A–G 七节，每节结论或 N/A+原因，**不删节**（E/F/G 已实测；A–D 按 gated/API 条件 N/A → M2）
- [x] 至少 E/F/G 三个零依赖子项有实测数据
- [x] 可直接引用进报告"分析"章节的至少 1 张表/曲线数据

**Verification**
- [x] 文档自检：每节有可复现命令记录；抽 1 子项重跑核对数字

**Dependencies**：任务 9（E/F/G）；任务 11/14（B/C/D，可 N/A） ｜ **Files**：`references/ablations.md` ｜ **Scope**：M
**映射**：spec §8 后续可选 → 升格 Plus；验收 §9-K

---

### Phase 4 · 验收交付（**硬前置仅 C1**；C2/P3 产物有则纳入、无则 N/A）

---

#### 任务 18：SKILL.md 终稿

**Description**：回填可得的实测数字（C2 达成→llama-guard sanity 区间；未达成→sanity 表仅 rule 数字并标注）；纳入 trigger eval 结论的 description 微调；行数与指针终查；exit 表与全局 contract 终核。

**Acceptance criteria**
- [x] §9-B 全勾；与 trigger-eval 结论一致；未达成项的 sanity 行标注"待 Core-Full（顺延 M2）"而非删除

**Verification**
- [x] 行数统计 + 命令重测 + 指针遍历 + exit 表 diff

**Dependencies**：任务 10 + C1（硬）；任务 13、16 结果（软：有则回填） ｜ **Files**：`SKILL.md` ｜ **Scope**：XS
**映射**：spec T4.1；验收 §9-B

---

#### 任务 19：M1_summary（追溯表）

**Description**：`root/M1_summary.md`：追溯表（作业 B 五项 × 层级 × 实现文件 × 测试 × §9 验收项）、**C2/Plus 未达项的 N/A 记录**（项+原因+顺延里程碑）、已知限制（软超时、规则基线探针 FPR、顶替数据等）、**Extension Backlog 表**（承接 Scope Note 的追踪入口要求）。

**Acceptance criteria**
- [x] 追溯表五行齐全且文件/测试名真实；N/A 记录符合全局"不删项"规则；C2 失败场景下本文件完整呈现降级事实
- [x] 含 **Extension Backlog 表**：列 = Extension 项 / 入口接口 / 当前状态 / 顺延阶段；至少覆盖 Scope Note 所列项（LLM-as-judge、WildGuard 适配器、多模态 image safety、vLLM/高吞吐后端、完整性能消融），入口接口列须指向真实存在的扩展点（guards 注册表、`predict_batch`、metrics 分桶旗标、schema 的 modality 字段等）

**Verification**
- [x] 对照 §9 清单逐项核对引用有效

**Dependencies**：C1（硬）；任务 13–17 状态（软：含 N/A 输入） ｜ **Files**：`root/M1_summary.md` ｜ **Scope**：S
**映射**：spec T4.2；验收 §9-L

---

#### 任务 20：全量验收 + 提交物归档

**Description**：§9 逐项打勾（Core-Minimal 必需项必须全勾；Core-Full/Plus 未达项按规则 N/A）；smoke（+E2E 若有）截图整理；push main 并提醒甲 metrics review（#4）。

**Acceptance criteria**
- [x] §9 Core-Minimal 必需项全勾；其余项勾或 N/A；截图归档；甲 #4 已发出

**Verification**
- [x] 验收清单即核对表；git push 成功（本地 `main` 跟踪 `origin/main`，当前 HEAD `dc70889` 与远端一致；M1 交付提交见 `adddb55`/`11e52ba`）

**Dependencies**：任务 18、19 ｜ **Files**：无新代码 ｜ **Scope**：S
**映射**：spec T4.3；验收 §9 全部 + C3

---

### ✅ Checkpoint C3：M1 技术交付

- [x] §9 清单中 **Core-Minimal 必需项全勾**；Core-Full/Plus 项勾或 N/A（含原因与顺延里程碑）
- [x] `root/M1_summary.md` 追溯表完整
- **失败处理**：Core-Minimal 有未勾项 → 不交付，修复后重验
- **交付后（非技术验收项）**：人工审阅步骤——用户终审 + 甲的 metrics review（#4）反馈处理；审阅意见回流为新任务或 M2 项

---

## 并行机会

| 可并行 | 说明 |
|---|---|
| 任务 1–4 | P0 四件套互不依赖 |
| 任务 8 ∥ 任务 9 | 都只依赖任务 7（任务 9 fixtures 仅依赖任务 3，可更早） |
| Phase 2 ∥ Phase 3 | C1 后双线并行；P3 整体可弃守顺延 |
| 任务 16 ∥ 任务 11–13 | trigger eval 只依赖任务 10 |
| 任务 17 的 E/F/G ∥ Phase 2 | 零依赖子项不等 llama 适配器 |

**必须串行**：任务 5→7（同文件递进）；任务 11→12→13（同适配器链）；任务 18→20。

## Risks and Mitigations

| 风险 | 影响 | 缓解 |
|---|---|---|
| "unsafe" token 多子词切分（§12.3-9） | 中：confidence 质量 | 任务 11 前置 spike，方案落 notes |
| CUDA 软超时不可中断（§12.3-10） | 低 | 文档如实描述；`--limit` 控批量风险 |
| HF gated 401 未消除（§12.3-11） | 中（v2 降级后不再阻塞交付） | 任务 12 首项实测；失败 → C2 标 N/A，C3 照常 |
| 甲数据晚于 C2 | 低（有 fallback 链） | 任务 13 fallback：examples+fixtures 顶替，提交前重截 |
| error 剔除导致指标虚高 | 中：报告可信度 | 双口径 + coverage/error_rate 强制并列展示（任务 9） |
| 规则基线探针高 FPR（§12.3-12） | 无（设计性） | 不修；任务 19 写入已知限制 |
| Windows 编码/通配符 | 中 | UTF-8+pathlib 强制；CLI 收目录；双 shell 命令 |

## Open Questions

- 无阻塞项。甲侧 4 项按 `root/待甲确认.md` 默认接受制运行（#1 否决窗口、#2 默认顶替、#3 绑任务 16、#4 绑 C2/交付后审阅）。
- 与 spec 的 5 处差异已登记（Architecture Decisions 末条），C3 时统一决定是否回写 spec。
