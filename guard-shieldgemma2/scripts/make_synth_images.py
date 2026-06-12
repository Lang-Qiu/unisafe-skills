"""Generate the synthetic fixture/example images. Stdlib only, deterministic.

Every committed PNG under tests/fixtures/images/ and examples/images/ is the
byte-exact output of this script (locked by tests/test_synth_images.py), so the
assets are reviewable and reproducible: `python scripts/make_synth_images.py`
rewrites them in place. All images are benign solid colors / simple geometry,
<1KB each — fixtures, not dataset dumps (M3_SPEC 0-5). The one deliberate
exception is bad_magic.png: text bytes behind a .png suffix, feeding the L0
image_decode_error magic-bytes case (M3_SPEC 4.2).
"""
from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path
from typing import Callable, Dict, List, Tuple

SKILL_ROOT = Path(__file__).resolve().parents[1]

Color = Tuple[int, int, int]


def _chunk(tag: bytes, data: bytes) -> bytes:
    body = tag + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))


def make_png(rows: List[List[Color]]) -> bytes:
    """Minimal truecolor PNG: bit depth 8, color type 2, filter 0 per row."""
    height = len(rows)
    width = len(rows[0])
    raw = b"".join(
        b"\x00" + b"".join(bytes(pixel) for pixel in row) for row in rows
    )
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n"
            + _chunk(b"IHDR", ihdr)
            + _chunk(b"IDAT", zlib.compress(raw, 9))
            + _chunk(b"IEND", b""))


def solid(size: int, color: Color) -> bytes:
    return make_png([[color] * size for _ in range(size)])


def centered_square(size: int, background: Color, foreground: Color) -> bytes:
    quarter = size // 4
    rows = []
    for y in range(size):
        row = []
        for x in range(size):
            inside = quarter <= x < size - quarter and quarter <= y < size - quarter
            row.append(foreground if inside else background)
        rows.append(row)
    return make_png(rows)


def checkerboard(size: int, color_a: Color, color_b: Color, cell: int = 4) -> bytes:
    rows = []
    for y in range(size):
        row = []
        for x in range(size):
            row.append(color_a if ((x // cell) + (y // cell)) % 2 == 0 else color_b)
        rows.append(row)
    return make_png(rows)


def bad_magic() -> bytes:
    return b"plain text wearing a .png suffix; magic-bytes check must reject this\n"


# relative path (POSIX) -> bytes producer; the single source of asset truth
MANIFEST: Dict[str, Callable[[], bytes]] = {
    "tests/fixtures/images/benign_blue.png": lambda: solid(8, (40, 90, 200)),
    "tests/fixtures/images/benign_green.png": lambda: solid(8, (60, 170, 80)),
    "tests/fixtures/images/benign_white.png": lambda: solid(8, (255, 255, 255)),
    "tests/fixtures/images/shape_square.png": lambda: centered_square(
        16, (255, 255, 255), (200, 40, 40)),
    "tests/fixtures/images/bad_magic.png": bad_magic,
    "examples/images/benign_blue.png": lambda: solid(8, (40, 90, 200)),
    "examples/images/benign_checker.png": lambda: checkerboard(
        16, (230, 230, 230), (40, 40, 40)),
}


def generate_all(root: Path) -> List[str]:
    written = []
    for relative, producer in MANIFEST.items():
        target = Path(root) / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(producer())
        written.append(relative)
    return written


def main() -> int:
    for relative in generate_all(SKILL_ROOT):
        size = (SKILL_ROOT / relative).stat().st_size
        print(f"wrote {relative} ({size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
