"""Foundation utilities for guard-llama-guard (pure stdlib).

Covers: unified-JSONL loading with the three record-level skip kinds
(blank / malformed_json / schema_invalid), input schema validation,
capability-based routing (eligible vs out_of_scope), unified guard-output
construction, versioned cache keys + JSON cache, metadata writing, seeding,
and actionable load-error hints. Contract: references/schema.md.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

SKILL_DIR = Path(__file__).resolve().parents[2]
CONFIG_PATH = SKILL_DIR / "config" / "category_mapping.json"

TASK_TYPES = {
    "prompt_only_safety", "response_only_safety", "prompt_response_safety",
    "conversation_safety", "refusal_detection", "jailbreak_detection",
    "image_safety", "image_text_safety", "video_safety",
}
TARGETS = {
    "prompt", "response", "prompt_response_pair", "conversation",
    "image", "image_text_pair", "video",
}
POLICY_ACTIONS = {"allow", "refuse", "safe_complete", "warn", "redirect",
                  "escalate", "uncertain"}


class FatalInputError(Exception):
    """Pre-run error: the task cannot start (CLI maps this to exit 3)."""


def load_config() -> Dict[str, Any]:
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return json.load(f)


# --------------------------------------------------------------------------- #
# Input loading & validation (fatal vs record-level skip — schema.md §4)
# --------------------------------------------------------------------------- #
def _nonempty(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return value is not None


def validate_record(rec: Any) -> Tuple[bool, Optional[str]]:
    """Required-field check per schema.md §1. Returns (ok, reason)."""
    if not isinstance(rec, dict):
        return False, "record is not a JSON object"
    if not (isinstance(rec.get("id"), str) and rec["id"].strip()):
        return False, "id missing/empty"
    source = rec.get("source")
    if not (isinstance(source, dict) and _nonempty(source.get("dataset"))):
        return False, "source.dataset missing"
    task = rec.get("task_type")
    if task not in TASK_TYPES:
        return False, f"task_type invalid: {task!r}"
    content = rec.get("content")
    if not isinstance(content, dict):
        return False, "content missing"
    content_fields = ("prompt", "response", "conversation", "images", "videos", "audio")
    if not any(_nonempty(content.get(k)) for k in content_fields):
        return False, "content has no non-empty field"
    label = rec.get("label")
    if not isinstance(label, dict):
        return False, "label missing"
    if label.get("target") not in TARGETS:
        return False, f"label.target invalid: {label.get('target')!r}"
    if not isinstance(label.get("is_unsafe"), bool):
        return False, f"label.is_unsafe must be a real bool, got {label.get('is_unsafe')!r}"
    if label.get("policy_action") not in POLICY_ACTIONS:
        return False, f"label.policy_action invalid: {label.get('policy_action')!r}"
    if not isinstance(label.get("canonical_categories"), list):
        return False, "label.canonical_categories must be a list"
    # Conditional requirements (schema.md §1).
    if task in ("image_safety", "image_text_safety") and not _nonempty(content.get("images")):
        return False, f"{task} requires non-empty content.images"
    if (task in ("response_only_safety",) or label.get("target") == "response") \
            and not _nonempty(content.get("response")):
        return False, f"{task}/target=response requires content.response"
    if task == "conversation_safety" and not _nonempty(content.get("conversation")):
        return False, "conversation_safety requires content.conversation"
    return True, None


def load_valid_records(path: Path | str) -> Tuple[List[Dict[str, Any]], Counter]:
    """Read unified JSONL. Returns (valid_records, skipped_counter).

    Raises FatalInputError if the file is missing/unreadable (exit 3 at the CLI).
    Per-line problems are NEVER fatal: they are counted in the returned Counter
    under blank / malformed_json / schema_invalid and the line is skipped.
    """
    path = Path(path)
    if not path.is_file():
        raise FatalInputError(f"input file not found: {path}")
    skipped: Counter = Counter()
    records: List[Dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise FatalInputError(f"cannot read input file {path}: {exc}") from exc
    for line in text.split("\n"):
        if line.strip() == "":
            # Trailing newline produces one empty tail entry; only count blanks
            # that sit between content lines (a lone final "" is the EOF artifact).
            skipped["blank"] += 1
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            skipped["malformed_json"] += 1
            continue
        ok, _reason = validate_record(rec)
        if not ok:
            skipped["schema_invalid"] += 1
            continue
        records.append(rec)
    # The split() EOF artifact: a well-formed file ends with "\n" -> one spurious
    # blank. Remove it so clean files report zero skips.
    if text.endswith("\n") and skipped["blank"] > 0:
        skipped["blank"] -= 1
    skipped += Counter()  # drop zero entries
    return records, skipped


# --------------------------------------------------------------------------- #
# Routing (eligible vs out_of_scope — schema.md §2/§4)
# --------------------------------------------------------------------------- #
@dataclass
class Route:
    """What a guard receives for one eligible record."""
    record_id: str
    task_type: str
    prompt: Optional[str] = None
    response: Optional[str] = None
    images: List[Dict[str, Any]] = field(default_factory=list)


def record_modalities(rec: Dict[str, Any]) -> List[str]:
    mods = rec.get("modality")
    if isinstance(mods, list) and mods:
        return [str(m) for m in mods]
    return ["image"] if rec.get("task_type", "").startswith("image") else ["text"]


def route(rec: Dict[str, Any], capabilities: Dict[str, Any]) -> Optional[Route]:
    """Build the guard input for one VALID record, or None if out of scope."""
    if rec.get("task_type") not in capabilities.get("tasks", []):
        return None
    if not set(record_modalities(rec)) <= set(capabilities.get("modalities", [])):
        return None
    content = rec.get("content", {})
    return Route(
        record_id=rec["id"],
        task_type=rec["task_type"],
        prompt=content.get("prompt"),
        response=content.get("response"),
        images=content.get("images") or [],
    )


def get_truth(rec: Dict[str, Any]) -> bool:
    """Core head-binary truth (schema.md §2)."""
    return bool(rec["label"]["is_unsafe"])


# --------------------------------------------------------------------------- #
# Guard output construction (schema.md §3)
# --------------------------------------------------------------------------- #
def build_guard_output(
    *,
    record_id: str,
    guard_name: str,
    guard_version: str,
    modalities: List[str],
    prediction: Optional[Dict[str, Any]] = None,
    raw_output: Optional[Dict[str, Any]] = None,
    latency_ms: Optional[int] = None,
    device: Optional[str] = None,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    pred = prediction or {}
    is_unsafe = pred.get("is_unsafe")
    if error is not None:
        is_unsafe = None  # a failed record never carries a usable verdict
    if is_unsafe is None:
        action = "uncertain"
    else:
        action = pred.get("action") or ("refuse" if is_unsafe else "allow")
    return {
        "id": record_id,
        "guard": {"name": guard_name, "version": guard_version,
                  "modality": list(modalities)},
        "prediction": {
            "is_unsafe": is_unsafe,
            "risk_categories": pred.get("risk_categories", []) if error is None else [],
            "severity": pred.get("severity"),
            "action": action,
            "confidence": pred.get("confidence") if error is None else None,
            "confidence_method": pred.get("confidence_method"),
        },
        "raw_output": raw_output or {},
        "runtime": {"latency_ms": latency_ms, "cost": None, "device": device},
        "error": error,
    }


# --------------------------------------------------------------------------- #
# Versioned cache (schema.md / plan Cache spec)
# --------------------------------------------------------------------------- #
def record_hash(rec: Dict[str, Any]) -> str:
    content = rec.get("content", {})
    payload = json.dumps(
        {"prompt": content.get("prompt"), "response": content.get("response"),
         "images": content.get("images"), "target": rec.get("label", {}).get("target")},
        ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def cache_key(*, record_id: str, record_hash: str, guard_name: str,
              model_id: Optional[str], model_revision: Optional[str],
              prompt_template_version: Optional[str], taxonomy_version: str,
              code_version: str, confidence_method: Optional[str]) -> str:
    payload = json.dumps({
        "record_id": record_id, "record_hash": record_hash,
        "guard_name": guard_name, "model_id": model_id,
        "model_revision": model_revision,
        "prompt_template_version": prompt_template_version,
        "taxonomy_version": taxonomy_version, "code_version": code_version,
        "confidence_method": confidence_method,
    }, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class JsonCache:
    """Per-guard JSON file cache: <root>/<guard_name>/<cache_key>.json."""

    def __init__(self, root: Path | str):
        self.root = Path(root)
        self.hits = 0
        self.misses = 0

    def _path(self, guard: str, key: str) -> Path:
        return self.root / guard / f"{key}.json"

    def get(self, guard: str, key: str) -> Optional[Dict[str, Any]]:
        p = self._path(guard, key)
        if p.is_file():
            try:
                payload = json.loads(p.read_text(encoding="utf-8"))
                self.hits += 1
                return payload
            except (OSError, json.JSONDecodeError):
                pass  # corrupt cache entry counts as a miss and gets rewritten
        self.misses += 1
        return None

    def put(self, guard: str, key: str, payload: Dict[str, Any]) -> None:
        p = self._path(guard, key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total else 0.0


# --------------------------------------------------------------------------- #
# Environment / metadata helpers
# --------------------------------------------------------------------------- #
def set_seed(seed: int) -> None:
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    try:  # optional deps — only if present
        import numpy as np  # type: ignore
        np.random.seed(seed)
    except Exception:
        pass
    try:
        import torch  # type: ignore
        torch.manual_seed(seed)
    except Exception:
        pass


def code_version() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=5,
                             cwd=str(SKILL_DIR))
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        pass
    return "unknown"


def package_versions(names: Iterable[str]) -> Dict[str, str]:
    import importlib.metadata as md
    versions = {}
    for name in names:
        try:
            versions[name] = md.version(name)
        except Exception:
            versions[name] = "not-installed"
    return versions


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_metadata(path: Path | str, meta: Dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str),
                    encoding="utf-8")


def explain_load_error(name: str, exc: Exception) -> str:
    """Actionable, copy-pasteable hints for a guard load failure."""
    msg = str(exc).lower()
    hints = [f"[{name}] failed to load: {exc}"]
    if any(k in msg for k in ("gated", "401", "403", "authenticated", "awaiting")):
        hints.append(
            "    FIX (gated model):\n"
            "      1) Open the model page on https://huggingface.co and click "
            "'Agree and access repository'.\n"
            "      2) Authenticate: hf auth login | huggingface-cli login | set HF_TOKEN=hf_xxx\n"
            "      3) Gated repos are NOT served by hf-mirror - use a direct connection, "
            "then re-run (reuse --cache-dir).\n"
            f"      Or degrade gracefully: --allow-missing-guards {name}")
    elif any(k in msg for k in ("no module named", "modulenotfound", "import")):
        hints.append(
            "    FIX (missing dependency): install the guard's requirements file, e.g.\n"
            f"      pip install -r requirements-{name.replace('_', '-')}.txt\n"
            f"      Or degrade gracefully: --allow-missing-guards {name}")
    elif any(k in msg for k in ("api key", "base_url", "llm_api_key")):
        hints.append(
            "    FIX (missing API config): set LLM_API_KEY / LLM_BASE_URL / LLM_MODEL "
            "environment variables.\n"
            f"      Or degrade gracefully: --allow-missing-guards {name}")
    else:
        hints.append(
            "    FIX: check network access and the model/dataset page on huggingface.co; "
            "if gated, authenticate as above.\n"
            f"      Or degrade gracefully: --allow-missing-guards {name}")
    return "\n".join(hints)


# --------------------------------------------------------------------------- #
# Self-test:  python -m guard_llama_guard.utils
#         or  python src/guard_llama_guard/utils.py   (no install needed)
# --------------------------------------------------------------------------- #
def _self_test() -> int:
    text_caps = {"modalities": ["text"],
                 "tasks": ["prompt_only_safety", "prompt_response_safety"]}
    tiny = SKILL_DIR / "examples" / "tiny_unified.jsonl"
    fixtures = SKILL_DIR / "tests" / "fixtures" / "tiny_malformed.jsonl"
    records, skipped = load_valid_records(tiny)
    routes = [route(r, text_caps) for r in records]
    eligible = sum(1 for r in routes if r is not None)
    print(f"tiny: {len(records)} valid, skips={dict(skipped)}, "
          f"text-eligible={eligible}, out_of_scope={len(records) - eligible}")
    bad_records, bad_skipped = load_valid_records(fixtures)
    print(f"fixtures: {len(bad_records)} valid, skips={dict(bad_skipped)}")
    ok = (len(records) == 8 and not skipped and eligible == 7
          and not bad_records and bad_skipped["malformed_json"] >= 1
          and bad_skipped["schema_invalid"] >= 1 and bad_skipped["blank"] >= 1)
    print("SELF-TEST:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(_self_test())
