"""Routing + image-path helpers (io-contract section 2 image edition; M3_SPEC 4.1/4.2).

Covers the four routing quadrants (eligible / eligible url-only / out_of_scope /
missing_content), the path resolution base rule (待甲确认.md #5 point 1) and the
stdlib magic-bytes check that backs the L0 image_decode_error tier.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from utils import (  # noqa: E402
    ROUTE_ELIGIBLE,
    ROUTE_MISSING_CONTENT,
    ROUTE_OUT_OF_SCOPE,
    first_image,
    image_magic_ok,
    record_caption_text,
    resolve_image_path,
    route_record,
)


def _record(task_type="image_safety", modality=None, images=None):
    record = {"id": "fixture:test:000001", "task_type": task_type,
              "modality": ["image"] if modality is None else modality}
    record["content"] = {"images": [] if images is None else images}
    return record


class TestRouteRecord(unittest.TestCase):
    def test_eligible_with_path(self):
        bucket, _ = route_record(_record(images=[{"path": "images/a.png", "url": None}]))
        self.assertEqual(bucket, ROUTE_ELIGIBLE)

    def test_eligible_url_only(self):
        # plan B (M3_SPEC 4.1): url-only is eligible; the error row comes later
        bucket, _ = route_record(_record(images=[{"path": None, "url": "https://x/a.png"}]))
        self.assertEqual(bucket, ROUTE_ELIGIBLE)

    def test_eligible_multi_image(self):
        bucket, _ = route_record(_record(images=[{"path": "a.png"}, {"path": "b.png"}]))
        self.assertEqual(bucket, ROUTE_ELIGIBLE)

    def test_out_of_scope_task_type(self):
        bucket, reason = route_record(_record(task_type="prompt_only_safety"))
        self.assertEqual(bucket, ROUTE_OUT_OF_SCOPE)
        self.assertIn("task_type", reason)

    def test_out_of_scope_modality(self):
        for modality in (["text"], ["image", "text"], [], None):
            record = _record(images=[{"path": "a.png"}])
            record["modality"] = modality  # explicit: None means JSON null, not default
            bucket, reason = route_record(record)
            self.assertEqual(bucket, ROUTE_OUT_OF_SCOPE, modality)
            self.assertIn("modality", reason)

    def test_missing_content_no_images(self):
        for images in ([], None):
            record = _record()
            if images is None:
                record["content"].pop("images")
            bucket, _ = route_record(record)
            self.assertEqual(bucket, ROUTE_MISSING_CONTENT, images)

    def test_missing_content_path_and_url_both_empty(self):
        for img in ({"path": None, "url": None}, {"path": "", "url": ""}, {}):
            bucket, _ = route_record(_record(images=[img]))
            self.assertEqual(bucket, ROUTE_MISSING_CONTENT, img)


class TestImageHelpers(unittest.TestCase):
    def test_first_image(self):
        self.assertIsNone(first_image(_record()))
        img = {"path": "a.png"}
        self.assertEqual(first_image(_record(images=[img, {"path": "b.png"}])), img)

    def test_resolve_relative_against_dataset_dir(self):
        record = _record(images=[{"path": "images/a.png"}])
        resolved = resolve_image_path(record, Path("E:/data/unified"))
        self.assertEqual(resolved, Path("E:/data/unified/images/a.png"))

    def test_resolve_absolute_passthrough(self):
        absolute = str(Path(tempfile.gettempdir()) / "a.png")
        record = _record(images=[{"path": absolute}])
        self.assertEqual(resolve_image_path(record, Path("E:/elsewhere")), Path(absolute))

    def test_resolve_url_only_returns_none(self):
        record = _record(images=[{"path": None, "url": "https://x/a.png"}])
        self.assertIsNone(resolve_image_path(record, Path("E:/data")))

    def test_caption_text_combinations(self):
        cases = [
            ({"path": "a.png", "caption": "a dog", "ocr": None}, "a dog"),
            ({"path": "a.png", "caption": None, "ocr": "STOP"}, "STOP"),
            ({"path": "a.png", "caption": "a dog", "ocr": "STOP"}, "a dog\nSTOP"),
            ({"path": "a.png"}, ""),
            ({"path": "a.png", "caption": "  ", "ocr": ""}, ""),
        ]
        for img, expected in cases:
            self.assertEqual(record_caption_text(_record(images=[img])), expected, img)


class TestImageMagic(unittest.TestCase):
    def _tmp(self, data: bytes) -> Path:
        handle = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        handle.write(data)
        handle.close()
        self.addCleanup(Path(handle.name).unlink)
        return Path(handle.name)

    def test_known_signatures_pass(self):
        signatures = [
            b"\x89PNG\r\n\x1a\n" + b"\x00" * 16,
            b"\xff\xd8\xff\xe0" + b"\x00" * 16,
            b"GIF89a" + b"\x00" * 16,
            b"BM" + b"\x00" * 16,
            b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 8,
        ]
        for data in signatures:
            self.assertTrue(image_magic_ok(self._tmp(data)), data[:8])

    def test_text_bytes_fail(self):
        self.assertFalse(image_magic_ok(self._tmp(b"this is not an image at all")))

    def test_riff_without_webp_fails(self):
        self.assertFalse(image_magic_ok(self._tmp(b"RIFF\x00\x00\x00\x00WAVE" + b"\x00" * 8)))

    def test_unreadable_returns_false(self):
        self.assertFalse(image_magic_ok(Path(tempfile.gettempdir()) / "definitely-missing.png"))


if __name__ == "__main__":
    unittest.main()
