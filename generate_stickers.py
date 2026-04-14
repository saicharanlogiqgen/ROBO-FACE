"""
generate_stickers.py
====================
Run ONCE to create all 8 AR sticker PNG files in ./stickers/

Only needs: Pillow (pip install Pillow)
All stickers have RGBA alpha channel for clean transparency overlay.

Usage:
    python3 generate_stickers.py
"""

import os
import math
import numpy as np
from PIL import Image, ImageDraw


STICKER_DIR = os.path.join(os.path.dirname(__file__), "stickers")


def star_pts(cx, cy, r, n=5):
    pts = []
    for i in range(n * 2):
        angle = math.pi / 2 + i * math.pi / n
        rr = r if i % 2 == 0 else r * 0.4
        pts.append((int(cx + rr * math.cos(angle)), int(cy - rr * math.sin(angle))))
    return pts


def save(img, name):
    os.makedirs(STICKER_DIR, exist_ok=True)
    path = os.path.join(STICKER_DIR, f"{name}.png")
    img.save(path)
    print(f"  ✓ {name}.png  ({img.size[0]}×{img.size[1]})")


# ──────────────────────────────────────────────────────────────────────────────
# 1. CROWN  (gold, 400×220)
# ──────────────────────────────────────────────────────────────────────────────
def make_crown():
    W, H = 400, 220
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    gold = (255, 200, 0, 255)
    dark = (180, 130, 0, 255)
    pts = [(int(x * W), int(y * H)) for x, y in [
        (0, 1), (0, 0.55), (0.10, 0.15), (0.22, 0.55),
        (0.35, 0.05), (0.50, 0.55), (0.65, 0.05),
        (0.78, 0.55), (0.90, 0.15), (1, 0.55), (1, 1),
    ]]
    d.polygon(pts, fill=gold, outline=dark)
    for cx, cy, col in [
        (W // 2,       int(H * 0.72), (255, 80,  80,  255)),
        (W // 5,       int(H * 0.72), (80,  180, 255, 255)),
        (4 * W // 5,   int(H * 0.72), (80,  255, 120, 255)),
    ]:
        d.ellipse([cx - 14, cy - 14, cx + 14, cy + 14],
                  fill=col, outline=(255, 255, 255, 200))
    save(img, "crown")


# ──────────────────────────────────────────────────────────────────────────────
# 2. WIZARD HAT  (purple, 280×380)
# ──────────────────────────────────────────────────────────────────────────────
def make_wizard_hat():
    W, H = 280, 380
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    purple = (100, 40,  180, 255)
    dark_p = (60,  20,  120, 255)
    yellow = (255, 220, 0,   255)
    d.ellipse([0, H - 50, W, H], fill=purple, outline=dark_p)
    d.polygon([(W // 2, 0), (0, H - 25), (W, H - 25)], fill=purple, outline=dark_p)
    d.rectangle([0, H - 72, W, H - 50], fill=yellow)
    for sx, sy, sr in [(W // 2, H // 3, 12), (W // 3, H // 2, 8), (2 * W // 3, int(H * 0.4), 9)]:
        d.polygon(star_pts(sx, sy, sr), fill=yellow)
    save(img, "wizard_hat")


# ──────────────────────────────────────────────────────────────────────────────
# 3. SUNGLASSES  (400×140)
# ──────────────────────────────────────────────────────────────────────────────
def make_sunglasses():
    W, H = 400, 140
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    black  = (10,  10,  10,  255)
    lens   = (40,  80,  200, 180)
    silver = (180, 180, 200, 255)
    d.ellipse([10,  20, 175, 120], fill=lens, outline=black, width=6)
    d.ellipse([225, 20, 390, 120], fill=lens, outline=black, width=6)
    d.rectangle([172, 58, 228, 78], fill=silver, outline=black, width=2)
    d.rectangle([0,   55,  14,  68], fill=silver, outline=black, width=2)
    d.rectangle([386, 55, 400,  68], fill=silver, outline=black, width=2)
    d.ellipse([30,  28,  90,  60], fill=(200, 220, 255, 100))
    d.ellipse([245, 28, 305,  60], fill=(200, 220, 255, 100))
    save(img, "sunglasses")


# ──────────────────────────────────────────────────────────────────────────────
# 4. RAINBOW BAND  (380×110)
# ──────────────────────────────────────────────────────────────────────────────
def make_rainbow_band():
    W, H = 380, 110
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cols = [
        (255, 0,   0,   220), (255, 140, 0,   220), (255, 220, 0,   220),
        (0,   200, 50,  220), (0,   120, 255, 220), (140, 0,   220, 220),
    ]
    sh = H // len(cols)
    for i, c in enumerate(cols):
        d.rectangle([0, i * sh, W, (i + 1) * sh + 2], fill=c)
    mask = Image.new("L", (W, H), 0)
    dm = ImageDraw.Draw(mask)
    dm.rounded_rectangle([0, 0, W, H], radius=30, fill=255)
    img.putalpha(mask)
    save(img, "rainbow_band")


# ──────────────────────────────────────────────────────────────────────────────
# 5. CAT EARS  (340×160)
# ──────────────────────────────────────────────────────────────────────────────
def make_cat_ears():
    W, H = 340, 160
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pink      = (230, 80,  140, 255)
    dark_pink = (160, 40,  90,  255)
    inner     = (255, 160, 190, 255)
    d.polygon([(20, H),  (80,  0),  (160, H)], fill=pink, outline=dark_pink)
    d.polygon([(180, H), (260, 0),  (320, H)], fill=pink, outline=dark_pink)
    d.polygon([(50,  H - 20), (80,  30), (140, H - 20)], fill=inner)
    d.polygon([(200, H - 20), (260, 30), (300, H - 20)], fill=inner)
    save(img, "cat_ears")


# ──────────────────────────────────────────────────────────────────────────────
# 6. SUPERHERO MASK  (400×160)
# ──────────────────────────────────────────────────────────────────────────────
def make_superhero_mask():
    W, H = 400, 160
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    red   = (210, 30, 30, 255)
    black = (10,  10, 10, 255)
    d.rounded_rectangle([0, 30, W, H - 10], radius=20, fill=red, outline=black)
    # Punch transparent eye holes via numpy
    arr = np.array(img)
    eye_mask = Image.new("L", (W, H), 0)
    md = ImageDraw.Draw(eye_mask)
    md.ellipse([32,  42, 148, H - 22], fill=255)
    md.ellipse([252, 42, 368, H - 22], fill=255)
    mask_arr = np.array(eye_mask)
    arr[mask_arr > 0] = [0, 0, 0, 0]
    img = Image.fromarray(arr)
    save(img, "superhero_mask")


# ──────────────────────────────────────────────────────────────────────────────
# 7. SANTA HAT  (260×360)
# ──────────────────────────────────────────────────────────────────────────────
def make_santa_hat():
    W, H = 260, 360
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    red_s  = (210, 30,  30,  255)
    white  = (255, 255, 255, 255)
    dark_r = (150, 20,  20,  255)
    d.polygon([(W // 2, 0), (0, H - 60), (W, H - 60)], fill=red_s, outline=dark_r)
    d.ellipse([0, H - 80, W, H],        fill=white)
    d.ellipse([W // 2 - 22, 0, W // 2 + 22, 44], fill=white)
    save(img, "santa_hat")


# ──────────────────────────────────────────────────────────────────────────────
# 8. BIRTHDAY HAT  (220×320)
# ──────────────────────────────────────────────────────────────────────────────
def make_birthday_hat():
    W, H = 220, 320
    base  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    scols = [
        (255, 80,  80,  255), (255, 180, 0,   255),
        (80,  200, 80,  255), (80,  120, 255, 255),
    ]
    for i, c in enumerate(scols):
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ld    = ImageDraw.Draw(layer)
        y0    = int(i * H / len(scols))
        y1    = int((i + 1) * H / len(scols))
        ld.polygon([(W // 2, y0), (0, y1), (W, y1)], fill=c)
        base  = Image.alpha_composite(base, layer)
    cone_mask = Image.new("L", (W, H), 0)
    cm = ImageDraw.Draw(cone_mask)
    cm.polygon([(W // 2, 0), (0, H), (W, H)], fill=255)
    base.putalpha(cone_mask)
    d = ImageDraw.Draw(base)
    d.ellipse([W // 2 - 18, 0, W // 2 + 18, 36], fill=(255, 255, 255, 255))
    d.ellipse([0, H - 40, W, H + 10], fill=(255, 220, 50, 255), outline=(200, 150, 0, 255))
    save(base, "birthday_hat")


# ──────────────────────────────────────────────────────────────────────────────
def main():
    print("=" * 45)
    print("  Generating AR stickers → ./stickers/")
    print("=" * 45)
    os.makedirs(STICKER_DIR, exist_ok=True)
    make_crown()
    make_wizard_hat()
    make_sunglasses()
    make_rainbow_band()
    make_cat_ears()
    make_superhero_mask()
    make_santa_hat()
    make_birthday_hat()
    print(f"\n✓ All stickers saved to: {STICKER_DIR}/")
    print("  Now run:  python3 ar_sticker_overlay.py")


if __name__ == "__main__":
    main()