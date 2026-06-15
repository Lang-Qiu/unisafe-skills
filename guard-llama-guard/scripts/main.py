"""Run text safety guards over unified safety JSONL records.

Reads unified records (dataset-format-checker PASS data), routes them per
references/io-contract.md section 2, runs the requested guard adapters and
writes <output_dir>/predictions/<guard>.predictions.jsonl + run_metadata.json.

Exit codes (authoritative table: references/io-contract.md section 7):
  0 = all requested guards succeeded   1 = fatal / ALL guards failed
  2 = partial success (>=1 guard succeeded, >=1 guard-level failure)
Always judge by exit code + the final 'RESULT:' line, never by `| tail`.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from guards import get_adapter, known_guards
from utils import (
    ROUTE_ELIGIBLE,
    ROUTE_MISSING_CONTENT,
    ROUTE_OUT_OF_SCOPE,
    Timer,
    discover_jsonl_files,
    iter_jsonl,
    now_iso,
    route_record,
    write_jsonl_line,
)

DEFAULT_GUARDS = "rule"
DEFAULT_MODEL_ID = "meta-llama/Llama-Guard-3-1B"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py", description="Run safety guards over unified JSONL records."
    )
    parser.add_argument("--input", required=True, help="unified .jsonl file or directory")
    parser.add_argument("--output-dir", required=True, help="output directory")
    parser.add_argument("--guards", default=DEFAULT_GUARDS,
                        help=f"comma-separated guard names (default: {DEFAULT_GUARDS}; known: {', '.join(known_guards())})")
    parser.add_argument("--limit", type=int, default=None, help="process at most N records")
    parser.add_argument("--device", default="auto", choices=("auto", "cuda", "cpu"))
    parser.add_argument("--timeout-s", type=float, default=None,
                        help="soft per-record timeout; per-guard defaults when omitted: "
                             "llama-guard/openai 30s, llm-judge 60s (CUDA inference "
                             "cannot be interrupted mid-step)")
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    parser.add_argument("--judge-model", default=None,
                        help="model id for the llm-judge guard (fallback: LLM_JUDGE_MODEL "
                             "env, then the adapter default)")
    parser.add_argument("--hf-token", default=None, help="HF token (never persisted; redacted in run_metadata)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--resume", action="store_true",
                        help="skip ids already present in existing prediction files")
    parser.add_argument("--dry-run", action="store_true",
                        help="read + route + count only; no guard calls")
    return parser


def _probe_env(requested: List[str],
               revisions: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Reproducibility block (W1). `revisions` = {guard: commit_hash|None}, threaded
    in by main.py from the loaded adapters. model_revision = first non-null among
    model guards; lib versions read from package metadata (no heavy import)."""
    revisions = dict(revisions or {})
    env: Dict[str, Any] = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "torch": None,
        "cuda": None,
        "model_revision": next((v for v in revisions.values() if v), None),
        "model_revisions": revisions,
        "lib_versions": {},
    }
    if "llama-guard" in requested:  # only pay the slow torch import when relevant
        try:
            import torch  # type: ignore

            # a broken/namespace torch import may succeed yet lack attributes
            env["torch"] = getattr(torch, "__version__", None)
            cuda = getattr(torch, "cuda", None)
            env["cuda"] = bool(cuda.is_available()) if cuda is not None else None
        except Exception:
            pass
        from importlib.metadata import version as _pkg_version
        for lib in ("transformers", "bitsandbytes", "accelerate"):
            try:
                env["lib_versions"][lib] = _pkg_version(lib)
            except Exception:
                env["lib_versions"][lib] = None
    return env


def _load_existing_ids(path: Path) -> set:
    ids = set()
    if path.is_file():
        for _, record, err in iter_jsonl(path):
            if err is None and record.get("id"):
                ids.add(record["id"])
    return ids


def _fatal(message: str) -> int:
    print(f"ERROR: {message}")
    print("RESULT: fatal predicted=0 errors=0 skipped=0")
    return 1


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    input_path = Path(args.input)
    if not input_path.exists():
        return _fatal(f"input path does not exist: {input_path}")
    files = discover_jsonl_files(input_path)
    if not files:
        return _fatal(f"no .jsonl files found under: {input_path}")

    with Timer() as timer:
        records: List[Dict[str, Any]] = []
        unparsable = 0
        for file_path in files:
            for lineno, record, err in iter_jsonl(file_path):
                if err is not None:
                    unparsable += 1
                    print(f"WARNING: {file_path.name}:{lineno}: {err} (line skipped)")
                    continue
                records.append(record)
                if args.limit is not None and len(records) >= args.limit:
                    break
            if args.limit is not None and len(records) >= args.limit:
                break
        if not records:
            return _fatal(f"0 parsable records in: {input_path}")

        eligible: List[Dict[str, Any]] = []
        skipped = {ROUTE_OUT_OF_SCOPE: 0, ROUTE_MISSING_CONTENT: 0}
        for record in records:
            bucket, _reason = route_record(record)
            if bucket == ROUTE_ELIGIBLE:
                eligible.append(record)
            else:
                skipped[bucket] += 1

        output_dir = Path(args.output_dir)
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return _fatal(f"output dir not writable: {output_dir} ({exc})")

        requested = [name.strip() for name in args.guards.split(",") if name.strip()]
        if not requested:
            return _fatal("--guards resolved to an empty list")

        completed: List[str] = []
        failed: Dict[str, str] = {}
        timeout_effective: Dict[str, Optional[float]] = {}
        loaded_revisions: Dict[str, Any] = {}  # W1: guard -> model commit hash (or None)
        predicted = 0
        errors = 0
        resume_hits = 0
        resume_misses = 0

        if not args.dry_run:
            unknown = [name for name in requested if name not in known_guards()]
            if len(unknown) == len(requested):
                return _fatal(
                    f"all requested guards are unknown: {', '.join(unknown)} "
                    f"(known: {', '.join(known_guards())})"
                )
            for name in unknown:
                failed[name] = f"unknown guard (known: {', '.join(known_guards())})"
                print(f"WARNING: skipping unknown guard {name!r}")

            adapter_config = {
                "device": args.device,
                "timeout_s": args.timeout_s,  # None = each adapter applies its default
                "retries": args.retries,
                "batch_size": args.batch_size,
                "model_id": args.model_id,
                "judge_model": args.judge_model,
                "hf_token": args.hf_token,
                "seed": args.seed,
            }
            predictions_dir = output_dir / "predictions"
            for name in requested:
                if name in failed:
                    continue
                adapter = get_adapter(name, adapter_config)
                timeout_effective[name] = getattr(adapter, "timeout_s", None)
                ok, reason = adapter.available()
                if not ok:
                    failed[name] = reason
                    print(f"GUARD-FAILURE [{name}]: {reason}")
                    if "FIX:" not in reason:
                        print(f"FIX: resolve the cause above, then re-run with --guards {name}")
                    continue
                loaded_revisions[name] = getattr(adapter, "model_revision", None)  # W1
                predictions_dir.mkdir(parents=True, exist_ok=True)
                pred_path = predictions_dir / f"{name}.predictions.jsonl"
                existing_ids = _load_existing_ids(pred_path) if args.resume else set()
                mode = "a" if (args.resume and pred_path.exists()) else "w"
                pending = []
                for record in eligible:
                    if record.get("id") in existing_ids:
                        resume_hits += 1
                    else:
                        pending.append(record)
                use_batch = adapter.capabilities.get("supports_batch") and args.batch_size > 1
                chunk_size = args.batch_size if use_batch else 1
                with open(pred_path, mode, encoding="utf-8", newline="\n") as fh:
                    for start in range(0, len(pending), chunk_size):
                        chunk = pending[start:start + chunk_size]
                        try:
                            results = (adapter.predict_batch(chunk) if use_batch
                                       else [adapter.predict(chunk[0])])
                        except Exception as exc:  # record-level error rows; keep going
                            results = [
                                adapter.make_result(
                                    record, is_unsafe=None,
                                    error=f"{type(exc).__name__}: {exc}",
                                )
                                for record in chunk
                            ]
                        for result in results:
                            resume_misses += 1
                            if result["prediction"]["is_unsafe"] is None:
                                errors += 1
                            else:
                                predicted += 1
                            write_jsonl_line(fh, result)
                        fh.flush()  # chunk-level durability: a crash keeps finished work
                completed.append(name)
                print(f"guard {name}: wrote {pred_path}")

    denominator = resume_hits + resume_misses
    run_metadata = {
        "run_id": f"{now_iso().replace(':', '').replace('-', '')}-{os.getpid()}",
        "timestamp": now_iso(),
        "input": {"path": str(input_path), "n_records": len(records), "n_unparsable": unparsable},
        "guards": {"requested": requested, "completed": completed, "failed": failed},
        "counts": {
            "total": len(records),
            "eligible": len(eligible),
            "predicted": predicted,
            "errors": errors,
            "skipped": {
                "out_of_scope": skipped[ROUTE_OUT_OF_SCOPE],
                "missing_content": skipped[ROUTE_MISSING_CONTENT],
            },
        },
        "resume_hits": resume_hits,
        "resume_misses": resume_misses,
        "resume_hit_rate": (resume_hits / denominator) if denominator else 0.0,
        "config": {
            "input": str(args.input),
            "output_dir": str(args.output_dir),
            "guards": requested,
            "limit": args.limit,
            "device": args.device,
            "timeout_s": args.timeout_s,
            "timeout_s_effective": timeout_effective,
            "retries": args.retries,
            "batch_size": args.batch_size,
            "model_id": args.model_id,
            "judge_model": args.judge_model,
            "hf_token": "<redacted>" if args.hf_token else None,
            "seed": args.seed,
            "resume": args.resume,
            "dry_run": args.dry_run,
        },
        "env": _probe_env(requested, loaded_revisions),
        "duration_s": round(timer.seconds, 3),
    }
    with open(output_dir / "run_metadata.json", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(run_metadata, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    skip_total = skipped[ROUTE_OUT_OF_SCOPE] + skipped[ROUTE_MISSING_CONTENT]
    if args.dry_run:
        status, code = "ok", 0
    elif completed and not failed:
        status, code = "ok", 0
    elif completed and failed:
        status, code = "partial", 2
    else:
        status, code = "fatal", 1
        print("ERROR: all requested guards failed:")
        for name, reason in failed.items():
            print(f"  - {name}: {reason}")
    print(f"counts: total={len(records)} eligible={len(eligible)} "
          f"out_of_scope={skipped[ROUTE_OUT_OF_SCOPE]} missing_content={skipped[ROUTE_MISSING_CONTENT]}")
    print(f"RESULT: {status} predicted={predicted} errors={errors} skipped={skip_total}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
