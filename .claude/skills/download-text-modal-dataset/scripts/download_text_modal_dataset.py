#!/usr/bin/env python3
"""Download and normalize text safety guard benchmark source datasets.

This script reconstructs a configurable, paper-like version of the 2026
"Benchmarking Open-Source Safety Guard Models" benchmark from public source
Hugging Face datasets.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

try:
    from datasets import Dataset, DatasetDict, load_dataset
except Exception as exc:  # pragma: no cover
    raise SystemExit(
        "Missing dependency: datasets.\n"
        "Install requirements into an ISOLATED environment (do not pollute system Python):\n"
        "  python -m venv .venv && source .venv/bin/activate\n"
        "    # if venv fails with 'No module named ensurepip', use conda instead:\n"
        "    # conda create -n harmful-content python=3.10 -y && conda activate harmful-content\n"
        "  python -m pip install -r requirements.txt\n"
        "Note: use `python -m pip`, not bare `pip` (bare pip may be missing).\n"
        f"Original import error: {exc}"
    )

try:
    from tqdm import tqdm
except Exception:  # pragma: no cover
    def tqdm(x, **_: Any):
        return x

SOURCE_ALIASES = {
    "harmbench": "harmbench",
    "walledai/harmbench": "harmbench",
    "strongreject": "strongreject",
    "strong_reject": "strongreject",
    "walledai/strongreject": "strongreject",
    "rtp": "real_toxicity_prompts",
    "realtoxicityprompts": "real_toxicity_prompts",
    "real_toxicity_prompts": "real_toxicity_prompts",
    "allenai/real-toxicity-prompts": "real_toxicity_prompts",
    "beavertails": "beavertails",
    "pku-alignment/beavertails": "beavertails",
}

SOURCE_REPOS = {
    "harmbench": "walledai/HarmBench",
    "strongreject": "walledai/StrongREJECT",
    "real_toxicity_prompts": "allenai/real-toxicity-prompts",
    "beavertails": "PKU-Alignment/BeaverTails",
}

DEFAULT_SPLITS = {
    "beavertails": "30k_train",
    "real_toxicity_prompts": None,
    "harmbench": None,
    "strongreject": None,
}

# Some repos expose multiple configs (subsets) and require an explicit config
# name. HarmBench needs one of: standard/contextual/copyright. We load the
# harmful-behavior configs and skip "copyright" (paper drops copyright behaviors).
SOURCE_CONFIGS = {
    "harmbench": ["standard", "contextual"],
}

SCHEMA_VERSION = "1.0"


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def json_default(obj: Any) -> Any:
    try:
        import numpy as np  # type: ignore
        if isinstance(obj, np.generic):
            return obj.item()
        if isinstance(obj, np.ndarray):
            return obj.tolist()
    except Exception:
        pass
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return str(obj)


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> int:
    n = 0
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, default=json_default) + "\n")
            n += 1
    return n


def stable_id(source: str, split: str, idx: int, text: str) -> str:
    digest = hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()[:12]
    return f"{source}:{split}:{idx}:{digest}"


def norm_source_name(name: str) -> str:
    key = name.strip().lower()
    if key == "all":
        return "all"
    if key not in SOURCE_ALIASES:
        allowed = ", ".join(sorted(set(SOURCE_ALIASES.values())))
        raise ValueError(f"Unknown source '{name}'. Allowed: all, {allowed}")
    return SOURCE_ALIASES[key]


def split_sources(value: str) -> List[str]:
    parts = [norm_source_name(x) for x in value.split(",") if x.strip()]
    if not parts or "all" in parts:
        return ["harmbench", "strongreject", "real_toxicity_prompts", "beavertails"]
    seen: List[str] = []
    for p in parts:
        if p not in seen:
            seen.append(p)
    return seen


def load_hf_dataset(repo: str, split: Optional[str], cache_dir: Optional[str], token: Optional[str], name: Optional[str] = None) -> Dataset | DatasetDict:
    kwargs: Dict[str, Any] = {}
    if name:
        kwargs["name"] = name
    if cache_dir:
        kwargs["cache_dir"] = cache_dir
    if token:
        kwargs["token"] = token
    if split:
        kwargs["split"] = split
    try:
        return load_dataset(repo, **kwargs)
    except TypeError:
        # Compatibility with older `datasets` releases.
        if "token" in kwargs:
            kwargs["use_auth_token"] = kwargs.pop("token")
        return load_dataset(repo, **kwargs)


def explain_load_error(repo: str, exc: Exception) -> str:
    """Return actionable, copy-pasteable hints for a dataset load failure.

    Written so that even a weak agent can read this stderr output and know
    exactly what to do next, without reasoning about Hugging Face internals.
    """
    msg = str(exc).lower()
    hints: List[str] = []
    if any(k in msg for k in ("gated", "awaiting", "must be authenticated", "401", "403", "access to this dataset")):
        hints.append(
            f"    FIX (gated dataset):\n"
            f"      1) Open https://huggingface.co/datasets/{repo} and click 'Agree and access repository'.\n"
            f"      2) Authenticate (any one):  hf auth login   |   huggingface-cli login   |   export HF_TOKEN=hf_xxx\n"
            f"      3) Re-run the SAME command with --sources all (the script overwrites output; a partial --sources would drop other sources)."
        )
    if "config name is missing" in msg or "config name" in msg:
        try:
            from datasets import get_dataset_config_names
            cfgs = get_dataset_config_names(repo)
            cfg_str = ", ".join(map(str, cfgs))
        except Exception:
            cfg_str = "(could not list; see the dataset page)"
        hints.append(
            f"    FIX (dataset needs an explicit config): available configs = [{cfg_str}].\n"
            f"      Add the harmful-behavior config(s) for '{repo}' to SOURCE_CONFIGS near the top of this script."
        )
    if not hints:
        hints.append(
            "    FIX: check network access and the dataset page; if it is private/gated, authenticate as shown above."
        )
    return "\n".join(hints)


def iter_splits(ds: Dataset | DatasetDict, default_split: Optional[str] = None) -> Iterator[Tuple[str, Dataset]]:
    if isinstance(ds, DatasetDict):
        for split_name, split_ds in ds.items():
            yield split_name, split_ds
    else:
        yield default_split or "data", ds


def limit_iter(ds: Dataset, max_items: Optional[int]) -> Iterable[Tuple[int, Dict[str, Any]]]:
    n = len(ds) if max_items is None else min(len(ds), max_items)
    for idx in range(n):
        yield idx, dict(ds[idx])


def get_in(obj: Any, path: Sequence[str]) -> Any:
    cur = obj
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            return None
        cur = cur[p]
    return cur


def coerce_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def first_text(ex: Dict[str, Any], keys: Sequence[str]) -> Optional[str]:
    for key in keys:
        value = ex.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            text = value.get("text") or value.get("content")
            if isinstance(text, str) and text.strip():
                return text.strip()
    return None


def extract_rtp_text(ex: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    prompt = ex.get("prompt")
    continuation = ex.get("continuation")

    text = None
    response = None
    if isinstance(prompt, dict):
        text = prompt.get("text")
    elif isinstance(prompt, str):
        text = prompt

    if isinstance(continuation, dict):
        response = continuation.get("text")
    elif isinstance(continuation, str):
        response = continuation

    return (text.strip() if isinstance(text, str) and text.strip() else None,
            response.strip() if isinstance(response, str) and response.strip() else None)


def extract_score_from_part(part: Any, dim: str) -> Optional[float]:
    if not isinstance(part, dict):
        return None
    return coerce_float(part.get(dim))


def average_available(values: Sequence[Optional[float]]) -> Optional[float]:
    real = [v for v in values if v is not None]
    if not real:
        return None
    return sum(real) / len(real)


def lower_join(values: Iterable[Any]) -> str:
    chunks: List[str] = []
    for v in values:
        if v is None:
            continue
        if isinstance(v, (str, int, float, bool)):
            chunks.append(str(v))
        elif isinstance(v, list):
            chunks.extend(str(x) for x in v if x is not None)
        elif isinstance(v, dict):
            for k, val in v.items():
                if isinstance(val, bool):
                    if val:
                        chunks.append(str(k))
                elif val in (1, "1", "true", "True", "yes", "Yes"):
                    chunks.append(str(k))
                elif isinstance(val, (list, tuple)):
                    chunks.append(str(k))
                    chunks.extend(str(x) for x in val)
    return " | ".join(chunks).lower()


def category_values(ex: Dict[str, Any]) -> List[str]:
    keys = [
        "category", "categories", "Category", "Categories", "subcategory", "sub_category",
        "SemanticCategory", "FunctionalCategory", "semantic_category", "functional_category",
        "risk_category", "harm_category", "source", "type"
    ]
    values: List[str] = []
    for key in keys:
        value = ex.get(key)
        if value is None:
            continue
        if isinstance(value, dict):
            for k, v in value.items():
                if isinstance(v, bool):
                    if v:
                        values.append(str(k))
                elif v in (1, "1", "true", "True", "yes", "Yes"):
                    values.append(str(k))
                elif isinstance(v, str) and v.strip() and v.strip().lower() not in {"false", "0", "no"}:
                    values.append(f"{k}:{v}")
        elif isinstance(value, list):
            values.extend(str(x) for x in value if x is not None)
        else:
            values.append(str(value))
    return values


def has_drop_keyword(text: str, drop_keywords: Sequence[str]) -> bool:
    lt = text.lower()
    return any(k.lower() in lt for k in drop_keywords)


def map_text_to_categories(text: str, keyword_map: Dict[str, List[str]]) -> List[str]:
    lt = text.lower().replace("_", " ")
    cats: List[str] = []
    for cat, keywords in keyword_map.items():
        if any(k.lower().replace("_", " ") in lt for k in keywords):
            cats.append(cat)
    return cats


def build_record(
    *,
    source: str,
    split: str,
    idx: int,
    text: str,
    response: Optional[str],
    label: int,
    categories: Sequence[str],
    scores: Optional[Dict[str, float]] = None,
    confidence: Optional[float] = None,
    original_category: Optional[str] = None,
    source_id: Optional[str] = None,
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    cats = sorted(set(categories))
    safety_label = "unsafe" if label == 1 else "safe"
    return {
        "id": stable_id(source, split, idx, text),
        "source_dataset": source,
        "source_split": split,
        "text": text,
        "response": response,
        "safety_label": safety_label,
        "label": int(label),
        "nist_safety_categories": cats,
        "category_scores": scores or {},
        "confidence": confidence,
        "original_category": original_category,
        "source_id": source_id,
        "metadata": {"schema_version": SCHEMA_VERSION, **(extra_metadata or {})},
    }


def normalize_real_toxicity_prompts(
    split: str,
    ds: Dataset,
    mapping: Dict[str, Any],
    threshold: float,
    max_items: Optional[int],
    counters: Dict[str, Counter],
) -> Iterator[Dict[str, Any]]:
    dim_to_cat = mapping["real_toxicity_prompts"]
    for idx, ex in tqdm(limit_iter(ds, max_items), total=min(len(ds), max_items or len(ds)), desc=f"RTP/{split}"):
        text, response = extract_rtp_text(ex)
        if not text:
            counters["skipped"]["rtp:no_text"] += 1
            continue
        prompt = ex.get("prompt")
        continuation = ex.get("continuation")
        cat_scores: Dict[str, float] = {}
        original_dims: List[str] = []
        for dim, cat in dim_to_cat.items():
            score = average_available([
                extract_score_from_part(prompt, dim),
                extract_score_from_part(continuation, dim),
            ])
            if score is None:
                continue
            current = cat_scores.get(cat)
            cat_scores[cat] = max(current if current is not None else score, score)
            original_dims.append(dim)
        if not cat_scores:
            counters["skipped"]["rtp:no_scores"] += 1
            continue
        max_score = max(cat_scores.values())
        unsafe_cats = [cat for cat, score in cat_scores.items() if score >= threshold]
        label = 1 if unsafe_cats else 0
        yield build_record(
            source="real_toxicity_prompts",
            split=split,
            idx=idx,
            text=text,
            response=response,
            label=label,
            categories=unsafe_cats,
            scores=cat_scores,
            confidence=max_score,
            original_category=",".join(sorted(set(original_dims))),
            source_id=str(ex.get("filename") or ex.get("id") or "") or None,
            extra_metadata={"threshold": threshold, "challenging": ex.get("challenging")},
        )


def normalize_beavertails(
    split: str,
    ds: Dataset,
    mapping: Dict[str, Any],
    max_items: Optional[int],
    keep_unmapped: bool,
    counters: Dict[str, Counter],
) -> Iterator[Dict[str, Any]]:
    aliases: Dict[str, List[str]] = mapping.get("beavertails_category_aliases", {})
    keyword_map: Dict[str, List[str]] = mapping["keyword_map"]
    drop_keywords: List[str] = mapping["drop_keywords"]

    for idx, ex in tqdm(limit_iter(ds, max_items), total=min(len(ds), max_items or len(ds)), desc=f"BeaverTails/{split}"):
        text = first_text(ex, ["prompt", "question", "instruction", "input", "text"])
        response = first_text(ex, ["response", "answer", "output", "completion"])
        if not text:
            counters["skipped"]["beavertails:no_text"] += 1
            continue

        raw_categories = category_values(ex)
        if not raw_categories and isinstance(ex.get("category"), dict):
            raw_categories = [k for k, v in ex["category"].items() if bool(v)]
        raw_joined = " | ".join(raw_categories)
        categories: List[str] = []
        dropped = False
        for raw in raw_categories:
            key = str(raw).strip().lower()
            key_norm = key.replace(" ", "_")
            if key_norm in aliases:
                categories.extend(aliases[key_norm])
                continue
            if has_drop_keyword(key, drop_keywords):
                dropped = True
                continue
            categories.extend(map_text_to_categories(key, keyword_map))

        categories = sorted(set(categories))
        if not categories:
            if dropped:
                counters["skipped"]["beavertails:non_safety_category"] += 1
                continue
            if keep_unmapped:
                categories = []
            else:
                counters["skipped"]["beavertails:unmapped_category"] += 1
                counters["unmapped_categories"][raw_joined or "<empty>"] += 1
                continue

        yield build_record(
            source="beavertails",
            split=split,
            idx=idx,
            text=text,
            response=response,
            label=1,
            categories=categories,
            scores={cat: 1.0 for cat in categories},
            confidence=1.0,
            original_category=raw_joined or None,
            source_id=str(ex.get("id") or ex.get("sample_id") or "") or None,
            extra_metadata={"is_safe_original": ex.get("is_safe")},
        )


def normalize_adversarial_source(
    source: str,
    split: str,
    ds: Dataset,
    mapping: Dict[str, Any],
    max_items: Optional[int],
    keep_unmapped: bool,
    allow_text_keyword_fallback: bool,
    counters: Dict[str, Counter],
) -> Iterator[Dict[str, Any]]:
    keyword_map: Dict[str, List[str]] = mapping["keyword_map"]
    drop_keywords: List[str] = mapping["drop_keywords"]
    text_keys = [
        "Behavior", "behavior", "forbidden_prompt", "prompt", "instruction", "question",
        "query", "goal", "text", "request", "content"
    ]
    response_keys = ["response", "answer", "output", "completion"]

    for idx, ex in tqdm(limit_iter(ds, max_items), total=min(len(ds), max_items or len(ds)), desc=f"{source}/{split}"):
        text = first_text(ex, text_keys)
        response = first_text(ex, response_keys)
        if not text:
            counters["skipped"][f"{source}:no_text"] += 1
            continue

        raw_categories = category_values(ex)
        raw_joined = " | ".join(raw_categories)
        category_text = raw_joined.lower()

        if category_text and has_drop_keyword(category_text, drop_keywords):
            counters["skipped"][f"{source}:non_safety_category"] += 1
            continue

        categories = map_text_to_categories(category_text, keyword_map) if category_text else []
        if not categories and allow_text_keyword_fallback:
            categories = map_text_to_categories(text, keyword_map)

        categories = sorted(set(categories))
        if not categories and not keep_unmapped:
            counters["skipped"][f"{source}:unmapped_category"] += 1
            counters["unmapped_categories"][raw_joined or "<empty>"] += 1
            continue

        yield build_record(
            source=source,
            split=split,
            idx=idx,
            text=text,
            response=response,
            label=1,
            categories=categories,
            scores={cat: 1.0 for cat in categories},
            confidence=1.0,
            original_category=raw_joined or None,
            source_id=str(ex.get("BehaviorID") or ex.get("id") or ex.get("source_id") or "") or None,
            extra_metadata={"source_fields": list(ex.keys())},
        )


def normalize_source(
    source: str,
    split: str,
    ds: Dataset,
    mapping: Dict[str, Any],
    threshold: float,
    max_items: Optional[int],
    keep_unmapped: bool,
    allow_text_keyword_fallback: bool,
    counters: Dict[str, Counter],
) -> Iterator[Dict[str, Any]]:
    if source == "real_toxicity_prompts":
        yield from normalize_real_toxicity_prompts(split, ds, mapping, threshold, max_items, counters)
    elif source == "beavertails":
        yield from normalize_beavertails(split, ds, mapping, max_items, keep_unmapped, counters)
    elif source in {"harmbench", "strongreject"}:
        yield from normalize_adversarial_source(
            source, split, ds, mapping, max_items, keep_unmapped, allow_text_keyword_fallback, counters
        )
    else:
        raise ValueError(f"Unsupported source: {source}")


def save_raw_dataset(ds: Dataset | DatasetDict, raw_dir: Path, source: str, max_items: Optional[int]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for split, split_ds in iter_splits(ds):
        path = raw_dir / source / f"{split}.jsonl"
        if max_items is None:
            count = write_jsonl(path, (dict(split_ds[i]) for i in range(len(split_ds))))
        else:
            count = write_jsonl(path, (ex for _, ex in limit_iter(split_ds, max_items)))
        counts[split] = count
    return counts


def summarize(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_source = Counter(r["source_dataset"] for r in rows)
    by_label = Counter(r["safety_label"] for r in rows)
    by_category: Counter[str] = Counter()
    for row in rows:
        if not row["nist_safety_categories"] and row["label"] == 0:
            by_category["safe"] += 1
        for cat in row["nist_safety_categories"]:
            by_category[cat] += 1
    return {
        "total": len(rows),
        "by_source_dataset": dict(by_source),
        "by_label": dict(by_label),
        "by_category": dict(by_category),
    }


def dedupe_rows(rows: Iterable[Dict[str, Any]], counters: Dict[str, Counter]) -> List[Dict[str, Any]]:
    seen = set()
    out = []
    for row in rows:
        key = row["text"].strip().lower()
        if key in seen:
            counters["skipped"]["duplicate_text"] += 1
            continue
        seen.add(key)
        out.append(row)
    return out


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="data/safety_guard_2026", help="Output directory.")
    parser.add_argument("--cache-dir", default=None, help="Optional Hugging Face cache directory.")
    parser.add_argument("--hf-token", default=os.environ.get("HF_TOKEN"), help="Optional HF token. Defaults to HF_TOKEN env var.")
    parser.add_argument("--sources", default="all", help="Comma-separated sources: all,harmbench,strongreject,real_toxicity_prompts,beavertails")
    parser.add_argument("--threshold", type=float, default=0.5, help="RTP unsafe threshold. Default: 0.5")
    parser.add_argument("--beavertails-split", default="30k_train", help="BeaverTails split. Default: 30k_train")
    parser.add_argument("--include-raw", action="store_true", help="Also save raw downloaded records as JSONL.")
    parser.add_argument("--max-samples-per-source", type=int, default=None, help="Debug limit per split/source.")
    parser.add_argument("--keep-unmapped", action="store_true", help="Keep harmful source rows even if categories cannot be mapped.")
    parser.add_argument("--allow-text-keyword-fallback", action="store_true", help="For HarmBench/StrongREJECT, infer category from text if source category is missing.")
    parser.add_argument("--no-dedupe", action="store_true", help="Do not deduplicate by normalized text.")
    parser.add_argument("--mapping", default=None, help="Path to category_mapping.json. Defaults to ../config/category_mapping.json.")
    parser.add_argument("--no-unified", action="store_true",
                        help="Skip the additional unified-format output (data/.../unified/*.unified.jsonl) "
                             "that conforms to dataset-format-checker. The flat normalized output is unaffected.")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    script_dir = Path(__file__).resolve().parent
    skill_dir = script_dir.parent
    mapping_path = Path(args.mapping) if args.mapping else skill_dir / "config" / "category_mapping.json"
    mapping = load_json(mapping_path)

    out_dir = Path(args.output_dir)
    raw_dir = out_dir / "raw"
    norm_dir = out_dir / "normalized"
    ensure_dir(norm_dir)

    sources = split_sources(args.sources)
    all_rows: List[Dict[str, Any]] = []
    counters: Dict[str, Counter] = defaultdict(Counter)
    load_errors: Dict[str, str] = {}
    raw_counts: Dict[str, Dict[str, int]] = {}

    for source in sources:
        repo = SOURCE_REPOS[source]
        split = DEFAULT_SPLITS.get(source)
        if source == "beavertails":
            split = args.beavertails_split
        configs = SOURCE_CONFIGS.get(source, [None])
        for cfg in configs:
            tag = f"{source}/{cfg}" if cfg else source
            print(f"\n==> Loading {tag} from {repo}" + (f" config={cfg}" if cfg else "") + (f" split={split}" if split else ""), file=sys.stderr)
            try:
                ds = load_hf_dataset(repo, split=split, cache_dir=args.cache_dir, token=args.hf_token, name=cfg)
            except Exception as exc:
                load_errors[tag] = str(exc)
                print(f"[WARN] Failed to load {tag}: {exc}", file=sys.stderr)
                print(explain_load_error(repo, exc), file=sys.stderr)
                continue

            if args.include_raw:
                raw_counts[tag] = save_raw_dataset(ds, raw_dir, tag, args.max_samples_per_source)

            for split_name, split_ds in iter_splits(ds, default_split=split):
                sname = f"{cfg}:{split_name}" if cfg else split_name
                counters["raw_loaded"][f"{source}:{sname}"] = min(len(split_ds), args.max_samples_per_source or len(split_ds))
                rows = list(normalize_source(
                    source=source,
                    split=sname,
                    ds=split_ds,
                    mapping=mapping,
                    threshold=args.threshold,
                    max_items=args.max_samples_per_source,
                    keep_unmapped=args.keep_unmapped,
                    allow_text_keyword_fallback=args.allow_text_keyword_fallback,
                    counters=counters,
                ))
                all_rows.extend(rows)
                print(f"    normalized {source}/{sname}: {len(rows)} rows", file=sys.stderr)

    if not args.no_dedupe:
        all_rows = dedupe_rows(all_rows, counters)

    output_path = norm_dir / "safety_guard_2026.jsonl"
    n_written = write_jsonl(output_path, all_rows)

    metadata = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": SCHEMA_VERSION,
        "script": "download_text_modal_dataset.py",
        "sources_requested": sources,
        "source_repos": SOURCE_REPOS,
        "threshold": args.threshold,
        "beavertails_split": args.beavertails_split,
        "paper_like_note": "Reconstructs a paper-like benchmark from public source datasets; not an official released master file.",
        "output_file": str(output_path),
        "summary": summarize(all_rows),
        "raw_counts": raw_counts,
        "raw_loaded": dict(counters["raw_loaded"]),
        "skipped": dict(counters["skipped"]),
        "top_unmapped_categories": counters["unmapped_categories"].most_common(50),
        "load_errors": load_errors,
        "args": vars(args),
    }
    metadata_path = norm_dir / "metadata.json"
    with metadata_path.open("w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2, default=json_default)

    # --- Additional UNIFIED-format output --------------------------------- #
    # Convert the flat records into the unified nested schema validated by the
    # sibling skill `dataset-format-checker` (see safety_dataset_format_guide.md).
    # This is purely additive: it writes ONLY under out_dir/"unified" and never
    # touches raw/ or normalized/. Any failure here is non-fatal — the flat
    # normalized output above is already fully written.
    unified_path: Optional[Path] = None
    if not args.no_unified:
        try:
            if str(script_dir) not in sys.path:
                sys.path.insert(0, str(script_dir))
            from to_unified_format import convert_rows, NIST2CANON

            unified_dir = out_dir / "unified"
            unified_path = unified_dir / "safety_guard_2026.unified.jsonl"
            conv_errors: List[Tuple[int, str]] = []
            n_unified = write_jsonl(unified_path, convert_rows(all_rows, errors=conv_errors))
            unified_meta = {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "format": "unified_nested_v1",
                "conforms_to": "dataset-format-checker (safety_dataset_format_guide.md)",
                "source_file": str(output_path),
                "records_in": len(all_rows),
                "records_written": n_unified,
                "records_skipped": len(conv_errors),
                "nist_to_canonical": NIST2CANON,
                "self_check": "python ../dataset-format-checker/scripts/check_dataset_format.py " + str(unified_dir),
            }
            with (unified_dir / "metadata.json").open("w", encoding="utf-8") as f:
                json.dump(unified_meta, f, ensure_ascii=False, indent=2, default=json_default)
            print(f"Unified output: {n_unified}/{len(all_rows)} rows -> {unified_path}", file=sys.stderr)
            if conv_errors:
                print(f"[WARN] {len(conv_errors)} record(s) skipped during unified conversion.", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001 - never let the extra output break the run
            unified_path = None
            print(f"[WARN] unified conversion failed (flat normalized output is unaffected): {exc}", file=sys.stderr)

    print("\nDone.", file=sys.stderr)
    print(f"Normalized rows: {n_written}", file=sys.stderr)
    print(f"Dataset: {output_path}", file=sys.stderr)
    print(f"Metadata: {metadata_path}", file=sys.stderr)
    if unified_path is not None:
        print(f"Unified (dataset-format-checker compatible): {unified_path}", file=sys.stderr)

    # Human-readable summary so a weak agent can tell success from partial failure.
    by_src = metadata["summary"]["by_source_dataset"]
    print("\n" + "=" * 64, file=sys.stderr)
    print("SUMMARY", file=sys.stderr)
    print("=" * 64, file=sys.stderr)
    for source in sources:
        failed_tags = [t for t in load_errors if t == source or t.startswith(f"{source}/")]
        rows = by_src.get(source, 0)
        if failed_tags and rows == 0:
            note = "FAILED to load"
        elif failed_tags:
            note = f"{rows} rows (some configs failed: {', '.join(failed_tags)})"
        else:
            note = f"{rows} rows"
        print(f"  {source:<22} {note}", file=sys.stderr)

    if load_errors:
        print("\n[!] Some sources FAILED to load (exit code = 2). This is NOT a crash:", file=sys.stderr)
        print("    the dataset above was still built from the sources that succeeded.", file=sys.stderr)
        for tag, err in load_errors.items():
            print(f"      - {tag}: {err}", file=sys.stderr)
        print("\n    To add the failed sources after fixing access, RE-RUN THE FULL COMMAND with --sources all:", file=sys.stderr)
        print(
            f"      python {Path(__file__).name} --output-dir {out_dir} "
            f"--sources all --threshold {args.threshold} --include-raw",
            file=sys.stderr,
        )
        print("    (The script OVERWRITES the output file, so running only the failed --sources would drop the others.)", file=sys.stderr)
        return 2

    print(f"\nAll requested sources loaded OK. Final dataset: {n_written} rows.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
