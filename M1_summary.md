# M1 交付总结 — `guard-llama-guard`（方向 B，乙）

> 日期：2026-06-11。规格：[`M1_SPEC.md`](M1_SPEC.md)；任务编排：[`tasks/plan.md`](tasks/plan.md)（v2.1，20 任务全部处置完毕：17 完成 + 3 项内含 N/A 子档）。
> 交付层级结论：**Core-Minimal ✅（C1）｜Core-Full ✅（C2，镜像权重+顶替数据，均如实溯源）｜Plus 全部交付（API 实测档 N/A）｜Extension 仅留接口（见 Backlog）**。

## 1. 追溯表（作业 B 五项要求）

| 作业要求 | 层级 | 实现文件 | 测试 | §9 验收项 |
|---|---|---|---|---|
| ① 统一输入接口（读 unified JSONL、路由、防御性读取） | Core-Minimal | `scripts/utils.py`（`iter_jsonl`/`route_record`）、`scripts/main.py`、`references/io-contract.md` §1–2 | `tests/test_rule_guard.py::TestRouting`、消融 F 实测 | A/E/G/I |
| ② Guard 调用（≥2 类 guard；超时/空输出/gated 异常处理） | Core-Minimal（rule）+ Core-Full（llama-guard）+ Plus（openai） | `scripts/guards/{base,rule_based,llama_guard,openai_moderation}.py`、注册表 `__init__.py` | `tests/test_rule_guard.py`、`tests/test_openai_guard.py`、降级三判例实测（`references/llama-guard-notes.md`） | C②③/J/N |
| ③ 输出解析为统一字段 | Core-Minimal | `guards/base.py::make_result`、`schemas/guard_output.schema.json`、`scripts/validate.py` | `tests/test_validate.py`（合法/三类非法/覆盖率/计数） | E/F |
| ④ 标签映射到 22 类（显式 `other` 兜底） | Core-Minimal | `references/category_mapping.json`（S1–S14/OpenAI/rule 三段，S6 双映射）、各适配器映射逻辑 | schema 枚举↔mapping 同源断言（C0 实测）、`test_rule_guard` 类别断言 | C④ |
| ⑤ 评测指标兼容（5 指标 + over-refusal，双口径） | Core-Minimal | `scripts/metrics.py`、`references/metrics-definitions.md` | `tests/test_metrics.py`（手算对照：0.75/0.75/0.25、0.60/0.60/0.40、AUROC 0.9375 含 ties、探针、响亮拒绝） | C⑤/H/K/M |

## 2. 第一版指标矩阵（任务 13，fallback 数据 10 eligible，`--limit 200`）

| guard | bucket | basis | n | Acc | Recall | FPR | Macro-F1 | AUROC |
|---|---|---|---|---|---|---|---|---|
| llama-guard | head_binary | answered_only = failure_as_wrong | 10 | 0.80 | 1.00 | 0.333 | 0.80 | **1.00** |
| llama-guard | pair_response_harm | 同上 | 4 | 1.00 | 1.00 | 0.00 | 1.00 | 1.00 |
| llama-guard | over_refusal_probe | 同上 | 2 | — | — | **1.00** | — | — |
| rule | head_binary | 同上 | 10 | 0.70 | 1.00 | 0.50 | 0.697 | —（无连续分） |
| rule | over_refusal_probe | 同上 | 2 | — | — | **1.00** | — | — |

两口径数值相同（本轮 error_rate=0，coverage=1.0——双口径在有 error 时才分叉，机制已被测试锁定）。
亮点发现：**Llama Guard 3-1B 与规则基线都在 XSTest 同形异义探针上全军覆没**（"kill a Python process"，llama conf≈0.71）——报告"规则 vs 模型"叙事的现成素材；llama 的 phishing→S1（而非 S2）是 M0 §4 预告的 taxonomy 分歧实例。

## 3. N/A 记录（不删项规则）

| 项 | 原因 | 顺延 |
|---|---|---|
| OpenAI Moderation 有 key 实测档（任务 14） | 用户提供的代理为 LLM 端点，无 `/moderations`（404 实测）；适配器与隔离测试已交付 | M2（或换真 OpenAI key 即跑，live 测试 `OPENAI_MODERATION_LIVE=1` 一键启用） |
| trigger eval 实测档（任务 16） | 需多个全新会话人工实测；文档化判定（8 正例+6 负例+协议+达标线）已交付 | C3 后 / M2；负例集待甲盲测（#3） |
| 消融 A/B/C/D（任务 17） | A/B/D 依赖 llama 长跑窗口、C 无可用连续分 API；E/F/G 已实测 | M2 |
| 官方 gated 权重 | `meta-llama/Llama-Guard-3-1B` 审批未下；以同权重非 gated 镜像 `alpindale/Llama-Guard-3-1B` 经 `--model-id` 运行，溯源进 `run_metadata.config.model_id` | 审批通过后默认 model-id 即切回（零代码改动） |
| 真实 WildGuardTest 数据（任务 13） | 甲的 unified 输出未就绪；examples+fixtures 顶替（10 eligible），按 `M1_待甲确认.md` #2 默认方案 | 提交前用真实数据重跑并重截图 |

## 4. 已知限制

1. `--timeout-s` 是**软超时**：CUDA 步进不可中断，超时记 error 行、迟到结果丢弃，GPU 占用直至该步完成（`llama-guard-notes.md` spike ②）。
2. 规则基线在探针上的高 FPR 是**设计性**的（关键词法必然误伤同形异义），不当缺陷修；实测 llama-guard 同样误伤，构成对比叙事。
3. 批推理 confidence 漂移 ≤0.018（bf16 批内 padding 改变浮点累加路径）；判定与类别批/单完全一致。
4. 本轮指标基于顶替数据（10 eligible）与镜像权重，样本量不具统计意义（low_sample_warning 已标注）；结论性数字以 M2 全量 1,725 条为准。
5. AUROC 不分双口径（error 行无 confidence），仅在 answered ∩ confidence≠null 上计算，输出有注明。

## 5. Extension Backlog（M1 只留接口，不实现）

| Extension 项 | 入口接口 | 当前状态 | 顺延阶段 |
|---|---|---|---|
| LLM-as-judge 适配器 | `guards/__init__.py` 注册表 + `GuardAdapter` 协议 | 接口就绪；**已有现成双协议端点**（MiMo 代理：OpenAI 兼容 `/v1` + Anthropic 兼容 `/anthropic`，key 用户持有不入库） | M2 |
| WildGuard 适配器 | 同上（注册表 + `predict_batch` 默认实现） | 未开工 | M2 |
| 多模态 image safety（ShieldGemma 2） | `schemas/guard_output.schema.json` 的 `guard.modality` 字段 + image 记录 out-of-scope skip 计数链路 | schema 已兼容（M0 样本 image 记录可表达）；归 `guard-shieldgemma2` | M3 |
| vLLM / 高吞吐后端 | `capabilities.supports_batch` + `predict_batch` + `--batch-size` 链路 | 真批路径已在 transformers 后端验证 | M2+ |
| 完整性能消融 | `references/ablations.md` A–D 占位 + `metrics.py --by-category/--adversarial-split` 旗标（响亮拒绝中） | E/F/G 已实测 | M2 |
| 全量 XSTest over-refusal | `metrics.py` 探针分桶 + `low_sample_warning` | 机制完整，只差数据 | M2 |

## 6. 验收状态（§9 A–N 速览）

A 结构 ✅｜B SKILL.md ✅（≤250 行、13 节、双 shell 命令、指针全验证）｜C 五项 ✅｜D 共同任务 ✅（端到端跑通；metrics-definitions 待甲签字 #4）｜E I/O 契约 ✅（守恒式 validate 实测）｜F schema ✅（四类非法被拒）｜G examples ✅（黄金双锁定）｜H tests ✅（41 绿，1 opt-in skip）｜I smoke ✅（干净 venv 1s，截图已存档）｜J Core-Full ✅（5/5 非 error、AUROC 可算、拔 token 真 403 实测）｜K 性能 ✅/N-A（负触发 ✅、trigger eval 文档档）｜L 报告 ✅（本文件 + README 链接）｜M 边界 ✅（image skip 不报错、旗标响亮拒绝）｜N 降级 ✅（cpu 可跑、L0 闭环、exit 2 实测）

## 7. 人工待办（非技术验收）

- [ ] E2E 截图（两 guard 指标矩阵运行画面）——smoke 截图已存档 ✅
- [ ] 甲：metrics-definitions.md 交叉 review（`M1_待甲确认.md` #4，PR approve 即签字）
- [ ] 甲：trigger eval 负例盲测（#3）；WildGuardTest unified 就绪日期（#2）
- [ ] 用户终审本交付
