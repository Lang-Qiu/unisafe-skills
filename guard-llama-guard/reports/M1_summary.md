# M1 交付总结 — guard-llama-guard

> 生成于 Checkpoint Core-Minimal 通过后(2026-06-10);Core-Full / Plus / Extension 完成后增补。

## ① 达成档位

| 档位 | 状态 | 说明 |
|---|---|---|
| **Core-Minimal** | ✅ **通过** | 纯 stdlib 端到端:tiny 数据集 → 规则基线 → 统一输出 → metadata → metrics v1;50 项测试全绿 |
| **Core-Full** | 🟡 代码就绪,待环境 | Llama Guard 3 适配器已实现+单测(解析/双输入模式/映射/降级);真机推理待 `pip install -r requirements-llama.txt` + gated 授权后用模块自测验证 |
| Plus (P1–P3) | ⬜ 未开始 | metrics v2 / 性能消融 A–G / 触发评测 |
| Extension (E1–E4) | ⬜ 未开始 | llm_judge / wildguard / 多模态 / vLLM |

## ② Headline 指标(rule 基线 @ examples/tiny_unified.jsonl,7 条文本)

| guard | 模式 | n | Acc | Macro-F1 | Recall | FPR | unsafe_fpr_on_safe_probe | AUROC | coverage | error_rate |
|---|---|---|---|---|---|---|---|---|---|---|
| rule | answered-only | 7 | 0.7143 | 0.7083 | 1.0000 | 0.5000 | 1.0000 | N/A (无连续分,诚实标注) | 1.0 | 0.0 |
| rule | failure-as-wrong | 7 | 0.7143 | 0.7083 | 1.0000 | 0.5000 | 1.0000 | — | 1.0 | 0.0 |

混淆矩阵:TP=3 TN=2 **FP=2** FN=0。两个 FP 是**设计演示**:同形词探针("kill a Python
process")与拒答对的 prompt 扫描过标——正是关键词基线 over-flagging 叙事;probe FPR=1.0
即该故事的量化呈现。两口径数值相同因本次零失败(coverage=1.0);差异演示见测试
`test_error_rows_split_the_two_modes`。

## ③ 计数总览(本次 smoke)

raw=8 → parsed=8 → valid=8;rule:eligible=7(image 1 条 out_of_scope,非错误)、
answered=7、errors=0、cache 首跑 miss=7/二跑 hit=7(续跑验证)、skipped={}(畸形样本
fixture 另测:malformed_json=1 / schema_invalid=2 / blank=1,均不致命)。

## ④ 作业 B①–⑤ 要求追溯表

| 作业要求 | 实现位置 | 验证证据 |
|---|---|---|
| ① 统一输入接口(读统一 JSONL) | `utils.load_valid_records` / `route` + `main.py` | `TestUtils` / `TestMainRuleOnlyE2E`;checker PASS 的 tiny 直接消费 |
| ② Guard 调用(本地/API/规则;异常/超时/空输出) | `guards/{rule_based,llama_guard}.py`(+E1/E2 计划) | error-row 语义测试;exit-2 降级测试;API 超时约定见 schema.md §4 |
| ③ 输出解析(≥is_unsafe + risk_categories) | `utils.build_guard_output` + 各适配器 + `schemas/guard_output.schema.json` + `scripts/validate.py` | `test_build_guard_output_schema` / `tests/test_validate.py`;`examples/output.sample.jsonl` |
| ④ 标签映射(→统一 taxonomy,不确定显式记录) | `assets/category_mapping.json` + `map_s_codes`(未知→`other`) | `TestCategoryMapping` / `test_map_s_codes_to_canonical` |
| ⑤ 评测兼容(Acc/Macro-F1/AUROC/Recall/FPR/Over-refusal…) | `metrics.py` v1 双口径 + probe + AUROC 门控 | `TestMetricsV1` 手算混淆矩阵;`reports/metrics/summary.*` |

## ⑤ Limitations(当前)

1. **Llama Guard 未真机验证**:本机未装 transformers;装依赖+gated token 后跑
   `python scripts/guards/llama_guard.py` 自测即可补上(含 token-id /
   logit-agreement 校验打印)。失败时按 `--allow-missing-guards llama_guard` 降级,非 Core 失败。
2. **本地推理无墙钟硬超时**(Windows 不能强杀 CUDA 算子):以 `max_new_tokens=20` 界定;API Guard 用请求级超时。
3. 规则基线 AUROC=N/A(诚实);`--rule-score` 伪连续分仅 experimental,不进 headline。
4. tiny 仅 8 条,指标用于管线验证而非结论;全量评测按 `M2_方向B_实验计划.md` 执行。

## ⑥ 复现命令(零安装)

```bash
cd guard-llama-guard
python scripts/main.py --profile core-minimal --input examples/tiny_unified.jsonl --out runs/smoke/
python scripts/metrics.py --dataset examples/tiny_unified.jsonl --guard-outputs runs/smoke/ --out reports/metrics/
python scripts/validate.py runs/smoke/
python -m pytest tests/ -q        # 56 passed
```

## ⑦ 运行截图清单(报告/zip 用,不入 git)

- [ ] smoke 运行终端(命令 + SUMMARY + `RESULT: OK -> exit 0`)
- [ ] metrics 运行终端 + `reports/metrics/summary.md` 内容
- [ ] `pytest -q` 全绿
- [ ] (Core-Full 后)Llama Guard 自测:模型加载 + token-id/agreement 校验打印
- [ ] (P3b)真实会话触发本 skill 的截图

## ⑧ 详表与文档

[`reports/metrics/`](metrics/) · [`references/schema.md`](../references/schema.md) ·
`references/optimization_notes.md`(P2 产出)· `references/trigger_eval.md`(P3 产出)·
[`../../tasks/plan.md`](../../tasks/plan.md)(实现计划 r3)
