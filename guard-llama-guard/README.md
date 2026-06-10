# guard-llama-guard

方向 B Guard Skill:在**统一安全 JSONL**(`dataset-*` skill 的输出格式)上运行多个文本安全 Guard,
输出统一判断记录 + 评测指标。**Core-Minimal 纯 stdlib、零下载、零密钥即可端到端跑通**;
Llama Guard 3 为 Core-Full;LLM-judge / WildGuard 为扩展。完整 I/O 契约自包含于
[`references/schema.md`](references/schema.md),Agent 操作指引见 [`SKILL.md`](SKILL.md)。

## Guard 方法来源

| Guard | 档位 | 来源 |
|---|---|---|
| `rule` 规则关键词基线 | Core-Minimal | 本仓库实现(stdlib);词表见 [`assets/category_mapping.json`](assets/category_mapping.json) |
| `llama_guard` Llama Guard 3-1B | Core-Full | [模型卡](https://huggingface.co/meta-llama/Llama-Guard-3-1B) · [论文 (Inan et al., 2023)](https://arxiv.org/abs/2312.06674) · MLCommons S1–S14 危害分类 |
| `llm_judge` LLM-as-judge | Extension | OpenAI 兼容 API,结构化 JSON 判别 + 注入防护(`LLM_API_KEY`/`LLM_BASE_URL`/`LLM_MODEL`) |
| `wildguard` WildGuard 7B | Extension | [模型卡](https://huggingface.co/allenai/wildguard) · [论文 (Han et al., 2024)](https://arxiv.org/abs/2406.18495) · 原生拒答检测 |

输入数据集来源(由方向 A 的 dataset skill 产出):WildGuardMix([HF](https://huggingface.co/datasets/allenai/wildguardmix), odc-by)、
XSTest([HF](https://huggingface.co/datasets/walledai/XSTest))等;本仓库自带
`examples/tiny_unified.jsonl`(8 条手写样本,已过 `dataset-format-checker`)供零依赖联调。

## 安装(分层依赖)

```bash
pip install -r requirements.txt              # = requirements-core.txt,仅 pytest;Core-Minimal 运行时纯 stdlib
pip install -r requirements-llama.txt        # + Llama Guard 3(torch/transformers/accelerate)→ Core-Full
pip install -r requirements-llm-judge.txt    # + LLM-as-judge(openai 兼容 SDK)
pip install -r requirements-wildguard.txt    # + WildGuard 7B
# pip install -r requirements-vllm.txt       # 可选加速后端(非默认依赖;Windows 需 WSL)
```

> **Windows + CUDA 装 torch 注意**:默认 PyPI 会装成 CPU 轮子。请用官方 index(按本机 CUDA 版本选):
> `pip install "torch>=2.2" --index-url https://download.pytorch.org/whl/cu121`
>
> 复现精确版本:每次运行的 `metadata.json` → `versions.packages` 记录了当时的全部关键包版本。

## 运行(零安装,从 skill 目录)

```bash
# Core-Minimal(纯 stdlib,无下载无密钥):
python scripts/main.py --profile core-minimal \
  --input examples/tiny_unified.jsonl --out runs/smoke/

# Core-Full(需 GPU + gated 授权,见下文认证):
python scripts/main.py --profile core-full \
  --input examples/tiny_unified.jsonl --out runs/full/ --hf-token %HF_TOKEN%

# 指标(真值来自数据集,预测来自 guard 输出,按 id join):
python scripts/metrics.py --dataset examples/tiny_unified.jsonl \
  --guard-outputs runs/smoke/ --out reports/metrics/

# 校验 Guard 输出是否符合 schemas/guard_output.schema.json:
python scripts/validate.py runs/smoke/

# 测试:
python -m pytest tests/ -q
```

环境变量模板见 [`templates/env.template`](templates/env.template)(HF_TOKEN / 镜像 / LLM-judge)。

常用参数:`--guards rule,llama_guard`(显式点名 = 全部 required)·
`--allow-missing-guards llama_guard`(降为 optional:加载失败→跳过记录,不报 exit 2)·
`--task prompt_only_safety` · `--max-samples N` · `--seed 42` ·
`--rule-score`(规则基线实验性伪连续分)· `--no-cache` / `--prediction-cache-dir`(预测缓存/续跑)。

## Exit code 约定(判断成败看它 + metadata.json,别用管道截断)

- **exit 0**:全部 required guard 成功(optional/allow-missing 缺失会被记录但不影响)。
- **exit 2**:至少一个 **required** guard 加载/整体运行失败(stderr 有可复制的 FIX 提示)。
- **exit 3**:运行前致命错误——输入不存在/非 JSONL、参数非法、输出目录不可建、**0 条有效记录**。
- 单条记录的问题**永不致命**:坏行/缺字段 → `metadata.skipped`(blank/malformed_json/schema_invalid);
  Guard 对某条预测失败 → 该行仍写入(`is_unsafe=null` + `error`),计入 errors/coverage。
- Guard 能力外的记录(如规则文本 Guard 遇到图像)→ `out_of_scope`,不是错误。

## Gated 模型认证(Llama Guard / WildGuard)

1. 网页端到模型页点 **Agree and access repository**(meta-llama/Llama-Guard-3-1B、allenai/wildguard)。
2. 本地认证任选:`hf auth login` / `huggingface-cli login` / `set HF_TOKEN=hf_xxx`(或 `--hf-token`)。
3. **gated 仓库不能走 hf-mirror 镜像**(镜像只 serve 公开仓库)——须直连 huggingface.co + token;
   下载后用 `--cache-dir` 复用。非 gated 资源才可 `set HF_ENDPOINT=https://hf-mirror.com`。

**失败降级(这不是 Core 失败)**:无授权/无显存时,
`--profile core-full --allow-missing-guards llama_guard` → 自动退回 Core-Minimal(仅规则基线),
exit 0,`metadata.skipped_guards` 记录原因 → 写入报告 limitations。

## 指标口径(防失败样本剔除导致虚高)

每个 Guard × 任务桶**同时报两套**(详见 `references/schema.md` §6):

- **answered-only**(分类能力,分母=answered):Acc / Macro-F1 / Recall / FPR /
  `unsafe_fpr_on_safe_probe` / AUROC(需非 experimental 连续分,否则诚实 N/A——规则基线即 N/A)。
- **failure-as-wrong**(系统可靠性,分母=eligible):每条失败记录按判错计——
  这是系统级可靠性指标,不是纯分类器指标。
- 并报 `coverage` / `error_rate`;拒答类指标(over/under-refusal)仅对有原生拒答能力的
  Guard(WildGuard/LLM-judge)计算,规则与 Llama Guard 不冒称做拒答检测。

## 目录结构(对齐作业 Skill 模板)

```
guard-llama-guard/
├── SKILL.md                       # 必需:元信息 + 主执行说明(给 agent)
├── README.md                      # 本文件(给人)
├── scripts/                       # 确定性脚本
│   ├── main.py                    #   运行 Guard(profile / exit 0·2·3 / 缓存续跑)
│   ├── metrics.py                 #   指标(双口径 + probe + AUROC 门控)
│   ├── validate.py                #   校验 Guard 输出 JSONL(对 schemas/)
│   ├── utils.py                   #   加载/校验/路由/缓存/metadata
│   └── guards/ base.py  rule_based.py  llama_guard.py  (llm_judge / wildguard 为扩展)
├── references/ INDEX.md  schema.md  # 自包含 I/O 契约(字段/真值选择/错误分级/指标口径)
├── schemas/ guard_output.schema.json # Guard 输出的 JSON Schema
├── templates/ env.template          # 环境变量模板(HF_TOKEN / LLM-judge)
├── examples/ tiny_unified.jsonl  input.sample.jsonl  output.sample.jsonl
│             # tiny/input 为数据集 schema(可过 dataset-format-checker);
│             # output.sample.jsonl 是 Guard 输出 schema(用 scripts/validate.py 校验)
├── tests/ test_basic.py  test_validate.py  fixtures/tiny_malformed.jsonl
├── assets/ category_mapping.json    # S1-S14/OpenAI -> 22 类 + 规则词表 + taxonomy_version
├── requirements*.txt                # 分层依赖(复现用,见上文安装)
└── reports/ metrics/  M1_summary.md # 交付证据
```

## 安全声明

输入基准可能含有害文本(安全评测的固有属性),仅用于防御性安全研究与 Guard 评测;
`examples/` 中不安全内容一律用占位符。遵守各模型/数据集 license(Meta Llama license、AI2 条款、odc-by)。
