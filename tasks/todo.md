# TODO — `guard-llama-guard` Skill (M1 主要产物) · 分层版（实现前最终修订 r3）

> 详见 [`plan.md`](plan.md)。四档：**◼Core-Minimal（必过）/ ◆Core-Full（默认目标）/ ◇Plus（强烈建议）/ ▷Extension（保留不阻塞）**。
> Python 包 = `guard_llama_guard`（下划线）；`python -m guard_llama_guard.*` 与 `python src/guard_llama_guard/main.py` **两跑法零安装均可**（sys.path bootstrap）。
> 状态：⬜ 待办 / 🟦 进行中 / ✅ 完成

## Phase 0 — Skill 本体 ◼
- [ ] **T0** `SKILL.md`(**示例级章节**：TL;DR/Quick command/gated 认证/Exit codes/sanity check/Troubleshooting/Good response pattern/Safety note + When (NOT) to use) + `manifest.yaml` + `pyproject.toml` + **顶层 `requirements.txt`(聚合入口,作业模板硬文件)** + 分层 requirements 骨架 + 自包含 `references/schema.md`(含 risk_metadata 可选字段/eligible 计数/fatal-vs-skip) + `INDEX.md`
- [ ] **Checkpoint P0** — `pip install -e .` 可导入；SKILL.md 章节齐；requirements.txt 在位；schema.md 自包含

## Phase 1 — Core Mainline（tiny 提前 / rule-only e2e 先行 / Llama 后接）
- [ ] **C1** ◼ `config/category_mapping.json` — Llama S1-S14 + 规则关键词(可带权重) + `taxonomy_version`（保留 OpenAI 表）
- [ ] **C2** ◼ tiny 拆两份 — `examples/tiny_unified.jsonl`(**全合法 ≥8 条**:safe/unsafe prompt+response+refusal+**probe**+**adversarial**+**url 图像**,可过 checker) + `tests/fixtures/tiny_malformed.jsonl`(坏 JSON/缺字段/空行,测 skip)
- [ ] **C3** ◼ `utils.py` — fatal vs skip vs **out_of_scope** 三级 / 路由(按 capabilities 出 **eligible**) / §5 输出 / 计数(raw/parsed/valid + per-guard eligible/answered/out_of_scope/join_misses) / 版本化 cache key / **sys.path bootstrap helper**
- [ ] **C4** ◼ `guards/base.py`+`rule_based.py` — `predict` + **`predict_batch`(默认循环)** + capabilities{refusal,continuous_score,modalities,tasks}；规则基线可选 `--rule-score` 伪连续分(experimental)
- [ ] **C5** ◼ `main.py` rule-only e2e — profile/`--guards` 覆盖规则/exit 0·2·3/**每 eligible 记录写行(含 error),行数==eligible_total**
- [ ] **C6** ◼ `metrics.py` v1 — **CLI: `--dataset`+`--guard-outputs`+`--out`(按 id join,join_misses 告警)**；Acc/F1/Recall/FPR/**unsafe_fpr_on_safe_probe**/AUROC + coverage/error_rate + 双口径(分母=answered/eligible)
- [ ] **✅ Checkpoint Core-Minimal（M1 必过线）** — tiny_unified exit 0；行数==eligible；metadata 计数齐；metrics 双口径+probe 有值；tests 绿；**📸 当场截图归档**
- [ ] **C7** ◆ `guards/llama_guard.py` — 官方模板(**prompt 单 turn / response 双 turn 两模式**) + unsafe-token prob + 可靠性校验(token_ids/logit agreement/confidence_status) + 真批量 predict_batch + **无墙钟硬超时声明** + gated 不可走镜像
- [ ] **C8** ◆ `main.py` 接入 Llama + 版本化 cache/resume + cache_hit_rate
- [ ] **C9** ◼/◆ `README.md`(**gated×镜像说明 / torch Windows index-url 装法** / 分层安装 / 两跑法) + `examples/{input,output}_example.jsonl` + `tests/test_basic.py`(e2e/指标/schema/错误分级/exit code/**两跑法**) + requirements 钉版本
- [ ] **C10** ◼ `reports/M1_summary.md` — 档位 + 指标表 + 计数 + **B①–⑤ 追溯表** + limitations + 两跑法复现命令 + **截图清单**
- [ ] **Checkpoint Core-Full** — 有授权 `--profile core-full` exit 0 + **📸 截图**；Llama 失败 `--allow-missing-guards llama_guard` 降级回 Minimal（≠Core 失败）

## Phase 2 — Mainline Plus ◇（强烈建议，不阻塞 Core）
- [ ] **P1** `metrics.py` v2 — bootstrap CI / McNemar+Holm(**配对集口径注明**) / 按类别 / 对抗分桶 / 阈值曲线 / 误判 dump
- [ ] **P2** 完整性能消融（**A–G 不收缩**）→ `optimization_notes.md`(含来源引用) + `reports/{performance_ablation,threshold_sweep,cache_ablation,throughput_ablation}.csv`；A–F 必有实测/N/A+原因，G optional
- [ ] **P3** 触发评测两层 — **P3a** static proxy(**skip-if-no-key + 关键词降级路径**) + **P3b** 真实平台证据(4–6 prompt 截图)
- [ ] **Checkpoint Plus** — metrics v2 全表；P2 A–F 实测/N/A + csv；P3a 指标 + P3b 证据

## Phase 3 — Extension Tracks ▷（全部保留，不阻塞 Core）
- [ ] **E1** `guards/llm_judge.py` — OpenAI 兼容多模态 API + 结构化 JSON + **注入防护** + **请求级 timeout(API 侧真实)**，文本(M1)/图像(M3)
- [ ] **E2** `guards/wildguard.py` — WildGuard 7B 原生 refusal+harm + over/under-refusal 指标 + 真批量；gated 不可走镜像
- [ ] **E3** 多模态图像路径 — main 放开 image_safety → llm_judge 图像分支，用 **tiny 的 url 图像样本**验证
- [ ] **E4** vLLM 可选后端 — `--backend vllm`，未装回退；不进默认依赖
- [ ] **Checkpoint Extension** — 跑通或优雅降级；缺失转 limitations/future work

## 决策状态（见 plan.md）
- [x] r3 合规修订：顶层 requirements.txt 恢复 / SKILL.md 示例级章节 / 截图挂 Checkpoint / B①–⑤ 追溯表
- [x] r3 实现消歧：sys.path 双跑法 / predict_batch 前置 / metrics CLI(--dataset+--guard-outputs) / 超时收窄 / tiny 拆分+补样本(probe/adversarial/url 图像) / eligible+out_of_scope 计数
- [x] r3 复现实操：gated×hf-mirror 不兼容写 README / torch Windows index-url / P3a skip-if-no-key / `.gitignore` 已加 `runs/`
- [x] 四档分层；WildGuard 纳入(E2)；LLM-judge 替换 OpenAI Moderation(E1)；P2 完整(A–G)
- [ ] vLLM 默认不进依赖（E4）
- [ ] E1 前补 API 参数：OpenAI 兼容? / base_url / 模型名 / 环境变量 / response_format JSON
- [ ] 同步 `M2_方向B_实验计划.md`：**§4 矩阵(OpenAI Moderation→LLM-judge) + §10 命令骨架(旧路径/旧 guard 列表已失效)**
