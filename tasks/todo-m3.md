# M3 Todo — guard-shieldgemma2（v1）

> 详细验收/验证见 [`plan-m3.md`](plan-m3.md)；契约见 [`root/M3_SPEC.md`](../M3_SPEC.md)。
> 路径约定：无 `root/`/`上游/` 前缀即相对 `guard-shieldgemma2/`；`上游/` = `guard-llama-guard/`。
> 标记规则：完成打 `x`；做不到的项**不删**，标 `N/A(原因→顺延里程碑)`。
> 交付底线：**C3 只硬依赖 C0a + C1 + 任务 18**；C0b/C2 软门；P3/真数据档"有则纳入、无则 N/A"进 `root/M3_summary.md`。
> ⛔ **执行放行点：本 todo 在用户放行前不开工**（沿 M2 惯例）。

## Phase 0 · 前置（两路并行、互不阻塞）

- [x] 任务 1：M0 #5 图像路径契约草拟 + 发甲（S · 依赖无）——五要点 + 影响面 + 时间窗已落 `root/待甲确认.md` #5，推送即启动否决窗口（约至 06-14）
- [x] 任务 2：gated 许可确认 + 权重可达性探查——官方 `gated=manual`（需用户申请，审批期同 meta-llama 先例）；**镜像路线可用**：`Nozim6690/hugging-face_shieldgemma-2-4b-it`（无门、全件、config 核验 ShieldGemma2ForImageClassification + SigLIP、8.6GB 双分片）→ 沿 M1 alpindale 模式（默认 model-id 留官方，实跑 `--model-id` 切镜像）；FIX 三形态素材定
- [x] 任务 3：transformers 就地升级 + 回归门——4.46.3→**4.57.6**（torch 2.5.1+cu121 未动；accelerate 1.10.1、bitsandbytes 0.48.2 同装）；上游 82 测试全绿；llama sanity 5 条判定与 M1 记录逐条一致、conf 漂移 ≤7e-4（< 消融 D 容差 0.0179）；唯一注记：sanity 期间 GPU 被外部进程占用（60%/5.4GB），默认 30s 超时不够 → 用 `--timeout-s 180` 完成，纯延迟对比待 GPU 空闲复测（非门槛项）
- [ ] 任务 4：4-bit 试装 + policy discovery（S · GPU · 依赖 2,3）——峰值显存实测 + policy 名称/顺序/输出 shape 实录（任务 12 mock 依据）

### ☑ Checkpoint C0a（硬门）：✅（2026-06-12）#5 已推送，否决窗口启动；P1 解锁
### ☐ Checkpoint C0b（软门）：任务 2/3/4 全清；**任一失败不得阻塞 P1/C1**

## Phase 1 · Core-Minimal（C0a 后；不等 C0b；零第三方依赖；M3 唯一硬门）

- [x] 任务 5：骨架 + utils 图像路由（方案 B）+ schema 字节同源断言 + 路由/magic 测试（M · 依赖 C0a）——utils 受控复制 @e72fa2be 薄层三项头注枚举；schema hash 相等；17 测试绿
- [x] 任务 6：合成图资产 + 确定性生成器（S · 依赖 5）——7 件 69–89 字节；字节级确定性 + 与入库资产一致性双断言；21 测试绿
- [x] 任务 7：main.py 适配 + 缺图预检链路（AD-3）+ 多图三落点（AD-7）+ caption-rule（AD-4）+ 注册表（M · 依赖 5,6）——main @3a115ecf 五项薄层头注枚举；fixture 实跑 predicted=4 errors=4 守恒；33 测试绿
- [x] 任务 8：缺图/异常四 error 用例 + exit 判例 + resume 测试（S · 依赖 7；提交序在 7 后）——四 error 名逐字断言；多图三落点 + 无多图时无 warnings 键；resume hits=8/misses=0；exit 1/2/1 判例；43 测试绿
- [x] 任务 9：validate.py 受控复制（逻辑零行修改实证，仅头注）+ 附加字段不被拒断言（S · 依赖 7）——实跑输出 --against+--metadata PASS；warnings 字段过 check_record；dup/coverage/结构违规 FAIL 链路全锁；52 测试绿
- [x] 任务 10：metrics.py 受控复制 + AD-2 薄层 + fixtures 答案钥 `image_expected.json`（两路核算一致后锁定，一次性脚本已删）+ 测试（M · 依赖 5；提交序在 9 后）——metrics @e5b2f70 薄层三项头注枚举；文本桶缺席/对抗全 unknown/纯 FP 类别出 macro/Δ 分叉全锁；64 测试绿
- [x] 任务 11：黄金样例三件（metrics.sample.json 精确锁 + output.sample 文档样例）+ `test_core_isolation`（链路进程内三步 + sys.modules 断言）+ SKILL.md 重写（103 行，feat 注记清除）+ README + `references/io-contract.md` 图像版起草 + requirements-shieldgemma.txt（提前自任务 12，供指针有效）（M · 依赖 7–10）——67 测试绿

### ☑ Checkpoint C1：✅（2026-06-12）spec §6-A/C 全勾 + §6-B 离线全勾（shieldgemma2 exit 判例归任务 12 补全）；67 测试全绿且核心链路零重模块 import（test_core_isolation 为证）；examples CLI 三步链路 exit 0

## Phase 2 · Core-Full：ShieldGemma 2（C0b 后；提交在 C1 后；软门）

- [ ] 任务 12：shieldgemma2.py 适配器（spec §5 全项 + unknown_policy_count 审计）+ mock 离线测试（以任务 4 实录为准）+ requirements-shieldgemma.txt + exit 判例补全（M · 依赖 C1, 任务 4）
- [ ] 任务 13：live sanity（`SHIELDGEMMA2_LIVE=1`：合成图判定 + M0 样本 AD-9 路径 + 显存/延迟/policy 对账）+ `references/shieldgemma2-notes.md` 落库 + 首版两 guard comparison 表（S · GPU+权重 · 依赖 12, C0b）

### ☐ Checkpoint C2（软门）：spec §6-E 全勾；两 guard 矩阵存在（截图素材）

## Phase 3 · Plus（C2 后或并行；逐项可 N/A）

- [ ] 任务 14：量化消融（4-bit vs CPU 子集）+ 阈值扫描 → notes 消融节（S · GPU · 依赖 13）
- [ ] 任务 15：trigger eval 图文互斥档（正负例表落库；实测与 M2 任务 16 / 甲 #3 合并同轮）（S · 人工 · 依赖 C1）
- [ ] 任务 16：report 模板图像章节 + Metric Caveats 占位（XS · 依赖 C1）
- [ ] 任务 17：真实 UnsafeBench 200–500 张档 + E2E 截图（S+等待 · 依赖甲数据 checker exit 0 + C2；状态机如实标注，未到 → fallback_only + 提交前重跑标记）

## Phase 4 · 交付（硬依赖 C0a + C1；软吸收 C2/P3/17）

- [ ] 任务 18：文档终稿 sweep + `references/io-contract.md` 定稿 + `root/M3_summary.md`（追溯表 + 状态机四态取一 + N/A 台账 + 偏差登记 + Metric Caveats + Backlog）+ spec §6 全量 sweep + 泄漏自查 + push（M · 依赖 C1 + 11–17 终态）

### ☐ Checkpoint C3 = M3 技术交付：§6-A/B/C/D + H 全勾；E/F/G 勾或 N/A+原因+顺延；M3_summary 完整
