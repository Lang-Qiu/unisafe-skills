# 复现核对 — 交付前验证记录（pre-M4）

> 日期：2026-06-16。范围：交付前可复现性核对（section 3a 全套件重跑 + 3b 干净 clone 离线全链 +
> 锚点覆盖自检）。本文件给 M4 报告直接引用，并**如实标注哪些能复现、哪些不能**。

## 0. 运行环境（主 env）

- Python：`E:/LQiu/conda_envs/pytorch_dl/python.exe`（3.9.x）；torch 2.5.1+cu121 / transformers 4.51.3 / bnb 0.48.2。
- **测试框架 = `unittest`（`unittest.TestCase`），不依赖 pytest**——用 `python -m unittest` 即可（`.pyc` 为 cpython-39，即本主 env）。
- Guard 核心循环纯 stdlib（Python ≥3.9，无安装、无网络）；模型/量化依赖仅在跑真模型时需要。

## 1. 全套件重跑（3a）

```bash
# 从各 skill 目录
<pytorch_dl-python> -m unittest discover -s tests -p "test_*.py"
```

| 套件 | 结果（2026-06-16） |
|---|---|
| `guard-llama-guard` | **Ran 105 — OK**（skipped=2） |
| `guard-shieldgemma2` | **Ran 110 — OK**（skipped=2） |

- 2 个 skip = LIVE-gated opt-in（如 `SHIELDGEMMA2_LIVE=1` 才跑的方差 smoke）；默认跳过，非失败。
- 无回归，当前主线为 `guard-llama-guard` 105 / `guard-shieldgemma2` 110。

## 2. 干净 clone 离线全链复现（3b）

从**已推送的提交**（HEAD `95250ea`）`git clone` 到临时目录，仅用本主 env，**不联网、不加载模型**：

```bash
git clone -q <repo-or-origin> /tmp/freshclone           # gitignored 真数据/reports 不进 clone
# 1) 套件在干净 checkout 复现
( cd guard-llama-guard  && <py> -m unittest discover -s tests -p "test_*.py" )   # 105 OK (skip 2)
( cd guard-shieldgemma2 && <py> -m unittest discover -s tests -p "test_*.py" )   # 110 OK (skip 2)
# 2) rule-only 离线预测（纯 stdlib，无模型无网络）
<py> scripts/main.py --input examples/input.sample.jsonl --guards rule \
      --output-dir /tmp/out_smoke --device cpu
#   -> counts: total=6 eligible=5 out_of_scope=1 ; RESULT: ok predicted=5 errors=0 skipped=1
# 3) 评分闭合全链（预测 -> 指标）
<py> scripts/metrics.py --predictions /tmp/out_smoke/predictions/rule.predictions.jsonl \
      --dataset examples/input.sample.jsonl --output-dir /tmp/out_smoke/metrics
#   -> wrote metrics.json + metrics.md ; RESULT: ok guards=1 joined=5
```

Dataset skill 的离线层也可复现（不联网、不读真数据）：

```bash
( cd dataset-wildguardmix && <py> -m unittest discover -s tests -p "test_*.py" )  # 5 OK
( cd dataset-unsafebench  && <py> -m unittest discover -s tests -p "test_*.py" )  # 4 OK
<py> .agents/skills/dataset-format-checker/scripts/check_dataset_format.py dataset-wildguardmix/examples/wildguardmix_unified_sample.jsonl
<py> .agents/skills/dataset-format-checker/scripts/check_dataset_format.py dataset-unsafebench/examples/unsafebench_output_sample.jsonl
# both -> RESULT: PASS
```

**结论**：干净 clone 即可复现 ① 四个 skill 的离线单测、② `rule` guard 端到端「预测 → 评分」离线全链、③ 两个 Dataset 样例的 checker PASS（fixture/example 级）。

## 3. 锚点覆盖自检（trigger-eval 佐证，**非真触发结果**）

- 工具：`reports/calibration/_anchor_coverage.py`（gitignored）；从两侧 `references/trigger-eval.md`
  探针 + 各 `SKILL.md` `description` 锚点做**关键词代理**判定。
- 结果（2026-06-16）：llama-guard 正例 **9/10** / 负例 **6/6**；shieldgemma2 正例 **6/6** / 负例 **7/7**；
  0 代理误触发。唯一代理风险点 = llama P6 问句无评测动词（与真测 P8 盲点不同，印证代理≠真路由）。
- **不替代人工触发测**：真触发的 after 行仍须在全新会话人工跑（trigger-eval §5 / §4，非交付门）。

## 4. 从干净 clone **不能**复现的部分（如实定位）

| 不可复现项 | 原因 | 如何再生 |
|---|---|---|
| 真数据指标（`全量标注结果/`） | 数据集与标注结果 **gitignore，仅在盘上**；clone 里不存在 | 用 `dataset-*` skills 重建统一数据集后重跑 guard（需 GPU + HF cache） |
| ShieldGemma 2 / Llama Guard 真模型推理 | 权重不入库（镜像 HF repo，多 GB） | 需 HF cache（`Nozim6690/...` rev `548e04f` / `alpindale/Llama-Guard-3-1B`）+ CUDA |
| 逐例 flip / over-refusal 复算 | 落 gitignored `reports/`，依赖盘上预测档 | `reports/calibration/_*.py` + `全量标注结果/.../predictions/`（均在盘） |

→ M4 报告须写明：**committed 仓库可离线复现到 fixture/单测/rule 级**；**真数据级数字的复现需 GPU + HF + 真数据集**（设计如此：避免把大数据/权重/真图入库）。
