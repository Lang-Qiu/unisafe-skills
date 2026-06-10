# 性能消融 A–G（任务 17）

> 全局规则：七节只标记不删除；未就绪项 = N/A + 原因 + 顺延里程碑。
> 环境：Windows 11 / Python 3.11.5（core）与 conda `pytorch_dl`（py3.9.25 + torch 2.5.1+cu121, RTX 4060 Laptop 8GB）。
> 日期：2026-06-11。复现命令随各节给出；E/F/G 的脚本化复现见各节"命令"。

## A. prompt/template ×2（官方 chat template vs 简化模板）

**N/A（依赖未就绪 → 顺延 M2 或 C2 后补）**：Llama Guard 3-1B gated 审批中
（`llama-guard-notes.md` 有 403 实录）。适配器已带 fallback 模板路径
（typed-content → plain-string），授权到位后跑两版对比 Recall/FPR。

## B. score extraction（token prob vs 文本正则）对 AUROC 的影响

**N/A（同 A）**。方法已实现：token 双向归一概率为主（`llama-guard-notes.md` spike ①），
文本解析为兜底（该路径 confidence=null）。授权后对比两法 AUROC 差值。

## C. threshold sweep（confidence 0.3/0.5/0.7 → FPR/Recall 曲线)

**N/A（双数据源均未就绪 → 顺延 M2）**：llama-guard 等审批；OpenAI Moderation 实测档
N/A（用户代理端点无 `/moderations`，404 实测）。rule 基线无连续分，无法做阈值扫描。

## D. batch size {1,4,8,16} 吞吐/延迟曲线

**N/A（依赖 A 同源 → 顺延）**。`predict_batch` 真批路径与 `--batch-size` 已接通，
授权后直接扫。

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
