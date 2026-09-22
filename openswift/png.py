"""Write a PNG with the standard library. No Pillow, no compiler."""

from __future__ import annotations

import struct
import zlib


def write_png(path, width: int, height: int, rgb: bytearray) -> None:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    rows = bytearray()
    stride = width * 3
    for y in range(height):
        rows.append(0)
        rows.extend(rgb[y * stride : (y + 1) * stride])
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    blob = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(bytes(rows), 9)) + chunk(b"IEND", b"")
    path.write_bytes(blob)


def fill(rgb: bytearray, width: int, x: int, y: int, w: int, h: int, color: tuple[int, int, int]) -> None:
    height = len(rgb) // (width * 3)
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(width, x + w), min(height, y + h)
    r, g, b = color
    for yy in range(y0, y1):
        row = yy * width * 3
        for xx in range(x0, x1):
            i = row + xx * 3
            rgb[i] = r
            rgb[i + 1] = g
            rgb[i + 2] = b
