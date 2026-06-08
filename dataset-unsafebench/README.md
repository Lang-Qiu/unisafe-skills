# dataset-unsafebench

Dataset Skill（方向 A，多模态亮点）。把 [UnsafeBench](https://huggingface.co/datasets/yiting/UnsafeBench) 图像安全集转成统一 JSONL（image 模态）。

**状态**：scaffold（M0）。实现见 M3，分支 `feat/dataset-unsafebench`。

- 源数据集：`yiting/UnsafeBench`（11 类，Safe/Unsafe，真实+AI 生成图像）。
- 含 Safe 样本 → 多模态侧也能算 FPR；严格限小样本（200–500 张）。
- 字段映射：见 [`../M0_接口约定.md`](../M0_接口约定.md) §4。
- 输出样例：见根目录样本的 `unsafebench:*` 记录。
- ⚠️ 含真实有害图像，仅用于防御性评测；图片不入 git。

## 待办（M3）

- [ ] 下载并落盘图片，`content.images` 记录 path + caption/OCR
- [ ] `safety_label`→`is_unsafe`；`category`→22 类映射
- [ ] 自跑 checker（image_safety 记录）= exit 0
