"""Synthetic fixture images (M3_SPEC 0-5; plan AD-10).

The committed PNGs under tests/fixtures/images/ and examples/images/ must be
exactly what scripts/make_synth_images.py regenerates (deterministic bytes),
stay tiny (<1KB), and behave correctly under the stdlib magic check.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from make_synth_images import MANIFEST, generate_all  # noqa: E402
from utils import image_magic_ok  # noqa: E402

MAX_BYTES = 1024


class TestSynthImages(unittest.TestCase):
    def test_committed_assets_match_generator(self):
        with tempfile.TemporaryDirectory() as tmp:
            generated = generate_all(Path(tmp))
            self.assertEqual(sorted(generated), sorted(MANIFEST))
            for relative in MANIFEST:
                committed = ROOT / relative
                self.assertTrue(committed.is_file(), f"missing committed asset {relative}")
                self.assertEqual(
                    committed.read_bytes(), (Path(tmp) / relative).read_bytes(),
                    f"{relative} diverged from make_synth_images.py output — "
                    "regenerate via `python scripts/make_synth_images.py`",
                )

    def test_all_assets_are_tiny(self):
        for relative in MANIFEST:
            size = (ROOT / relative).stat().st_size
            self.assertLess(size, MAX_BYTES, relative)

    def test_magic_check_separates_good_from_bad(self):
        for relative in MANIFEST:
            path = ROOT / relative
            if "bad_magic" in relative:
                self.assertFalse(image_magic_ok(path), relative)
            else:
                self.assertTrue(image_magic_ok(path), relative)

    def test_generator_is_deterministic(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            generate_all(Path(a))
            generate_all(Path(b))
            for relative in MANIFEST:
                self.assertEqual((Path(a) / relative).read_bytes(),
                                 (Path(b) / relative).read_bytes(), relative)


if __name__ == "__main__":
    unittest.main()
