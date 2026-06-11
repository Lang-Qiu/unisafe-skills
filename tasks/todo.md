# M1 Todo — guard-llama-guard（v2）

> 详细验收/验证见 [`plan.md`](plan.md)；契约见 [`root/M1_SPEC.md`](../M1_SPEC.md)。
> 路径约定：无 `root/` 前缀即相对 `guard-llama-guard/`。
> 标记规则：完成打 `x`；做不到的项**不删**，标 `N/A(原因→顺延里程碑)`。
> 交付底线：**C3 只硬依赖 C1**；C2/Plus 未达 → N/A 进 `root/M1_summary.md`。

## Phase 0 · 契约与骨架（可并行）

- [x] 任务 1：`schemas/guard_output.schema.json`（XS · 依赖无）
- [x] 任务 2：`references/io-contract.md`（含全局 exit code contract 表）（XS · 依赖无）
- [x] 任务 3：`references/category_mapping.json` + `metrics-definitions.md`（含双口径定义）（S · 依赖无）
- [x] 任务 4：`examples/input.sample.jsonl` 覆盖矩阵 6 条（M0 的 skill 内 fallback）（XS · 依赖无）

### ☑ Checkpoint C0：✅ 已通过（2026-06-11）——四件套可解析；mapping↔M0 §4 一致；exit 表一致；甲侧文档已推送 ✅

## Phase 1 · Core-Minimal 闭环（只依赖 skill 内文件）

- [x] 任务 5：dry-run 链路 `utils.py`+`main.py` 骨架（eligible 计数）（M · 依赖 2,4）
- [x] 任务 6：guards 框架（capabilities+predict_batch 默认实现）+ rule 适配器 + 词表 + 测试（M · 依赖 3）
- [x] 任务 7：rule 预测落盘 + `--resume`（含 resume_hits/misses/hit_rate 计数）+ 黄金输出固化（S · 依赖 5,6）
- [x] 任务 8：`validate.py`（eligible 双向覆盖；`--metadata` 提供时才校验 skip 计数）+ 测试（S · 依赖 1,7）
- [x] 任务 9：`metrics.py` 双口径 + 四计数字段 + 测试（M · 依赖 3,7；fixtures 可提前）
- [x] 任务 10：SKILL.md v1 + README + requirements 三分层（S · 依赖 7,8,9）

### ☑ Checkpoint C1：技术项已全过（2026-06-11）——干净 venv（0 第三方包）smoke `--guards rule` 1s 全绿（main/validate/metrics 均 exit 0）；unittest 35 全绿；SKILL.md 152 行、指针全有效；`pip install -r requirements.txt` 零安装实证。**待办：smoke 终端截图存档（需人工）**——M1 交付唯一硬前置

## Phase 2 · Core-Full（与 Phase 3 并行；**失败不阻塞 C3**）

- [x] 任务 11：llama_guard.py（spike 前置；predict_batch 真批）（M · 依赖 C1）——spike①实测：safe=19193/unsafe=39257 均单 token；5/5 非 error、conf ∈ (0.0002,0.9954)、S 码保留；批/单判定 5/5 一致（conf 漂移 ≤0.018 如实记录）。**权重用非 gated 镜像 alpindale/Llama-Guard-3-1B（--model-id 切换，官方 gated 仍在批，notes 有溯源与 license 说明）**
- [x] 任务 12：gated/GPU 联调 + 降级实测（§9-J/N）（S · 依赖 11）——GPU bf16 batch=4 约 0.2s/条；`--device cpu --limit 5` 24.7s 判定与 GPU 一致；降级三判例实测（缺依赖→2/单独→1/真 403→2+FIX+rule 完好）
- [x] 任务 13：第一版指标 `--limit 200` + E2E 截图（有 fallback 链）（S · 依赖 12；甲数据可选）——两 guard×4 桶×双口径矩阵 ✅；AUROC 仅 llama-guard（head 1.0）；**甲数据未到，examples+fixtures 顶替（10 eligible），按 #2 默认如实记录，提交前重截**；E2E 截图待人工

### ☑ Checkpoint C2：✅ 已达（2026-06-11，镜像权重+顶替数据，均如实记录）——§9-J 全勾；metrics 矩阵存在；**待办：metrics-definitions.md 发甲启动交叉 review（#4）+ E2E 截图**

## Phase 3 · Plus（C1 后并行；可整体顺延 M2）

- [x] 任务 14：API Guard 基线适配器（OpenAI Moderation；无 key 即 N/A，不进 smoke/默认 CI）（S · 依赖 C1）——适配器+隔离测试 ✅；**有 key 实测档 N/A（用户代理端点无 /moderations，404 实测 → 顺延 M2/换真 OpenAI key）**；live 测试显式 opt-in（OPENAI_MODERATION_LIVE=1）
- [x] 任务 15：over-refusal 正式化 + report 模板 + metrics 样例（S · 依赖 9）——metrics.sample.json 黄金锁定测试 + report-section.md 占位符与字段一一对应
- [x] 任务 16：trigger eval 一轮（实测或文档化判定；负例发甲 #3）（S · 依赖 10）——文档化判定档（8 正例+6 负例，标注未实测，含实测协议与达标线）；实测顺延 C3 前/M2
- [x] 任务 17：性能消融 A–G（E=resume/idempotence；E/F/G 零依赖先行；B/C/D 可 N/A）（M · 依赖 9；11/14 软依赖）——E/F/G 实测 ✅（resume 3.6×+幂等 hash 一致；畸形行恢复；懒 import 0 启动差/4.6GB 依赖差）；A–D N/A(gated 审批/无 moderation 端点 → 顺延)

## Phase 4 · 验收交付（硬前置仅 C1）

- [x] 任务 18：SKILL.md 终稿（实测数字软回填；未达项标注不删除）（XS · 依赖 10+C1；13/16 软）——llama sanity 两行回填（5/5、conf 区间、探针行为）、镜像提示入 troubleshooting；152 行、指针全验证
- [x] 任务 19：`root/M1_summary.md` 追溯表 + N/A 记录 + 已知限制 + Extension Backlog 表（S · 依赖 C1；13–17 状态输入）——五项追溯、指标矩阵内嵌、5 条 N/A、5 条限制、Backlog 6 行（含 MiMo 双协议端点入口）
- [x] 任务 20：§9 全量验收 + 截图归档 + push + 甲 #4 跟进（S · 依赖 18,19）——§9 A–N 速览入 M1_summary §6；41 测试绿；#4 已在待甲确认中标注就绪；E2E 截图待人工

### ☑ Checkpoint C3 = M1 技术交付：✅（2026-06-11）Core-Minimal 必需项全勾；其余勾或 N/A（见 M1_summary §3/§6）；M1_summary 完整。人工余项：E2E 截图、甲 #2/#3/#4、用户终审
### ↓ 交付后人工审阅（非技术验收）：用户终审 + 甲 metrics review 反馈处理
