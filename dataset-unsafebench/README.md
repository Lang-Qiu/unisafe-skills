# dataset-unsafebench

Dataset skill for direction A. This converter turns
[UnsafeBench](https://huggingface.co/datasets/yiting/UnsafeBench) into unified
JSONL records for the image-safety branch of the project.

## What it produces

- unified `image_safety` records
- local image files saved under the output directory
- canonical category mapping from UnsafeBench's 11 classes
- a `metadata.json` summary for handoff and checking

This dataset contains both safe and unsafe images, so downstream image guards
can compute standard metrics such as Accuracy, Recall, and FPR on real image
records.

## Source dataset

- Hugging Face dataset: `yiting/UnsafeBench`
- content type: image safety
- labels: `Safe` / `Unsafe`
- categories: 11 source classes mapped into the unified canonical taxonomy

## Main files

- `scripts/main.py`: converter entry point
- `references/category_mapping.json`: UnsafeBench 11-class mapping
- `examples/output.sample.jsonl`: minimal safe / unsafe sample records

## Output layout

Given `--output-dir <OUT>`, the converter writes:

- `<OUT>/unified/unsafebench.unified.jsonl`
- `<OUT>/unified/metadata.json`
- `<OUT>/unified/images/unsafebench/...`

## Notes

- This skill is for dataset construction only, not guard evaluation.
- It does not append XSTest probes.
- Real dataset images are written to the chosen output directory and should not
  be committed into the repository.
