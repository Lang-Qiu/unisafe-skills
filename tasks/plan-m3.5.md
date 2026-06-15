# M3.5 Plan — Skill 性能优化

> 契约：[`../M3.5_SPEC.md`](../M3.5_SPEC.md)（W1-W4、Cα/Cβ、§9 决议、§12 后置效果台账）。
> 路径约定：无前缀相对仓库根；`llama/` = `guard-llama-guard/`、`sg2/` = `guard-shieldgemma2/`。
> 原则：纯增量、默认值向后兼容（W4 默认串行）；受控复制双侧同步；不动判别逻辑；现有 **llama 90 / sg2 94** 套件保持绿。
> ⛔ 放行点：本计划经用户确认前不开工（沿 M1-M3 惯例）。

## 架构决策（落点已勘）

- **W1**：`llama/sg2 main.py` 的 `_probe_env()` 现把 `model_revision` 硬编码 `None`（`main.py:76`）。改为：adapter 载入后暴露解析到的 commit hash（`config._commit_hash` 或 `huggingface_hub`）+ 库版本；main.py 从**已完成 adapter**收集写入 env 块。rule/caption-rule（无权重）该字段如实 null。
- **W4**：main.py 经 `adapter.capabilities['supports_batch']` + `--batch-size` 走 `predict_batch(chunk)`（`main.py:204-211`）。judge 现 `predict()`=单次 `_post_chat`。**落点**：给 `llm_judge` 加 `predict_batch`（有界 `ThreadPoolExecutor(max_workers=judge_concurrency)`，**按输入 id 顺序回填**），`main.py` 增 `--judge-concurrency N`（默认 1）注入 config；每请求保留既有 retry/timeout/error 行。
- **W2/W3**：纯文档 + opt-in 测试，无管道改动。

## 依赖图

```
T1 W1 可复现性 ─┐
T2 W2 文档修正 ─┼─(并行,互不依赖)─► Cα(Core 软门)
T3 W3 方差smoke ┘
                          │
T2 ─► T4 W2 description 调优 ─┐
        T5 W4 并发(TDD) ─────┼─► T6 W4 实测提速+守恒+R7 登记 ─► Cβ(M3.5 硬门)
                            ┘
                                              │
                          T7 文档终稿 + M3.5_summary + 偏差台账 + push
```

## Phase A · Core（低风险，三任务并行）

### T1（W1）可复现性硬化 — 两侧 adapter + main.py env 块
**描述**：adapter 载入后暴露 `model_revision`（HF commit hash）；main.py env 块写入 revision + transformers/bitsandbytes/accelerate 版本 + 可选 `weight_sha256`（config.json + 首分片，§9-1，不哈全 8GB）。
**验收**：① 真跑后 `run_metadata.env.model_revision` 非 null（两侧）；② 库版本字段齐；③ rule/caption-rule 该字段如实 null；④ 离线 mock 测试不触网。
**验证**：`python -m unittest discover -s tests`（两侧绿）；真跑一条查 `run_metadata.json` 的 env 块。
**文件**：`llama/sg2 scripts/guards/{llama_guard,shieldgemma2}.py`、`llama/sg2 scripts/main.py`、`llama/sg2 tests/`。**依赖**：无。**规模**：M。

### T2（W2-doc）trigger-eval 文档修正 + before/after 脚手架 — 两侧
**描述**：修 `trigger-eval.md` 第 3 行"未实测"与 §5 已有 6/15 结果不一致；§1 增"评估预测/算 AUROC·FPR/给 guard 输出打分"指标型正例；§5 建 **before/after 回归记录**表头（before=7/8+P8 漏，after 待 M4 人工复测填）。
**验收**：① 第 3 行状态与 §5 一致；② §1 新增 ≥1 指标评估正例；③ §5 有 before/after 结构、标注"after 待人工"。
**验证**：阅读核对 + `grep` 状态行；负例表未动（diff 自检）。
**文件**：`llama/sg2 references/trigger-eval.md`。**依赖**：无。**规模**：S。

### T3（W3）量化/GPU 方差 smoke — sg2 opt-in
**描述**：opt-in 测试（`SHIELDGEMMA2_LIVE=1` 门控），固定 **N=5 图 / K=3 次**，int8 连跑测每策略 yes-prob 极差/std + **flip_rate**（is_unsafe 二分翻转占比）；结论落 `sg2 references/shieldgemma2-notes.md`。
**验收**：① 离线默认 skip；② 开门产出 方差 + flip_rate；③ N/K 写死常量。
**验证**：离线 `unittest`（skip 该例，套件绿）；有 GPU 时 `SHIELDGEMMA2_LIVE=1` 跑一次记数。
**文件**：`sg2 tests/test_variance_smoke.py`、`sg2 references/shieldgemma2-notes.md`。**依赖**：无。**规模**：S。

### ☐ Checkpoint Cα（Core 软门）
T1 真跑 revision 非 null + T3 opt-in 绿 + T2 文档一致 + **llama 90/sg2 94 套件绿**。失败：该项标 N/A 顺延，不阻塞 Cβ。

## Phase B · Plus（行为变更，含 W4 硬门）

### T4（W2-desc）description 调优 — 两侧 SKILL.md frontmatter
**描述**：扩 description 覆盖"评估已有预测 / 算 AUROC·FPR / 跑 metrics / 给 guard 输出打分"语义（补 P8 缺口）；**不碰**"数据集下载/格式检查"排除边界。
**验收**：① description 含指标评估措辞；② 负例排除语义未削弱（自检 diff：无新增会与甲 dataset skill 抢触发的词）；③ SKILL.md 仍 ≤250 行。
**验证**：diff 自检 + 行数；人工盲测复测属**报告项**（顺延 M4，记 §5 after）。
**文件**：`llama/sg2 SKILL.md`。**依赖**：T2。**规模**：S。

### T5（W4）judge 并发（TDD） — llm_judge + main.py
**描述**：TDD——先写失败测试再实现。`llm_judge` 加 `predict_batch`（有界 ThreadPool，按 id 顺序回填，每请求保留 retry/timeout/error）；`main.py` 增 `--judge-concurrency N`（默认 1=串行）。
**验收（测试）**：① `-j 1` 输出与历史串行**逐 id 一致**（mock transport）；② 并发输出**按 id 规范化后行集合==串行**（不重排/重复/丢行）；③ `success/errors/skipped` 与串行**逐项守恒**；④ mock-sleep 用例证并发壁钟 < 串行（机制证明）；⑤ 默认 `-j` 缺省=串行（向后兼容）。
**验证**：`python -m unittest discover -s tests`（llama 含新例全绿）。
**文件**：`llama scripts/guards/llm_judge.py`、`llama scripts/main.py`、`llama tests/test_llm_judge.py`。**依赖**：Cα（提交序）。**规模**：M。

### T6（W4-live）实测提速 + 守恒 + R7 偏差登记
**描述**：真跑 judge 子集 `-j 1` vs `-j 4`（凭证 env-only），测壁钟与计数；M2_summary 偏差台账登记"R7 superseded by M3.5 §3-W4"。
**验收**：① `-j 4` 壁钟提速**硬门 ≥30%（目标 ≥2×）**；② `success/errors/skipped` 两次逐项一致；③ 输出按 id 规范化后相同；④ R7 偏差登记落库。
**验证**：两次跑壁钟对比；`diff` 规范化预测；查 M2_summary 台账。
**文件**：M2_summary.md（台账）；运行产物落 gitignore 的 `out_*/`。**依赖**：T5（+ judge 凭证 env）。**规模**：S。

### ☐ Checkpoint Cβ（M3.5 交付硬门）
T5 串行等价 + T6 **提速 ≥30%（目标 ≥2×）** + `success/errors/skipped` 守恒 + **llama 90+/sg2 94+ 套件绿** + `git grep` 凭证/权重零命中 + R7 偏差登记。W2 人工盲测=报告项（不在门内）。

## Phase C · 交付

### T7 文档终稿 + 提交
**描述**：`root/M3.5_summary.md`（W1-W4 追溯表 + 真实数字：revision 样例/方差+flip_rate/提速倍数 + before/after 触发脚手架 + R7 偏差 + §12 后置效果台账指针）；扫 spec §10 全勾；泄漏自查；commit + push（沿直连 main 惯例，待用户点头）。
**验收**：§10 全勾或 N/A 标注；leak 净；summary 完整。**依赖**：T1-T6 终态。**规模**：M。

## 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| W4 并发竞态致输出重排/丢行 | 高（破判定可信） | TDD 锁 id 规范化 + 守恒断言；默认串行 |
| 代理 429/限流 | 中（提速打折/error 增） | N=4 保守 + record-level error 降级（§9-2）；守恒断言会暴露 error 漂移 |
| `config._commit_hash` 在某些版本不存在 | 低（revision 仍 null） | huggingface_hub 兜底；取不到则如实 null + 注记 |
| description 调优引入负例误触 | 中（破既有强项） | T4 自检 diff 不加数据集类词；人工盲测 before/after 兜底（报告项） |
| W2 盲测无法本轮量化 | 低（已移出门） | 改报告项，after 顺延 M4，不阻塞 Cβ |

## 非目标（M3.5 不做）

判别效果优化（E1 应用校准阈值 / E2 栈升级修 NaN / E3 NaN 回退）——**后置 M3.6 重点**（M3.5_SPEC §12）；SKILL.md 上下文瘦身（用户排除）；M4 报告/截图/打包。
