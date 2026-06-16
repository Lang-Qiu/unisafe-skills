# Best-known configuration — guard-shieldgemma2（M3.6 收口）

> 本轮（M3.6 E1）之后的推荐配置。阈值来自 `calibration-notes.md` 的 **int8 生产分** sweep；版本=主 env（M3.5 W1 自动写入 `run_metadata.env`）。

```yaml
guard-shieldgemma2:
  default_threshold: 0.30          # M3.6 E1 int8 recall@FPR<=0.1（references/calibration-notes.md）；
                                   # NOT max_macro_f1（=0.05/FPR 0.383，安全 guard 不可接受）；
                                   # --threshold 0.5 复现旧 model-card 默认
  quantization: int8               # 生产精度（CUDA；CPU 走 bf16 仅作参考真值）
  nan_fallback: none               # M3.7 E3: none(默认)=int8 NaN -> error 行（快、可复现，复现旧行为）。
                                   # 全覆盖评测用 --nan-fallback auto：8GB 上 GPU 路径 OOM（dead-mode 缓存，
                                   # 不重试）-> 每张 NaN 图回退 CPU bf16（~74s/图），找回 ~19.4% 丢失覆盖。
                                   # 恢复分是 bf16、用 int8 校准的 0.30 阈值；E3 找回的是覆盖率，不是 int8 质量漂移。
  model_id: google/shieldgemma-2-4b-it   # 非门镜像: Nozim6690/hugging-face_shieldgemma-2-4b-it
  model_revision: 548e04faf66e2234e6d113a71f530e1affa8dd86   # M3.5 W1（镜像 commit）
  transformers: 4.51.3             # 钉死: 4.53+ 的 Gemma3 前向需 torch>=2.6
  torch: 2.5.1+cu121
  bitsandbytes: 0.48.2
  known_issues:
    - int8 NaN rate ~19.4% on real images (deterministic quantization artifact, not noise)
    - "E2 stack-upgrade spike (torch 2.6.0 + transformers 4.57.1) = not_fixed: NaN 60%->35%
       on probe but surviving int8 scores only 31% aligned with CPU bf16 (drift 0.67) — see
       shieldgemma2-notes.md §6.1c. int8 stays untrustworthy; CPU bf16 is the reference."
    - 3-policy ceiling (dangerous/sexual/violence) caps AUROC (~0.72 even on clean CPU bf16);
      8 of 11 UnsafeBench categories have no policy — STRUCTURAL, not solvable by calibration
    - CPU bf16 reference (74 s/img) differs from int8 production precision; don't reuse thresholds across precision
```

**真实效果（M3.6 E1，新默认 0.30 vs 旧 0.5）**：Macro-F1 0.480→**0.523**、Recall 0.125→**0.198**、FPR 0.051→0.089（48 TP recovered vs 37 FP introduced，FPR 仍守 ~9%）。AUROC 0.613（int8 下界；CPU bf16 真值 0.719）。

**E3 NaN 回退（M3.7，可选 `--nan-fallback`）**：100 NaN 子集实测 **恢复 100/100**，**覆盖率 0%→100%**（全量投影 80.6%→~100%）；恢复分 truth-grade（子集 AUROC 0.675 ≈ CPU 0.719）。**找回的是覆盖率，不是 int8 质量**（全量 E3 后为混精度）。详见 `shieldgemma2-notes.md §6.3` / `M3.7_summary.md`。默认 `none`。
