# Best-known configuration — guard-llama-guard（M3.6 收口）

> 本轮（M3.6 E1）之后的推荐配置。阈值来自 `calibration-notes.md` 的生产分 sweep；版本=主 env（M3.5 W1 自动写入 `run_metadata.env`）。

```yaml
guard-llama-guard:
  default_threshold: 0.55          # M3.6 E1 max_macro_f1（references/calibration-notes.md）；
                                   # --threshold 0.5 构造上 argmax-equivalent，但与已存 native
                                   # 判定实测差 ~20/1911 head + 2/250 探针（文本解析 vs 概率切点）；
                                   # post-M3.6 无 CLI 路径回到纯 native argmax（None→0.55）
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

**真实效果（M3.6 E1，shipped 0.55 vs 真实旧行为 = native argmax；统一口径见 `M3.6_summary.md` §2.0）**：
Macro-F1 0.7921→**0.7928**（≈持平）、FPR 0.0632→**0.0559**（约 −12%）、Recall 0.6604→0.6377（约 −3.4%）、
over-refusal（XSTest 250）6.4%→**6.0%**。AUROC 0.888（阈值无关，不变）。
**口径提示**：0.55 是 precision-favoring 操作点（降 FPR/过拒，非 Macro-F1 杠杆）；§2.1/flip 报的 "0.779→0.793" 是相对
`confidence>=0.50` 中间基线（0.7788）所测，该基线略低于 native argmax 故放大了增益。
