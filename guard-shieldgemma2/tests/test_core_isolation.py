"""Core-Minimal isolation + golden sample locks (task 11; M3_SPEC 6-A).

1. The full caption-rule chain (main -> validate -> metrics) must run without
   importing any heavy third-party module (torch / transformers / PIL /
   bitsandbytes) — asserted on sys.modules after an in-process end-to-end run.
2. examples/metrics.sample.json is an exact-equality golden: re-running the
   chain on examples/input.sample.jsonl must reproduce it byte-for-value.
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
import metrics  # noqa: E402
import validate  # noqa: E402

EXAMPLES = ROOT / "examples"
HEAVY_MODULES = ("torch", "transformers", "PIL", "bitsandbytes")


def run_chain(tmp: Path):
    out = tmp / "out"
    silent = io.StringIO()
    with contextlib.redirect_stdout(silent):
        main_code = main_module.main([
            "--input", str(EXAMPLES / "input.sample.jsonl"),
            "--output-dir", str(out), "--guards", "caption-rule"])
        validate_code = validate.main([
            str(out / "predictions"), "--against", str(EXAMPLES / "input.sample.jsonl"),
            "--metadata", str(out / "run_metadata.json")])
        metrics_code = metrics.main([
            "--predictions", str(out / "predictions"),
            "--dataset", str(EXAMPLES / "input.sample.jsonl"),
            "--output-dir", str(out / "metrics"),
            "--by-category", "--adversarial-split"])
    return main_code, validate_code, metrics_code, out


class TestCoreIsolationAndGolden(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.codes = run_chain(Path(cls.tmp.name))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_chain_exit_codes(self):
        main_code, validate_code, metrics_code, _ = self.codes
        self.assertEqual((main_code, validate_code, metrics_code), (0, 0, 0))

    def test_no_heavy_module_imported(self):
        # Core-Minimal contract (M3_SPEC 6-A): the image pipeline runs the
        # whole chain without touching torch/transformers/PIL/bitsandbytes
        loaded = [name for name in HEAVY_MODULES if name in sys.modules]
        self.assertEqual(loaded, [], f"heavy modules leaked into the core chain: {loaded}")

    def test_metrics_sample_golden_exact(self):
        _, _, _, out = self.codes
        produced = json.loads((out / "metrics" / "metrics.json").read_text(encoding="utf-8"))
        golden = json.loads((EXAMPLES / "metrics.sample.json").read_text(encoding="utf-8"))
        self.assertEqual(produced, golden,
                         "metrics on examples/input.sample.jsonl diverged from the "
                         "frozen golden examples/metrics.sample.json")


if __name__ == "__main__":
    unittest.main()
