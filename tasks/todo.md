# TODO — `guard-llama-guard` Skill (M1 主要产物) · 分层版（实现前最终修订 r3）

> 详见 [`plan.md`](plan.md)。四档：**◼Core-Minimal（必过）/ ◆Core-Full（默认目标）/ ◇Plus（强烈建议）/ ▷Extension（保留不阻塞）**。
> Python 包 = `guard_llama_guard`（下划线）；`python -m guard_llama_guard.*` 与 `python src/guard_llama_guard/main.py` **两跑法零安装均可**（sys.path bootstrap）。
> 状态：⬜ 待办 / 🟦 进行中 / ✅ 完成

## Phase 0 — Skill 本体 ◼
- [x] ✅ **T0** `SKILL.md`(示例级章节齐) + `manifest.yaml` + `pyproject.toml` + 顶层 `requirements.txt` + 分层 requirements + 自包含 `references/schema.md` + `INDEX.md` (commit 18dc422)
- [x] ✅ **Checkpoint P0** — `pip install -e .` 导入 OK

## Phase 1 — Core Mainline（tiny 提前 / rule-only e2e 先行 / Llama 后接）
- [x] ✅ **C1** ◼ `config/category_mapping.json` — S1-S14→22 类 + 规则词表 + taxonomy_version；5 测试 (559d3a0)
- [x] ✅ **C2** ◼ tiny 两份 — tiny_unified 8 条**过 checker exit 0**(含 probe/adversarial/url 图像) + fixtures 三类坏行 (caa21aa)
- [x] ✅ **C3** ◼ `utils.py` — fatal/skip/out_of_scope 三级 + 路由 + 计数 + 版本化 cache key;双跑法自测 PASS (477473a)
- [x] ✅ **C4** ◼ `base.py`+`rule_based.py` — predict_batch 前置 + capabilities;tiny 上 TP=3 TN=2 FP=2(设计演示) FN=0 (f01ae78)
- [x] ✅ **C5** ◼ `main.py` rule-only e2e — exit 0/2/3 全路径测试;行数==eligible_total (af61645)
- [x] ✅ **C6** ◼ `metrics.py` v1 — 双口径+probe+AUROC 门控(experimental 降级/诚实 N/A);手算混淆矩阵对上 (b6085e7)
- [x] ✅ **Checkpoint Core-Minimal（M1 必过线）** — smoke exit 0;metrics 报告入库 (c59384c);50 tests 绿;📸 截图待用户补(命令见 M1_summary §⑦)
- [x] ✅ **C7** ◆ `guards/llama_guard.py` — 官方模板双输入模式 + unsafe-token prob + token-id/agreement 校验 + 真批量;模型无关单测全过,**真机推理待装依赖+token** (c7c29df)
- [x] ✅ **C8** ◆ 版本化预测缓存/续跑 — 二跑 hit 7/7;error 行不缓存;--no-cache (eb5d904)
- [x] ✅ **C9** ◼/◆ `README.md`(来源链接/gated×镜像/torch index-url/分层安装/两跑法) + input/output 示例 + 50 tests (1adf9d2)
- [x] ✅ **C10** ◼ `reports/M1_summary.md` — 档位+指标+计数+B①–⑤追溯表+limitations+复现命令+截图清单
- [ ] 🟦 **Checkpoint Core-Full** — 代码就绪;待 `pip install -r requirements-llama.txt` + HF gated 授权后跑 `--profile core-full` + 📸;失败则 allow-missing 降级(≠Core 失败)

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
