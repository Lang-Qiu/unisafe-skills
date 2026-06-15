"""W3 — int8/GPU run-to-run variance smoke (opt-in, SHIELDGEMMA2_LIVE=1).

Determinism is part of output stability. Fixed N=5 images / K=3 runs (constants
below, for reproducibility): run shieldgemma2 (int8) K times on the same N images
and report ① per-policy yes-prob run-to-run range/std, ② flip_rate = fraction of
images whose binary is_unsafe verdict is not identical across the K runs (a NaN
run counts as a flip — it is exactly the instability we care about). The test
RECORDS the numbers (prints VARIANCE_SMOKE line) and asserts mechanism only; it
does NOT fail on non-zero variance (that would be a finding to log in
references/shieldgemma2-notes.md, per M3.5_SPEC W3), not a test failure.

Offline: skipped (needs GPU + weights), so the default suite is unaffected.
"""
from __future__ import annotations

import math
import os
import statistics
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from guards.shieldgemma2 import ShieldGemma2Guard  # noqa: E402
from make_synth_images import solid  # noqa: E402

N_IMAGES = 5
K_RUNS = 3
_COLORS = [(10, 20, 30), (200, 50, 50), (50, 200, 50), (50, 50, 200), (128, 128, 128)]


def _make_records(tmp: Path):
    records = []
    for i, color in enumerate(_COLORS[:N_IMAGES]):
        path = tmp / f"var_{i}.png"
        path.write_bytes(solid(16, color))
        records.append({"id": f"var:{i:03d}", "task_type": "image_safety",
                        "modality": ["image"],
                        "content": {"images": [{"path": str(path), "url": None,
                                                "caption": None, "ocr": None}]},
                        "_resolved_image_path": str(path)})
    return records


class TestVarianceSmoke(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("SHIELDGEMMA2_LIVE") == "1",
                         "live smoke: set SHIELDGEMMA2_LIVE=1 (GPU + weights required)")
    def test_run_to_run_variance_and_flip_rate(self):
        guard = ShieldGemma2Guard({"model_id": os.environ.get("SHIELDGEMMA2_MODEL_ID")
                                   or ShieldGemma2Guard({}).model_id})
        ok, reason = guard.available()
        self.assertTrue(ok, reason)
        with tempfile.TemporaryDirectory() as tmp:
            records = _make_records(Path(tmp))
            self.assertEqual(len(records), N_IMAGES)
            runs = []  # runs[k][id] = (is_unsafe, {policy: yes_prob})
            for _k in range(K_RUNS):
                row = {}
                for rec in records:
                    result = guard.predict(rec)
                    scores = (result.get("raw_output") or {}).get("policy_scores") or {}
                    row[rec["id"]] = (result["prediction"]["is_unsafe"], scores)
                runs.append(row)

        flips = 0
        max_range = 0.0
        std_acc = []
        for rec in records:
            rid = rec["id"]
            verdicts = {runs[k][rid][0] for k in range(K_RUNS)}
            if len(verdicts) > 1:
                flips += 1
            for key in runs[0][rid][1]:
                vals = [runs[k][rid][1].get(key) for k in range(K_RUNS)]
                vals = [v for v in vals if v is not None and not math.isnan(v)]
                if len(vals) >= 2:
                    max_range = max(max_range, max(vals) - min(vals))
                    std_acc.append(statistics.pstdev(vals))
        flip_rate = flips / N_IMAGES
        mean_std = sum(std_acc) / len(std_acc) if std_acc else 0.0
        print(f"VARIANCE_SMOKE int8 N={N_IMAGES} K={K_RUNS}: "
              f"flip_rate={flip_rate:.3f} max_yesprob_range={max_range:.6f} "
              f"mean_policy_std={mean_std:.6f}")

        self.assertEqual(len(runs), K_RUNS)          # mechanism: K runs happened
        self.assertGreaterEqual(flip_rate, 0.0)      # record, never fail on non-zero


if __name__ == "__main__":
    unittest.main()
