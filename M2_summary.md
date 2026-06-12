# M2 交付总结 — guard-llama-guard 增量（方向 B，乙）

> 日期：2026-06-12。契约：[`M2_SPEC.md`](M2_SPEC.md)；编排：[`tasks/plan-m2.md`](tasks/plan-m2.md) / [`tasks/todo-m2.md`](tasks/todo-m2.md)（20 任务：18 完成 + 2 项外部依赖待办）。
> 层级结论：**Core-Minimal ✅（C1，零依赖 82 测试）｜Core-Full ✅（C2，judge live 实测 + 三 Guard 矩阵）｜Plus 消融 A–D 全实测、trigger eval 与全量档待外部｜Extension 只留接口**。

## 1. 追溯表（spec §6 验收项 × 实现 × 测试）

| spec §6 | 内容 | 实现文件 | 测试/证据 | 状态 |
|---|---|---|---|---|
| A 向后兼容 | 无旗标输出 ≡ M1 黄金；M1 测试全集保持绿 | `scripts/metrics.py`（分节按需输出，AD-1/2） | `TestMetricsSampleGolden`（M1 原测试在 M2 代码上保持绿）+ 82 全绿 | ✅（唯一例外：响亮拒绝测试按 spec §3"替换响亮拒绝"退役，见 §5-3） |
| B by-category | 五量 + 分歧计数 + 审计 + macro | `compute_by_category` | `TestByCategory` ×5（对照答案钥 `category_expected.json`） | ✅ |
| C adversarial-split | 三态 + 双口径 + 守恒 | `compute_adversarial_split` | `TestAdversarialSplit` ×6 | ✅ |
| D comparison | 计数列 + ao 五指标 + fw 两指标 + Δ | `compute_comparison` + `--baseline` | `TestComparison` ×7（含 error 行 ao/fw 分叉防虚高） | ✅ |
| O over-refusal | 双口径正式核验 + 进对比 | M1 探针路径复用 + comparison 行 | `TestOverRefusalFormal` ×4；字段名与 v2 一致**无需别名** | ✅ |
| E llm-judge | 适配器 + 隔离 + live | `scripts/guards/llm_judge.py` | 19 离线测试（transport mock）+ live 18/18 + 样本 5/5 非 error + validate PASS + exit 1/2 判例实证 + git grep key/URL 零命中 | ✅ |
| F 顺延项清算 | 消融 A–D、trigger eval | `references/ablations.md` 回填 | A/B/D 实测 + C 双源实测；trigger eval 实测档 N/A（需人工新会话 + 甲 #3，见 §3） | ✅/N-A |
| G 全量结果档 | 1,725 三 Guard 矩阵 | — | 甲数据未到 → 顶替矩阵已出（`out_m2_threeguard/`，可截图），按"提交前重跑"标记；judge 档允许 partial | 待数据 |
| H 文档与交付 | SKILL.md ≤250 行、v2 发甲、本文件 | `SKILL.md`（~168 行）、`M1_待甲确认.md` #4 追加行 | 指针全验证；本文件含 Metric Caveats | ✅ |

## 2. 三 Guard 对比矩阵（顶替数据 10 eligible，head_binary，baseline=rule）

| guard | Acc (ao) | Recall | FPR | Macro-F1 | AUROC | 探针 over-refusal |
|---|---|---|---|---|---|---|
| **llm-judge** | **0.90** | 1.00 | **0.167** | 0.899 | 1.00* | **0.0（唯一通过）** |
| llama-guard | 0.80 | 1.00 | 0.333 | 0.80 | 1.00 | 1.0 |
| rule | 0.70 | 1.00 | 0.50 | 0.697 | — | 1.0 |

\* judge AUROC 基于自报分的方向映射（见 §5-2 与 Metric Caveats）。亮点叙事：judge 是三者中唯一不被 XSTest 同形异义探针误导的 guard，且 phishing 类别判对（`cyber_safety`，llama 判 S1/violence——taxonomy 分歧的量化见 `--by-category` 的 divergence 计数）；代价是延迟 22.5 s/条（推理链）≈ llama 的 100 倍以上。

## 3. N/A / 待外部（不删项规则）

| 项 | 原因 | 顺延 |
|---|---|---|
| trigger eval 实测档（任务 16） | 需多个全新会话人工实测 + 甲 #3 盲测合并（已决事项 3） | M2 收尾前/M4 报告期；协议与正负例在 `references/trigger-eval.md` |
| 全量 1,725 结果档（任务 18） | 甲 #2 数据未到（checker exit 0 为门）；judge 串行 ≈11h → **partial 规则生效**：rule/llama 全量 + judge 子集即标 partial，不声称三 Guard 全量 | 数据到位即跑（`--resume` 分段） |
| OpenAI Moderation live | 仍无真 OpenAI key（MiMo 代理无 `/moderations`，M1 404 实测）；judge 已顶多 Guard 名额，此项降为可选 | 真 key 到手即 `OPENAI_MODERATION_LIVE=1` |

## 4. Metric Caveats（报告引用数字前必读）

1. **by-category 仅 answered_only 口径**：error 行无预测类别，"双口径类别表"是虚假精度；failure 影响已由头部双口径覆盖。
2. **llm-judge 的 confidence 非校准概率**：自报"裁决把握"经方向映射后才参与 AUROC；与 llama 的 token 概率不可混算，跨 guard AUROC 对比须注明（实证：映射前 AUROC 0.375）。
3. **low_sample_warning / low_support_warning 桶不作强结论**：本轮全部桶均为小样本（≤13 条），仅机制验证与趋势。
4. **fallback/顶替数据不可作为最终全量结果**：§2 矩阵与消融数字提交前以甲的真实数据重跑。

## 5. 已知限制与 spec 偏差登记

1. **max_tokens 256 → 4096**（偏离 M2_SPEC §5 的"默认 256"）：mimo-v2.5-pro 是推理模型，思维链先耗预算——256 时 `finish_reason=length` 且 content 为空（live 实录于 `references/llm-judge-notes.md`）；`judge_max_tokens` 可配置。
2. **confidence 方向映射**（spec §5 未明说方向，M0 §5 隐含 unsafe 方向）：judge 自报分对 safe 判定取 `1−c` 后入库；原始自报值保留在 `raw_output.parsed`。
3. **M1 响亮拒绝测试退役**：两旗标实现后该测试断言对象消失（spec §3 明令"替换响亮拒绝"）；行为改由 `TestByCategory`/`TestAdversarialSplit` 锁定，io-contract §7 措辞已历史化。
4. judge 对抗面：判官有指令遵循面，对抗样本可能"说服"其在合法 JSON 里给错判（注入防护与残余风险见 notes）——本身是对抗分桶的分析素材。
5. 全量 judge 延迟（22.5 s/条）使三 Guard 全量在单机串行下不现实；partial 规则与 `--resume` 是既定路径，**不引入并发**（Ask-first，见 plan R7）。

## 6. Extension Backlog（更新）

| 项 | 状态 |
|---|---|
| ~~LLM-as-judge 适配器~~ | **M2 已交付**（毕业出 Backlog） |
| WildGuard 适配器 | 接口就绪（注册表 + GuardAdapter），未开工 → M3+/加分 |
| vLLM / 高吞吐后端 | `predict_batch` 链路已验证 → M3+ |
| judge 并发请求 | 可把全量 judge 从 ~11h 压到 <1h；spec 未授权，Ask-first → M3+/M4 前 |
| Anthropic 协议 judge 端点 | 适配器 base-url 已参数化，仅 OpenAI 协议实现 → 可选加分 |
| 多模态（ShieldGemma 2） | schema 兼容已留 → M3（`guard-shieldgemma2`） |
| 全量 XSTest over-refusal | 机制完整（O 验收全勾），只差数据 → 随任务 18 |

## 7. 人工待办（非技术验收）

- [ ] M2 E2E 截图（三 Guard comparison 表运行画面；素材已在 `out_m2_threeguard/metrics/metrics.md`）
- [ ] 甲：#2 数据日期（到位后任务 18 全量跑）+ #3 盲测（与任务 16 合并）+ #4 review（v1+v2 一并）
- [ ] 用户终审本交付；官方 gated 权重获批后 `--model-id` 默认值一条命令切回
