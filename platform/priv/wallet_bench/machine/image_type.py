"""Prints an image file's type and pixel size, such as `PNG 1024x1024`, from its header alone, or `not an image`.

Usage: image_type.py <file>. PNG, JPEG and WebP; standard library only, so it runs on the machine's own Python.
"""

import struct
import sys


def describe(data: bytes) -> str:
    if data[:8] == b"\x89PNG\r\n\x1a\n" and data[12:16] == b"IHDR":
        width, height = struct.unpack(">II", data[16:24])
        return f"PNG {width}x{height}"
    if data[:2] == b"\xff\xd8":
        return jpeg(data)
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return webp(data)
    return "not an image"


def jpeg(data: bytes) -> str:
    at = 2
    while at + 9 < len(data) and data[at] == 0xFF:
        marker, length = data[at + 1], struct.unpack(">H", data[at + 2 : at + 4])[0]
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            height, width = struct.unpack(">HH", data[at + 5 : at + 9])
            return f"JPEG {width}x{height}"
        at += 2 + length
    return "JPEG, size unreadable"


def webp(data: bytes) -> str:
    chunk = data[12:16]
    if chunk == b"VP8 " and len(data) >= 30:
        width, height = struct.unpack("<HH", data[26:30])
        return f"WebP {width & 0x3FFF}x{height & 0x3FFF}"
    if chunk == b"VP8L" and len(data) >= 25:
        bits = int.from_bytes(data[21:25], "little")
        return f"WebP {(bits & 0x3FFF) + 1}x{((bits >> 14) & 0x3FFF) + 1}"
    if chunk == b"VP8X" and len(data) >= 30:
        return f"WebP {int.from_bytes(data[24:27], 'little') + 1}x{int.from_bytes(data[27:30], 'little') + 1}"
    return "WebP, size unreadable"


if __name__ == "__main__":
    with open(sys.argv[1], "rb") as image:
        print(describe(image.read()))
