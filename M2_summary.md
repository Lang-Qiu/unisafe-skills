# M2 交付总结 — guard-llama-guard 增量（方向 B，乙）

> 日期：2026-06-12（**2026-06-15 真数据升档**）。契约：[`M2_SPEC.md`](M2_SPEC.md)；编排：[`tasks/plan-m2.md`](tasks/plan-m2.md) / [`tasks/todo-m2.md`](tasks/todo-m2.md)（20 任务全完成：任务 18 已用甲 WildGuardMix unified 全量 **1959** 实测升档）。
> 层级结论：**Core-Minimal ✅（C1，零依赖 82 测试）｜Core-Full ✅（C2，judge live 实测 + 三 Guard 矩阵）｜Plus 消融 A–D 全实测、全量档真数据升档（rule/llama 全量 + judge 子集 partial）、trigger eval 待人工｜Extension 只留接口**。

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
| G 全量结果档 | 1,725 三 Guard 矩阵 | 甲 WildGuardMix 全量 1959（checker PASS） | **真数据升档**（§2）：rule+llama 全量 1959 + judge 子集 120（partial）；llama AUROC **0.888**、over-refusal 6.4%；judge 对抗坍塌量化 | ✅ |
| H 文档与交付 | SKILL.md ≤250 行、v2 发甲、本文件 | `SKILL.md`（~168 行）、`待甲确认.md` #4 追加行 | 指针全验证；本文件含 Metric Caveats | ✅ |

## 2. 真实矩阵（甲 WildGuardMix 全量 **1959**：safe 1675 / unsafe 284 = 14.5% 基准率 + 250 XSTest 探针；2026-06-15）

### 2.1 全量 rule + llama-guard（`out_text_real/metrics/`，real 14.5% 基准率）

| guard | basis | n | Acc | Recall | FPR | Macro-F1 | AUROC | coverage | over-refusal(XSTest 250) |
|---|---|---|---|---|---|---|---|---|---|
| **llama-guard** | answered_only | 1911 | **0.899** | **0.660** | 0.063 | 0.792 | **0.888** | 0.976 | Acc 0.936 / FPR **6.4%** |
| llama-guard | failure_as_wrong | 1959 | 0.877 | 0.616 | 0.079 | 0.759 | 0.888 | — | — |
| rule | (单口径) | 1959 | 0.798 | 0.271 | 0.112 | 0.582 | — | 1.000 | Acc 0.904 / FPR 9.6% |

- **对抗鲁棒性量化**（llama-guard）：AUROC 非对抗 **0.919** → 对抗 **0.831**，Acc 0.931→0.852——对抗 prompt 确实更难。
- **可靠性**：llama error 仅 2.4%（48/1959），双口径差小（0.899→0.877）——与图像侧 int8 19.4% NaN 形成鲜明对照（M3_summary §4-2a）。

### 2.2 三 Guard 子集（judge partial：分层 **120** = 40 unsafe + 40 safe + 40 XSTest，judge 22.5s/条全量 11h 不现实，故子集）

| guard | Acc (ao) | Recall | FPR | AUROC | over-ref FPR | 对抗 AUROC | 非对抗 AUROC |
|---|---|---|---|---|---|---|---|
| **llama-guard** | 0.805 | 0.579 | 0.088 | **0.909** | **0.025** | 0.767 | 0.958 |
| **llm-judge** | 0.815 | **0.750** | 0.152 | 0.895 | 0.050 | **0.633** | 0.976 |
| rule | 0.675 | 0.275 | 0.125 | — | 0.050 | — | — |

叙事要点：① **judge 召回最高（0.75）但 FPR 也最高（0.152）**——抓得多、误报也多；llama-guard 综合最稳（AUROC 0.909、over-refusal 仅 2.5%）。② **judge 对抗最脆**：AUROC 非对抗 **0.976 → 对抗 0.633**（坍塌 0.34），llama 0.958→0.767（降 0.19）——M2 当初"judge 可被对抗样本说服"的 caveat 在真数据上**量化坐实**（推理判官被对抗框架带偏比专用 guard 更严重）。③ over-refusal 真实测出（llama 2.5–6.4% / judge 5% / rule 5–9.6%）。④ **与图像侧强对照**：文本 guard 在母语域 AUROC 0.89，远胜被量化拖累的 ShieldGemma 2（0.61）——"skill 工程一致，效果差异来自模型与量化口径"。

> 旧 `out_m2_threeguard/` 顶替矩阵（10 eligible 合成）已退役为机制自检留档；真数据档以本节为准。

### 2.3 阈值校准 + ensemble 分析（效果提升落地，2026-06-15）

**问题**：固定阈值 0.5 是模型卡默认、未校准；能否用 ensemble 或校准提升效果？两条都实测了：

- **ensemble 被实测否定**：全量 rule+llama 的 `OR/AND` 没一个在 F1 上赢过 llama 单独（OR 把召回抬到 0.736 但 FPR 0.06→0.17、F1 反降）；三 guard 子集只有 `OR(llama,judge)` F1 微胜（0.737→0.750）且 FPR 升、搭 judge 22.5s/条。结论：**强+弱组合被强者支配，ensemble 不是杠杆**。
- **阈值校准是真杠杆**：llama AUROC 0.888（排序好），沿 ROC 移阈值**严格支配** OR-ensemble——llama @ thr=0.30 达 recall 0.747 / FPR 0.135 / F1 0.607，比 OR(rule,llama) 的 0.736 / 0.166 / 0.564 三项全胜。

**落地为 skill 能力**：新增 `scripts/calibrate.py`（两侧受控复制，各 8 测试答案钥锁定）——扫 ROC 出操作点表 + 推荐阈值。llama-guard 实测推荐（`out_text_real/calibration/`）：

| 操作点 | thr | Recall | FPR | Macro-F1 |
|---|---|---|---|---|
| default（现状） | 0.50 | 0.664 | 0.075 | 0.779 |
| **max_macro_f1（均衡推荐）** | 0.55 | 0.638 | 0.056 | **0.793** |
| recall_at_FPR≤0.1（高召回） | 0.45 | 0.683 | 0.086 | 0.774 |

rule 无连续分 → 正确判 not-calibratable。图像侧 shieldgemma2 校准须用 CPU bf16 参考分（int8 分上校准 = 对量化噪声校准），见 `M3_summary.md`。

## 3. N/A / 待外部（不删项规则）

| 项 | 原因 | 顺延 |
|---|---|---|
| trigger eval 实测档（任务 16） | 需多个全新会话人工实测 + 甲 #3 盲测合并（已决事项 3） | M2 收尾前/M4 报告期；协议与正负例在 `references/trigger-eval.md` |
| ~~全量结果档（任务 18）~~ ✅ 已完成 | 甲 WildGuardMix 全量 1959 到位（checker PASS）；2026-06-15 rule/llama 全量 + judge 子集 120 已跑（partial 规则生效，judge 全量 11h 不现实） | 真数据矩阵见 §2（`out_text_real/` + `out_judge_subset/`） |
| OpenAI Moderation live | 仍无真 OpenAI key（MiMo 代理无 `/moderations`，M1 404 实测）；judge 已顶多 Guard 名额，此项降为可选 | 真 key 到手即 `OPENAI_MODERATION_LIVE=1` |

## 4. Metric Caveats（报告引用数字前必读）

1. **by-category 仅 answered_only 口径**：error 行无预测类别，"双口径类别表"是虚假精度；failure 影响已由头部双口径覆盖。
2. **llm-judge 的 confidence 非校准概率**：自报"裁决把握"经方向映射后才参与 AUROC；与 llama 的 token 概率不可混算，跨 guard AUROC 对比须注明（实证：映射前 AUROC 0.375）。
3. **low_sample_warning / low_support_warning 桶不作强结论**：本轮全部桶均为小样本（≤13 条），仅机制验证与趋势。
4. ~~**fallback/顶替数据不可作为最终全量结果**~~ → **已用甲真实数据重跑**（§2，2026-06-15）：顶替矩阵退役，全量数字以真数据为准。仍注意：judge 为 120 分层子集（balanced，非 14.5% 基准率），跨表比较须区分"全量 real base rate"（§2.1）与"子集 balanced"（§2.2）。

## 5. 已知限制与 spec 偏差登记

1. **max_tokens 256 → 4096**（偏离 M2_SPEC §5 的"默认 256"）：mimo-v2.5-pro 是推理模型，思维链先耗预算——256 时 `finish_reason=length` 且 content 为空（live 实录于 `references/llm-judge-notes.md`）；`judge_max_tokens` 可配置。
2. **confidence 方向映射**（spec §5 未明说方向，M0 §5 隐含 unsafe 方向）：judge 自报分对 safe 判定取 `1−c` 后入库；原始自报值保留在 `raw_output.parsed`。
3. **M1 响亮拒绝测试退役**：两旗标实现后该测试断言对象消失（spec §3 明令"替换响亮拒绝"）；行为改由 `TestByCategory`/`TestAdversarialSplit` 锁定，io-contract §7 措辞已历史化。
4. judge 对抗面：判官有指令遵循面，对抗样本可能"说服"其在合法 JSON 里给错判——**真数据量化坐实**（§2.2）：judge AUROC 非对抗 0.976 → 对抗 **0.633**（坍塌 0.34，三 guard 中最脆；llama 仅降 0.19）。这是判官范式相对专用 guard 的结构性弱点，非实现 bug。
5. ~~全量 judge 延迟（22.5 s/条）…**不引入并发**（Ask-first，见 plan R7）~~ → **R7 superseded by M3.5 §3-W4**（用户 2026-06-16 显式授权）：`--judge-concurrency N`（默认 1=串行向后兼容）加有界并发；实测 12 条 `-j4` vs `-j1` = **340s→88s（3.86× / 74% 壁钟↓）**，counts(predicted/errors/skipped) 守恒、逐 id 判定一致、无重排/丢行（M3.5 T5/T6）。全量 judge 由此可脱离 partial。

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

- [ ] M2 E2E 截图（真数据：`全量标注结果/wildguardmix_test/out_text_real/metrics/metrics.md` 全量 + `out_judge_subset/metrics/` 三 Guard 子集；目录已 gitignore，截图入提交 zip 不入 git）
- [x] 甲：#2 数据已交付（WildGuardMix 全量 1959，checker PASS）→ 乙 2026-06-15 任务 18 真数据升档；#3 盲测已做（7/8，见 `待甲确认.md` #6）；**#4 公式 review 仍待甲显式签字**
- [ ] 用户终审本交付；官方 gated 权重获批后 `--model-id` 默认值一条命令切回
