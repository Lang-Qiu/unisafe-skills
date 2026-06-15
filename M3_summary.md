# M3 交付总结 — guard-shieldgemma2（方向 B，乙）

> 日期：2026-06-12（**2026-06-15 真数据升档**）。契约：[`M3_SPEC.md`](M3_SPEC.md)；编排：[`tasks/plan-m3.md`](tasks/plan-m3.md) / [`tasks/todo-m3.md`](tasks/todo-m3.md)（18 任务全完成：任务 17 已用甲 UnsafeBench unified 全量 **2037** 实测升档）。
> 层级结论：**Core-Minimal ✅（C1，零依赖 84 测试）｜Core-Full ✅（C2，live 实测 + 双 guard 矩阵）｜Plus 量化/阈值消融全实测、trigger eval N/A(人工)｜Extension 只留接口**。
> **结果档状态机：`partial_shieldgemma2`**（甲 UnsafeBench 全量 2037 实测；int8 在真实图像上 **19.4% NaN** → 有效覆盖仅 80.6%，故 partial 而非 full；CPU bf16 子集量化归因见 §4-2）。

## 1. 追溯表（spec §6 验收项 × 实现 × 测试）

| spec §6 | 内容 | 实现 | 证据 | 状态 |
|---|---|---|---|---|
| A 结构与发现性 | 标准结构 + 图文互斥 + 零依赖链路 | `SKILL.md`（133 行）、骨架全件 | 三步链路 exit 0；`test_core_isolation`（sys.modules 无 torch/transformers/PIL/bitsandbytes）；黄金 `metrics.sample.json` 精确锁 | ✅ |
| B 路由与守恒 | 图像 eligible 方案 B + 守恒 + exit 三态 | `utils.route_record`、`main.py` | `TestRouteRecord` 四象限；守恒/resume/exit 判例（shieldgemma2 判例经可用性 seam 确定性复现：单跑 1 / 同跑 2） | ✅ |
| C 基线与指标 | caption-rule + 手算对照 + 缺图四 error | `caption_rule.py`、`metrics.py` 受控复制 | `image_expected.json` 两路核算逐位命中；四 error 名逐字断言；多图三落点 | ✅ |
| D 适配器离线 | mock 四例 + 审计 + FIX | `guards/shieldgemma2.py` | 17 离线测试（discovery 实录形态）；unknown_policy 审计落 run_metadata.warnings | ✅ |
| E live 实测 | 显存/延迟/policy 对账/回归门 | int8 基准 | live 17/17；峰值 **5.95GB**；稳态 **~1.9s/图**；policy keys `['dangerous','sexual','violence']` 对账；升级回归门（上游 82 测试 + llama sanity 判定逐条一致） | ✅ |
| F 对比与消融 | 量化/阈值/trigger eval/judge-vision | notes §6、trigger-eval.md | 量化三档实测（int8/CPU bf16/4-bit=NaN）+ 阈值扫描；**真数据新增 int8 19.4% NaN 发现**；trigger eval 正负例落库、实测 N/A(人工同轮)；judge-vision N/A（spec 期探测：代理无 image 端点） | ✅/N-A |
| G 真数据档 | UnsafeBench 200–500 张 | 甲 `dataset-unsafebench` 全量 2037（safe 1260 / unsafe 777，11 类，checker PASS） | **partial_shieldgemma2**：真实双 guard 矩阵已出（`out_m3_real/metrics/`）；int8 真图 NaN 19.4% → 覆盖 80.6%；CPU bf16 子集量化对照（§4-2） | ✅ |
| H 文档与交付 | #5 发甲 + notes + 本文件 | `待甲确认.md` #5、references 全件 | #5 否决窗口进行中（约至 06-14）；`git grep` key/URL/token 零命中；真实图像零入库（合成 fixture 豁免已注 .gitignore） | ✅ |

## 2. 双 Guard 矩阵（`partial_shieldgemma2`：甲 UnsafeBench 全量 **2037**，head_binary，baseline=caption-rule，gold 38% unsafe）

实测档（`out_m3_real/metrics/`，2026-06-15，int8 / device=cuda / threshold 0.5）：

| guard | basis | n | Acc | Recall | FPR | Macro-F1 | AUROC | coverage | error_rate |
|---|---|---|---|---|---|---|---|---|---|
| caption-rule | answered_only | 1428 | 0.605 | 0.020 | 0.014 | 0.395 | — | 0.701 | 0.299 |
| caption-rule | failure_as_wrong | 2037 | 0.424 | 0.014 | 0.323 | 0.306 | — | — | — |
| shieldgemma2 (int8) | answered_only | 1642 | 0.622 | 0.125 | 0.051 | 0.480 | **0.613** | 0.806 | 0.194 |
| shieldgemma2 (int8) | failure_as_wrong | 2037 | 0.502 | 0.104 | 0.253 | 0.394 | 0.613 | — | — |

叙事要点：① **双口径防虚高在真数据爆发力十足**——int8 的 19.4% NaN 在 answered_only 完全隐形，failure_as_wrong 下 Acc 0.62→0.50、FPR 0.05→0.25（NaN 损耗按错算）；caption-rule 同理 0.61→0.42。② **三策略天花板被量化**：shieldgemma2 对 `illicit_behavior` divergence=**19**（binary_recall 0.24 但 category_recall 0）、`self_harm` binary_recall **0.30** 但 category_recall 0——能感知有害却无策略命名（只有 dangerous/sexual/violence 三策略，gold 是 11 类）。③ **AUROC 0.613** = 首个真实图像 guard 排序信号（弱但 >0.5，置信分有效）。④ 两 guard 在 38% 真值基准率下都**重度漏报**（caption-rule recall 0.02、shieldgemma2 0.125）：前者是文本关键词替身遇图像描述，后者是天花板+阈值+NaN 三重叠加。⑤ ⚠️ **shieldgemma2 的 int8 数字受量化噪声污染**（19.4% NaN + 非-NaN 子集 3/6 翻转，§4-2a）→ 视作下界，勿作 ShieldGemma 真实质量结论。

> 旧 `fallback_only` 合成矩阵（examples 6 eligible）已退役为机制自检留档，见 git 历史 `out_m3_twoguard/`；真数据档以本表为准。

### 2.1 真实质量 + 阈值校准（效果提升落地，CPU bf16 参考 150 张，2026-06-15）

§2 的 int8 数字是量化退化下界。用 **CPU bf16 干净分**（150 张分层，0% NaN）测真实质量并校准：

- **真实 AUROC = 0.719**（int8 全量 0.613 / int8 同 150 张 0.676 → 量化把 AUROC 压了 ~0.04–0.11）。**同 150 张直接对照**：CPU 0.719（n=150，0 NaN）vs int8 0.676（n=123，**18% NaN 剔除**）——量化代价首次在自然图像上量化坐实。
- **默认 0.5 阈值严重过保守**：CPU 下 recall 仅 **0.350**（FPR 0.011）——抓不到 2/3 有害图。`calibrate.py` 推荐（`out_cpu_ref150/calibration/`）：

| 操作点 | thr | Recall | FPR | Macro-F1 |
|---|---|---|---|---|
| default（现状） | 0.50 | 0.350 | 0.011 | 0.664 |
| **max_macro_f1（推荐）** | 0.10 | 0.433 | 0.056 | **0.692** |
| recall_at_FPR≤0.1 | 0.05 | 0.467 | 0.100 | 0.688 |

- **结论**：图像侧两个杠杆都有效但有限——(1) 去量化（CPU/换栈）把 AUROC 抬到 0.72；(2) 阈值从 0.5 降到 ~0.10 把召回从 0.35 提到 0.43。**但 AUROC 0.72 仍受三策略天花板封顶**（11 类里 8 类 ShieldGemma 无策略），这是结构上限，非校准能解。校准能力 `scripts/calibrate.py`（两侧受控复制，各 8 测试答案钥锁定）；图像侧**只在 CPU bf16 分上校准**（int8 分是噪声）。

## 3. N/A / 待外部（不删项规则）

| 项 | 原因 | 顺延 |
|---|---|---|
| ~~真实 UnsafeBench 档（任务 17）~~ ✅ 已完成 | 甲全量 2037 到位（checker PASS）；2026-06-15 int8 全量 + CPU bf16 子集对照已跑 | 升档 `partial_shieldgemma2`（§2）；int8 NaN 19.4% 是真数据新发现（§4-2a） |
| trigger eval 实测档（任务 15） | 需多个全新会话人工实测 | 与 M2 任务 16、甲 #3 盲测三方同轮（M4 前） |
| judge-vision | MiMo 代理无 image 端点（404 实测，M3_SPEC §9-4） | 换支持视觉的端点即可复活（L3 接口已留） |
| OpenAI omni 图像档 | 无真 OpenAI key | 真 key 到手即做 |

## 4. Metric Caveats + 限制/偏差登记（引用数字前必读）

1. **结果档 = partial_shieldgemma2**（升档自 fallback_only）：真数据 §2 矩阵成立但 **int8 仅覆盖 80.6%**（19.4% 真图 NaN）；引用 shieldgemma2 数字须同时看 answered_only 与 failure_as_wrong 两口径，勿用单口径下结论。
2. **int8 量化漂移可翻转判定**（核心 caveat）：对极端值合成图最大单策略漂移 **0.710**、翻转 **2/5** 判定（CPU bf16 参考下五图全 safe）——任务 13 初判的"棋盘格 OOD 误报"已改判为量化伪影；真数据上引用 int8 数字前须抽 10–20 张做 CPU 对照（notes §6）。
2a. **【真数据新发现，核心 caveat】int8 在自然图像上既 NaN 又漂移，量化不可信**（CPU 对照 18 图子集实测，2026-06-15）：
   - **NaN**：甲 UnsafeBench 全量 2037 上 int8 `nan_probabilities` 达 **395/2037 = 19.4%**（合成 fixture 0%，据此曾定 int8 为工作基准）——量化不稳定是**数据依赖**的，自然图像远比合成图严重。管道按 error 行优雅降级（不污染 answered_only，进 failure_as_wrong）。
   - **CPU 归因**：12 张 int8-NaN 图在 CPU bf16 上 **12/12 全给有效概率**（0 NaN，其中 2 张真值有害 maxyes≥0.9）→ **坐实 NaN = int8 量化伪影、权重无罪**（与下条 task 14 归因一脉相承）。
   - **漂移（更糟）**：即便 int8 未 NaN 的 6 张图，int8 vs CPU 单策略漂移 mean **0.32** / max **0.60**，**3/6 判定翻转**（含 int8 漏报真值、int8 误报）——把 task 14 合成图结论（max 0.710 / 2-5 翻转）规模化坐实到自然图像。
   - **后果**：§2 的 int8 数字（Recall 0.125 / AUROC 0.613）是**量化退化的下界**，非 ShieldGemma 真实质量；真实质量须读 CPU bf16，但 74s/图 × 2037 ≈ 42h 不实际 → 故档标 `partial`。torch≥2.6 升级后须复测是否随栈修复（原始对照数据 `全量标注结果/.../out_cpu_crosscheck/`，gitignore）。
3. **量化口径偏差**：spec §9-3 的 4-bit NF4 基准在实测环境全 NaN（fp32 compute/eager 复现、CPU bf16 验明权重无罪）→ 基准改 **int8**；4-bit 留 NaN 防御行。
4. **CPU bf16 参考路径 74s/图** → 500 张 ≈10.3h：真数据档按 partial 规则（int8 全量 + CPU 子集），不引入并发。
5. **版本耦合**：transformers 4.53+ 的 Gemma3 前向需 torch≥2.6 → 本环境钉 **4.51.3**（requirements 上界 <4.53 + 注释）；torch 升级后可放开。
6. **caption-rule 是文本替身基线**：不读像素；coverage 受 caption/ocr 覆盖率支配。真数据实测 **覆盖 70.1%**（1428/2037 有 caption，609 条 `missing_caption_ocr`）——缺 caption 的 30% 上双 guard 对比退化为 ShieldGemma 单 guard；且即便有 caption，关键词替身在图像描述上 recall 仅 0.02（23/1428），是机制下限不是 bug。
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
- [ ] 用户：M3 E2E 截图（素材：真数据 `全量标注结果/unsafebench_test/out_m3_real/metrics/metrics.md` 双 guard 矩阵 + by-category 天花板表；该目录已 gitignore，截图入提交 zip 不入 git）
- [x] 甲：`dataset-unsafebench` 全量 2037 已交付（checker PASS）→ 乙 2026-06-15 重跑任务 17 升档 `partial_shieldgemma2`；`待甲确认.md` #5 路径契约经实测落盘布局一致、默认接受成立（见 #6 回执）
- [ ] 三方同轮 trigger eval（甲 #3 + M2 任务 16 + 本档正负例）
- [ ] 用户终审本交付
