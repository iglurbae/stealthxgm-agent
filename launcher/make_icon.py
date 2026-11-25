#!/usr/bin/env python3
"""Generate StealthXGM icon: shield + X, dark theme with red/blue gradient accent.
Outputs icon.svg + icon16/48/128.png into launcher/brand/ and gui/static/.
"""
import math
import os
from PIL import Image, ImageDraw

BASE = os.path.dirname(os.path.abspath(__file__))
BRAND_DIR = os.path.join(BASE, "brand")
STATIC_DIR = os.path.join(BASE, "..", "gui", "static")
BG_TOP = (22, 27, 38)      # #161b26
BG_BOT = (13, 17, 23)      # #0d1117
RED = (233, 69, 96)        # #e94560
BLUE = (79, 140, 255)      # #4f8cff


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def draw_icon(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # rounded-square background with vertical gradient
    r = size * 0.22
    for y in range(size):
        t = y / max(size - 1, 1)
        c = lerp(BG_TOP, BG_BOT, t)
        d.line([(0, y), (size, y)], fill=c + (255,))
    # round the corners by masking
    mask = Image.new("L", (size, size), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([0, 0, size, size], radius=int(r), fill=255)
    img.putalpha(mask)

    d = ImageDraw.Draw(img)
    cx = size / 2
    # shield outline (gradient red->blue top to bottom)
    sw = size * 0.62
    sh = size * 0.72
    top = (size - sh) / 2 + size * 0.02
    shield = [
        (cx - sw / 2, top),
        (cx + sw / 2, top),
        (cx + sw / 2, top + sh * 0.45),
        (cx, top + sh),
        (cx - sw / 2, top + sh * 0.45),
    ]
    # draw shield as thick polyline with gradient
    lw = max(2, int(size * 0.055))
    n = len(shield)
    for i in range(n):
        p1 = shield[i]
        p2 = shield[(i + 1) % n]
        t = i / n
        col = lerp(RED, BLUE, t)
        d.line([p1, p2], fill=col + (255,), width=lw, joint="curve")
    # X in the middle
    xw = sw * 0.30
    xh = sh * 0.26
    xcy = top + sh * 0.42
    xwdt = max(2, int(size * 0.075))
    d.line([(cx - xw / 2, xcy - xh / 2), (cx + xw / 2, xcy + xh / 2)],
           fill=(255, 255, 255, 255), width=xwdt)
    d.line([(cx + xw / 2, xcy - xh / 2), (cx - xw / 2, xcy + xh / 2)],
           fill=(255, 255, 255, 255), width=xwdt)
    return img


def write_svg(path):
    svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" stop-color="#161b26"/><stop offset="1" stop-color="#0d1117"/></linearGradient>
<linearGradient id="sh" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" stop-color="#e94560"/><stop offset="1" stop-color="#4f8cff"/></linearGradient></defs>
<rect x="4" y="4" width="120" height="120" rx="28" fill="url(#bg)"/>
<path d="M64 22 L96 30 V62 C96 84 80 100 64 108 C48 100 32 84 32 62 V30 Z"
fill="none" stroke="url(#sh)" stroke-width="7" stroke-linejoin="round"/>
<path d="M52 52 L76 76 M76 52 L52 76" stroke="#fff" stroke-width="9" stroke-linecap="round"/>
</svg>"""
    with open(path, "w") as f:
        f.write(svg)


def main():
    os.makedirs(BRAND_DIR, exist_ok=True)
    os.makedirs(STATIC_DIR, exist_ok=True)
    write_svg(os.path.join(BRAND_DIR, "icon.svg"))
    for s in (16, 48, 128):
        img = draw_icon(s)
        for dest in (BRAND_DIR, STATIC_DIR):
            img.save(os.path.join(dest, f"icon{s}.png"))
    print("icons written:", sorted(os.listdir(BRAND_DIR)))


if __name__ == "__main__":
    main()
