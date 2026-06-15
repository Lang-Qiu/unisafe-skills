# M2 Todo — guard-llama-guard（v1）

> 详细验收/验证见 [`plan-m2.md`](plan-m2.md)；契约见 [`root/M2_SPEC.md`](../M2_SPEC.md)。
> 路径约定：无 `root/` 前缀即相对 `guard-llama-guard/`。
> 标记规则：完成打 `x`；做不到的项**不删**，标 `N/A(原因→顺延里程碑)`。
> 交付底线：**C3 只硬依赖 C1 + 任务 19/20**；C2 软门；P3/全量档"有则纳入、无则 N/A"进 `root/M2_summary.md`。
> ⛔ **执行放行点：本 todo 在用户放行前不开工**（spec §9 注记）。

## Phase 0 · 定义先行（零依赖）

- [x] 任务 1：`references/metrics-definitions.md` v2 增补段（S · 依赖无）——§9–§12 落库，v1 零改动（62d651f）
- [x] 任务 2：category/adversarial/probe fixtures + 答案钥文件 `tests/fixtures/category_expected.json`（M · 依赖 1）——13 条覆盖矩阵全项；答案钥两路独立核算一致（4ff9412）；f1 完全漏检极限规则补进 §9

### ☑ Checkpoint C0：✅（2026-06-11）v2 定义自审过 + `category_expected.json` 定稿 + `待甲确认.md` #4 已追加 v2 一行（AD-1/R1 默认接受制生效）

## Phase 1 · Core-Minimal（C0 后；零第三方依赖；M2 唯一硬门）

- [x] 任务 3：`--by-category` 实现 + TestByCategory（M · 依赖 2）——答案钥逐项命中；数据缺口 WARNING；46 绿（161e171）
- [x] 任务 4：`--adversarial-split` 实现 + TestAdversarialSplit（S · 依赖 2；提交序在 3 后）——三态+守恒+n=0 省略；M1 响亮拒绝测试按 spec 退役；51 绿（3fbd0e3）
- [x] 任务 5：comparison 渲染 + `--baseline` + docstring 更新（M · 依赖 2；提交序在 4 后）——≥2 guards 触发；计数+ao 五指标+fw 两指标+Δ；基线缺席 note；58 绿（e5b2f70）
- [x] 任务 6：over-refusal 对比正式化 + TestOverRefusalFormal（S · 依赖 5）——**字段名兼容检查结论：M1 字段名与 v2 定义一致，无需别名**；fw>ao 分叉锁定；62 绿（d4b6c47）
- [x] 任务 7：`examples/metrics.sample.m2.json` 黄金 + 向后兼容锁（S · 依赖 3,4,5,6）——M2 黄金锁定；M1 黄金锁（TestMetricsSampleGolden）原样在 M2 代码上保持绿即兼容断言；63 绿

### ☑ Checkpoint C1：✅（2026-06-11）spec §6-A/B/C/D/O 全勾；干净 venv `pip freeze` 为空 + 63 tests OK（1 opt-in skip）；带旗标 CLI 全链路 exit 0

## Phase 2 · Core-Full：LLM-as-judge（C1 后；软门，失败不阻塞 C3）

- [x] 任务 8：`llm_judge.py` + 注册表 + 离线测试（M · 依赖 C1）——18 离线测试（transport mock）；RED 抓到 general_harm 兜底缺失并修复；81 绿（8fa8fed）
- [x] 任务 9：`main.py` 接线 `--judge-model` + timeout None 哨兵（S · 依赖 8）——None→llama/openai 30 / judge 60 实证；run_metadata 增 timeout_s_effective + judge_model（3a115ec）
- [x] 任务 10：`references/llm-judge-notes.md`（XS · 依赖 8）——git grep key/URL 零命中（cb11753）
- [x] 任务 11：live 联调（用户授权 key 注入后完成）——18/18 live 全绿；样本 5/5 非 error + validate PASS；exit 1（无 env 单跑，用户误跑意外实证）/ exit 2（与 rule 同跑）双判例 ✅；**两个 live 实证修复**：max_tokens 256→4096（推理模型思维链吃预算，finish=length 实录）、confidence 方向映射（自报把握分→unsafe 方向，AUROC 0.375→1.0）；git grep key/URL 零命中
- [x] 任务 12：三 Guard 对比矩阵（顶替数据 10 条）+ notes 回填——judge Acc .90/FPR .167/AUROC 1.0 ＞ llama .80/.333/1.0 ＞ rule .70/.50/—；**judge 是唯一通过 XSTest 探针的 guard**（probe rate 0 vs 1.0/1.0）；judge 延迟 22.5s/条 → 全量串行 ≈11h，task 18 partial 规则现实化

### ☑ Checkpoint C2（软门）：✅（2026-06-12）spec §6-E 全勾；三 Guard 矩阵存在（`out_m2_threeguard/metrics/`，可截图）

## Phase 3 · Plus（C1 后与 P2 并行；逐项可 N/A）

> 引用纪律：M1 数字须有 `ablations.md`/`llama-guard-notes.md` 记录并标注来源；否则轻量 sanity 复测后再引用。

- [x] 任务 13：消融 A+B 回填（M · GPU · 依赖 C1）——A：plain-string 变体渲染空会话（diff 实证）→ 3/5 判定翻转，模板=正确性开关；B：token 概率是唯一连续分来源，AUROC 1.0 vs null（1d49a96）
- [x] 任务 14：消融 D batch 扫描（S · GPU · 依赖 C1）——bs 1→8 单条延迟 249.7→128.2ms，16 饱和；判定批不变，conf 漂移 0.0179 与 M1 记录吻合（标注来源）
- [x] 任务 15：消融 C 阈值扫描（llama 单源 + judge 第二源均 ✅）——llama：双峰，0.75 消探针误报不丢召回；judge：唯一 FP 为高置信误判，阈值不可救（误报形状与 llama 相反，校准告诫再实证）（c0470ff）
- [ ] 任务 16：trigger eval 实测档（与甲 #3 合并；人工新会话）（S · 依赖 C1 + 甲配合）
- [x] 任务 17：report 模板 v2 占位符（XS · 依赖 C1）——comparison/by-category/adversarial/Caveats 四块，v1 不动（389ae56）
- [x] 任务 18：全量结果档（2026-06-15）——甲 WildGuardMix 全量 **1959**（safe 1675/unsafe 284 + 250 XSTest，checker PASS）；rule+llama 全量 + judge 子集 120（**partial** 规则：judge 全量 11h 不现实）。真实数字 **llama AUROC 0.888 / Recall 0.660 / over-refusal FPR 6.4%**；judge 召回最高 0.75 但对抗 AUROC 坍塌 0.976→0.633（三 guard 最脆）。矩阵 `out_text_real/` + `out_judge_subset/`（M2_summary §2）。E2E 截图仍属人工项

## Phase 4 · 交付（硬依赖 C1；软吸收 C2/P3/18）

- [x] 任务 19：文档同步终稿：SKILL.md（~168 行，指针全验证）+ io-contract §6/§7 措辞历史化 + README judge 行与测试计数修正（6234537）
- [x] 任务 20：`root/M2_summary.md`（追溯表 + N/A + 限制/spec 偏差登记 + Backlog 更新 + Metric Caveats 四条）+ spec §6 全量 sweep + push

### ☑ Checkpoint C3 = M2 技术交付：✅（2026-06-12）§6-A/B/C/D/O/E/H 全勾；F = 消融全实测 + trigger eval N/A(人工/甲)；G = 待甲数据（顶替矩阵已出，partial 规则就位）；M2_summary 完整。人工余项：M2 截图、甲 #2/#3/#4、用户终审
