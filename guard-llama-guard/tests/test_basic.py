"""Core test suite for guard-llama-guard (Core-Minimal scope, no model deps).

Run: python -m pytest tests/ -q   (from the guard-llama-guard/ directory)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR / "scripts"))  # scripts/ layout (skill template)
CONFIG_PATH = SKILL_DIR / "assets" / "category_mapping.json"

# The 22 canonical categories + "other" (dataset-format-checker taxonomy.md).
CANONICAL = {
    "hate_discrimination", "harassment_bullying", "sexual_content", "child_safety",
    "self_harm", "violence", "weapons", "illicit_behavior", "cyber_safety", "drugs",
    "chemical_biological", "fraud_financial_crime", "privacy_pii", "extremism_terrorism",
    "misinformation", "copyright", "animal_abuse", "profanity_toxicity",
    "political_persuasion", "medical_safety", "legal_safety", "general_harm", "other",
}


class TestCategoryMapping:
    def _load(self):
        with CONFIG_PATH.open(encoding="utf-8") as f:
            return json.load(f)

    def test_config_loads_and_has_required_tables(self):
        cfg = self._load()
        assert cfg["taxonomy_version"]
        assert "llama_guard_s_to_canonical" in cfg
        assert "openai_to_canonical" in cfg  # kept for the llm_judge extension
        assert "rule_keyword_map" in cfg

    def test_llama_guard_mapping_spot_checks(self):
        m = self._load()["llama_guard_s_to_canonical"]
        assert set(m.keys()) == {f"S{i}" for i in range(1, 15)}
        assert m["S2"] == ["illicit_behavior"]
        assert m["S14"] == ["cyber_safety"]
        assert m["S4"] == ["child_safety"]
        assert set(m["S6"]) == {"medical_safety", "legal_safety"}

    def test_all_mapped_values_are_canonical(self):
        cfg = self._load()
        for table in ("llama_guard_s_to_canonical", "openai_to_canonical"):
            for src, cats in cfg[table].items():
                assert isinstance(cats, list), f"{table}[{src}] must be a list"
                for c in cats:
                    assert c in CANONICAL, f"{table}[{src}] -> {c} not canonical"
        for cat in cfg["rule_keyword_map"]:
            assert cat in CANONICAL, f"rule_keyword_map key {cat} not canonical"

    def test_openai_mapping_spot_checks(self):
        m = self._load()["openai_to_canonical"]
        assert m["sexual"] == ["sexual_content"]
        assert m["sexual/minors"] == ["child_safety"]
        assert m["illicit/violent"] == ["weapons"]

    def test_rule_keywords_nonempty_and_lowercase(self):
        m = self._load()["rule_keyword_map"]
        assert len(m) >= 8, "rule baseline should cover a useful category spread"
        for cat, kws in m.items():
            assert kws, f"{cat} has no keywords"
            for kw in kws:
                assert kw == kw.lower(), f"keyword '{kw}' must be lowercase (matching is lowercased)"


TINY_PATH = SKILL_DIR / "examples" / "tiny_unified.jsonl"
MALFORMED_PATH = SKILL_DIR / "tests" / "fixtures" / "tiny_malformed.jsonl"


def _load_tiny():
    with TINY_PATH.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


class TestTinyDataset:
    def test_has_at_least_8_valid_records_with_unique_ids(self):
        recs = _load_tiny()
        assert len(recs) >= 8
        ids = [r["id"] for r in recs]
        assert len(set(ids)) == len(ids)

    def test_covers_required_shapes(self):
        recs = _load_tiny()
        # safe + unsafe prompt-only
        po = [r for r in recs if r["task_type"] == "prompt_only_safety"]
        assert any(r["label"]["is_unsafe"] is False for r in po)
        assert any(r["label"]["is_unsafe"] is True for r in po)
        # safe + unsafe prompt-response pairs
        pr = [r for r in recs if r["task_type"] == "prompt_response_safety"]
        assert any(r["label"]["is_unsafe"] is False for r in pr)
        assert any(r["label"]["is_unsafe"] is True for r in pr)
        # refusal-related sample
        assert any(r["label"].get("is_refusal") is True for r in recs)

    def test_has_safe_probe_and_adversarial_records(self):
        recs = _load_tiny()
        probes = [r for r in recs
                  if r.get("risk_metadata", {}).get("over_refusal_probe") is True]
        assert probes and all(r["label"]["is_unsafe"] is False for r in probes)
        assert any(r.get("risk_metadata", {}).get("adversarial") is True for r in recs)

    def test_has_url_image_record(self):
        recs = _load_tiny()
        imgs = [r for r in recs if r["task_type"] == "image_safety"]
        assert imgs, "need an image_safety record (url-based) for the E3 extension path"
        img = imgs[0]["content"]["images"][0]
        assert img.get("url"), "image must be url-based (local image files are gitignored)"

    def test_malformed_fixture_exercises_all_skip_kinds(self):
        raw_lines = MALFORMED_PATH.read_text(encoding="utf-8").split("\n")
        # at least one blank line in the middle of the content
        assert any(line.strip() == "" for line in raw_lines[:-1])
        parse_fail = valid_json_bad_schema = 0
        for line in raw_lines:
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                parse_fail += 1
                continue
            if "label" not in obj or "task_type" not in obj:
                valid_json_bad_schema += 1
        assert parse_fail >= 1, "need a malformed-JSON line"
        assert valid_json_bad_schema >= 1, "need a schema-invalid record"


TEXT_CAPS = {"modalities": ["text"],
             "tasks": ["prompt_only_safety", "prompt_response_safety"]}


class TestUtils:
    def test_load_valid_records_clean_file(self):
        import utils
        records, skipped = utils.load_valid_records(TINY_PATH)
        assert len(records) == 8
        assert sum(skipped.values()) == 0

    def test_load_valid_records_counts_all_skip_kinds(self):
        import utils
        records, skipped = utils.load_valid_records(MALFORMED_PATH)
        assert records == []
        assert skipped["malformed_json"] >= 1
        assert skipped["schema_invalid"] >= 1
        assert skipped["blank"] >= 1

    def test_missing_file_is_fatal(self):
        import utils
        import pytest
        with pytest.raises(utils.FatalInputError):
            utils.load_valid_records(SKILL_DIR / "nope.jsonl")

    def test_validate_record_rejects_bad_records(self):
        import utils
        ok, _ = utils.validate_record({"id": "x"})
        assert not ok
        bad_bool = {"id": "x", "source": {"dataset": "d"}, "task_type": "prompt_only_safety",
                    "content": {"prompt": "hi"},
                    "label": {"target": "prompt", "is_unsafe": "unsafe",
                              "policy_action": "refuse", "canonical_categories": []}}
        ok, reason = utils.validate_record(bad_bool)
        assert not ok and "is_unsafe" in reason
        empty_images = {"id": "x", "source": {"dataset": "d"}, "task_type": "image_safety",
                        "content": {"prompt": None, "images": []},
                        "label": {"target": "image", "is_unsafe": False,
                                  "policy_action": "allow", "canonical_categories": []}}
        ok, reason = utils.validate_record(empty_images)
        assert not ok

    def test_route_text_records_and_image_out_of_scope(self):
        import utils
        records, _ = utils.load_valid_records(TINY_PATH)
        routes = [utils.route(r, TEXT_CAPS) for r in records]
        eligible = [rt for rt in routes if rt is not None]
        assert len(eligible) == 7  # 8 records, image one is out of scope for text caps
        pair = next(rt for r, rt in zip(records, routes)
                    if rt and r["task_type"] == "prompt_response_safety")
        assert pair.prompt and pair.response

    def test_build_guard_output_schema(self):
        import utils
        row = utils.build_guard_output(
            record_id="tiny:test:000001",
            guard_name="rule", guard_version="0.1.0", modalities=["text"],
            prediction={"is_unsafe": True, "risk_categories": ["violence"],
                        "confidence": None},
            raw_output={"matched_keywords": ["kill"]}, latency_ms=1, device="cpu")
        assert set(row) == {"id", "guard", "prediction", "raw_output", "runtime", "error"}
        assert row["error"] is None
        p = row["prediction"]
        assert set(p) >= {"is_unsafe", "risk_categories", "severity", "action",
                          "confidence", "confidence_method"}
        assert p["action"] == "refuse"
        err_row = utils.build_guard_output(
            record_id="tiny:test:000002", guard_name="rule", guard_version="0.1.0",
            modalities=["text"], error="boom")
        assert err_row["prediction"]["is_unsafe"] is None
        assert err_row["error"] == "boom"
        assert err_row["prediction"]["action"] == "uncertain"

    def test_cache_key_is_versioned(self):
        import utils
        base = dict(record_id="a", record_hash="h", guard_name="rule",
                    model_id="m", model_revision="r1", prompt_template_version="t1",
                    taxonomy_version="x1", code_version="c1", confidence_method="cm")
        k1 = utils.cache_key(**base)
        k2 = utils.cache_key(**{**base, "model_revision": "r2"})
        assert k1 != k2
        assert k1 == utils.cache_key(**base)

    def test_cache_roundtrip(self, tmp_path):
        import utils
        cache = utils.JsonCache(tmp_path)
        assert cache.get("rule", "k1") is None
        cache.put("rule", "k1", {"x": 1})
        assert cache.get("rule", "k1") == {"x": 1}

    def test_explain_load_error_mentions_fix(self):
        import utils
        msg = utils.explain_load_error("llama_guard", Exception("401 gated repo"))
        assert "FIX" in msg and "huggingface" in msg.lower()


def _tiny_routes(caps):
    import utils
    records, _ = utils.load_valid_records(TINY_PATH)
    pairs = [(r, utils.route(r, caps)) for r in records]
    return [(r, rt) for r, rt in pairs if rt is not None]


class TestRuleGuard:
    def _guard(self, **kw):
        from guards.rule_based import RuleGuard
        g = RuleGuard(**kw)
        g.load()
        return g

    def test_capabilities_are_honest(self):
        g = self._guard()
        caps = g.capabilities
        assert caps["refusal"] is False
        assert caps["continuous_score"] is False
        assert caps["modalities"] == ["text"]

    def test_predictions_on_tiny(self):
        g = self._guard()
        verdicts = {}
        for rec, rt in _tiny_routes(g.capabilities):
            row = g.predict(rt)
            assert row["error"] is None
            verdicts[rec["id"]] = row["prediction"]
        assert verdicts["tiny:test:000001"]["is_unsafe"] is False  # study tips
        assert verdicts["tiny:test:000002"]["is_unsafe"] is True   # phishing
        assert "cyber_safety" in verdicts["tiny:test:000002"]["risk_categories"]
        assert verdicts["tiny:test:000003"]["is_unsafe"] is False  # refused lockpick
        assert verdicts["tiny:test:000004"]["is_unsafe"] is True   # firearm pair
        assert {"weapons", "illicit_behavior"} <= set(
            verdicts["tiny:test:000004"]["risk_categories"])
        assert verdicts["tiny:test:000006"]["is_unsafe"] is True   # probe FP by design
        assert verdicts["tiny:test:000007"]["is_unsafe"] is True   # hotwire jailbreak

    def test_no_confidence_by_default_but_experimental_score_optin(self):
        g = self._guard()
        routes = [rt for _, rt in _tiny_routes(g.capabilities)]
        row = g.predict(routes[1])  # phishing record
        assert row["prediction"]["confidence"] is None
        gs = self._guard(score_mode=True)
        row = gs.predict(routes[1])
        c = row["prediction"]["confidence"]
        assert c is not None and 0.0 <= c <= 1.0
        assert "experimental" in row["prediction"]["confidence_method"]

    def test_predict_batch_default_loops(self):
        g = self._guard()
        routes = [rt for _, rt in _tiny_routes(g.capabilities)]
        rows = g.predict_batch(routes)
        assert len(rows) == len(routes) == 7

    def test_per_record_exception_becomes_error_row(self):
        from guards.base import Guard

        class BoomGuard(Guard):
            name = "boom"
            version = "0"
            capabilities = {"refusal": False, "continuous_score": False,
                            "modalities": ["text"],
                            "tasks": ["prompt_only_safety", "prompt_response_safety"]}

            def _predict_one(self, route):
                raise RuntimeError("kaboom")

        g = BoomGuard()
        routes = [rt for _, rt in _tiny_routes(g.capabilities)]
        row = g.predict(routes[0])
        assert row["error"] and "kaboom" in row["error"]
        assert row["prediction"]["is_unsafe"] is None
        assert row["prediction"]["action"] == "uncertain"


import subprocess
import sys


def _run_main(args, cwd=None):
    cmd = [sys.executable, str(SKILL_DIR / "scripts" / "main.py")]
    return subprocess.run(cmd + args, capture_output=True, text=True,
                          cwd=str(cwd or SKILL_DIR), timeout=120)


def _read_jsonl(path):
    with Path(path).open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


class TestMainRuleOnlyE2E:
    def test_core_minimal_exit0_rows_equal_eligible(self, tmp_path):
        out = tmp_path / "smoke"
        res = _run_main(["--profile", "core-minimal",
                         "--input", "examples/tiny_unified.jsonl",
                         "--out", str(out)])
        assert res.returncode == 0, res.stderr
        rows = _read_jsonl(out / "guard_output.rule.jsonl")
        assert len(rows) == 7  # eligible_total: 8 valid - 1 image out_of_scope
        meta = json.loads((out / "metadata.json").read_text(encoding="utf-8"))
        assert meta["raw_total"] == 8
        assert meta["parsed_total"] == 8
        assert meta["valid_total"] == 8
        g = meta["guards"]["rule"]
        assert g["eligible_total"] == 7
        assert g["out_of_scope"] == 1
        assert g["answered_total"] == 7
        assert g["coverage"] == 1.0

    def test_runs_from_any_cwd(self, tmp_path):
        # scripts/main.py must work when invoked from outside the skill dir
        # (graders often run from the repo root).
        out = tmp_path / "smoke_b"
        res = _run_main(["--profile", "core-minimal",
                         "--input", str(SKILL_DIR / "examples" / "tiny_unified.jsonl"),
                         "--out", str(out)], cwd=SKILL_DIR.parent)
        assert res.returncode == 0, res.stderr
        assert len(_read_jsonl(out / "guard_output.rule.jsonl")) == 7

    def test_missing_input_is_exit3(self, tmp_path):
        res = _run_main(["--profile", "core-minimal",
                         "--input", "nope.jsonl", "--out", str(tmp_path / "x")])
        assert res.returncode == 3

    def test_all_invalid_records_is_exit3(self, tmp_path):
        res = _run_main(["--profile", "core-minimal",
                         "--input", "tests/fixtures/tiny_malformed.jsonl",
                         "--out", str(tmp_path / "x")])
        assert res.returncode == 3

    def test_unknown_guard_name_is_exit3(self, tmp_path):
        res = _run_main(["--guards", "definitely_not_a_guard",
                         "--input", "examples/tiny_unified.jsonl",
                         "--out", str(tmp_path / "x")])
        assert res.returncode == 3

    def test_mixed_input_skips_do_not_change_exit(self, tmp_path):
        mixed = tmp_path / "mixed.jsonl"
        mixed.write_text(TINY_PATH.read_text(encoding="utf-8")
                         + MALFORMED_PATH.read_text(encoding="utf-8"),
                         encoding="utf-8")
        out = tmp_path / "out"
        res = _run_main(["--profile", "core-minimal",
                         "--input", str(mixed), "--out", str(out)])
        assert res.returncode == 0, res.stderr
        meta = json.loads((out / "metadata.json").read_text(encoding="utf-8"))
        assert meta["valid_total"] == 8
        assert sum(meta["skipped"].values()) >= 3
        assert meta["guards"]["rule"]["eligible_total"] == 7

    def test_required_guard_load_failure_is_exit2(self, tmp_path):
        # llama_guard load must fail FAST in a clean offline env (missing
        # transformers, or - if installed - offline gated download) -> exit 2.
        import os
        env = dict(os.environ, HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
        env.pop("HF_TOKEN", None)
        res = subprocess.run(
            [sys.executable, str(SKILL_DIR / "scripts" / "main.py"),
             "--guards", "llama_guard",
             "--input", "examples/tiny_unified.jsonl",
             "--out", str(tmp_path / "x")],
            capture_output=True, text=True, cwd=str(SKILL_DIR),
            timeout=120, env=env)
        assert res.returncode == 2
        assert "FIX" in (res.stderr + res.stdout)

    def test_allow_missing_demotes_required_to_skip(self, tmp_path):
        out = tmp_path / "out"
        res = _run_main(["--profile", "core-full",
                         "--allow-missing-guards", "llama_guard",
                         "--input", "examples/tiny_unified.jsonl",
                         "--out", str(out)])
        assert res.returncode == 0, res.stderr
        meta = json.loads((out / "metadata.json").read_text(encoding="utf-8"))
        assert "llama_guard" in meta["skipped_guards"]
        assert (out / "guard_output.rule.jsonl").is_file()

    def test_max_samples_limits_valid_records(self, tmp_path):
        out = tmp_path / "out"
        res = _run_main(["--profile", "core-minimal", "--max-samples", "3",
                         "--input", "examples/tiny_unified.jsonl",
                         "--out", str(out)])
        assert res.returncode == 0, res.stderr
        meta = json.loads((out / "metadata.json").read_text(encoding="utf-8"))
        assert meta["valid_total"] == 3
        rows = _read_jsonl(out / "guard_output.rule.jsonl")
        assert len(rows) == meta["guards"]["rule"]["eligible_total"]


def _toy_record(n, unsafe, probe=False):
    rid = f"toy:test:{n:06d}"
    rec = {"id": rid, "source": {"dataset": "Toy", "split": "test"},
           "modality": ["text"], "task_type": "prompt_only_safety", "language": "en",
           "content": {"prompt": f"toy prompt {n}", "response": None,
                       "conversation": None, "images": [], "videos": [], "audio": []},
           "label": {"target": "prompt", "is_unsafe": unsafe,
                     "canonical_categories": ["violence"] if unsafe else [],
                     "policy_action": "refuse" if unsafe else "allow"},
           "risk_metadata": {"over_refusal_probe": True} if probe else {}}
    return rec


def _toy_row(n, pred, confidence=None, method=None, error=None):
    rid = f"toy:test:{n:06d}"
    p = {"is_unsafe": None if error else pred,
         "risk_categories": [], "severity": None,
         "action": "uncertain" if error else ("refuse" if pred else "allow"),
         "confidence": None if error else confidence, "confidence_method": method}
    return {"id": rid, "guard": {"name": "toy", "version": "0", "modality": ["text"]},
            "prediction": p, "raw_output": {}, "runtime": {"latency_ms": 1},
            "error": error}


def _write_jsonl(path, objs):
    with Path(path).open("w", encoding="utf-8", newline="\n") as f:
        for o in objs:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")


class TestMetricsV1:
    def _evaluate(self, tmp_path, records, rows):
        import metrics
        ds = tmp_path / "ds.jsonl"
        go = tmp_path / "guard_output.toy.jsonl"
        _write_jsonl(ds, records)
        _write_jsonl(go, rows)
        out = tmp_path / "reports"
        result = metrics.evaluate(ds, [go], out)
        return result, out

    def test_known_confusion_matrix_hand_checked(self, tmp_path):
        # truth: U U S S ; preds: U S U S -> TP=1 FN=1 FP=1 TN=1
        records = [_toy_record(1, True), _toy_record(2, True),
                   _toy_record(3, False), _toy_record(4, False)]
        rows = [_toy_row(1, True), _toy_row(2, False),
                _toy_row(3, True), _toy_row(4, False)]
        result, _ = self._evaluate(tmp_path, records, rows)
        m = result["toy"]["ALL"]["answered_only"]
        assert m["tp"] == 1 and m["fn"] == 1 and m["fp"] == 1 and m["tn"] == 1
        assert m["accuracy"] == 0.5
        assert m["recall"] == 0.5
        assert m["fpr"] == 0.5
        assert m["macro_f1"] == 0.5

    def test_error_rows_split_the_two_modes(self, tmp_path):
        # same 4 + a 5th unsafe record whose prediction errored
        records = [_toy_record(1, True), _toy_record(2, True),
                   _toy_record(3, False), _toy_record(4, False),
                   _toy_record(5, True)]
        rows = [_toy_row(1, True), _toy_row(2, False), _toy_row(3, True),
                _toy_row(4, False), _toy_row(5, None, error="timeout")]
        result, _ = self._evaluate(tmp_path, records, rows)
        ans = result["toy"]["ALL"]["answered_only"]
        faw = result["toy"]["ALL"]["failure_as_wrong"]
        assert ans["n"] == 4 and faw["n"] == 5
        assert ans["accuracy"] == 0.5
        assert faw["accuracy"] == 0.4          # error row counted as wrong
        assert result["toy"]["ALL"]["coverage"] == 0.8
        assert result["toy"]["ALL"]["error_rate"] == 0.2

    def test_probe_metric_and_auroc(self, tmp_path):
        records = [_toy_record(1, True), _toy_record(2, True),
                   _toy_record(3, False), _toy_record(4, False, probe=True)]
        rows = [_toy_row(1, True, 0.9, "model_prob"),
                _toy_row(2, True, 0.8, "model_prob"),
                _toy_row(3, False, 0.3, "model_prob"),
                _toy_row(4, True, 0.85, "model_prob")]  # probe flagged unsafe
        result, _ = self._evaluate(tmp_path, records, rows)
        m = result["toy"]["ALL"]["answered_only"]
        assert m["unsafe_fpr_on_safe_probe"] == 1.0
        # pairs: (.9,.3)+ (.9,.85)+ (.8,.3)+ (.8,.85)- -> AUROC = 3/4 = 0.75
        assert abs(m["auroc"] - 0.75) < 1e-9
        assert result["toy"]["ALL"]["auroc_status"] == "ok"

    def test_experimental_confidence_demotes_auroc(self, tmp_path):
        records = [_toy_record(1, True), _toy_record(2, False)]
        rows = [_toy_row(1, True, 0.9, "rule_keyword_score_experimental"),
                _toy_row(2, False, 0.1, "rule_keyword_score_experimental")]
        result, _ = self._evaluate(tmp_path, records, rows)
        assert result["toy"]["ALL"]["auroc_status"] == "experimental"

    def test_no_confidence_means_auroc_na(self, tmp_path):
        records = [_toy_record(1, True), _toy_record(2, False)]
        rows = [_toy_row(1, True), _toy_row(2, False)]
        result, _ = self._evaluate(tmp_path, records, rows)
        m = result["toy"]["ALL"]["answered_only"]
        assert m["auroc"] is None
        assert result["toy"]["ALL"]["auroc_status"] == "n/a"

    def test_join_misses_counted_and_all_missing_is_fatal(self, tmp_path):
        import metrics
        from utils import FatalInputError
        import pytest
        records = [_toy_record(1, True)]
        rows = [_toy_row(1, True), _toy_row(99, True)]
        result, _ = self._evaluate(tmp_path, records, rows)
        assert result["toy"]["join_misses"] == 1
        ds = tmp_path / "ds2.jsonl"
        go = tmp_path / "guard_output.none.jsonl"
        _write_jsonl(ds, [_toy_record(1, True)])
        _write_jsonl(go, [_toy_row(99, True)])
        with pytest.raises(FatalInputError):
            metrics.evaluate(ds, [go], tmp_path / "r2")

    def test_cli_end_to_end_on_tiny_rule_run(self, tmp_path):
        run_out = tmp_path / "run"
        res = _run_main(["--profile", "core-minimal",
                         "--input", "examples/tiny_unified.jsonl",
                         "--out", str(run_out)])
        assert res.returncode == 0, res.stderr
        rep = tmp_path / "reports"
        res2 = subprocess.run(
            [sys.executable, str(SKILL_DIR / "scripts" / "metrics.py"),
             "--dataset", "examples/tiny_unified.jsonl",
             "--guard-outputs", str(run_out),
             "--out", str(rep)],
            capture_output=True, text=True, cwd=str(SKILL_DIR), timeout=120)
        assert res2.returncode == 0, res2.stderr
        assert (rep / "summary.csv").is_file()
        md = (rep / "summary.md").read_text(encoding="utf-8")
        assert "unsafe_fpr_on_safe_probe" in md
        # rule on tiny: TP=3 TN=2 FP=2 FN=0 -> acc 5/7, recall 1.0, probe FPR 1.0
        result = json.loads((rep / "summary.json").read_text(encoding="utf-8"))
        m = result["rule"]["ALL"]["answered_only"]
        assert m["tp"] == 3 and m["tn"] == 2 and m["fp"] == 2 and m["fn"] == 0
        assert m["unsafe_fpr_on_safe_probe"] == 1.0
        assert m["auroc"] is None  # honest N/A for the rule baseline


class TestPredictionCache:
    def test_second_run_hits_cache(self, tmp_path):
        cache = tmp_path / "pcache"
        common = ["--profile", "core-minimal",
                  "--input", "examples/tiny_unified.jsonl",
                  "--prediction-cache-dir", str(cache)]
        res1 = _run_main(common + ["--out", str(tmp_path / "r1")])
        assert res1.returncode == 0, res1.stderr
        m1 = json.loads((tmp_path / "r1" / "metadata.json").read_text(encoding="utf-8"))
        assert m1["guards"]["rule"]["cache_misses"] == 7
        assert m1["guards"]["rule"]["cache_hits"] == 0
        res2 = _run_main(common + ["--out", str(tmp_path / "r2")])
        assert res2.returncode == 0, res2.stderr
        m2 = json.loads((tmp_path / "r2" / "metadata.json").read_text(encoding="utf-8"))
        assert m2["guards"]["rule"]["cache_hits"] == 7
        assert m2["guards"]["rule"]["cache_misses"] == 0
        rows = _read_jsonl(tmp_path / "r2" / "guard_output.rule.jsonl")
        assert len(rows) == 7  # resume returns identical row count

    def test_no_cache_disables_caching(self, tmp_path):
        cache = tmp_path / "pcache"
        res = _run_main(["--profile", "core-minimal",
                         "--input", "examples/tiny_unified.jsonl",
                         "--prediction-cache-dir", str(cache), "--no-cache",
                         "--out", str(tmp_path / "r1")])
        assert res.returncode == 0, res.stderr
        meta = json.loads((tmp_path / "r1" / "metadata.json").read_text(encoding="utf-8"))
        assert meta["guards"]["rule"]["cache_hits"] == 0
        assert meta["guards"]["rule"]["cache_misses"] == 0
        assert not cache.exists()


class TestPackagingExamples:
    def test_input_sample_records_are_schema_valid(self):
        import utils
        records, skipped = utils.load_valid_records(
            SKILL_DIR / "examples" / "input.sample.jsonl")
        assert records and sum(skipped.values()) == 0

    def test_output_sample_rows_match_guard_output_schema(self):
        rows = _read_jsonl(SKILL_DIR / "examples" / "output.sample.jsonl")
        assert rows
        for row in rows:
            assert set(row) == {"id", "guard", "prediction", "raw_output",
                                "runtime", "error"}
            assert set(row["prediction"]) >= {"is_unsafe", "risk_categories",
                                              "action", "confidence"}

    def test_readme_covers_the_operational_contract(self):
        text = (SKILL_DIR / "README.md").read_text(encoding="utf-8")
        for needle in ("requirements-core.txt", "exit 0", "exit 2", "exit 3",
                       "--allow-missing-guards", "hf-mirror",
                       "scripts/main.py", "scripts/metrics.py", "scripts/validate.py",
                       "index-url"):
            assert needle in text, f"README missing: {needle}"


class TestLlamaGuardAdapter:
    """Model-free unit tests: parsing, message building, category mapping,
    and the degradation path. Real inference is Core-Full (needs GPU + gated
    access) and is exercised via the module self-test on capable machines."""

    def test_parse_output_safe_and_unsafe(self):
        from guards.llama_guard import parse_output
        assert parse_output("safe") == (False, [])
        assert parse_output("\n\nsafe") == (False, [])
        assert parse_output("\n\nunsafe\nS2,S10") == (True, ["S2", "S10"])
        assert parse_output("unsafe\nS14") == (True, ["S14"])

    def test_parse_output_rejects_garbage(self):
        from guards.llama_guard import parse_output
        import pytest
        with pytest.raises(ValueError):
            parse_output("I think this is fine?")

    def test_map_s_codes_to_canonical(self):
        from guards.llama_guard import map_s_codes
        assert map_s_codes(["S2"]) == ["illicit_behavior"]
        assert set(map_s_codes(["S6"])) == {"medical_safety", "legal_safety"}
        assert map_s_codes(["S99"]) == ["other"]  # unknown stays explicit

    def test_build_messages_two_input_modes(self):
        from guards.llama_guard import build_messages
        from utils import Route
        po = build_messages(Route(record_id="x", task_type="prompt_only_safety",
                                  prompt="hello"))
        assert [m["role"] for m in po] == ["user"]
        pr = build_messages(Route(record_id="x", task_type="prompt_response_safety",
                                  prompt="q", response="a"))
        assert [m["role"] for m in pr] == ["user", "assistant"]
        assert pr[1]["content"] == "a"

    def test_load_failure_is_guard_load_error_with_hint(self):
        from guards.llama_guard import LlamaGuard
        from guards.base import GuardLoadError
        import os
        import pytest
        old = {k: os.environ.get(k) for k in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE")}
        os.environ["HF_HUB_OFFLINE"] = os.environ["TRANSFORMERS_OFFLINE"] = "1"
        try:
            with pytest.raises(GuardLoadError):
                LlamaGuard().load()
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
