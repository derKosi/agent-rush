#!/usr/bin/env python3
"""Compose the submission cover: generated key art + typographic overlay.

    .venv/bin/python docs/slides/make_cover.py /tmp/cover_raw.jpg
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).with_name("cover.png")
W, H = 1920, 1080
MINT = (76, 194, 160)
WHITE = (230, 237, 243)
MUTED = (139, 148, 158)

FONTS = [
    "/System/Library/Fonts/SFNS.ttf",
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/System/Library/Fonts/Helvetica.ttc",
]


def font(size, weight=0):
    for path in FONTS:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size, index=weight)
            except OSError:
                try:
                    return ImageFont.truetype(path, size)
                except OSError:
                    continue
    return ImageFont.load_default()


def main(src):
    art = Image.open(src).convert("RGB").resize((W, H), Image.LANCZOS)

    # Scrim: darken the left third so the title reads on any art.
    scrim = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(scrim)
    for x in range(int(W * 0.62)):
        alpha = int(210 * (1 - x / (W * 0.62)) ** 1.2)
        d.line([(x, 0), (x, H)], fill=alpha)
    art = Image.composite(Image.new("RGB", (W, H), (10, 14, 19)), art, scrim)
    art = art.filter(ImageFilter.GaussianBlur(0))

    draw = ImageDraw.Draw(art)
    left = 132

    draw.text((left, 330), "Quarantine", font=font(118), fill=WHITE)
    draw.text((left, 480), "Prove a package is safe", font=font(46), fill=WHITE)
    draw.text((left, 540), "before it touches your machine", font=font(46), fill=WHITE)

    draw.line([(left, 650), (left + 420, 650)], fill=MINT, width=3)

    draw.text((left, 690), "Vultr: Agent Rush  ·  Track 1 Blast Radius Zero",
              font=font(24), fill=MINT)
    draw.text((left, 962), "github.com/derKosi/agent-rush", font=font(22), fill=MUTED)
    draw.text((left, 998), "agent-driven triage for untrusted packages", font=font(22), fill=MUTED)

    art.save(OUT)
    print(f"wrote {OUT} · {art.size[0]}x{art.size[1]}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/tmp/cover_raw.jpg")
