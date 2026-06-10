"""validate.py: structural PASS/FAIL, --against coverage, --metadata counts."""
import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

import main as main_mod  # noqa: E402
import validate  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
EXAMPLES = SKILL_ROOT / "examples"
GOLDEN = EXAMPLES / "output.sample.jsonl"
INPUT_SAMPLE = EXAMPLES / "input.sample.jsonl"


def run_validate(argv):
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = validate.main(argv)
    return code, buffer.getvalue()


class TestStructural(unittest.TestCase):
    def test_golden_passes(self):
        code, out = run_validate([str(GOLDEN)])
        self.assertEqual(code, 0, out)
        self.assertIn("RESULT: PASS", out)

    def test_fixture_predictions_pass(self):
        code, out = run_validate([str(FIXTURES / "mini_predictions.jsonl")])
        self.assertEqual(code, 0, out)

    def test_missing_id_fails_with_line_number(self):
        code, out = run_validate([str(FIXTURES / "bad_missing_id.jsonl")])
        self.assertEqual(code, 1)
        self.assertIn(":1:", out)
        self.assertIn("id", out)

    def test_string_is_unsafe_fails(self):
        code, out = run_validate([str(FIXTURES / "bad_string_unsafe.jsonl")])
        self.assertEqual(code, 1)
        self.assertIn("is_unsafe", out)

    def test_orphan_error_fails(self):
        code, out = run_validate([str(FIXTURES / "bad_orphan_error.jsonl")])
        self.assertEqual(code, 1)
        self.assertIn("orphan", out)

    def test_missing_target_is_usage_error(self):
        code, _ = run_validate([str(FIXTURES / "does_not_exist.jsonl")])
        self.assertEqual(code, 2)


class TestAgainstCoverage(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="guard-validate-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_golden_covers_eligible_bidirectionally(self):
        code, out = run_validate([str(GOLDEN), "--against", str(INPUT_SAMPLE)])
        self.assertEqual(code, 0, out)

    def test_missing_prediction_fails(self):
        lines = GOLDEN.read_text(encoding="utf-8").splitlines()
        target = self.tmp / "missing.predictions.jsonl"
        target.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
        code, out = run_validate([str(target), "--against", str(INPUT_SAMPLE)])
        self.assertEqual(code, 1)
        self.assertIn("missing predictions", out)

    def test_ghost_id_fails(self):
        rows = GOLDEN.read_text(encoding="utf-8").splitlines()
        ghost = json.loads(rows[0])
        ghost["id"] = "ghost:test:999999"
        target = self.tmp / "ghost.predictions.jsonl"
        target.write_text("\n".join(rows + [json.dumps(ghost)]) + "\n", encoding="utf-8")
        code, out = run_validate([str(target), "--against", str(INPUT_SAMPLE)])
        self.assertEqual(code, 1)
        self.assertIn("non-eligible ids", out)

    def test_image_skip_needs_no_prediction(self):
        # input has 1 image record; golden has no row for it; that must PASS
        code, out = run_validate([str(GOLDEN), "--against", str(INPUT_SAMPLE)])
        self.assertEqual(code, 0, out)


class TestMetadataChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="guard-meta-"))
        cls.out_dir = cls.tmp / "out"
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = main_mod.main([
                "--input", str(INPUT_SAMPLE),
                "--output-dir", str(cls.out_dir),
                "--guards", "rule",
            ])
        assert code == 0, buffer.getvalue()
        cls.metadata_path = cls.out_dir / "run_metadata.json"
        cls.predictions_dir = cls.out_dir / "predictions"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_consistent_metadata_passes(self):
        code, out = run_validate([
            str(self.predictions_dir),
            "--against", str(INPUT_SAMPLE),
            "--metadata", str(self.metadata_path),
        ])
        self.assertEqual(code, 0, out)

    def test_tampered_skip_count_fails(self):
        tampered = json.loads(self.metadata_path.read_text(encoding="utf-8"))
        tampered["counts"]["skipped"]["out_of_scope"] = 99
        tampered_path = self.tmp / "tampered.json"
        tampered_path.write_text(json.dumps(tampered), encoding="utf-8")
        code, out = run_validate([
            str(self.predictions_dir),
            "--against", str(INPUT_SAMPLE),
            "--metadata", str(tampered_path),
        ])
        self.assertEqual(code, 1)
        self.assertIn("out_of_scope", out)

    def test_no_metadata_skips_count_check(self):
        # the same tampered counts cannot fail when --metadata is not given
        code, out = run_validate([
            str(self.predictions_dir),
            "--against", str(INPUT_SAMPLE),
        ])
        self.assertEqual(code, 0, out)

    def test_metadata_without_against_is_usage_error(self):
        code, _ = run_validate([
            str(self.predictions_dir),
            "--metadata", str(self.metadata_path),
        ])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
