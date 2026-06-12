# M3 Spec：多模态亮点 — `guard-shieldgemma2`（UnsafeBench + ShieldGemma 2，小样本；乙侧部分）

> 状态：**评审通过，五项已拍板**（2026-06-12，§9；含 judge-vision 探测实测定案）；⛔ **用户显式放行后才进 tasks 阶段**（沿 M2 惯例）。
> 推导依据：`团队分工计划.md` §6（M3 定义：甲建数据 → 乙接）与 §7（乙侧 16%：guard-shieldgemma2 + 报告 Guard/结果章节）、`M0_接口约定.md` §3/§4/§5（图像真值、ShieldGemma 三策略映射、输出 schema 全部既有）、`guard-shieldgemma2/` M0 脚手架、M1/M2 已交付实现（注册表、metrics 分桶、双口径、exit 契约）。
> 与 M1/M2 的关系：M3 **新建 skill 目录交付**（脚手架已在），但不发明新契约——M0 的输出 schema、22 类映射、指标定义、exit code 三态、错误三分法、守恒式、不删项规则**原样继承**，本文不复述。`dataset-unsafebench` 属甲，本 spec 只约定接口期望，不涉其实现。

---

## 0. 假设声明（ASSUMPTIONS — 不同意请先纠正）

1. **M3 乙侧范围 = `guard-shieldgemma2` 全量交付**：统一 image_safety 输入 → ShieldGemma 2（本地）判定 → 统一 Guard 结果 schema → 指标。叙事卖点 = **同一套 schema/接口跨模态零改动**（分工 §0 统一叙事）。
2. **小样本纪律**：评测目标 200–500 张（脚手架既定）；不追求全量 UnsafeBench；多模态不拖垮文本主干（分工 §8）。
3. **真值字段零新增**：图像真值 = `label.is_unsafe` + `label.canonical_categories`（M0 §3 图像安全行）。**唯一新增契约是文件布局级补充**：`content.images[].path` 的解析基准 + 缺图处理（§4.2），按 M1 #1 模式走默认接受制 → 追加 `M1_待甲确认.md` **#5**。
4. **甲数据解耦**：`dataset-unsafebench` 仍是脚手架、UnsafeBench（HF gated）未动 → 开发用 M0 样本 2 条 image 记录 + 乙自造 fixtures；真数据到位（checker exit 0）后一条命令重出（M1 #2 模式三度复用）。**数据未到不阻塞 M3 技术交付**。
5. **铁律延续**：key/代理 URL/HF token 只活在运行时环境变量；模型权重与数据集 dump 不入库。**乙自造的 <1KB 合成测试图（纯色/几何图形，脚本可再生）允许入库**——它是 fixture，不是数据集 dump；真实 UnsafeBench 图像一张都不进 git。
6. **显存约束是硬现实**：RTX 4060 8GB（实测空闲 ~6GB），ShieldGemma 2 为 4B（Gemma 3 架构含视觉塔），fp16 ≈ 8.6GB 装不下 → **4-bit NF4 量化为 M3 基准口径**（§9-3 已确认）；高精度仅做子集对照消融。
7. **transformers 升级是前置**：conda 环境 4.46.3 无 ShieldGemma2 模型类（需 ≥4.50）；升级策略见 §9-2，无论选哪种，**回归门 = guard-llama-guard 全部 82 测试 + llama sanity 5 条**，回归红则回退锁定 4.46.3 并改走独立环境。
8. **OpenAI omni-moderation 图像交叉验证降级为 L3**：仍无真 OpenAI key（M1 实测代理无 `/moderations`）；脚手架原计划的该项只留接口。图像侧第二真实 Guard 的候选 **judge-vision 已被探测否决**：MiMo 代理对 image 输入返回 404 `No endpoints found that support image input`（2026-06-12 实测，§9-4）→ 图像侧 comparison = caption-rule vs shieldgemma2。
9. **ShieldGemma 2 只评图像本体**（image_safety）；`image_text_safety`/视频/音频不在 M3（out-of-scope skip 链路照常计数）。多图记录评首图 + warning 计数（UnsafeBench 为单图，此为防御性约定）。

---

## 1. 分层目标

### L0 · Core-Minimal —— M3 必须完成，决定 M3 是否交付（零第三方依赖）

| 项 | 内容 |
|---|---|
| 包含 | 标准 skill 骨架（SKILL.md frontmatter 含图像触发词、与 guard-llama-guard **图文互斥**）；`scripts/main.py` image_safety 路由（eligible 规则 §4.1、守恒式、exit 三态、run_metadata 同构）；**caption-rule 基线 guard**（stdlib：对 `content.images[].caption/ocr` 文本做关键词判定——管线可零依赖闭环，诚实标注"文本替身基线"）；`validate.py` + `schemas/guard_output.schema.json`（与 guard-llama-guard 同源，§9-1）；`scripts/metrics.py` 图像档（head_binary 双口径 + AUROC + by-category + comparison ≥2 guards；over-refusal/对抗桶无真值自然缺席）；自造合成小图 + fixtures + 手算答案钥 + 测试；`references/io-contract.md`（图像增量）；M0 #5 路径契约补充发甲 |
| 为什么在这层 | 这是"接口跨模态零改动"主张的本体——schema、守恒、双口径、对比全部在无模型状态可证；与 M1 的 rule 基线同构 |
| 成功标准 | fixtures 上全部指标与答案钥逐位一致（测试锁定）；干净 venv `pip freeze` 为空、unittest 全绿；smoke（caption-rule）exit 0 |
| 失败降级 | 无降级空间——这层失败即 M3 失败 |
| 影响交付 | **是**，唯一硬门 |

### L1 · Core-Full —— GPU + gated 权重具备时必须完成

| 项 | 内容 |
|---|---|
| 包含 | `scripts/guards/shieldgemma2.py` 适配器：4-bit NF4 加载、3 内置策略逐策略 yes 概率、`is_unsafe = max(yes) ≥ 阈值(默认 0.5)`、`confidence = max(yes)`（unsafe 方向，与 openai 适配器取 `category_scores` 最大值同构）、超阈策略 → M0 §4 映射（sexual_content / violence / general_harm）、原始 per-policy 概率全留 `raw_output`；超时/重试/空输出 → 既有错误三分法；`requirements-shieldgemma.txt`（transformers≥4.50 + accelerate + bitsandbytes + pillow）；离线测试（mock 模型输出）+ live opt-in（`SHIELDGEMMA2_LIVE=1`）；M0 样本 2 条 + 合成图 live sanity；`references/shieldgemma2-notes.md` |
| 为什么在这层 | M3 标题的模型本体；依赖 GPU、gated 许可、transformers 升级，但不依赖甲 |
| 成功标准 | live：合成良性图 + M0 样本判定全部非 error、良性图判 safe、延迟记录在案；无权重/无依赖时 `available()=false` + `FIX:` 提示（exit 语义照全局契约）；离线测试不碰 GPU/网络 |
| 失败降级 | 权重/显存不可行 → 适配器 + 离线测试照常交付，live 档 N/A + 原因；指标退回 caption-rule 单 guard |
| 影响交付 | 影响亮点成色，**不阻塞**验收 |

### L2 · Plus —— 强烈建议，不阻塞验收

| 项 | 内容 |
|---|---|
| 包含 | ~~judge-vision~~（探测否决，移入 L3，§9-4）；**量化消融**（4-bit vs CPU 高精度，10–20 张子集：判定翻转数 + confidence 漂移 + 延迟）；**阈值扫描**（per-policy yes 概率连续分现成）；trigger eval 增量（图文互斥正负例实测）；**真实 UnsafeBench 200–500 张结果档**（等甲，checker exit 0 为门）；report 模板图像章节；taxonomy 粗细分歧分析（11 类真值 vs 3 策略——divergence 计数是现成报告素材） |
| 为什么在这层 | 消融/对比是报告 30% 的素材；真数据与 judge-vision 各有外部依赖（甲 / 用户授权） |
| 成功标准 | 各出数字表进 notes/ablations；做不到逐项 N/A + 原因 + 顺延 |
| 失败降级 | N/A + 顺延 M4 报告期；真数据未到 → M0 样本 + 合成图矩阵 + "提交前重跑"标记 |
| 影响交付 | 否 |

### L3 · Extension —— 只留接口，M3 明确不实现

| 项 | 留的接口 | 去向 |
|---|---|---|
| OpenAI omni-moderation 图像档 | 注册表 + schema 已通用 | 真 OpenAI key 到手即做 |
| judge-vision（多模态 LLM 判官） | llm_judge 适配器协议可带 image 内容 | MiMo 代理不收 image（404 实测，§9-4）；换支持视觉的端点即可做 |
| `image_text_safety` 多模态成对评测 | task_type 路由表预留枚举 | M4 后/加分 |
| 视频/音频模态 | schema `modality` 枚举已含 | 不做 |
| 官方权重 vs 镜像切换 | `--model-id` 参数化（M1 同款） | 镜像情况 P0 探明 |
| vLLM/批量吞吐 | `predict_batch` 协议沿用 | 不做 |

---

## 2. 主线任务

- **一句话目标**：用同一套 Guard 结果 schema 与指标机器，把安全评测从文本泛化到图像——ShieldGemma 2 判 UnsafeBench 小样本，证明"统一实验平台"跨模态成立。
- **输入**：unified JSONL（`task_type=image_safety`，`content.images[].path` 指向本地图）；**输出**：与 guard-llama-guard 逐字段同构的 predictions/metrics/run_metadata（守恒式、双口径、comparison 全继承）。
- **最小可运行链路**：`examples/input.sample.jsonl（含自造小图）→ main.py --guards caption-rule → validate.py PASS → metrics.py 出表`，零依赖零网络零 GPU。
- **与甲的对接点**：① 图像路径解析契约（M0 #5 补充，默认接受制）；② UnsafeBench unified 小样本（checker exit 0）+ 11 类 → canonical 映射表一致性（M0 §4 既有）；③ 真数据到位后 200–500 张结果档。
- **只留接口不实现**：见 §1 L3 表。

---

## 3. 文件增量（路径相对 `guard-shieldgemma2/`；root/ 前缀为仓库根）

| 文件 | 动作 | 职责 | 层级 |
|---|---|---|---|
| `SKILL.md` | 重写脚手架 | frontmatter 图像触发 + 图文互斥；≤250 行；quickstart/旗标/sanity/troubleshooting/Safety 同 M1 版式 | L0 |
| `README.md` | 更新 | 人读说明 + 三步复现 + guards 表 | L0 |
| `scripts/main.py` | 新增 | image_safety 路由、eligible §4.1、注册表、--limit/--resume/--timeout-s 哨兵/--model-id/--threshold、run_metadata 同构 | L0 |
| `scripts/guards/__init__.py` + `caption_rule.py` | 新增 | 注册表 + 零依赖文本替身基线 | L0 |
| `scripts/validate.py` + `schemas/guard_output.schema.json` | 同源引入 | 结构+覆盖率校验；schema 与 guard-llama-guard **逐字节一致 + 同源断言测试**（§9-1） | L0 |
| `scripts/metrics.py` | 同源引入+图像适配 | 双口径/AUROC/by-category/comparison 机器复用；eligible 改图像规则 | L0 |
| `references/category_mapping.json` | 新增 | 3 策略 → canonical（M0 §4 原文落库） | L0 |
| `references/io-contract.md` | 新增 | 图像 eligible/路径解析/缺图错误三分法/exit 契约副本 | L0 |
| `examples/`（input/output/metrics 样例 + `images/*.png` 自造 <1KB） | 新增 | 黄金样例 + 最小复现 | L0 |
| `tests/`（test_validate / test_metrics / test_caption_rule / test_shieldgemma2 + fixtures 答案钥 + 合成图） | 新增 | 手算对照 + mock 适配器 + live opt-in | L0/L1 |
| `scripts/guards/shieldgemma2.py` + `requirements-shieldgemma.txt` | 新增 | §5 契约 | L1 |
| `references/shieldgemma2-notes.md` | 新增 | 权重/量化/延迟/校准告诫/policy 原文 | L1 |
| `references/trigger-eval.md` | 新增 | 图文互斥正负例（与 guard-llama-guard 的表互链） | L2 |
| `templates/report-section.md` | 新增 | 图像章节占位符（含 Metric Caveats） | L2 |
| `root/M1_待甲确认.md` | 追加 #5 | 图像路径契约补充（默认接受制 48h） | L0 |
| `root/M3_summary.md` | 新增 | 追溯表 + N/A + 限制/偏差 + Backlog + Metric Caveats（交付件） | L0 |

不动 `guard-llama-guard/` 任何已交付文件（同源文件如有缺陷需双侧修，走 Ask-first）。

---

## 4. 评测口径增量（其余全继承 metrics-definitions v1+v2）

### 4.1 图像 eligible 定义（io-contract §2 的图像版）

记录 eligible 当且仅当：① `task_type == image_safety`；② `modality == ["image"]`；③ `content.images` 非空且首图 `path` 非空。不满足 ①② → `skipped.out_of_scope`；满足但 ③ 缺 → `skipped.missing_content`。守恒式与双向覆盖率核对原样继承。

### 4.2 路径解析与缺图（= M0 #5 补充的实质内容）

- `path` 为相对路径时，**相对 unified JSONL 文件所在目录**解析（绝对路径原样用）；`url`-only 记录 M3 不下载（read-only + 网络隔离）→ 记录级 error `image_url_not_supported`。
- eligible 但文件不存在 / 不可解码 → **记录级 error**（`image_not_found` / `image_decode_error`），照常写行、计入 `counts.errors`、双口径处理——缺图是数据缺口，必须可见而非静默跳过。

### 4.3 指标范围

- head_binary（双口径）+ AUROC（caption-rule 无连续分 → null+注记；shieldgemma2/judge-vision 有）。
- `--by-category`：真值 11 类 → canonical vs 预测 3 策略 → canonical——**taxonomy_divergence 预期显著**（粗细不对称），是报告素材不是 bug，v2 定义原样适用。
- `--adversarial-split` / over-refusal 探针：图像真值无此字段 → 桶 n=0 自然缺席（M2 既有机制，零新代码）。
- comparison：≥2 guards 时照常出透视 + Δ（基线默认 caption-rule）。

---

## 5. ShieldGemma 2 适配器契约要点

| 项 | 约定 |
|---|---|
| 注册名 | `shieldgemma2`；`guard.version` = 实际 model id（运行时取）；`guard.modality = ["image"]` |
| 模型 | 默认 `google/shieldgemma-2-4b-it`（gated，P0 确认许可）；`--model-id` 可换（镜像可用性 P0 探明，M1 镜像先例） |
| 依赖 | `requirements-shieldgemma.txt`：transformers≥4.50、accelerate、bitsandbytes、pillow；缺依赖/缺权重 → `available()=false` + `FIX:` 提示 |
| 加载 | 4-bit NF4（基准口径，§9-3）；`--device` cuda 默认、cpu 可选；加载失败按 guard 级失败 |
| 判定 | 3 内置策略（以 processor 默认 policy 原文为准，存 notes + raw_output）逐策略 yes 概率；`is_unsafe = max(yes_p) ≥ threshold`（默认 0.5，`--threshold` 可调）；`risk_categories` = 超阈策略按 M0 §4 映射；全 safe → `[]` |
| confidence | `max(yes_p)`（unsafe 方向分，天然 [0,1]，无需方向映射——与 M2 judge 的教训对照记录）；per-policy 概率全留 `raw_output.policy_scores` |
| 错误处理 | 单条超时（`--timeout-s` 哨兵：本适配器默认 120s——4-bit 视觉推理比文本慢）/异常 → 记录级 error 行；缺图见 §4.2 |
| 隔离 | live 测试 `SHIELDGEMMA2_LIVE=1` opt-in；默认 unittest 不碰 GPU/权重/网络 |
| 校准告诫 | 量化扰动 per-policy 概率（消融量化）；阈值 0.5 为模型卡默认而非本数据集校准值——AUROC 不受阈值影响，Acc/FPR 受 |

---

## 6. 评测与验收（全部可打勾；不删项规则继承）

**A. 结构与发现性**
- [ ] 标准 skill 结构齐备；SKILL.md ≤250 行、frontmatter 图像触发词与 guard-llama-guard 互斥、指针全有效
- [ ] 干净 venv：caption-rule 三步链路（main→validate→metrics）exit 0，`pip freeze` 为空

**B. 路由与守恒**
- [ ] image_safety eligible 三条件 + 两类 skip 计数正确；守恒式测试锁定；exit 三态判例（无权重单跑 shieldgemma2 → 1；与 caption-rule 同跑 → 2）

**C. 基线与指标（手算对照）**
- [ ] caption-rule 在 fixtures 上判定与答案钥一致；head_binary 双口径/AUROC-null 注记/by-category（含 divergence）/comparison 全部逐位命中
- [ ] 缺图 error 行（not_found/decode/url）三用例进 fixtures，双口径分叉正确

**D. shieldgemma2 适配器（离线）**
- [ ] mock 输出：超阈/欠阈/多策略并发/全 safe 四例的 is_unsafe/categories/confidence 正确；缺依赖 available()=false + FIX；注册表可取

**E. live 实测（GPU+权重，opt-in；软门）**
- [ ] 4-bit 加载峰值显存记录 <8GB；合成良性图判 safe；M0 样本 2 条非 error；延迟记录在案
- [ ] transformers 升级回归门：guard-llama-guard 82 测试全绿 + llama sanity 5 条复测通过（红则回退并改独立环境）

**F. 对比与消融（Plus，逐项可 N/A）**
- [x] judge-vision 探测结论已定案（spec 评审期实测：代理不收 image，404 → 适配器 N/A+原因，入 M3_summary；对比 = caption-rule vs shieldgemma2）
- [ ] 量化消融 / 阈值扫描 / trigger eval 图文互斥实测——各出数字表或 N/A

**G. 真实数据档（甲依赖，非阻塞）**
- [ ] 甲 UnsafeBench unified（checker exit 0）后：200–500 张矩阵 + E2E 截图；未到 → 合成+M0 样本矩阵 + "提交前重跑"标记

**H. 文档与交付**
- [ ] M0 #5 路径契约已追加 `M1_待甲确认.md`（默认接受制）；`references/` 各 notes 就位；key/token/权重/真实图像 `git grep` + 目录自查零泄漏
- [ ] `root/M3_summary.md`：追溯表 + N/A + 限制/偏差 + Metric Caveats（小样本不作强结论；量化口径注记；caption-rule 是替身基线不入主叙事；taxonomy 粗细不对称说明）

---

## 7. 任务依赖图（DAG）

```
P0 前置探查（半天；C0 前全清）
  T0.1 transformers 升级 + 回归门（§9-2 路线）─┐
  T0.2 gated 许可确认 + 权重可达性（官方/镜像）─┤
  T0.3 4-bit 显存试装（峰值实测）──────────────┼─► C0
  T0.4 M0 #5 路径契约草拟 + 发甲（默认接受制）──┘
  T0.5 MiMo 多模态探测 ✅ 已于 spec 评审期实测（不支持 → judge-vision N/A，§9-4）

P1 Core-Minimal（1–2 天，C0 后；零依赖）
  T1.1 骨架 + main.py 路由 + caption-rule ──┐
  T1.2 validate/schema 同源引入 + 同源断言 ──┤
  T1.3 metrics 图像档 + fixtures + 答案钥 ───┼─► T1.5 黄金样例 + SKILL.md ─► C1（唯一硬门）
  T1.4 缺图错误三用例 + 守恒/exit 测试 ──────┘

P2 Core-Full（C0 后可与 P1 尾部并行）        P3 Plus（C2 后/并行）
  T2.1 shieldgemma2.py + mock 测试            T3.1 judge-vision N/A（T0.5 探测否决，不删项）
  T2.2 live sanity（合成图+M0 样本）─► C2     T3.2 量化消融 + 阈值扫描
                                              T3.3 trigger eval 图文互斥实测
                                              T3.4 report 模板图像章节
P4 交付（硬依赖 C1；软吸收 C2/P3/G）
  T4.1 真实 UnsafeBench 档（等甲；--resume 链路）  [软依赖]
  T4.2 文档终稿 + M3_summary.md ─► C3 = M3 技术交付
```

| Checkpoint | 成功条件 | 失败处理 |
|---|---|---|
| **C0** | T0.1–T0.4 全清（T0.5 已于 spec 期定案） | 升级回归红 → 独立环境路线；权重不可达 → L1 整体降 N/A，L0 照常 |
| **C1** | §6-A/B/C/D 全勾；零依赖全绿 | 阻塞修复，不进交付 |
| **C2**（软） | §6-E 全勾 | 显存/权重不可行 → live N/A，单 guard 交付 |
| **C3** | §6-H 全勾；F/G 勾或 N/A | 未勾项 N/A+原因+顺延，入 M3_summary |

---

## 8. 边界（增量；M1 §11 / M2 §8 全部继承）

- **Always**：每个指标数字有答案钥对照；缺图按 error 行可见化；shieldgemma 判定逻辑与对比表完全解耦（不为表好看调阈值——阈值变动只进消融）。
- **Ask first**：动 `guard-llama-guard/` 任何已交付文件（含同源 schema 的双侧修改）；transformers 升级路线变更；judge-vision 探测与实现（涉及 key 使用与多模态数据出境到代理）；向甲提出 M0 #5 之外的新契约。
- **Never**：真实 UnsafeBench 图像/HF token/key/代理 URL 入库；用 caption-rule 数字冒充模型结果（表中必须标注 guard 名）；为省显存静默改判定路径而不记录口径。

---

## 9. 不确定项 → 已决事项（2026-06-12 用户拍板）

1. ✅ **同源代码 = A 受控复制**：validate.py/schema/metrics 核心复制进本 skill + 头部同源注记 + 测试断言 schema 与 guard-llama-guard 逐字节一致；skill 独立可跑，分发 zip 不依赖相对路径。
2. ✅ **transformers = A 就地升级**：pytorch_dl 升至最新 4.x + 回归门（guard-llama-guard 82 测试全绿 + llama sanity 5 条）；回归红 → 回退锁定 4.46.3 并改走独立环境。
3. ✅ **量化口径确认**：4-bit NF4 为 M3 基准；高精度只做 10–20 张子集消融。
4. ✅ **MiMo 多模态探测：已授权并于 spec 评审期实测（2026-06-12）**——红/蓝两张合成图的 `chat/completions` image_url 请求均返回 404 `No endpoints found that support image input`（端点能力缺失，与 M1 的 `/moderations` 404 同性质）→ **judge-vision N/A**，图像侧 comparison = caption-rule vs shieldgemma2；换支持视觉的端点即可复活（L3 表已留接口）。
5. ✅ **分支 = main 直推**（M1/M2 既定流程延续；脚手架的 `feat/guard-shieldgemma2` 注记作废，L0 重写 SKILL.md/README 时一并清除）。

> 执行放行点保留：用户放行后才进 tasks 阶段（先 `tasks/plan-m3.md` / `todo-m3.md` 评审，再实现）。
