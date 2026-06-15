# M3.5 Todo — Skill 性能优化（v1）

> 详细验收/验证见 [`plan-m3.5.md`](plan-m3.5.md)；契约见 [`../M3.5_SPEC.md`](../M3.5_SPEC.md)。
> 路径：无前缀相对仓库根；`llama/`=guard-llama-guard、`sg2/`=guard-shieldgemma2。
> 标记：完成打 `x`；做不到的项**不删**，标 `N/A(原因→顺延)`。
> 交付底线：**Cβ 硬依赖 T5+T6+套件绿+leak净+R7登记**；Cα 软门；W2 人工盲测=报告项（不在门内）。
> ⛔ **执行放行点：本 todo 在用户放行前不开工**。

## Phase A · Core（三任务并行，互不依赖）

- [x] 任务 1（W1）可复现性硬化：两侧 adapter 暴露 `model_revision`（`config._commit_hash`）+ main.py env 块写 `model_revision`/`model_revisions`/`lib_versions`（transformers/bnb/accelerate，importlib.metadata 不触网）；rule/caption-rule 如实 null；真跑实测 `model_revision=548e04f…86` 非 null；离线 8 测试绿（llama 94/sg2 98）。SHA256 留 §9-1 可选未做（足够辨版本）
- [x] 任务 2（W2-doc）trigger-eval 修正：llama 第 3 行状态改"已实测一轮(before)"与 §5 一致；§1 增 P9/P10（评估已有预测）；§5 改 before/after 回归表；§4 过时"任务18"引用修为 W2-T4；sg2 加 P6 + before/after 脚手架（图像侧 before 空缺如实）；**负例表两侧均未动**（S · 依赖无）
- [x] 任务 3（W3）方差 smoke：sg2 opt-in（`SHIELDGEMMA2_LIVE=1`），固定 **N=5/K=3**（synth 生成自包含），int8 测 yes-prob 极差/std + **flip_rate**；离线 skip（sg2 99 测试 2 skip）；**live 实测 flip_rate=0/极差=0/σ=0 → int8 完全确定性**（NaN/漂移=确定性伪影非随机噪声），落 notes §6.1b（S · 依赖无）

### ☑ Checkpoint Cα（Core 软门）：✅（2026-06-16）T1 真跑 `model_revision=548e04f…` 非 null + T3 opt-in 绿且 flip_rate=0 + T2 文档一致 + **llama 94/sg2 99 套件绿**

## Phase B · Plus（行为变更 + W4 硬门）

- [x] 任务 4（W2-desc）description 调优：两侧 SKILL.md frontmatter 加"score/compute AUROC·precision·recall for an existing/saved set of guard predictions against gold labels"（补 P8"评估已有预测"缺口）；**负例排除子句两侧未动**（llama 5/sg2 3 处 dataset 排除仍在，自检 diff 无 dataset 触发词进正例）；行数 llama 173/sg2 139 ≤250；盲测复测=报告项顺延 M4（S · 依赖 T2）
- [ ] 任务 5（W4）judge 并发（TDD）：`llm_judge.predict_batch`（有界 ThreadPool，按 id 回填）+ main.py `--judge-concurrency N`（默认 1）；测：串行等价 / id 行集合相同 / **success·errors·skipped 守恒** / mock-sleep 证提速 / 默认串行（M · 依赖 Cα 提交序）
- [ ] 任务 6（W4-live）实测：judge 子集 `-j1` vs `-j4`（凭证 env-only），壁钟提速 **≥30%(目标≥2×)** + 计数逐项守恒 + 输出按 id 相同；M2_summary 台账登记 **R7 superseded**（S · 依赖 T5 + judge 凭证）

### ☐ Checkpoint Cβ（M3.5 交付硬门）：T5 串行等价 + T6 提速≥30%(目标≥2×) + success/errors/skipped 守恒 + **llama 90+/sg2 94+ 绿** + leak 零命中 + R7 登记；W2 盲测=报告项不在门内

## Phase C · 交付

- [ ] 任务 7：`root/M3.5_summary.md`（W1-W4 追溯表 + 真实数字 revision/方差+flip_rate/提速倍数 + before/after 触发脚手架 + R7 偏差 + §12 后置效果台账指针）+ spec §10 全勾 sweep + 泄漏自查 + push（M · 依赖 T1-T6 终态）

## 非目标（不做，登记防漏）

- 判别效果优化 E1/E2/E3 → **后置 M3.6 重点**（[`../M3.5_SPEC.md`](../M3.5_SPEC.md) §12）
- SKILL.md 上下文瘦身（用户排除）
- M4 报告/截图/复现核对/打包
