"""main.py pipeline behavior on the synthetic image fixture.

Task-7 scope: conservation, counts, exit codes, dry-run. Task 8 extends this
file with the per-error-name quadrants, multi-image landing points, resume and
exit-code precedents (plan AD-6: serial edits 7 -> 8).
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import main as main_module  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "pipeline_dataset.jsonl"


def run_main(argv):
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        code = main_module.main(argv)
    return code, stdout.getvalue()


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()]


class TestMainPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "out"
        cls.code, cls.stdout = run_main([
            "--input", str(FIXTURE), "--output-dir", str(cls.out),
            "--guards", "caption-rule",
        ])
        cls.rows = read_rows(cls.out / "predictions" / "caption-rule.predictions.jsonl")
        cls.metadata = json.loads((cls.out / "run_metadata.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_exit_ok(self):
        self.assertEqual(self.code, 0)
        self.assertIn("RESULT: ok", self.stdout)

    def test_conservation(self):
        counts = self.metadata["counts"]
        self.assertEqual(counts["total"], 10)
        self.assertEqual(counts["eligible"], 8)
        self.assertEqual(counts["skipped"], {"out_of_scope": 1, "missing_content": 1})
        self.assertEqual(len(self.rows), counts["eligible"])  # one row per eligible record

    def test_predicted_and_errors_split(self):
        counts = self.metadata["counts"]
        self.assertEqual(counts["predicted"], 4)  # 0001/0002/0003/0008
        self.assertEqual(counts["errors"], 4)     # url-only / not-found / bad-magic / no-caption
        self.assertEqual(counts["predicted"] + counts["errors"], len(self.rows))

    def test_config_echo(self):
        config = self.metadata["config"]
        self.assertEqual(config["guards"], ["caption-rule"])
        self.assertIsNone(config["timeout_s"])
        self.assertIn("threshold", config)


class TestDryRun(unittest.TestCase):
    def test_dry_run_writes_no_predictions(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            code, stdout = run_main([
                "--input", str(FIXTURE), "--output-dir", str(out),
                "--guards", "caption-rule", "--dry-run",
            ])
            self.assertEqual(code, 0)
            self.assertFalse((out / "predictions").exists())
            self.assertTrue((out / "run_metadata.json").is_file())


if __name__ == "__main__":
    unittest.main()
