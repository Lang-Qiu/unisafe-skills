"""W4 — judge bounded concurrency (predict_batch). All transport mocked at
_post_chat (no network). Acceptance (M3.5_SPEC §3-W4):
  - capabilities.supports_batch tracks judge_concurrency (1 -> serial path)
  - predict_batch at concurrency 1 == serial predict(), id-for-id
  - concurrency >1 preserves input id order, no drop / no dup
  - success/error counts + per-id verdicts conserved between serial and concurrent
  - concurrent wall-time is materially (>=30%) below serial under a per-call sleep
  - main.py exposes --judge-concurrency (default 1)
"""
from __future__ import annotations

import json
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import main as main_module  # noqa: E402
from guards.llm_judge import LLMJudgeGuard  # noqa: E402


def _records(n, unsafe_idxs=(), fail_idxs=()):
    recs = []
    for i in range(n):
        prompt = f"benign content {i}"
        if i in unsafe_idxs:
            prompt = f"BOMBMARKER {i}"
        if i in fail_idxs:
            prompt = f"FAILME {i}"
        recs.append({"id": f"judge:test:{i:04d}", "task_type": "prompt_only_safety",
                     "modality": ["text"], "content": {"prompt": prompt, "response": None}})
    return recs


def _fake_post(sleep=0.0):
    def post(messages):  # patch.object replaces the method -> no self bound
        user = messages[-1]["content"]
        if "FAILME" in user:
            raise RuntimeError("boom")
        if sleep:
            time.sleep(sleep)
        verdict = "unsafe" if "BOMBMARKER" in user else "safe"
        return json.dumps({"verdict": verdict, "categories": [], "confidence": 0.8})
    return post


def _run_batch(concurrency, records, sleep=0.0):
    guard = LLMJudgeGuard({"judge_concurrency": concurrency})
    with mock.patch.object(LLMJudgeGuard, "_post_chat", side_effect=_fake_post(sleep)):
        return guard.predict_batch(records)


class TestJudgeConcurrency(unittest.TestCase):
    def test_capabilities_tracks_concurrency(self):
        self.assertFalse(LLMJudgeGuard({"judge_concurrency": 1}).capabilities["supports_batch"])
        self.assertTrue(LLMJudgeGuard({"judge_concurrency": 4}).capabilities["supports_batch"])
        self.assertFalse(LLMJudgeGuard({}).capabilities["supports_batch"])  # default serial

    def test_serial_equivalent_at_concurrency_1(self):
        recs = _records(5, unsafe_idxs=(1, 3))
        batch = _run_batch(1, recs)
        serial_guard = LLMJudgeGuard({})
        with mock.patch.object(LLMJudgeGuard, "_post_chat", side_effect=_fake_post()):
            serial = [serial_guard.predict(r) for r in recs]
        self.assertEqual(
            [(r["id"], r["prediction"]["is_unsafe"]) for r in batch],
            [(r["id"], r["prediction"]["is_unsafe"]) for r in serial])

    def test_order_and_completeness_concurrent(self):
        recs = _records(8, unsafe_idxs=(2, 5, 7))
        batch = _run_batch(4, recs, sleep=0.01)
        self.assertEqual([r["id"] for r in batch], [r["id"] for r in recs])  # order preserved
        self.assertEqual(len(batch), 8)  # no drop / no dup
        self.assertEqual([r["prediction"]["is_unsafe"] for r in batch],
                         [False, False, True, False, False, True, False, True])

    def test_conservation_with_errors_serial_vs_concurrent(self):
        recs = _records(6, unsafe_idxs=(1,), fail_idxs=(2, 4))

        def tally(out):
            errs = sum(1 for r in out if r["prediction"]["is_unsafe"] is None)
            preds = sum(1 for r in out if r["prediction"]["is_unsafe"] is not None)
            verdicts = [(r["id"], r["prediction"]["is_unsafe"]) for r in out]
            return errs, preds, verdicts

        e1, p1, v1 = tally(_run_batch(1, recs))
        e4, p4, v4 = tally(_run_batch(4, recs))
        self.assertEqual((e1, p1), (2, 4))     # 2 FAILME -> error rows, 4 success
        self.assertEqual((e1, p1), (e4, p4))   # counts conserved
        self.assertEqual(v1, v4)               # per-id verdicts identical

    def test_concurrent_is_at_least_30pct_faster(self):
        recs = _records(8)
        t0 = time.perf_counter(); _run_batch(1, recs, sleep=0.05); serial = time.perf_counter() - t0
        t0 = time.perf_counter(); _run_batch(4, recs, sleep=0.05); concurrent = time.perf_counter() - t0
        self.assertLess(concurrent, serial * 0.7)  # >=30% wall-time reduction

    def test_main_parser_has_judge_concurrency(self):
        args = main_module.build_parser().parse_args(
            ["--input", "x", "--output-dir", "y", "--judge-concurrency", "4"])
        self.assertEqual(args.judge_concurrency, 4)
        default = main_module.build_parser().parse_args(["--input", "x", "--output-dir", "y"])
        self.assertEqual(default.judge_concurrency, 1)


if __name__ == "__main__":
    unittest.main()
