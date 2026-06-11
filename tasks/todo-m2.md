# M2 Todo — guard-llama-guard（v1）

> 详细验收/验证见 [`plan-m2.md`](plan-m2.md)；契约见 [`root/M2_SPEC.md`](../M2_SPEC.md)。
> 路径约定：无 `root/` 前缀即相对 `guard-llama-guard/`。
> 标记规则：完成打 `x`；做不到的项**不删**，标 `N/A(原因→顺延里程碑)`。
> 交付底线：**C3 只硬依赖 C1 + 任务 19/20**；C2 软门；P3/全量档"有则纳入、无则 N/A"进 `root/M2_summary.md`。
> ⛔ **执行放行点：本 todo 在用户放行前不开工**（spec §9 注记）。

## Phase 0 · 定义先行（零依赖）

- [ ] 任务 1：`references/metrics-definitions.md` v2 增补段（S · 依赖无）
- [ ] 任务 2：category/adversarial/probe fixtures + 手算答案钥（M · 依赖 1）

### ☐ Checkpoint C0：v2 定义自审 + 答案钥定稿 + AD-1/R1 用户确认 + `M1_待甲确认.md` #4 追加 v2 一行

## Phase 1 · Core-Minimal（C0 后；零第三方依赖；M2 唯一硬门）

- [ ] 任务 3：`--by-category` 实现 + TestByCategory（M · 依赖 2）
- [ ] 任务 4：`--adversarial-split` 实现 + TestAdversarialSplit（S · 依赖 2；与 3 并行）
- [ ] 任务 5：comparison 渲染 + `--baseline` + docstring 更新（M · 依赖 2；与 3/4 并行）
- [ ] 任务 6：over-refusal 对比正式化 + TestOverRefusalFormal（S · 依赖 5）
- [ ] 任务 7：`examples/metrics.sample.m2.json` 黄金 + 向后兼容锁（S · 依赖 3,4,5,6）

### ☐ Checkpoint C1：spec §6-A/B/C/D/O 全勾；unittest 全绿仍零依赖（干净 venv 复证）；带旗标 CLI 全链路 exit 0

## Phase 2 · Core-Full：LLM-as-judge（C1 后；软门，失败不阻塞 C3）

- [ ] 任务 8：`llm_judge.py` + 注册表 + 离线测试（M · 依赖 C1）
- [ ] 任务 9：`main.py` 接线 `--judge-model` + timeout None 哨兵（S · 依赖 8）
- [ ] 任务 10：`references/llm-judge-notes.md`（XS · 依赖 8）
- [ ] 任务 11：live 联调（LLM_JUDGE_LIVE=1；需用户 session 注入 env）+ git grep 自查（S · 依赖 8,9,10）
- [ ] 任务 12：三 Guard 对比矩阵（顶替数据）+ notes 回填观测（S · 依赖 11）

### ☐ Checkpoint C2（软门）：spec §6-E 全勾；三 Guard 矩阵存在；失败 → live 档 N/A、对比退回两 Guard

## Phase 3 · Plus（C1 后与 P2 并行；逐项可 N/A）

- [ ] 任务 13：消融 A+B 回填（M · GPU · 依赖 C1）
- [ ] 任务 14：消融 D batch 扫描（S · GPU · 依赖 C1）
- [ ] 任务 15：消融 C 阈值扫描（llama 单源先行；judge 源依赖 12 后补）（S · 依赖 C1）
- [ ] 任务 16：trigger eval 实测档（与甲 #3 合并；人工新会话）（S · 依赖 C1 + 甲配合）
- [ ] 任务 17：report 模板 v2 占位符（XS · 依赖 C1）
- [ ] 任务 18：全量 1,725 条结果档 + E2E 截图（S+等待 · 依赖 C1 + 甲 #2 数据；judge 行依赖 C2 可选）

## Phase 4 · 交付（硬依赖 C1；软吸收 C2/P3/18）

- [ ] 任务 19：文档同步终稿：SKILL.md（≤250 行）+ io-contract §6/§7 措辞 + README judge 行（S · 依赖 C1；回填 C2/P3 实况）
- [ ] 任务 20：`root/M2_summary.md`（追溯表 + N/A + 限制 + Backlog + Metric Caveats 四条）+ spec §6 全量 sweep + push（S · 依赖 19）

### ☐ Checkpoint C3 = M2 技术交付：§6-H 全勾；A/B/C/D/O 全勾；E/F/G 勾或 N/A+原因+顺延；M2_summary 完整
