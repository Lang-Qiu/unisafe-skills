# Best-known configuration — guard-llama-guard（M3.6 收口）

> 本轮（M3.6 E1）之后的推荐配置。阈值来自 `calibration-notes.md` 的生产分 sweep；版本=主 env（M3.5 W1 自动写入 `run_metadata.env`）。

```yaml
guard-llama-guard:
  default_threshold: 0.55          # M3.6 E1 max_macro_f1（references/calibration-notes.md）；
                                   # natively argmax≈0.5；--threshold 0.5 复现旧 argmax 行为
  verdict_mechanism: confidence >= threshold (fallback argmax when confidence is None)
  model_id: meta-llama/Llama-Guard-3-1B   # 非门镜像: alpindale/Llama-Guard-3-1B
  model_revision: <auto-recorded in run_metadata.env.model_revision>  # M3.5 W1
  transformers: 4.51.3
  torch: 2.5.1+cu121
  llm_judge:                       # 可选第三 guard（API，env-only 凭证）
    model: mimo-v2.5-pro
    judge_concurrency: 4           # M3.5 W4（默认 1=串行；4 实测 3.86x 提速）
  known_limits:
    - threshold tuned on WildGuardMix test split / native scores — re-calibrate on new distribution
    - adversarial robustness remains limited (judge AUROC 0.976 -> 0.633; llama 0.919 -> 0.831)
    - E1 is post-hoc threshold calibration — does not change the model
```

**真实效果（M3.6 E1，新默认 0.55 vs 旧 0.5）**：Macro-F1 0.779→**0.793**、FPR 0.075→**0.056**、Recall 0.664→0.638（32 FP removed vs 7 FN introduced）。AUROC 0.888（阈值无关，不变）。
