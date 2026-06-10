"""Core test suite for guard-llama-guard (Core-Minimal scope, no model deps).

Run: python -m pytest tests/ -q   (from the guard-llama-guard/ directory)
"""
from __future__ import annotations

import json
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = SKILL_DIR / "config" / "category_mapping.json"

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
        from guard_llama_guard import utils
        records, skipped = utils.load_valid_records(TINY_PATH)
        assert len(records) == 8
        assert sum(skipped.values()) == 0

    def test_load_valid_records_counts_all_skip_kinds(self):
        from guard_llama_guard import utils
        records, skipped = utils.load_valid_records(MALFORMED_PATH)
        assert records == []
        assert skipped["malformed_json"] >= 1
        assert skipped["schema_invalid"] >= 1
        assert skipped["blank"] >= 1

    def test_missing_file_is_fatal(self):
        from guard_llama_guard import utils
        import pytest
        with pytest.raises(utils.FatalInputError):
            utils.load_valid_records(SKILL_DIR / "nope.jsonl")

    def test_validate_record_rejects_bad_records(self):
        from guard_llama_guard import utils
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
        from guard_llama_guard import utils
        records, _ = utils.load_valid_records(TINY_PATH)
        routes = [utils.route(r, TEXT_CAPS) for r in records]
        eligible = [rt for rt in routes if rt is not None]
        assert len(eligible) == 7  # 8 records, image one is out of scope for text caps
        pair = next(rt for r, rt in zip(records, routes)
                    if rt and r["task_type"] == "prompt_response_safety")
        assert pair.prompt and pair.response

    def test_build_guard_output_schema(self):
        from guard_llama_guard import utils
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
        from guard_llama_guard import utils
        base = dict(record_id="a", record_hash="h", guard_name="rule",
                    model_id="m", model_revision="r1", prompt_template_version="t1",
                    taxonomy_version="x1", code_version="c1", confidence_method="cm")
        k1 = utils.cache_key(**base)
        k2 = utils.cache_key(**{**base, "model_revision": "r2"})
        assert k1 != k2
        assert k1 == utils.cache_key(**base)

    def test_cache_roundtrip(self, tmp_path):
        from guard_llama_guard import utils
        cache = utils.JsonCache(tmp_path)
        assert cache.get("rule", "k1") is None
        cache.put("rule", "k1", {"x": 1})
        assert cache.get("rule", "k1") == {"x": 1}

    def test_explain_load_error_mentions_fix(self):
        from guard_llama_guard import utils
        msg = utils.explain_load_error("llama_guard", Exception("401 gated repo"))
        assert "FIX" in msg and "huggingface" in msg.lower()
