"""M3.6 E1 — llama-guard threshold knob (AD-1).

Llama Guard is natively argmax (generates safe/unsafe token); confidence =
normalized p_unsafe is computed post-hoc. E1 adds a threshold knob:
is_unsafe = (confidence >= threshold) when confidence is available, else fall
back to the argmax verdict. threshold=0.5 is argmax-equivalent (argmax-unsafe iff
normalized p_unsafe > 0.5). Default = max_macro_f1 point 0.55 (calibration-notes).
The threshold logic is isolated in _apply_threshold so it tests without torch.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from guards.llama_guard import LlamaGuard  # noqa: E402


class TestLlamaThreshold(unittest.TestCase):
    def test_default_threshold_is_055(self):
        self.assertEqual(LlamaGuard({}).threshold, 0.55)

    def test_threshold_override_from_config(self):
        self.assertEqual(LlamaGuard({"threshold": 0.3}).threshold, 0.3)

    def test_threshold_applies_when_confidence_available(self):
        guard = LlamaGuard({"threshold": 0.55})
        # argmax said safe but conf 0.6 >= 0.55 -> unsafe (threshold overrides)
        self.assertTrue(guard._apply_threshold(False, 0.6))
        # argmax said unsafe but conf 0.5 < 0.55 -> safe (threshold overrides)
        self.assertFalse(guard._apply_threshold(True, 0.5))

    def test_fallback_to_argmax_when_confidence_none(self):
        guard = LlamaGuard({"threshold": 0.55})
        self.assertTrue(guard._apply_threshold(True, None))
        self.assertFalse(guard._apply_threshold(False, None))

    def test_threshold_half_is_argmax_equivalent(self):
        guard = LlamaGuard({"threshold": 0.5})
        # argmax-unsafe => normalized p_unsafe > 0.5 => conf >= 0.5 True (matches)
        self.assertTrue(guard._apply_threshold(True, 0.6))
        # argmax-safe => normalized p_unsafe < 0.5 => conf >= 0.5 False (matches)
        self.assertFalse(guard._apply_threshold(False, 0.4))


if __name__ == "__main__":
    unittest.main()
