"""guard-llama-guard CLI: run guards over unified safety JSONL.

Exit codes (references/schema.md §4):
  0  all required guards succeeded (optional/allow-missing may be skipped)
  2  at least one REQUIRED guard failed to load or run
  3  fatal pre-run error (bad input/args/output dir, or zero valid records)

Zero-install run modes:
  python -m guard_llama_guard.main --profile core-minimal --input examples/tiny_unified.jsonl --out runs/smoke/
  python src/guard_llama_guard/main.py  (same arguments)
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

if __package__ in (None, ""):  # direct-path run without install
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from guard_llama_guard import __version__, utils
from guard_llama_guard.guards.base import Guard, GuardLoadError

EXIT_OK = 0
EXIT_REQUIRED_GUARD_FAILED = 2
EXIT_FATAL = 3

# Known guards. Factories import lazily so missing optional deps only fail
# the guard that needs them. Extensions are implicitly optional under
# --profile all (unless explicitly named via --guards).
EXTENSION_GUARDS = {"llm_judge", "wildguard"}

PROFILES: Dict[str, List[str]] = {
    "core-minimal": ["rule"],
    "core-full": ["rule", "llama_guard"],
    "all": ["rule", "llama_guard", "llm_judge", "wildguard"],
}


def _make_guard(name: str, args: argparse.Namespace) -> Guard:
    if name == "rule":
        from guard_llama_guard.guards.rule_based import RuleGuard
        return RuleGuard(score_mode=args.rule_score)
    if name == "llama_guard":
        from guard_llama_guard.guards.llama_guard import LlamaGuard
        return LlamaGuard(hf_token=args.hf_token, cache_dir=args.cache_dir)
    if name == "llm_judge":
        from guard_llama_guard.guards.llm_judge import LlmJudgeGuard
        return LlmJudgeGuard()
    if name == "wildguard":
        from guard_llama_guard.guards.wildguard import WildGuardGuard
        return WildGuardGuard(hf_token=args.hf_token, cache_dir=args.cache_dir,
                              backend=args.backend)
    raise KeyError(name)


class _Exit3ArgumentParser(argparse.ArgumentParser):
    """argparse exits 2 on bad args by default; our contract reserves 2 for
    required-guard failures, so CLI errors must map to exit 3."""

    def error(self, message: str):  # noqa: D401
        self.print_usage(sys.stderr)
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        raise SystemExit(EXIT_FATAL)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = _Exit3ArgumentParser(description=__doc__,
                             formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", required=True, help="unified safety JSONL")
    p.add_argument("--out", required=True, help="output directory")
    p.add_argument("--profile", choices=sorted(PROFILES), default="core-minimal")
    p.add_argument("--guards", default=None,
                   help="comma list overriding the profile guard set "
                        "(explicitly named guards are REQUIRED unless also in "
                        "--allow-missing-guards)")
    p.add_argument("--allow-missing-guards", default="",
                   help="comma list of guards demoted to optional: load failure "
                        "-> skip + record, not exit 2")
    p.add_argument("--task", default=None,
                   help="optional task_type filter applied before routing")
    p.add_argument("--max-samples", type=int, default=None,
                   help="limit the number of valid records (smoke tests)")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--rule-score", action="store_true",
                   help="opt-in EXPERIMENTAL pseudo score for the rule baseline")
    p.add_argument("--hf-token", default=None, help="HuggingFace token (gated models)")
    p.add_argument("--cache-dir", default=None, help="HF download cache dir")
    p.add_argument("--prediction-cache-dir", default=None,
                   help="versioned per-record prediction cache root "
                        "(default: <skill>/.cache; key includes model revision, "
                        "template, taxonomy and code versions)")
    p.add_argument("--no-cache", action="store_true",
                   help="disable the prediction cache (P2.F ablation)")
    p.add_argument("--backend", choices=["transformers", "vllm"], default="transformers")
    return p.parse_args(argv)


def resolve_guard_sets(args: argparse.Namespace) -> Dict[str, List[str]]:
    """Plan r3 rule: explicit --guards names are all required unless also
    allow-missing; extensions are implicitly optional only under --profile all
    when --guards was NOT given."""
    known = set(PROFILES["all"])
    if args.guards:
        active = [g.strip() for g in args.guards.split(",") if g.strip()]
        implicit_optional: set = set()
    else:
        active = list(PROFILES[args.profile])
        implicit_optional = EXTENSION_GUARDS if args.profile == "all" else set()
    unknown = [g for g in active if g not in known]
    if unknown:
        raise utils.FatalInputError(
            f"unknown guard(s): {', '.join(unknown)}. Known: {', '.join(sorted(known))}")
    allow_missing = {g.strip() for g in args.allow_missing_guards.split(",") if g.strip()}
    allow_missing |= implicit_optional
    return {
        "active": active,
        "required": [g for g in active if g not in allow_missing],
        "optional": [g for g in active if g in allow_missing],
    }


def run(args: argparse.Namespace) -> int:
    t0 = time.perf_counter()
    sets = resolve_guard_sets(args)
    utils.set_seed(args.seed)

    records, skipped = utils.load_valid_records(args.input)
    raw_total = sum(skipped.values()) + len(records)
    parsed_total = raw_total - skipped.get("blank", 0) - skipped.get("malformed_json", 0)
    if args.task:
        records = [r for r in records if r["task_type"] == args.task]
    if args.max_samples is not None:
        records = records[: args.max_samples]
    if not records:
        raise utils.FatalInputError(
            "zero valid records after parsing/filtering - nothing to evaluate "
            f"(skipped: {dict(skipped)})")

    out_dir = Path(args.out)
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise utils.FatalInputError(f"cannot create output dir {out_dir}: {exc}") from exc

    meta: Dict[str, Any] = {
        "created_at": utils.utc_now_iso(),
        "command": " ".join(sys.argv),
        "seed": args.seed,
        "task_filter": args.task,
        "versions": {
            "python": sys.version.split()[0],
            "skill": __version__,
            "taxonomy_version": utils.load_config().get("taxonomy_version"),
            "code_version": utils.code_version(),
            "packages": utils.package_versions(
                ["transformers", "torch", "accelerate", "openai"]),
        },
        "raw_total": raw_total,
        "parsed_total": parsed_total,
        "valid_total": len(records),
        "skipped": dict(skipped),
        "skipped_guards": [],
        "guards": {},
    }

    required_failures: List[str] = []
    for name in sets["active"]:
        print(f"==> guard {name}: loading", file=sys.stderr)
        try:
            guard = _make_guard(name, args)
            guard.load()
        except (GuardLoadError, ImportError, Exception) as exc:  # noqa: BLE001
            print(utils.explain_load_error(name, exc), file=sys.stderr)
            if name in sets["required"]:
                required_failures.append(name)
                meta["guards"][name] = {"load_error": str(exc), "required": True}
            else:
                meta["skipped_guards"].append(name)
                meta["guards"][name] = {"load_error": str(exc), "required": False}
            continue

        g_start = time.perf_counter()
        routes, out_of_scope, rec_by_id = [], 0, {}
        for rec in records:
            rt = utils.route(rec, guard.capabilities)
            if rt is None:
                out_of_scope += 1
            else:
                routes.append(rt)
                rec_by_id[rec["id"]] = rec
        # Versioned prediction cache (resume support): error rows are never
        # cached, so an interrupted/failed record retries on the next run.
        cache = None
        if not args.no_cache:
            cache_root = Path(args.prediction_cache_dir) if args.prediction_cache_dir \
                else utils.SKILL_DIR / ".cache"
            cache = utils.JsonCache(cache_root)
        taxonomy_version = meta["versions"]["taxonomy_version"]
        code_ver = meta["versions"]["code_version"]

        def _key(rt):
            return utils.cache_key(
                record_id=rt.record_id,
                record_hash=utils.record_hash(rec_by_id[rt.record_id]),
                guard_name=name, model_id=guard.model_id,
                model_revision=guard.model_revision,
                prompt_template_version=guard.prompt_template_version,
                taxonomy_version=taxonomy_version, code_version=code_ver,
                confidence_method=guard.confidence_method)

        rows_by_id: Dict[str, Dict[str, Any]] = {}
        to_predict: List[Any] = []
        if cache is not None:
            for rt in routes:
                hit = cache.get(name, _key(rt))
                if hit is not None:
                    rows_by_id[rt.record_id] = hit
                else:
                    to_predict.append(rt)
        else:
            to_predict = routes
        for row in guard.predict_batch(to_predict):
            rows_by_id[row["id"]] = row
            if cache is not None and row["error"] is None:
                rt = next(r for r in to_predict if r.record_id == row["id"])
                cache.put(name, _key(rt), row)
        rows = [rows_by_id[rt.record_id] for rt in routes]
        out_path = out_dir / f"guard_output.{name}.jsonl"
        with out_path.open("w", encoding="utf-8", newline="\n") as f:
            for row in rows:
                f.write(utils.json_dumps(row) + "\n")
        answered = sum(1 for r in rows
                       if r["error"] is None and r["prediction"]["is_unsafe"] is not None)
        errors = len(rows) - answered
        eligible = len(rows)
        meta["guards"][name] = {
            "eligible_total": eligible,
            "answered_total": answered,
            "out_of_scope": out_of_scope,
            "errors": errors,
            "coverage": round(answered / eligible, 4) if eligible else None,
            "error_rate": round(errors / eligible, 4) if eligible else None,
            "cache_hits": cache.hits if cache else 0,
            "cache_misses": cache.misses if cache else 0,
            "cache_hit_rate": round(cache.hit_rate, 4) if cache else 0.0,
            "confidence_method": guard.confidence_method,
            "confidence_status": guard.confidence_status,
            "model_id": guard.model_id,
            "model_revision": guard.model_revision,
            "prompt_template_version": guard.prompt_template_version,
            "device": guard.device,
            "wall_clock_s": round(time.perf_counter() - g_start, 3),
        }
        print(f"    {name}: eligible={eligible} answered={answered} "
              f"errors={errors} out_of_scope={out_of_scope} -> {out_path}",
              file=sys.stderr)

    meta["wall_clock_s"] = round(time.perf_counter() - t0, 3)
    meta["required_guard_failures"] = required_failures
    utils.write_metadata(out_dir / "metadata.json", meta)

    print("\n" + "=" * 60, file=sys.stderr)
    print("SUMMARY", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(f"  records: raw={meta['raw_total']} valid={meta['valid_total']} "
          f"skipped={meta['skipped']}", file=sys.stderr)
    for name, g in meta["guards"].items():
        if "load_error" in g:
            status = "FAILED (required)" if g.get("required") else "skipped (optional)"
            print(f"  {name:<12} {status}: {g['load_error']}", file=sys.stderr)
        else:
            print(f"  {name:<12} eligible={g['eligible_total']} "
                  f"answered={g['answered_total']} errors={g['errors']} "
                  f"coverage={g['coverage']}", file=sys.stderr)
    print(f"  metadata: {out_dir / 'metadata.json'}", file=sys.stderr)

    if required_failures:
        print(f"RESULT: FAIL (required guard(s) failed: "
              f"{', '.join(required_failures)}) -> exit 2", file=sys.stderr)
        return EXIT_REQUIRED_GUARD_FAILED
    print("RESULT: OK -> exit 0", file=sys.stderr)
    return EXIT_OK


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    try:
        return run(args)
    except utils.FatalInputError as exc:
        print(f"FATAL: {exc}", file=sys.stderr)
        return EXIT_FATAL


if __name__ == "__main__":
    raise SystemExit(main())
