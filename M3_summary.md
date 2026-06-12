# M3 交付总结 — guard-shieldgemma2（方向 B，乙）

> 日期：2026-06-12。契约：[`M3_SPEC.md`](M3_SPEC.md)；编排：[`tasks/plan-m3.md`](tasks/plan-m3.md) / [`tasks/todo-m3.md`](tasks/todo-m3.md)（18 任务：17 完成 + 任务 17 待甲数据）。
> 层级结论：**Core-Minimal ✅（C1，零依赖 84 测试）｜Core-Full ✅（C2，live 实测 + 双 guard 矩阵）｜Plus 量化/阈值消融全实测、trigger eval N/A(人工)｜Extension 只留接口**。
> **结果档状态机：`fallback_only`**（合成 examples 数据；甲的 UnsafeBench unified 到位后重跑升档）。

## 1. 追溯表（spec §6 验收项 × 实现 × 测试）

| spec §6 | 内容 | 实现 | 证据 | 状态 |
|---|---|---|---|---|
| A 结构与发现性 | 标准结构 + 图文互斥 + 零依赖链路 | `SKILL.md`（103 行）、骨架全件 | 三步链路 exit 0；`test_core_isolation`（sys.modules 无 torch/transformers/PIL/bitsandbytes）；黄金 `metrics.sample.json` 精确锁 | ✅ |
| B 路由与守恒 | 图像 eligible 方案 B + 守恒 + exit 三态 | `utils.route_record`、`main.py` | `TestRouteRecord` 四象限；守恒/resume/exit 判例（shieldgemma2 判例经可用性 seam 确定性复现：单跑 1 / 同跑 2） | ✅ |
| C 基线与指标 | caption-rule + 手算对照 + 缺图四 error | `caption_rule.py`、`metrics.py` 受控复制 | `image_expected.json` 两路核算逐位命中；四 error 名逐字断言；多图三落点 | ✅ |
| D 适配器离线 | mock 四例 + 审计 + FIX | `guards/shieldgemma2.py` | 17 离线测试（discovery 实录形态）；unknown_policy 审计落 run_metadata.warnings | ✅ |
| E live 实测 | 显存/延迟/policy 对账/回归门 | int8 基准 | live 17/17；峰值 **5.95GB**；稳态 **~1.9s/图**；policy keys `['dangerous','sexual','violence']` 对账；升级回归门（上游 82 测试 + llama sanity 判定逐条一致） | ✅ |
| F 对比与消融 | 量化/阈值/trigger eval/judge-vision | notes §6、trigger-eval.md | 量化三档实测（int8/CPU bf16/4-bit=NaN）+ 阈值扫描；trigger eval 正负例落库、实测 N/A(人工同轮)；judge-vision N/A（spec 期探测：代理无 image 端点） | ✅/N-A |
| G 真数据档 | UnsafeBench 200–500 张 | — | 甲 `dataset-unsafebench` 未实现 → **fallback_only**：双 guard 合成数据矩阵已出（`guard-shieldgemma2/out_m3_twoguard/metrics/`，截图素材）；数据到位（checker exit 0）即重跑升档 | 待数据 |
| H 文档与交付 | #5 发甲 + notes + 本文件 | `待甲确认.md` #5、references 全件 | #5 否决窗口进行中（约至 06-14）；`git grep` key/URL/token 零命中；真实图像零入库（合成 fixture 豁免已注 .gitignore） | ✅ |

## 2. 双 Guard 矩阵（fallback_only：examples 合成数据 6 eligible，head_binary，baseline=caption-rule）

| guard | coverage | error_rate | Acc (ao) | Recall | FPR | AUROC | Acc (fw) |
|---|---|---|---|---|---|---|---|
| caption-rule | 0.50 | 0.50 | 1.00 | 1.00 | 0.00 | —(无连续分) | 0.50 |
| shieldgemma2 (int8) | 0.67 | 0.33 | 0.75 | 1.00 | 0.333 | 0.833 | 0.50 |

叙事要点：① **双口径防虚高在两类 guard 上同时生效**——caption-rule 的 ao Acc 1.0 是覆盖率只有 0.5 的幸存者数字，fw 口径双方同落 0.5；② by-category 出活的**粗细分歧**（shieldgemma2 二分类命中 violence 真值但归 dangerous→general_harm → divergence=1 + 纯 FP 类别）；③ shieldgemma2 的 FPR 0.333 来自量化伪影（见 §4-2）。

## 3. N/A / 待外部（不删项规则）

| 项 | 原因 | 顺延 |
|---|---|---|
| 真实 UnsafeBench 档（任务 17） | 甲 `dataset-unsafebench` 未实现（checker exit 0 为门）；M0 样本 AD-9 实测并入同一档（同为顶替性质） | 数据到位即跑；int8 全量 + CPU bf16 子集对照（§4-4 的 partial 规则） |
| trigger eval 实测档（任务 15） | 需多个全新会话人工实测 | 与 M2 任务 16、甲 #3 盲测三方同轮（M4 前） |
| judge-vision | MiMo 代理无 image 端点（404 实测，M3_SPEC §9-4） | 换支持视觉的端点即可复活（L3 接口已留） |
| OpenAI omni 图像档 | 无真 OpenAI key | 真 key 到手即做 |

## 4. Metric Caveats + 限制/偏差登记（引用数字前必读）

1. **结果档 = fallback_only**：合成数据仅做机制验证；§2 矩阵不可作为模型质量结论；提交前以真数据重跑并按状态机重标。
2. **int8 量化漂移可翻转判定**（核心 caveat）：对极端值合成图最大单策略漂移 **0.710**、翻转 **2/5** 判定（CPU bf16 参考下五图全 safe）——任务 13 初判的"棋盘格 OOD 误报"已改判为量化伪影；真数据上引用 int8 数字前须抽 10–20 张做 CPU 对照（notes §6）。
3. **量化口径偏差**：spec §9-3 的 4-bit NF4 基准在实测环境全 NaN（fp32 compute/eager 复现、CPU bf16 验明权重无罪）→ 基准改 **int8**；4-bit 留 NaN 防御行。
4. **CPU bf16 参考路径 74s/图** → 500 张 ≈10.3h：真数据档按 partial 规则（int8 全量 + CPU 子集），不引入并发。
5. **版本耦合**：transformers 4.53+ 的 Gemma3 前向需 torch≥2.6 → 本环境钉 **4.51.3**（requirements 上界 <4.53 + 注释）；torch 升级后可放开。
6. **caption-rule 是文本替身基线**：不读像素；coverage 受 caption/ocr 覆盖率支配（真数据上可能大面积 `missing_caption_ocr`——是发现不是噪声）。
7. 小样本（≤13 条/桶）：全部 low_sample/low_support，只作机制验证。
8. 流程偏差（小）：requirements-shieldgemma.txt 提前至任务 11 落库（SKILL.md 指针有效性）；io-contract.md 同步提前起草。

## 5. Extension Backlog

| 项 | 状态 |
|---|---|
| 真实 UnsafeBench 全档 + E2E 截图 | 等甲数据，机制全就位（任务 17） |
| judge-vision（多模态判官） | 端点不支持（404 实测）；换端点即做 |
| OpenAI omni-moderation 图像档 | 真 key 到手即做 |
| torch≥2.6 升级 | 解锁 transformers ≥4.53；届时复测 4-bit NaN 是否随栈修复 |
| 官方 `google/shieldgemma-2-4b-it` 切换 | gated=manual 审批通过后 `--model-id` 一条命令 |
| `image_text_safety` / 视频音频 | 枚举接口已留，不做 |

## 6. 人工待办（非技术验收）

- [ ] 用户：HF 上申请官方 `google/shieldgemma-2-4b-it` 许可（gated=manual；镜像已可用，不阻塞）
- [ ] 用户：M3 E2E 截图（素材：`guard-shieldgemma2/out_m3_twoguard/metrics/metrics.md` 双 guard comparison 表）
- [ ] 甲：`dataset-unsafebench` 实现 + UnsafeBench unified（checker exit 0）→ 乙重跑任务 17 升档；`待甲确认.md` #5 否决窗口（约至 06-14）
- [ ] 三方同轮 trigger eval（甲 #3 + M2 任务 16 + 本档正负例）
- [ ] 用户终审本交付
