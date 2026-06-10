"""Rule baseline determinism + GuardAdapter protocol + golden-output lock."""
import copy
import json
import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from guards import get_adapter, known_guards  # noqa: E402
from utils import ROUTE_ELIGIBLE, iter_jsonl, route_record  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
EXAMPLES = SKILL_ROOT / "examples"


def load_jsonl(path):
    return [record for _, record, err in iter_jsonl(path) if err is None]


def eligible_records(path):
    return [r for r in load_jsonl(path) if route_record(r)[0] == ROUTE_ELIGIBLE]


def strip_latency(result):
    clone = copy.deepcopy(result)
    clone["runtime"].pop("latency_ms", None)
    return clone


class TestRouting(unittest.TestCase):
    def test_mini_unified_routing_counts(self):
        buckets = {}
        for record in load_jsonl(FIXTURES / "mini_unified.jsonl"):
            bucket, _ = route_record(record)
            buckets[bucket] = buckets.get(bucket, 0) + 1
        self.assertEqual(buckets, {"eligible": 5, "out_of_scope": 1, "missing_content": 1})


class TestRuleGuard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.adapter = get_adapter("rule")
        cls.records = eligible_records(FIXTURES / "mini_unified.jsonl")

    def test_registry_has_rule(self):
        self.assertIn("rule", known_guards())

    def test_available_without_third_party(self):
        ok, reason = self.adapter.available()
        self.assertTrue(ok, reason)

    def test_capabilities(self):
        caps = self.adapter.capabilities
        self.assertEqual(caps["supports_batch"], False)
        self.assertEqual(caps["returns_confidence"], False)
        self.assertEqual(caps["modalities"], ["text"])

    def test_deterministic_predictions(self):
        expected = [
            ("mini:test:000001", True, ["violence"], "refuse"),
            ("mini:test:000002", False, [], "allow"),
            ("mini:test:000003", True, ["cyber_safety"], "refuse"),
            ("mini:test:000004", True, ["weapons"], "refuse"),
            ("mini:test:000005", True, ["violence"], "refuse"),  # probe FP by design
        ]
        for record, (rid, is_unsafe, categories, action) in zip(self.records, expected):
            result = self.adapter.predict(record)
            prediction = result["prediction"]
            self.assertEqual(result["id"], rid)
            self.assertEqual(prediction["is_unsafe"], is_unsafe, rid)
            self.assertEqual(prediction["risk_categories"], categories, rid)
            self.assertEqual(prediction["action"], action, rid)
            self.assertIsNone(prediction["confidence"], rid)
            self.assertIsNone(prediction["severity"], rid)
            self.assertIsNone(result["error"], rid)
            self.assertEqual(result["guard"]["name"], "rule")

    def test_predict_is_repeatable(self):
        for record in self.records:
            first = strip_latency(self.adapter.predict(record))
            second = strip_latency(self.adapter.predict(record))
            self.assertEqual(first, second)

    def test_predict_batch_default_equals_loop(self):
        batch = [strip_latency(r) for r in self.adapter.predict_batch(self.records)]
        loop = [strip_latency(self.adapter.predict(r)) for r in self.records]
        self.assertEqual(batch, loop)


class TestGoldenOutput(unittest.TestCase):
    """examples/output.sample.jsonl is the frozen rule output on
    examples/input.sample.jsonl; field-level identical except runtime.latency_ms."""

    def test_golden_matches_fresh_run(self):
        adapter = get_adapter("rule")
        records = eligible_records(EXAMPLES / "input.sample.jsonl")
        golden = load_jsonl(EXAMPLES / "output.sample.jsonl")
        self.assertEqual(len(golden), 5)
        self.assertEqual(len(records), len(golden))
        for record, frozen in zip(records, golden):
            fresh = strip_latency(adapter.predict(record))
            self.assertEqual(fresh, strip_latency(frozen), record.get("id"))

    def test_golden_contains_no_error_rows(self):
        for row in load_jsonl(EXAMPLES / "output.sample.jsonl"):
            self.assertIsNone(row["error"])
            self.assertIsNotNone(row["prediction"]["is_unsafe"])


if __name__ == "__main__":
    unittest.main()
