# I/O Contract — guard-shieldgemma2（图像版）

> 本文件是 `M3_SPEC.md` §4 的库内落地版，与 `M0_接口约定.md` §3/§5 及 `待甲确认.md` #5（图像路径契约，2026-06-12 默认接受制）零冲突。
> 单条输出记录的机器可读约束：[`../schemas/guard_output.schema.json`](../schemas/guard_output.schema.json)（与 guard-llama-guard **逐字节一致**，同源断言测试锁定）。
> 指标公式与双口径定义：完全继承 [`../../guard-llama-guard/references/metrics-definitions.md`](../../guard-llama-guard/references/metrics-definitions.md) v1+v2（本 skill 零新公式）。

## 1. 输入

| 项 | 约定 |
|---|---|
| 形态 | 单个 `.jsonl` 文件或目录（目录则发现 `*.jsonl`，跳过裸对象 `.json`） |
| 前置 | 数据应已通过 dataset-format-checker（exit 0）；本 skill 只防御性读取 |
| 消费字段 | `id`；`task_type`；`modality`；`content.images[]`（`path`/`url`/`caption`/`ocr`）。真值仅 `metrics.py` 读取：`label.is_unsafe`、`label.canonical_categories`、`risk_metadata.adversarial`（图像数据通常缺失 → unknown 片）、`risk_metadata.over_refusal_probe`（图像数据无 → 探针桶恒 n=0） |
| M3 范围 | `task_type == image_safety` 且 `modality == ["image"]`；其余 → out-of-scope skip |
| Read-only | 绝不修改输入；**绝不下载远端图片** |

## 2. eligible 定义（覆盖率与指标的统一分母）

一条记录 eligible 当且仅当同时满足（方案 B，M3_SPEC §4.1）：

1. `task_type == image_safety`；
2. `modality == ["image"]`；
3. `content.images` 非空且**首图** `path` 或 `url` 至少一个非空。

不满足 1/2 → `skipped.out_of_scope`；满足 1/2 但 3 缺（path 与 url 均空）→ `skipped.missing_content`。两类 skip **不写输出行**。url-only（path 空）**算 eligible**，按 §4 记录级 error 写行。

守恒式（每个 completed guard 的 predictions 文件）：

```
行数 = eligible = total − skipped.out_of_scope − skipped.missing_content
```

`validate.py --against <input>` 以本节 eligible 集合做双向 id 核对（无缺失、无多余、无重复）。

## 3. 路径解析与多图（= 待甲确认.md #5）

- `path` 为相对路径 → 以 **unified JSONL 文件所在目录**为基准解析；绝对路径原样用。
- 多图记录只评**首图**；三处固定落点：`run_metadata.warnings.multi_image_records` 计数、该行 `prediction.warnings` 含 `"multi_image_first_only"`、`raw_output.image_index = 0`。`warnings` 键只在非空时出现。

## 4. 错误三分法（图像增量；全局契约继承 M1）

| 级别 | 触发 | 处理 | exit |
|---|---|---|---|
| Fatal | 输入不存在 / 0 条可解析 / 输出不可写 / `--guards` 全未知 | 终止 | 1 |
| Guard 级失败 | shieldgemma2 缺依赖/缺权重/gated 401/加载失败 | 跳过该 guard + `FIX:` 提示 | 全失败 1；部分 2 |
| **记录级 error（图像四类）** | `image_url_not_supported`（url-only，不下载）；`image_not_found`；`image_decode_error`（L0 = stdlib magic bytes：PNG/JPEG/WebP/GIF/BMP 头；适配器像素级解码失败同名）；`missing_caption_ocr`（仅 caption-rule：caption/ocr 全空，**不默认 safe**）。前三类由 main.py 预检统一产生（guard 无关，数据缺口对全部 guard 可见）；超时/异常照 M1 规则 | 照常写行、`is_unsafe=null`、计入 `counts.errors`、进双口径 | 不影响 |
| Out-of-scope skip | §2 条件 1/2 不满足；path+url 均空 | 不写行，计数 | 不影响 |

## 5. run_metadata 增量

与 guard-llama-guard 同构（M1 io-contract §6），增量字段：`config.threshold`（shieldgemma2 判限回显）；`config.timeout_s_effective`（shieldgemma2 默认 120s）；`warnings.multi_image_records` 与 `warnings.unknown_policy_count`（仅非空时出现）。

## 6. Exit Code Contract

与 guard-llama-guard `references/io-contract.md` §7 **一字不差**（全局权威副本在彼处）。本 skill 判例：

| 场景 | 判定 | exit |
|---|---|---|
| `--guards shieldgemma2` 且缺依赖/权重 | 唯一 guard 失败 = 全部失败 | **1** |
| `--guards caption-rule,shieldgemma2` 且 shieldgemma2 失败 | 部分成功 | **2** |
| smoke（`--guards caption-rule`） | 零依赖，不受权重/网络影响 | **0** |

## 7. 对后续的可用性保证

`id` join 键、输出 schema、metrics 分组逻辑与文本侧完全共用——跨 skill 的 guard×bucket 对比只需把两边 predictions 喂给任一侧 metrics.py（task_type 路由天然分桶）。
