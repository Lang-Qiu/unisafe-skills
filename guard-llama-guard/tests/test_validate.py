"""Tests for scripts/validate.py (guard-output schema validator)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR / "scripts"))

from validate import validate_row  # noqa: E402


def _run_validate(args):
    return subprocess.run(
        [sys.executable, str(SKILL_DIR / "scripts" / "validate.py")] + args,
        capture_output=True, text=True, cwd=str(SKILL_DIR), timeout=60)


GOOD_ROW = {"id": "x:1", "guard": {"name": "rule", "version": "0", "modality": ["text"]},
            "prediction": {"is_unsafe": True, "risk_categories": ["violence"],
                           "severity": None, "action": "refuse",
                           "confidence": 0.9, "confidence_method": "m"},
            "raw_output": {}, "runtime": {"latency_ms": 1}, "error": None}


class TestValidateRow:
    def test_good_row_passes(self):
        assert validate_row(GOOD_ROW) is None

    def test_error_row_invariant_enforced(self):
        bad = json.loads(json.dumps(GOOD_ROW))
        bad["error"] = "boom"  # error row but is_unsafe stays bool -> violation
        assert "is_unsafe=null" in validate_row(bad)
        ok = json.loads(json.dumps(GOOD_ROW))
        ok.update(error="boom")
        ok["prediction"].update(is_unsafe=None, action="uncertain", confidence=None)
        assert validate_row(ok) is None

    def test_bad_action_and_confidence_rejected(self):
        bad = json.loads(json.dumps(GOOD_ROW))
        bad["prediction"]["action"] = "panic"
        assert "action" in validate_row(bad)
        bad2 = json.loads(json.dumps(GOOD_ROW))
        bad2["prediction"]["confidence"] = 1.5
        assert "confidence" in validate_row(bad2)


class TestValidateCli:
    def test_output_sample_passes(self):
        res = _run_validate(["examples/output.sample.jsonl"])
        assert res.returncode == 0, res.stdout + res.stderr
        assert "RESULT: PASS" in res.stdout

    def test_dataset_file_fails_as_not_guard_output(self):
        res = _run_validate(["examples/tiny_unified.jsonl"])
        assert res.returncode == 2  # dataset rows are not guard-output rows

    def test_missing_path_is_fatal(self):
        res = _run_validate(["nope.jsonl"])
        assert res.returncode == 3
