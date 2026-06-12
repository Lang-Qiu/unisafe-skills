# M3 Todo — guard-shieldgemma2（v1）

> 详细验收/验证见 [`plan-m3.md`](plan-m3.md)；契约见 [`root/M3_SPEC.md`](../M3_SPEC.md)。
> 路径约定：无 `root/`/`上游/` 前缀即相对 `guard-shieldgemma2/`；`上游/` = `guard-llama-guard/`。
> 标记规则：完成打 `x`；做不到的项**不删**，标 `N/A(原因→顺延里程碑)`。
> 交付底线：**C3 只硬依赖 C0a + C1 + 任务 18**；C0b/C2 软门；P3/真数据档"有则纳入、无则 N/A"进 `root/M3_summary.md`。
> ⛔ **执行放行点：本 todo 在用户放行前不开工**（沿 M2 惯例）。

## Phase 0 · 前置（两路并行、互不阻塞）

- [x] 任务 1：M0 #5 图像路径契约草拟 + 发甲（S · 依赖无）——五要点 + 影响面 + 时间窗已落 `root/待甲确认.md` #5，推送即启动否决窗口（约至 06-14）
- [ ] 任务 2：gated 许可确认 + 权重可达性探查（S · **用户协助**）——三种 FIX 文案 + 官方/镜像/不可达结论
- [ ] 任务 3：transformers 就地升级 + 回归门（M · GPU）——上游 82 测试全绿 + llama sanity 5 条；红则回退 4.46.3 改独立环境（不阻塞 P1）
- [ ] 任务 4：4-bit 试装 + policy discovery（S · GPU · 依赖 2,3）——峰值显存实测 + policy 名称/顺序/输出 shape 实录（任务 12 mock 依据）

### ☑ Checkpoint C0a（硬门）：✅（2026-06-12）#5 已推送，否决窗口启动；P1 解锁
### ☐ Checkpoint C0b（软门）：任务 2/3/4 全清；**任一失败不得阻塞 P1/C1**

## Phase 1 · Core-Minimal（C0a 后；不等 C0b；零第三方依赖；M3 唯一硬门）

- [ ] 任务 5：骨架 + utils 图像路由（方案 B）+ schema 字节同源断言 + 路由/magic 测试（M · 依赖 C0a）
- [ ] 任务 6：合成图资产 + 确定性生成器（S · 依赖 5）——全部 <1KB；含 magic 坏图
- [ ] 任务 7：main.py 适配 + 缺图预检链路（AD-3）+ 多图三落点（AD-7）+ caption-rule（AD-4）+ 注册表（M · 依赖 5,6）
- [ ] 任务 8：缺图/异常四 error 用例 + exit 判例 + resume 测试（S · 依赖 7；提交序在 7 后）
- [ ] 任务 9：validate.py 受控复制（预期零行修改）+ 附加字段不被拒断言（S · 依赖 7）
- [ ] 任务 10：metrics.py 受控复制 + AD-2 薄层 + fixtures 答案钥 `image_expected.json`（两路核算）+ 测试（M · 依赖 5；提交序在 9 后）
- [ ] 任务 11：黄金样例三件 + `test_core_isolation`（sys.modules 断言）+ SKILL.md 重写（≤250 行，清 feat 分支注记）+ README（M · 依赖 7–10）

### ☐ Checkpoint C1：spec §6-A/B/C 全勾；unittest 全绿且核心链路不 import torch/transformers/PIL/bitsandbytes；CLI 全链路 exit 0

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
