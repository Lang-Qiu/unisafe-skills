# M2 Todo — guard-llama-guard（v1）

> 详细验收/验证见 [`plan-m2.md`](plan-m2.md)；契约见 [`root/M2_SPEC.md`](../M2_SPEC.md)。
> 路径约定：无 `root/` 前缀即相对 `guard-llama-guard/`。
> 标记规则：完成打 `x`；做不到的项**不删**，标 `N/A(原因→顺延里程碑)`。
> 交付底线：**C3 只硬依赖 C1 + 任务 19/20**；C2 软门；P3/全量档"有则纳入、无则 N/A"进 `root/M2_summary.md`。
> ⛔ **执行放行点：本 todo 在用户放行前不开工**（spec §9 注记）。

## Phase 0 · 定义先行（零依赖）

- [x] 任务 1：`references/metrics-definitions.md` v2 增补段（S · 依赖无）——§9–§12 落库，v1 零改动（62d651f）
- [x] 任务 2：category/adversarial/probe fixtures + 答案钥文件 `tests/fixtures/category_expected.json`（M · 依赖 1）——13 条覆盖矩阵全项；答案钥两路独立核算一致（4ff9412）；f1 完全漏检极限规则补进 §9

### ☑ Checkpoint C0：✅（2026-06-11）v2 定义自审过 + `category_expected.json` 定稿 + `M1_待甲确认.md` #4 已追加 v2 一行（AD-1/R1 默认接受制生效）

## Phase 1 · Core-Minimal（C0 后；零第三方依赖；M2 唯一硬门）

- [x] 任务 3：`--by-category` 实现 + TestByCategory（M · 依赖 2）——答案钥逐项命中；数据缺口 WARNING；46 绿（161e171）
- [x] 任务 4：`--adversarial-split` 实现 + TestAdversarialSplit（S · 依赖 2；提交序在 3 后）——三态+守恒+n=0 省略；M1 响亮拒绝测试按 spec 退役；51 绿（3fbd0e3）
- [x] 任务 5：comparison 渲染 + `--baseline` + docstring 更新（M · 依赖 2；提交序在 4 后）——≥2 guards 触发；计数+ao 五指标+fw 两指标+Δ；基线缺席 note；58 绿（e5b2f70）
- [x] 任务 6：over-refusal 对比正式化 + TestOverRefusalFormal（S · 依赖 5）——**字段名兼容检查结论：M1 字段名与 v2 定义一致，无需别名**；fw>ao 分叉锁定；62 绿（d4b6c47）
- [x] 任务 7：`examples/metrics.sample.m2.json` 黄金 + 向后兼容锁（S · 依赖 3,4,5,6）——M2 黄金锁定；M1 黄金锁（TestMetricsSampleGolden）原样在 M2 代码上保持绿即兼容断言；63 绿

### ☑ Checkpoint C1：✅（2026-06-11）spec §6-A/B/C/D/O 全勾；干净 venv `pip freeze` 为空 + 63 tests OK（1 opt-in skip）；带旗标 CLI 全链路 exit 0

## Phase 2 · Core-Full：LLM-as-judge（C1 后；软门，失败不阻塞 C3）

- [ ] 任务 8：`llm_judge.py` + 注册表 + 离线测试（M · 依赖 C1）
- [ ] 任务 9：`main.py` 接线 `--judge-model` + timeout None 哨兵（S · 依赖 8）
- [ ] 任务 10：`references/llm-judge-notes.md`（XS · 依赖 8）
- [ ] 任务 11：live 联调（LLM_JUDGE_LIVE=1；需用户 session 注入 env；无 key 判例仅限显式 llm-judge 命令，smoke/默认 CI 不跑 judge）+ git grep 自查（S · 依赖 8,9,10）
- [ ] 任务 12：三 Guard 对比矩阵（顶替数据）+ notes 回填观测（S · 依赖 11）

### ☐ Checkpoint C2（软门）：spec §6-E 全勾；三 Guard 矩阵存在；失败 → live 档 N/A、对比退回两 Guard

## Phase 3 · Plus（C1 后与 P2 并行；逐项可 N/A）

> 引用纪律：M1 数字须有 `ablations.md`/`llama-guard-notes.md` 记录并标注来源；否则轻量 sanity 复测后再引用。

- [ ] 任务 13：消融 A+B 回填（M · GPU · 依赖 C1）
- [ ] 任务 14：消融 D batch 扫描（S · GPU · 依赖 C1）
- [ ] 任务 15：消融 C 阈值扫描（llama 单源先行；judge 源依赖 12 后补）（S · 依赖 C1）
- [ ] 任务 16：trigger eval 实测档（与甲 #3 合并；人工新会话）（S · 依赖 C1 + 甲配合）
- [ ] 任务 17：report 模板 v2 占位符（XS · 依赖 C1）
- [ ] 任务 18：全量 1,725 条结果档 + E2E 截图（S+等待 · 依赖 C1 + 甲 #2 数据；judge 行依赖 C2 可选；judge 未完则标 **partial**，不得声称三 Guard 全量）

## Phase 4 · 交付（硬依赖 C1；软吸收 C2/P3/18）

- [ ] 任务 19：文档同步终稿：SKILL.md（≤250 行）+ io-contract §6/§7 措辞 + README judge 行（S · 依赖 C1；回填 C2/P3 实况）
- [ ] 任务 20：`root/M2_summary.md`（追溯表 + N/A + 限制 + Backlog + Metric Caveats 四条）+ spec §6 全量 sweep + push（S · 依赖 19）

### ☐ Checkpoint C3 = M2 技术交付：§6-H 全勾；A/B/C/D/O 全勾；E/F/G 勾或 N/A+原因+顺延；M2_summary 完整
