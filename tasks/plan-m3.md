# Implementation Plan：guard-shieldgemma2 M3（v1，2026-06-12）

> 来源契约：[`root/M3_SPEC.md`](../M3_SPEC.md)（评审通过、五项拍板 + 九条修订已落；本计划**不改 spec、不实现代码**）。
> 背景契约：[`root/M0_接口约定.md`](../M0_接口约定.md) §3/§4/§5 + M1/M2 全局契约（exit 三态、错误三分法、双口径、守恒式、GuardAdapter 协议、不删项规则——全部继承，不复述）。
> 现状基线：M2 C3 已交付（[`root/M2_summary.md`](../M2_summary.md)）；本计划基于对上游 `guard-llama-guard/scripts/{main,utils,validate,metrics}.py`、`guards/{base,rule_based,__init__}.py`、M0 样本 2 条 image 记录、`guard-shieldgemma2/` M0 脚手架的**实读**编排。

## 路径约定（全局）

**除非带 `root/` 或 `上游/` 前缀，所有路径相对 `guard-shieldgemma2/`**；`上游/` = `guard-llama-guard/`。本计划与 todo 位于 `root/tasks/plan-m3.md`、`root/tasks/todo-m3.md`（M1/M2 的计划文件原位不动）。

## Overview

把 M3_SPEC 拆为 **18 个 XS/S/M 档任务、5 个阶段、5 个 checkpoint（C0a/C0b/C1/C2/C3）**。垂直切片：每个 L0 任务交付"路由→实现→fixtures 手算对照→落盘可见"的完整链路。**M3 技术交付（C3）只硬依赖 C0a + C1 + 任务 18**；C0b/C2 是环境软门；P3 与真实数据档按"有则纳入、无则 N/A"吸收（spec §7）。

**实读关键结论（编排依据）**：上游代码的文本特异性高度集中——`utils.route_record`（eligible 单一来源，main/validate/metrics 三处共用）与 `utils.record_text`（guard 输入），外加 `metrics.build_metrics` 的 `prompt_harm`/`pair_response_harm` 两个文本真值桶；其余全部模态无关（compute_bucket、双口径、by-category、comparison、守恒、resume、exit 契约）。`validate.py` 的覆盖率核对完全经由 `utils.route_record` → **受控复制预期零行修改**；`check_record` 只查必需键、不拒附加键 → `prediction.warnings` 无验证阻力（schema 亦无 `additionalProperties` 限制，spec §0-9 已核）。

## Architecture Decisions（编排层执行决策，不改 spec）

- **AD-1 受控复制清单与同源纪律**（spec §9-1 细化）：`schemas/guard_output.schema.json` **字节复制**，同源断言测试比对 `../guard-llama-guard/schemas/...`，上游路径缺席（独立分发 zip）时 `skipTest` + 注记（登记 R7）。`scripts/{utils,validate,metrics,main}.py` 与 `guards/{base,__init__}.py` 受控复制，每个文件头部注记 `Derived from guard-llama-guard@<commit> scripts/<file>; image adaptation: <修改点枚举>`，`<commit>` 取复制时 `git log -1 --format=%H -- 上游/<file>`。**薄层修改点必须在头注里逐条枚举**——头注之外的差异即缺陷。
- **AD-2 metrics 薄层的桶差异（唯一允许的行为 diff）**：`prompt_harm`/`pair_response_harm` 改为 **rows 非空才输出**（图像数据无此真值 → 自然缺席）；`head_binary` 恒出；`over_refusal_probe` 保持上游行为（恒出，n=0 无指标——图像真值无探针字段，恒为 n=0，如实呈现）；`--baseline` 默认值 `rule` → `caption-rule`；`--by-category`/`--adversarial-split` 旗标零修改保留（图像数据 adversarial 全缺 → 全进 unknown 片，设计即如实暴露，登记 R6）。其余函数体零行为差异。
- **AD-3 缺图预检统一在 main.py、错误行 guard 无关**（spec §4.4"缺图错误仍由 main 链路统一产生"的实现）：路由后对每条 eligible 记录做一次预检——`resolve_image_path`（相对 JSONL 所在目录）→ url-only → `image_url_not_supported`；文件不存在 → `image_not_found`；stdlib magic bytes（PNG/JPEG/WebP/GIF/BMP 头）不符或读取异常 → `image_decode_error`。预检失败的记录对**每个** guard 直接写 `make_result(is_unsafe=None, error=...)` 行，不调 `predict`（数据缺口是数据属性而非 guard 属性；守恒式不受影响）。预检通过的记录把解析后绝对路径以 `_resolved_image_path` 注入 record 副本传给 adapter（下划线键不落盘）。
- **AD-4 caption-rule 形态**：`guards/caption_rule.py` 注册名 `caption-rule`，`guard.modality=["image"]`（按消费的记录模态）；关键词表 = 受控复制 `上游/assets/rule_keywords.json` → `assets/caption_keywords.json`（独立演化，头部 `$comment` 注同源）；输入 = 首图 `caption`+`ocr` 拼接（spec §4.4：不读像素、不做 OCR）；两者全空 → 该 guard 自产 error `missing_caption_ocr`（与 AD-3 的 main 级预检错误互补：缺图对所有 guard 是 error，缺 caption 只对 caption-rule 是 error）；`raw_output = {engine: "caption-keyword-regex-v1", matched, text_source}`；confidence 恒 null（AUROC 剔除注记复用上游机制）。
- **AD-5 合成 fixture guards 延续 M2 模式**：metrics fixtures 用 `fixture-guard-a`（带 confidence）/`fixture-guard-b`（无 confidence）两合成 guard，**仅作为数据存在，不注册、不可被 main.py 调用**。
- **AD-6 同改文件串行提交序**：任务 7 → 8 同改 `scripts/main.py` 与 `tests/test_main.py`，任务 9 → 10 同涉 utils 路由消费，**实现与提交顺序固定**；禁止并发落盘同一文件。
- **AD-7 多图 warning 三落点的实现位**：main.py 在路由处统计 `run_metadata.warnings.multi_image_records`；行级落点（`prediction.warnings` 含 `"multi_image_first_only"`、`raw_output.image_index=0`）由 main 在**写行前统一后注**（post-annotate），adapter 保持模态无关——单一实现点，所有 guard 行为一致。`warnings` 键仅在非空时出现（继承 M2 AD-2"无空占位"原则）。
- **AD-8 `unknown_policy_count` 落点 = `run_metadata.warnings.unknown_policy_count`**：策略名集合是模型属性而非记录属性，运行级审计；行级原文照常留 `raw_output.policy_scores`（spec §5"不私自映射 + raw 保留"）。
- **AD-9 M0 样本图片缺失的处置**：`root/M0_dataset_unified_sample.jsonl` 的 2 条 image 记录路径指向仓库根 `images/unsafebench/`（不存在，且真实图不入库）。live sanity（任务 13）以 `examples/` 自造数据为主；M0 样本实测用"复制该 2 条到 `out_*/`（gitignored）+ 就地生成合成占位图"完成，**不在仓库根新建 images/ 目录**。
- **AD-10 合成图生成器**：`scripts/make_synth_images.py`（stdlib zlib+struct 手写 PNG chunk，确定性输出——同参数重跑字节一致）；生成 `tests/fixtures/images/` 与 `examples/images/` 全部小图（<1KB）+ 一张"`.png` 后缀的文本字节坏图"（L0 magic 用例）。图与生成脚本都入库（spec §0-5：fixture 非数据集 dump）。

## 与 spec / 现状的冲突与风险登记（只登记，不改 spec）

| # | 类型 | 内容 | 处置 |
|---|---|---|---|
| R1 | 契约 | M0 #5 路径契约走默认接受制，甲可能在 48h 窗口内异议 | C0a = "已发甲"即过门（spec 评审定）；异议 → 修订 `utils.resolve_image_path` + fixtures 同步，影响面已收敛在单函数 |
| R2 | 环境 | transformers 就地升级可能打破上游 llama 链路 | 任务 3 自带回归门（上游 82 测试 + llama sanity 5 条）与回退路径（`pip install transformers==4.46.3` + 改走独立环境）；**失败不阻塞 P1**（C0b 软门） |
| R3 | 外部 | `google/shieldgemma-2-4b-it` gated 许可须用户 HF 账号亲点（乙不可代点）；镜像可用性未知 | 任务 2 探查 + 用户协助项；不可达 → L1 整体 N/A，`--model-id` 与 FIX 文案保留切换能力 |
| R4 | 资源 | 8GB 显存对 4B 视觉模型 4-bit 推理是否够未实证（权重 ~2.5–3GB + 视觉塔激活 + 3 策略批） | 任务 4 实测峰值；不够 → `--device cpu` 退路（延迟↑，小样本可承受）；再不行 live 档 N/A |
| R5 | API | ShieldGemma2 的 transformers API 形态（policy 暴露方式、输出 shape）未实读过 | 任务 4 policy discovery 先行；任务 12 的 mock 以 discovery 实录为准；API 与 spec §5 预期不符 → **登记偏差进 M3_summary，不擅改契约** |
| R6 | 数据 | 甲 UnsafeBench 数据布局未知：images 目录形态、caption/ocr 覆盖率（caption-rule 在真数据上可能大面积 `missing_caption_ocr`）、adversarial 字段全缺 | 设计即如实暴露（error 行 + unknown 片 + 审计计数）；进 M3_summary Metric Caveats；路径契约由 #5 锁定 |
| R7 | 分发 | 同源断言测试引用 `../guard-llama-guard/`，独立分发 zip 中上游在侧（同包）但单独拷走本 skill 时缺席 | 断言测试 `skipTest`（带原因）当上游路径不存在；课程提交 zip 两 skill 同包 → 实际恒可断言 |
| R8 | 实测 | 模型对纯色合成图的判定未知，spec §6-E"合成良性图判 safe"可能落空 | 判 unsafe 则如实记录 + 换一张公开域真实良性照片复测（用户提供，不入库），验收以复测为准；sanity 的硬断言是"非 error + 判定与延迟记录在案" |
| R9 | 文档 | 脚手架 SKILL.md/README 的 `feat/guard-shieldgemma2` 分支注记已作废（§9-5）；上游 `guard-llama-guard/` 文档零改动（其 L3 表/Backlog 提及 M3 的行在任务 18 评估是否需 Ask-first 微调） | 分支注记清除归任务 11（SKILL.md 重写自然覆盖）；上游任何改动走 Ask-first（spec §8） |

---

## Phase 0 · 前置（≈半天；两路并行、互不阻塞）

### 任务 1：M0 #5 图像路径契约草拟 + 发甲（S）
- **描述**：在 `root/待甲确认.md` 追加 **#5**（默认接受制 48h）：① `content.images[].path` 相对路径以 unified JSONL 所在目录为基准（绝对路径原样用）；② eligible 方案 B（path 或 url 至少一个非空；均空才 missing_content）；③ url-only → 乙侧记录级 error `image_url_not_supported`（M3 不下载）；④ 缺图/坏图 → error 行可见化（`image_not_found`/`image_decode_error`），不静默跳过；⑤ 多图评首图 + 三落点 warning。同步更新文末时间窗表。推送即启动否决窗口。
- **验收**：#5 含上述五要点 + 影响面说明（只增不改，甲侧唯一动作=按 ① 摆放图片目录）+ 时间窗行。
- **验证**：人工对照 spec §4.1/§4.2/§0-9 逐项勾；git push 成功。
- **依赖**：无。**文件**：`root/待甲确认.md`。

### 任务 2：gated 许可确认 + 权重可达性探查（S；**用户协助项**）
- **描述**：用户在 HF 页面确认/点击 `google/shieldgemma-2-4b-it` 许可（乙不可代点；Google 许可通常即时通过）；乙侧探查：带 token 的 `model_info` 探针确认 gated 状态与可下载性；镜像路线核查（`HF_ENDPOINT` 镜像对 gated 模型需 token 的行为、是否存在可用非官方镜像——M1 alpindale 先例）。产出：`--model-id` 默认值的最终确认 + guard 级失败 `FIX:` 文案素材（许可未点/无 token/网络三种）。
- **验收**：三种失败形态的 FIX 文案定稿；权重可达性结论（官方/镜像/不可达三选一）记录在案（落库归任务 13 的 notes）。
- **验证**：探针命令 exit code + 输出实录。
- **依赖**：用户点许可。**文件**：无（结论暂存，任务 12/13 落库）。

### 任务 3：transformers 就地升级 + 回归门（M；GPU；§9-2 路线 A）
- **描述**：`pytorch_dl` 环境 `pip install -U transformers`（目标 ≥4.50，记录精确版本与 accelerate/bitsandbytes 一并装齐——后两者是 requirements-shieldgemma 成员，提前装供任务 4 用）；**回归门**：上游 `python -m unittest discover -s tests`（82 测试，2 opt-in skip）全绿 + llama sanity（`上游/examples/input.sample.jsonl` 5 条，`--guards rule,llama-guard`，输出 out_*/ gitignored）判定与 M1 记录一致。
- **验收**：回归门全绿；版本号四元组（transformers/torch/accelerate/bitsandbytes）记录在案。
- **验证**：unittest 输出 + sanity RESULT 行 + 与 `上游/references/llama-guard-notes.md` 既有判定对照。
- **失败路径**（R2，不阻塞 P1）：任一回归红 → `pip install transformers==4.46.3` 回退复证绿 → 改走独立环境（venv 复用系统 CUDA torch 不可行时再议，Ask-first）。
- **依赖**：无。**文件**：无（环境操作；结论落库归任务 13 notes）。

### 任务 4：4-bit 试装 + policy discovery（S；GPU；依赖 2,3）
- **描述**：一次性探查脚本（不入库）：NF4 4-bit 加载 `shieldgemma-2-4b-it` → 记录峰值显存（`torch.cuda.max_memory_allocated`）与加载耗时；**policy discovery**（spec §5）：实录 processor/model 暴露的 policy 名称、顺序、默认 prompt 形态；单张合成图 forward → 输出对象结构与概率 shape 实录；单条延迟初值。
- **验收**：峰值显存 <8GB 实证（或如实记录超限 + cpu 退路实测）；policy 名称/顺序原文实录；输出 shape 确认（任务 12 mock 的依据）。
- **验证**：脚本输出实录（截图/文本）。
- **依赖**：任务 2（权重可达）、任务 3（环境就绪）。**文件**：无（实录归任务 13 notes；探查脚本用后即删，沿 M2 答案钥纪律）。

### ☑ Checkpoint C0a（硬门：L0 契约就绪）
- **成功条件**：任务 1 已推送（否决窗口启动即算，沿 M1 #1 先例，不等窗口关闭）。
- **失败处理**：甲异议 → 契约修订 + 后续 fixtures 同步；修订完仍是 P1 前置。

### ☑ Checkpoint C0b（软门：L1 环境探查）
- **成功条件**：任务 2/3/4 全清。
- **失败处理**：**任一失败不得阻塞 P1/C1**——R2/R3/R4 各自路径；最坏 L1 整体 N/A，L0 照常交付。

---

## Phase 1 · Core-Minimal（≈1–2 天；C0a 后；**不等 C0b**；全程零第三方依赖）

> 通用纪律：受控复制头注（AD-1）；每个指标数字两路独立手算（M2 答案钥纪律——人工 + 一次性定义脚本，脚本用后即删）；`sys.modules` 重模块断言纳入任务 11。

### 任务 5：骨架 + utils 图像路由 + schema 同源断言（M）
- **描述**：建目录骨架（scripts/guards、schemas、references、examples/images、tests/fixtures/images、templates、assets）；`scripts/utils.py` 受控复制 + 图像薄层：`route_record` 改 §4.1 三条件（方案 B：首图 path 或 url 至少一非空；均空 → missing_content）、`record_text` → `record_caption_text`（首图 caption+ocr 拼接）、新增 `resolve_image_path(record, dataset_dir)` 与 `image_magic_ok(path)`（stdlib 头字节：PNG/JPEG/WebP/GIF/BMP）；`schemas/guard_output.schema.json` 字节复制；`references/category_mapping.json`（M0 §4 三策略 → canonical + UnsafeBench 11 类表收录为注释参考）；`tests/test_routing.py`（eligible/out_of_scope/missing_content/url-only-eligible 四象限 + 路径解析基准 + magic 判定真伪用例）+ `tests/test_schema_sync.py`（字节相等断言，上游缺席 skipTest，AD-1/R7）。
- **验收**：路由四象限与 spec §4.1 逐条一致；schema 断言绿；magic 判定对"文本字节假 .png"返回 False。
- **验证**：`python -m unittest discover -s tests -v`。
- **依赖**：C0a。**文件**：`scripts/utils.py`、`schemas/guard_output.schema.json`、`references/category_mapping.json`、`tests/test_routing.py`、`tests/test_schema_sync.py`。

### 任务 6：合成图资产 + 生成器（S）
- **描述**：`scripts/make_synth_images.py`（AD-10：stdlib 写 PNG，确定性）；生成 `tests/fixtures/images/`（良性纯色 ≥3、几何图形 1、文本字节坏图 1）与 `examples/images/`（良性 2）；全部 <1KB；README of fixtures 不需要——生成参数注释在脚本内。
- **验收**：重跑生成器字节一致（确定性断言进 `tests/test_synth_images.py`）；全部文件 <1KB；坏图 magic 判定 False。
- **验证**：unittest + `git status` 确认体积。
- **依赖**：任务 5（magic 函数）。**文件**：`scripts/make_synth_images.py`、`tests/fixtures/images/*`、`examples/images/*`、`tests/test_synth_images.py`。

### 任务 7：main.py 适配 + caption-rule + 注册表（M）
- **描述**：`scripts/main.py` 受控复制 + 薄层：DEFAULT_GUARDS=`caption-rule`、DEFAULT_MODEL_ID=`google/shieldgemma-2-4b-it`、新增 `--threshold`（透传 adapter_config）、移除 `--judge-model`（头注枚举）；**AD-3 缺图预检链路**（resolve → url-only/not_found/magic 三类 error 行统一产生 + `_resolved_image_path` 注入）；**AD-7 多图三落点**（run_metadata.warnings 计数 + 写行前 post-annotate）；`guards/base.py` 受控复制（零修改预期）；`guards/__init__.py`（注册 `caption-rule`；`shieldgemma2` 行**留待任务 12**——避免 known_guards 宣称未实现的模块）；`guards/caption_rule.py`（AD-4 全项）+ `assets/caption_keywords.json`；`tests/test_caption_rule.py`（关键词命中/未命中/`missing_caption_ocr` error/谐音误报样例照搬上游已知特性）+ `tests/test_main.py` 基础（守恒式、run_metadata 形状、dry-run）。
- **验收**：`main.py --guards caption-rule` 在 examples 上 exit 0 + RESULT 行；守恒式测试锁定；caption/ocr 全空 → error 行非默认 safe。
- **验证**：unittest + CLI 实跑对照 run_metadata。
- **依赖**：任务 5,6。**文件**：`scripts/main.py`、`scripts/guards/{__init__,base,caption_rule}.py`、`assets/caption_keywords.json`、`tests/test_caption_rule.py`、`tests/test_main.py`。

### 任务 8：缺图/异常链路完整化 + exit 判例（S；提交序在 7 后，AD-6）
- **描述**：`tests/fixtures/pipeline_dataset.jsonl`（≈8 条：正常 ×3、url-only、not_found、magic 坏图、caption/ocr 全空、多图 ×1，配 fixtures/images）；test_main 增补：四 error 用例逐条断言 error 名与行存在性（守恒不破）、多图三落点（run_metadata 计数 + prediction.warnings + raw_output.image_index）、`--resume` 命中不重算、exit 判例（未知 guard 全失败 → 1；空输入 → 1）。
- **验收**：spec §6-B 全勾的离线半（shieldgemma2 判例除外，归任务 12）；四 error 名逐字与 spec §4.2/§4.4 一致。
- **验证**：unittest -v。
- **依赖**：任务 7。**文件**：`tests/fixtures/pipeline_dataset.jsonl`、`tests/test_main.py`。

### 任务 9：validate.py 受控复制（S）
- **描述**：`scripts/validate.py` 受控复制——**预期零行修改**（覆盖率经由本 skill 的 `utils.route_record` 自动取图像规则；canonical 集取本 skill mapping）；头注同源；`tests/test_validate.py`（结构合法/error 行合法/覆盖率双向/重复 id FAIL/`prediction.warnings` 附加字段**不被拒**断言——AD-7 的回归锁）。
- **验收**：caption-rule 实跑输出 `validate.py --against` PASS；附加字段断言绿。
- **验证**：unittest + CLI。
- **依赖**：任务 7（有输出可验）。**文件**：`scripts/validate.py`、`tests/test_validate.py`。

### 任务 10：metrics.py 受控复制 + 图像档 + 答案钥（M；提交序在 9 后，AD-6）
- **描述**：`scripts/metrics.py` 受控复制 + AD-2 薄层（文本桶条件化、baseline 默认 caption-rule，头注枚举）；`tests/fixtures/metrics_dataset.jsonl`（≈10–12 条 image eligible：safe/unsafe、多类别真值、divergence 用例、unsafe 缺类别审计、未知类别值审计）+ `metrics_predictions.jsonl`（fixture-guard-a/b，AD-5：a 带 confidence 与 error 行、b 仿 caption-rule 无 confidence）+ **`tests/fixtures/image_expected.json` 手算答案钥**（两路独立核算一致后入库，`_notes` 记录推导；结构对齐 metrics.json）；`tests/test_metrics.py`（head_binary 双口径逐位、AUROC null 注记、by-category 含 divergence、comparison Δ 与 error 行 ao/fw 分叉、adversarial 全 unknown 片如实计数、文本桶缺席断言）。
- **验收**：spec §6-C 第一勾全绿；答案钥逐位命中；无文本桶键。
- **验证**：unittest + fixtures CLI 全链路 exit 0。
- **依赖**：任务 5（路由）；与 7/8 无文件交集可并行实现、**提交序在 9 后**。**文件**：`scripts/metrics.py`、`tests/fixtures/metrics_{dataset,predictions}.jsonl`、`tests/fixtures/image_expected.json`、`tests/test_metrics.py`。

### 任务 11：黄金样例 + 重模块断言 + SKILL.md/README（M）
- **描述**：`examples/input.sample.jsonl`（≈6 条：正常良性/正常标 unsafe（真值标注即可，图仍是合成良图）/url-only/多图/缺 caption/坏图——一份样例同时演示 happy path 与全部 error 形态）+ `examples/output.sample.jsonl`（caption-rule 实跑核对后固化）+ `examples/metrics.sample.json` 黄金（实跑→人工核对→锁定，`TestMetricsSampleGolden` 逐字段）；**`tests/test_core_isolation.py`**：跑通 main→validate→metrics 进程内入口后断言 `sys.modules` 不含 torch/transformers/PIL/bitsandbytes（spec §6-A）；`SKILL.md` 重写（≤250 行：frontmatter 图像触发词 + 与 guard-llama-guard 互斥的 negative triggers、零安装 quickstart 三步、guards 表、执行步骤、失败处理、sanity 表、troubleshooting、Safety/校准/caption-rule 替身注记；**feat 分支注记清除**，R9）；`README.md` 更新（人读三步 + guards 表 + 契约链接）。
- **验收**：spec §6-A 两勾全绿；黄金锁定；SKILL.md 指针全有效。
- **验证**：unittest 全绿 + 行数统计 + 指针逐一打开。
- **依赖**：任务 7,8,9,10。**文件**：`examples/*`、`tests/test_core_isolation.py`、`SKILL.md`、`README.md`。

### ☑ Checkpoint C1（M3 唯一硬门的技术半）
- **成功条件**：spec §6-A/B/C 全勾 + §6-D 的离线部分就绪条件确认；unittest 全绿且核心链路零重模块 import（test_core_isolation 为证）；fixtures/examples CLI 全链路 exit 0。
- **失败处理**：阻塞修复，不进交付。

---

## Phase 2 · Core-Full：ShieldGemma 2（C0b 后；可与 P1 尾部并行实现、提交在 C1 后；C2 软门）

### 任务 12：shieldgemma2.py 适配器 + mock 离线测试（M）
- **描述**：`scripts/guards/shieldgemma2.py`（GuardAdapter；spec §5 全项：延迟 import、4-bit NF4 默认、`--device` cuda/cpu、缺依赖/缺权重 → available()=false + 任务 2 的三种 FIX 文案、3 策略 yes 概率 → `is_unsafe=max≥threshold(0.5)`、超阈映射 M0 §4、全 safe→[]、confidence=max(yes_p) unsafe 方向、`raw_output.policy_scores` 全留、未识别策略 → 不映射 + AD-8 审计计数上报、超时默认 120s 哨兵、异常 → error 行）；注册表加 `shieldgemma2`；`requirements-shieldgemma.txt`（transformers≥4.50/accelerate/bitsandbytes/pillow，版本下限取任务 3 实测）；main.py 接 `unknown_policy_count` 进 run_metadata.warnings；`tests/test_shieldgemma2.py`（mock 形态以任务 4 discovery 实录为准：超阈/欠阈/多策略并发/全 safe 四例 + 未识别策略审计 + 缺依赖 unavailable + 注册表 + threshold 透传；live 类 `skipUnless SHIELDGEMMA2_LIVE=1`）；exit 判例补全（无权重单跑 shieldgemma2 → 1；与 caption-rule 同跑 → 2）。
- **验收**：spec §6-D 四例全绿 + §6-B 的 shieldgemma2 判例补全；离线测试不碰 GPU/网络/权重。
- **验证**：unittest -v（零第三方环境也全绿——延迟 import 保证）。
- **依赖**：C1（提交序）；mock 形态依赖任务 4 实录。**文件**：`scripts/guards/{shieldgemma2,__init__}.py`、`scripts/main.py`（warnings 接线）、`requirements-shieldgemma.txt`、`tests/test_shieldgemma2.py`、`tests/test_main.py`（判例）。

### 任务 13：live sanity + notes 落库（S；GPU + 权重；opt-in）
- **描述**：`SHIELDGEMMA2_LIVE=1` 测试 + CLI 实跑：examples 合成良性图判定（预期 safe，R8 放宽断言路径备用）、M0 样本 2 条按 AD-9 实测、峰值显存/单条延迟/policy 对账（discovery vs 运行时）记录；`references/shieldgemma2-notes.md` 落库（权重来源与 gated 路线、版本四元组、量化口径、policy 原文、显存/延迟实测、校准告诫、R8 实情）；两 guard（caption-rule + shieldgemma2）在 examples 上跑出**首版 comparison 表**（截图素材）。
- **验收**：spec §6-E 前两勾 + policy discovery 勾；comparison 表两行齐。
- **验证**：exit code + RESULT 行 + metrics RESULT: ok guards=2。
- **依赖**：任务 12 + C0b。**文件**：`references/shieldgemma2-notes.md`（+ out_*/ gitignored）。

### ☑ Checkpoint C2（软门）
- **成功条件**：spec §6-E 全勾（升级回归门已在任务 3 预完成，此处只确认未漂移）。
- **失败处理**：权重/显存不可行 → live 档 N/A + 原因，交付退回 caption-rule 单 guard，**不阻塞 C3**。

---

## Phase 3 · Plus（C2 后或并行；逐项可 N/A）

### 任务 14：量化消融 + 阈值扫描（S；GPU）
- **描述**：4-bit vs CPU 高精度在 10–20 张子集（合成 + 可得真图）上：判定翻转数、confidence 漂移、延迟对比；阈值扫描（per-policy yes 概率现成连续分，扫 {0.3,0.5,0.7,0.9}）。结果进 `references/shieldgemma2-notes.md` 消融节（M3 无独立 ablations.md——体量不需要）。
- **验收**：两张数字表 + 各一句结论 + 复现命令；做不到 N/A+原因。
- **验证**：表中数字可由命令重出。
- **依赖**：任务 13。**文件**：`references/shieldgemma2-notes.md`。

### 任务 15：trigger eval 图文互斥档（S；需人工新会话）
- **描述**：`references/trigger-eval.md`：正例（图像安全评测请求 ≥4 条）+ 负例（文本 guard 请求、数据集类请求 ≥6 条，与 `上游/references/trigger-eval.md` 互链互斥）；实测需全新会话人工逐条——与 M2 任务 16 / 甲 #3 合并为同一轮（三方一次测完：甲负例、乙文本正例、乙图像正负例）。
- **验收**：协议与正负例表落库；实测档有数或 N/A（人工依赖）+ 顺延注记。
- **验证**：人工。
- **依赖**：C1（SKILL.md frontmatter 定稿）。**文件**：`references/trigger-eval.md`。

### 任务 16：report 模板图像章节（XS）
- **描述**：`templates/report-section.md`：方法（量化口径/policy 映射）、结果表占位（comparison/按类别 divergence）、Metric Caveats 四条（spec §6-H）、误判案例占位。
- **验收**：占位齐 + 与 M3_summary Caveats 一致。
- **验证**：人工对照。
- **依赖**：C1。**文件**：`templates/report-section.md`。

### 任务 17：真实 UnsafeBench 档（S + 等待；依赖甲 #2'/checker exit 0）
- **描述**：甲 `dataset-unsafebench` 输出（checker exit 0）到位后：200–500 张两 guard 全链路 + `--resume` 分段 + E2E 截图；结果档状态机如实标注（`full_shieldgemma2`/`partial_shieldgemma2_n`/`baseline_only`）；caption/ocr 覆盖率与 `missing_caption_ocr` 比例如实记录（R6）。
- **验收**：spec §6-G 勾或"未到 → 合成+M0 矩阵 + 提交前重跑标记（fallback_only）"。
- **验证**：checker exit 0 前置 + RESULT 行。
- **依赖**：甲数据 + C2（shieldgemma2 行）。**文件**：out_*/（gitignored）+ notes 回填。

---

## Phase 4 · 交付（硬依赖 C0a + C1；软吸收 C2/P3/G）

### 任务 18：文档终稿 + `root/M3_summary.md`（M）
- **描述**：文档 sweep（SKILL.md 指针/行数复核、io-contract 图像版定稿、README 一致性、guard-llama-guard 侧零改动确认——若其 Backlog/L3 表需更新 M3 状态行则 Ask-first，R9）；`references/io-contract.md`（任务 5–10 期间随实现起草，此处定稿）；`root/M3_summary.md`：追溯表（spec §6 A–H × 文件 × 测试 × 状态）、**结果档状态机标注（四态取一）**、N/A 台账（judge-vision 探测否决实录、trigger eval 人工依赖、真数据待甲）、限制/偏差登记（量化口径、R5 若有 API 偏差、R8 实情）、Metric Caveats 四条、Extension Backlog；spec §6 全量 sweep；泄漏自查（`git grep` key/URL/token + 目录查真实图像）；push。
- **验收**：spec §6-H 全勾；C3 判定可下。
- **验证**：sweep 清单逐项 + git grep 零命中。
- **依赖**：C1 + 任务 11–17 各自终态（勾或 N/A）。**文件**：`root/M3_summary.md`、`references/io-contract.md`、文档微调。

### ☑ Checkpoint C3 = M3 技术交付
- **成功条件**：§6-A/B/C/D 全勾（C1）+ §6-H 全勾 + E/F/G 各项勾或 N/A+原因+顺延；M3_summary 完整。
- **失败处理**：未勾项 N/A+原因+顺延入 M3_summary（不删项规则）。

---

## 并行化与执行注记

- **可并行**：任务 1 ∥ 任务 2/3/4（C0a 与 C0b 两路）；任务 5/6 ∥ 任务 2–4；任务 10 与 7/8 文件无交集可并行实现（提交序 AD-6）；任务 14/15/16 互相独立。
- **必须串行**：7→8（同文件）；9→10（提交序）；12 在 C1 后提交；18 收尾。
- **用户人工项**：任务 2 点许可；任务 15 新会话实测；M3 E2E 截图（素材出自任务 13/17）。
- **甲依赖项**：任务 1 的否决窗口；任务 17 的数据。
- **提交纪律**：一事一提交，直推 main（§9-5）；每次提交前跑全量 unittest；涉密自查随手跑。
