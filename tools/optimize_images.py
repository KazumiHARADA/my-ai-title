#!/usr/bin/env python3
"""Shrink character images for distribution (needs Pillow).

Usage:
    python3 tools/optimize_images.py SRC_DIR OUT_DIR [--width 800] [--webp]

Reads every .png/.webp in SRC_DIR (not recursive), trims transparent margins,
scales it down to at most --width pixels wide (never up), and writes an
optimized PNG (or lossless-alpha WebP with --webp) with the same base name to
OUT_DIR. SRC_DIR is never modified, so keep your full-size originals there.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def optimize(src: Path, out_dir: Path, width: int, webp: bool) -> tuple:
    from PIL import Image
    with Image.open(src) as im:
        img = im.convert("RGBA")
    box = img.getchannel("A").getbbox()
    if box:
        img = img.crop(box)
    if img.width > width:
        img = img.resize((width, round(img.height * width / img.width)), Image.LANCZOS)
    out = out_dir / (src.stem + (".webp" if webp else ".png"))
    if webp:
        img.save(out, "WEBP", quality=90, method=6)
    else:
        # 256-colour quantization keeps alpha and is visually lossless for flat illustrations
        img.quantize(colors=256, method=Image.FASTOCTREE, dither=Image.FLOYDSTEINBERG).save(out, "PNG", optimize=True)
    return src.stat().st_size, out.stat().st_size, img.size


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--width", type=int, default=800)
    ap.add_argument("--webp", action="store_true")
    args = ap.parse_args(argv)
    if args.src.resolve() == args.out.resolve():
        ap.error("OUT_DIR must differ from SRC_DIR (originals are never overwritten)")
    try:
        import PIL  # noqa: F401
    except ImportError:
        print("Pillow is required: python3 -m pip install Pillow", file=sys.stderr)
        return 1
    args.out.mkdir(parents=True, exist_ok=True)
    before = after = 0
    for src in sorted(p for p in args.src.iterdir() if p.suffix.lower() in (".png", ".webp")):
        b, a, size = optimize(src, args.out, args.width, args.webp)
        before, after = before + b, after + a
        print(f"{src.name}: {b // 1024} KB -> {a // 1024} KB  {size[0]}x{size[1]}")
    print(f"total: {before / 1e6:.1f} MB -> {after / 1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
