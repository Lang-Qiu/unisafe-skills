"""validate.py on image-pipeline output (task 9).

Locks: real caption-rule output passes structure + bidirectional coverage +
metadata counts; the AD-7 additive field prediction.warnings is NOT rejected;
duplicates / coverage gaps / structural violations still fail loudly.
"""
from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import main as main_module  # noqa: E402
import validate  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "pipeline_dataset.jsonl"


def run(module, argv):
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        code = module.main(argv)
    return code, stdout.getvalue()


class TestValidateOnPipelineOutput(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "out"
        run(main_module, ["--input", str(FIXTURE), "--output-dir", str(cls.out),
                          "--guards", "caption-rule"])
        cls.pred = cls.out / "predictions" / "caption-rule.predictions.jsonl"

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_pass_with_against_and_metadata(self):
        code, stdout = run(validate, [str(cls := self.pred),
                                      "--against", str(FIXTURE),
                                      "--metadata", str(self.out / "run_metadata.json")])
        self.assertEqual(code, 0, stdout)
        self.assertIn("RESULT: PASS", stdout)

    def test_warnings_field_is_not_rejected(self):
        # the multi-image row (000008) carries prediction.warnings and passed
        # above; assert directly that check_record tolerates the additive field
        rows = [json.loads(line) for line in
                self.pred.read_text(encoding="utf-8").splitlines()]
        multi = next(r for r in rows if r["id"] == "synthimg:test:000008")
        self.assertIn("warnings", multi["prediction"])
        canonical = set(validate.canonical_categories())
        self.assertEqual(validate.check_record(multi, canonical), [])

    def test_duplicate_ids_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            duped = Path(tmp) / "duped.predictions.jsonl"
            content = self.pred.read_text(encoding="utf-8")
            first_line = content.splitlines()[0]
            duped.write_text(content + first_line + "\n", encoding="utf-8")
            code, stdout = run(validate, [str(duped), "--against", str(FIXTURE)])
            self.assertEqual(code, 1)
            self.assertIn("duplicate ids", stdout)

    def test_missing_prediction_fails_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            partial = Path(tmp) / "partial.predictions.jsonl"
            lines = self.pred.read_text(encoding="utf-8").splitlines()
            partial.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
            code, stdout = run(validate, [str(partial), "--against", str(FIXTURE)])
            self.assertEqual(code, 1)
            self.assertIn("missing predictions", stdout)


class TestCheckRecordRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.canonical = set(validate.canonical_categories())
        cls.base = {
            "id": "synthimg:test:000001",
            "guard": {"name": "caption-rule", "version": "1.0", "modality": ["image"]},
            "prediction": {"is_unsafe": False, "risk_categories": [], "severity": None,
                           "action": "allow", "confidence": None},
            "raw_output": {},
            "runtime": {"latency_ms": 0.1, "cost": None, "device": "cpu"},
            "error": None,
        }

    def _mutated(self, **overrides):
        record = json.loads(json.dumps(self.base))
        for dotted, value in overrides.items():
            target = record
            *parents, leaf = dotted.split(".")
            for key in parents:
                target = target[key]
            target[leaf] = value
        return record

    def test_clean_record_passes(self):
        self.assertEqual(validate.check_record(self.base, self.canonical), [])

    def test_string_is_unsafe_rejected(self):
        problems = validate.check_record(
            self._mutated(**{"prediction.is_unsafe": "unsafe"}), self.canonical)
        self.assertTrue(any("is_unsafe" in p for p in problems))

    def test_orphan_error_row_rejected(self):
        problems = validate.check_record(
            self._mutated(**{"prediction.is_unsafe": None}), self.canonical)
        self.assertTrue(any("orphan error" in p for p in problems))

    def test_legal_error_row_passes(self):
        record = self._mutated(**{"prediction.is_unsafe": None,
                                  "prediction.action": "uncertain"})
        record["error"] = "image_not_found: x"
        self.assertEqual(validate.check_record(record, self.canonical), [])

    def test_non_canonical_category_rejected(self):
        problems = validate.check_record(
            self._mutated(**{"prediction.risk_categories": ["alien_tech"]}), self.canonical)
        self.assertTrue(any("canonical" in p for p in problems))


if __name__ == "__main__":
    unittest.main()
