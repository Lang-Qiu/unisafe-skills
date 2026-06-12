# 性能消融 A–G（M1 任务 17 / M2 任务 13–15）

> 全局规则：七节只标记不删除；未就绪项 = N/A + 原因 + 顺延里程碑。
> 环境：Windows 11 / Python 3.11.5（core）与 conda `pytorch_dl`（py3.9.25 + torch 2.5.1+cu121, RTX 4060 Laptop 8GB）。
> 日期：E/F/G 实测 2026-06-11（M1）；A/B/C/D 实测 2026-06-12（M2 任务 13–15，镜像权重
> `alpindale/Llama-Guard-3-1B`，数据 = `examples/input.sample.jsonl` 5 条 eligible——
> **样本量极小，全部结论仅作机制验证与趋势参考，定论以全量数据复测为准**）。

## A. prompt/template ×2（官方 typed-content 模板 vs plain-string 变体）——实测 ✅（2026-06-12）

（M1 曾 N/A：gated 审批中；M2 以镜像权重实测。）方法：一次性脚本对同一 5 条记录
分别用 typed-content（适配器现行路径）与 plain-string 两种会话形式渲染并推理。

| 度量 | typed-content（现行） | plain-string 变体 |
|---|---|---|
| 渲染正确性 | 完整（政策头 + `User: <prompt>`） | **会话块为空**（diff 实测：`User: hello` 整行缺失——该模板的会话循环只认 typed content） |
| 判定 | 4/5 头部正确（M1 已知基线） | **3/5 判定翻转**，与输入内容无关 |
| confidence | 双峰（unsafe 0.84–0.995 / safe ≤0.0007 / 探针 0.71） | **坍缩至 0.4688/0.5622**（空对话 → 同一 logits，仅 padding 差） |

**结论（报告可直接引用）**：模板选择不是格式细节而是**正确性开关**——plain-string
变体在该 tokenizer 模板下渲染出空会话，模型在"判空"，输出近乎随机。适配器先走
typed、仅在 typed 抛异常时才落 plain 的设计因此是安全的（本模板下 typed 不抛异常，
坏路径永不触发）；fallback 仅服务于"模板只认 plain 字符串"的其他 tokenizer 版本。

## B. score extraction（token prob vs 文本正则）对 AUROC 的影响——实测 ✅（2026-06-12）

- token 双向归一概率（现行）：5 条样本 AUROC = **1.00**（正类 conf 0.8355/0.9954 全部
  高于负类最大值 0.7058）；探针 0.7058 是唯一落在双峰之间的样本。
- 文本正则路径：verdict 本就来自文本解析（两法判定恒等 5/5），但该路径**无连续分**
  （confidence=null）→ AUROC = null（与 rule 基线同一注记机制）。
- **结论**："差值"在机制上不存在——token 概率不是替代判定，而是**唯一的连续分来源**；
  丢掉它等于放弃 AUROC 与阈值可调性（见 C）。

## C. threshold sweep（confidence 0.3/0.5/0.7 → FPR/Recall）——单源实测 ✅（2026-06-12，llama）

数据：D 节 bs=4 跑的 5 条预测 × 样本真值（2 unsafe / 3 safe 含 1 探针）。

| threshold | Recall | FPR |
|---|---|---|
| 0.3 | 2/2 = 1.00 | 1/3 = 0.333 |
| 0.5 | 2/2 = 1.00 | 1/3 = 0.333 |
| 0.7 | 2/2 = 1.00 | 1/3 = 0.333 |
| **0.75** | 2/2 = 1.00 | **0/3 = 0.000** |

**结论**：confidence 分布强双峰（≤0.0007 与 ≥0.84），0.3–0.7 整段无差别；唯一的
中间质量是 XSTest 探针（0.7058）——**阈值提到 0.75 即可在不丢 Recall 的前提下消掉
探针误报**。n=5 不具统计意义，但"探针落在双峰之间、阈值可单独切它"是机制级发现。

**第二源（llm-judge，2026-06-12 C2 后补测）**：fallback 数据 10 条（4 unsafe / 6 safe），
unsafe 方向分（`llm-judge-notes.md` 的方向映射修复后）：

| threshold | Recall | FPR |
|---|---|---|
| 0.3 / 0.5 / 0.7（三档全同） | 4/4 = 1.00 | 1/6 = 0.167 |

judge 方向分同样强双峰（safe 侧 0.00–0.05 / unsafe 侧 0.90–0.95），但**误报形状与
llama 相反**：judge 唯一的 FP 是 0.9+ 的高置信误判，任何阈值都切不掉；llama 的误报
（探针）落在双峰之间，阈值可单独切除。结论：阈值扫描对 llama 是可用的运营旋钮，
对 judge 则几乎无作用——其自报分是"裁决把握"而非风险强度，校准告诫再次得到实证
（非校准来源详见 `llm-judge-notes.md`）。

## D. batch size {1,4,8,16} 吞吐/延迟曲线——实测 ✅（2026-06-12，GPU bf16）

命令：`foreach bs: main.py --input examples/input.sample.jsonl --guards llama-guard
--model-id alpindale/Llama-Guard-3-1B --batch-size <bs> --device cuda`（5 条/轮）。

| batch | duration_s（含加载） | mean latency ms/条 | 判定 vs bs=1 | conf 漂移 vs bs=1 |
|---|---|---|---|---|
| 1 | 17.96 | 249.7 | — | — |
| 4 | 12.57 | 157.8 | 5/5 一致 | ≤0.0179 |
| 8 | 12.06 | 128.2 | 5/5 一致 | ≤0.0179 |
| 16 | 11.89 | 124.6 | 5/5 一致 | ≤0.0179 |

**结论**：bs 1→8 单条延迟降约 2×，8→16 已饱和（5 条样本单 chunk）；判定全批次一致，
conf 漂移 0.0179 与 M1 记录的 ≤0.018（`llama-guard-notes.md` 整合结果节）吻合——
引用该来源，本轮复测未见矛盾。8GB 卡上 `--batch-size 8` 是甜点位。

## E. resume / idempotence（实测 ✅）

合成 2,000 条 text 记录（examples 样本循环改 id），rule guard：

| 场景 | duration_s | resume_hits / misses / hit_rate |
|---|---|---|
| 冷跑（无 --resume） | 0.152 | 0 / 2000 / 0.0 |
| --resume 全命中重跑 | **0.042（3.6×）** | 2000 / 0 / 1.0 |
| --resume 第二次（幂等性） | 0.041 | 2000 / 0 / 1.0 |
| 截掉后 500 行再 --resume | 0.076 | 1500 / 500 / 0.75 |

- **幂等性**：冷跑、resume×2 后 predictions 文件 SHA-256 三次完全一致。
- **断点恢复**：截断后 resume 只补 500 条，行数恢复 2000 = eligible（守恒式成立）。
- 数据源：`run_metadata.json` 的 `resume_hits/resume_misses/resume_hit_rate`（任务 7 字段）。
- 命令：`main.py --input <synth.jsonl> --output-dir <out> --guards rule [--resume]`。
- 注：rule 基线单条耗时极低，时间差在重 guard（llama）上会显著放大；hit/miss 计数与
  幂等性结论与 guard 无关。

## F. robust parsing（畸形输入错误恢复，实测 ✅）

在 6 条好记录间注入 4 条坏行（截断 JSON ×2、非对象 JSON ×1、空行 ×1）：

- exit 0；3 条坏行逐行告警（`file:lineno` 定位），空行静默跳过；
- 好记录无损：`counts: total=6 eligible=5 out_of_scope=1`，`RESULT: ok predicted=5 errors=0 skipped=1`；
- `run_metadata.input.n_unparsable = 3` 如实记录；
- 同一坏文件做 `validate --against --metadata` → PASS（eligible 推导与 main 的坏行跳过逻辑一致）。

## G. dependency footprint（stdlib core vs 全量安装，实测 ✅）

| 度量 | stdlib core | full（torch env） |
|---|---|---|
| `main.py --help` 启动（3 次中位） | 0.120 s | 0.123 s |
| 裸 `import torch` | — | 2.64 s |
| 裸 `import transformers` | — | 3.51 s |
| 第三方磁盘占用 | **0.00 GB**（pip freeze 实证零安装） | torch 4.57 GB + transformers 0.08 GB |

**结论（可直接进报告"分析"章节）**：懒 import 设计让两环境的 CLI 启动时间几乎相同
（0.120 vs 0.123 s）——torch 只在显式请求 `llama-guard` 时才付出 2.6 s 导入与 4.6 GB
安装成本；Core-Minimal 闭环零第三方依赖即可复现全部验收路径。
