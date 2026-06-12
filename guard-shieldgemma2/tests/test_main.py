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


class TestErrorQuadrants(unittest.TestCase):
    """The four error names of M3_SPEC 4.2/4.4, asserted verbatim (task 8)."""

    EXPECTED = {
        "synthimg:test:000004": "image_url_not_supported",
        "synthimg:test:000005": "image_not_found",
        "synthimg:test:000006": "image_decode_error",
        "synthimg:test:000007": "missing_caption_ocr",
    }

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        out = Path(cls.tmp.name) / "out"
        run_main(["--input", str(FIXTURE), "--output-dir", str(out),
                  "--guards", "caption-rule"])
        cls.by_id = {row["id"]: row for row in
                     read_rows(out / "predictions" / "caption-rule.predictions.jsonl")}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_error_names_verbatim(self):
        for record_id, prefix in self.EXPECTED.items():
            row = self.by_id[record_id]
            self.assertIsNone(row["prediction"]["is_unsafe"], record_id)
            self.assertTrue(row["error"].startswith(prefix),
                            f"{record_id}: {row['error'][:60]!r} !~ {prefix}")

    def test_non_error_rows_have_no_error(self):
        for record_id in ("synthimg:test:000001", "synthimg:test:000002",
                          "synthimg:test:000003", "synthimg:test:000008"):
            self.assertIsNone(self.by_id[record_id]["error"], record_id)


class TestMultiImageLanding(unittest.TestCase):
    """AD-7: the three fixed landing points, and no empty placeholders."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "out"
        run_main(["--input", str(FIXTURE), "--output-dir", str(cls.out),
                  "--guards", "caption-rule"])
        cls.rows = {row["id"]: row for row in
                    read_rows(cls.out / "predictions" / "caption-rule.predictions.jsonl")}
        cls.metadata = json.loads(
            (cls.out / "run_metadata.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_run_metadata_counter(self):
        self.assertEqual(self.metadata["warnings"]["multi_image_records"], 1)

    def test_row_level_landing_points(self):
        row = self.rows["synthimg:test:000008"]
        self.assertEqual(row["prediction"]["warnings"], ["multi_image_first_only"])
        self.assertEqual(row["raw_output"]["image_index"], 0)

    def test_single_image_rows_carry_no_warnings_key(self):
        for record_id, row in self.rows.items():
            if record_id == "synthimg:test:000008":
                continue
            self.assertNotIn("warnings", row["prediction"], record_id)

    def test_no_warnings_key_without_multi_image(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        from make_synth_images import solid  # noqa: E402
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "img").mkdir()
            (Path(tmp) / "img" / "a.png").write_bytes(solid(8, (1, 2, 3)))
            record = {"id": "synthimg:test:777001", "task_type": "image_safety",
                      "modality": ["image"],
                      "content": {"images": [{"path": "img/a.png", "url": None,
                                              "caption": "a plain wall", "ocr": None}]},
                      "label": {"target": "image", "is_unsafe": False,
                                "policy_action": "allow", "canonical_categories": []}}
            dataset = Path(tmp) / "single.jsonl"
            dataset.write_text(json.dumps(record) + "\n", encoding="utf-8")
            out = Path(tmp) / "out"
            code, _ = run_main(["--input", str(dataset), "--output-dir", str(out),
                                "--guards", "caption-rule"])
            self.assertEqual(code, 0)
            metadata = json.loads((out / "run_metadata.json").read_text(encoding="utf-8"))
            self.assertNotIn("warnings", metadata)


class TestResume(unittest.TestCase):
    def test_resume_skips_existing_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            run_main(["--input", str(FIXTURE), "--output-dir", str(out),
                      "--guards", "caption-rule"])
            code, _ = run_main(["--input", str(FIXTURE), "--output-dir", str(out),
                                "--guards", "caption-rule", "--resume"])
            self.assertEqual(code, 0)
            metadata = json.loads((out / "run_metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["resume_hits"], 8)
            self.assertEqual(metadata["resume_misses"], 0)
            self.assertEqual(metadata["counts"]["predicted"], 0)
            self.assertEqual(metadata["counts"]["errors"], 0)
            rows = read_rows(out / "predictions" / "caption-rule.predictions.jsonl")
            self.assertEqual(len(rows), 8)  # conservation regardless of resume


class TestDirectoryInput(unittest.TestCase):
    """Directory mode + path-resolution base (待甲确认.md #5 point 1, review I-2).

    Two JSONL files discovered from one input directory; relative image paths
    must resolve against the JSONL files' own directory — never the CWD (the
    test deliberately references images that do not exist relative to CWD).
    """

    def test_two_files_resolve_against_their_directory(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        from make_synth_images import solid  # noqa: E402

        def record(rid, path, caption):
            return {"id": rid, "task_type": "image_safety", "modality": ["image"],
                    "content": {"images": [{"path": path, "url": None,
                                            "caption": caption, "ocr": None}]},
                    "label": {"target": "image", "is_unsafe": False,
                              "policy_action": "allow", "canonical_categories": []}}

        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "unified"
            (data / "images").mkdir(parents=True)
            (data / "images" / "a.png").write_bytes(solid(8, (10, 20, 30)))
            (data / "part1.jsonl").write_text(
                json.dumps(record("synthimg:test:888001", "images/a.png", "a plain wall"))
                + "\n", encoding="utf-8")
            (data / "part2.jsonl").write_text(
                json.dumps(record("synthimg:test:888002", "images/a.png", "another wall"))
                + "\n", encoding="utf-8")
            out = Path(tmp) / "out"
            code, _ = run_main(["--input", str(data), "--output-dir", str(out),
                                "--guards", "caption-rule"])
            self.assertEqual(code, 0)
            rows = read_rows(out / "predictions" / "caption-rule.predictions.jsonl")
            self.assertEqual(len(rows), 2)  # both files discovered and aggregated
            for row in rows:
                self.assertIsNone(row["error"], row["id"])  # resolution hit the image


class TestExitPrecedents(unittest.TestCase):
    def test_all_unknown_guards_is_fatal(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, stdout = run_main(["--input", str(FIXTURE),
                                     "--output-dir", str(Path(tmp) / "out"),
                                     "--guards", "no-such-guard"])
            self.assertEqual(code, 1)
            self.assertIn("RESULT: fatal", stdout)

    def test_unknown_plus_caption_rule_is_partial(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, stdout = run_main(["--input", str(FIXTURE),
                                     "--output-dir", str(Path(tmp) / "out"),
                                     "--guards", "caption-rule,no-such-guard"])
            self.assertEqual(code, 2)
            self.assertIn("RESULT: partial", stdout)

    def test_zero_parsable_records_is_fatal(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "empty.jsonl"
            empty.write_text("", encoding="utf-8")
            code, stdout = run_main(["--input", str(empty),
                                     "--output-dir", str(Path(tmp) / "out"),
                                     "--guards", "caption-rule"])
            self.assertEqual(code, 1)
            self.assertIn("RESULT: fatal", stdout)


if __name__ == "__main__":
    unittest.main()
