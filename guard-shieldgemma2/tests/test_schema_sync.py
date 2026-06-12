"""schemas/guard_output.schema.json must stay byte-identical to the upstream copy.

M3_SPEC 9-1 / plan AD-1: only the schema carries the byte-equality requirement
(validate.py/metrics.py are controlled copies with documented thin diffs). When
this skill is distributed without its sibling, the assertion skips with a note.
"""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCAL_SCHEMA = ROOT / "schemas" / "guard_output.schema.json"
UPSTREAM_SCHEMA = ROOT.parent / "guard-llama-guard" / "schemas" / "guard_output.schema.json"


class TestSchemaSync(unittest.TestCase):
    def test_schema_byte_identical_to_upstream(self):
        if not UPSTREAM_SCHEMA.is_file():
            self.skipTest("upstream guard-llama-guard not present beside this skill "
                          "(standalone distribution); byte-equality not checkable")
        self.assertEqual(
            LOCAL_SCHEMA.read_bytes(),
            UPSTREAM_SCHEMA.read_bytes(),
            "guard_output.schema.json diverged from guard-llama-guard — the shared "
            "output contract must be changed on both sides via Ask-first (M3_SPEC 8)",
        )


if __name__ == "__main__":
    unittest.main()
