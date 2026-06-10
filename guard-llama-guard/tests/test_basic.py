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
