"""Thumbnail generator — three A/B variants at 1280x720.

Design rules taken from the CTR research in docs/00-analisis.md:
  * 3–4 words maximum, legible at 168 px wide
  * one idea per thumbnail: a number, a question, or a scale shock
  * KAL reacts at thumbnail scale (a readable silhouette, not detail)
  * high value separation: ink panel + paper text + one amber accent

    python env/bin/python tools/make_thumbs.py
"""
from __future__ import annotations

import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import ink, palette as P, stickman as S  # noqa: E402
from engine.fonts import draw_tracked, font, tracked_width  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "art", "raw")
OUT = os.path.join(ROOT, "social")
W, H = 1280, 720


def plate(name: str) -> Image.Image:
    from tools.render_video import _autocrop, _grade
    im = _autocrop(Image.open(os.path.join(RAW, name)).convert("RGB"))
    tar = W / H
    ar = im.width / im.height
    if ar > tar:
        nw = int(im.height * tar)
        im = im.crop(((im.width - nw) // 2, 0, (im.width + nw) // 2, im.height))
    else:
        nh = int(im.width / tar)
        im = im.crop((0, (im.height - nh) // 2, im.width, (im.height + nh) // 2))
    return _grade(im.resize((W, H), Image.LANCZOS)).convert("RGBA")


def kal(img, pose, h, sx, sy, flip=False):
    scale = h / (S.Y1 + 46.0)
    sprite, anchor = S.Rig(3).render(S.POSES[pose](1.37), scale)
    if flip:
        sprite = sprite.transpose(Image.FLIP_LEFT_RIGHT)
        anchor = (sprite.width - anchor[0], anchor[1])
    soles = (S.Y1 + 46.0) / (S.Y1 - S.Y0) * sprite.height
    img.alpha_composite(sprite, (int(sx - anchor[0]), int(sy - soles)))
    return img


def panel(img, box, colour=P.INK, alpha=238):
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(lay).rectangle(box, fill=colour + (alpha,))
    return Image.alpha_composite(img, lay)


def fit_line(img, txt, max_w, size_from, fill, x, y, track=3, name="display"):
    """Draw txt at the largest size that fits max_w, return the bottom y."""
    d = ImageDraw.Draw(img)
    s = size_from
    while s > 20:
        f = font(name, s)
        if tracked_width(d, txt, f, track) <= max_w:
            break
        s -= 4
    f = font(name, s)
    draw_tracked(d, (x, y), txt, f, fill, track)
    return y + int(s * 1.06)


def finish(img: Image.Image) -> Image.Image:
    out = ink.vignette(img.convert("RGB"), 0.26, 1.6)
    return ink.add_grain(out, 1.8, seed=4)


def variant_a() -> Image.Image:
    """The impossible number."""
    img = plate("img05_column.png")
    pw = 452
    img = panel(img, [0, 0, pw, H], P.INK, 240)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 16, H], fill=P.rgba(P.AMBER))
    y = 74
    for txt, col in (("74.000", P.PAPER), ("TAHUN", P.PAPER), ("LALU", P.AMBER)):
        y = fit_line(img, txt, pw - 96, 152, P.rgba(col), 52, y, 2)
    d.rectangle([52, y + 26, pw - 52, y + 34], fill=P.rgba(P.RUST))
    y2 = fit_line(img, "SUMATERA MELEDAK", pw - 104, 52, P.rgba(P.PAPER_DARK), 52, y + 60, 4, "mono")
    img = kal(img, "shock", 400, 690, 706)
    return finish(img)


def variant_b() -> Image.Image:
    """The question — a pure curiosity gap, no clutter."""
    img = plate("img07_long_night.png")
    img = panel(img, [0, 0, W, 352], P.INK, 228)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 14, H], fill=P.rgba(P.AMBER))
    fit_line(img, "KITA HAMPIR", 900, 132, P.rgba(P.PAPER), 58, 40, 2)
    fit_line(img, "PUNAH?", 900, 176, P.rgba(P.AMBER), 58, 158, 2)
    # small factual tag, bottom right, keeps the claim honest
    tag = "BUKTI 2024"
    f = font("mono", 40)
    tw = tracked_width(d, tag, f, 4)
    d.rectangle([W - tw - 84, H - 92, W - 30, H - 26], fill=(25, 22, 20, 224))
    draw_tracked(d, (W - tw - 56, H - 84), tag, f, P.rgba(P.AMBER), 4)
    img = kal(img, "shock", 420, 300, 706)
    return finish(img)


def variant_c() -> Image.Image:
    """Scale shock — the wall of ash and one small figure."""
    img = plate("img06_pyroclastic.png")
    img = panel(img, [0, 0, 640, 330], P.INK, 214)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 14, H], fill=P.rgba(P.AMBER))
    y = 34
    for txt, col in (("NERAKA", P.PAPER), ("YANG", P.PAPER_DARK), ("BERGERAK", P.AMBER)):
        y = fit_line(img, txt, 560, 112, P.rgba(col), 44, y, 3)
    img = kal(img, "run", 350, 800, 706, flip=True)
    return finish(img)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for name, fn in (("thumb_A_number", variant_a), ("thumb_B_question", variant_b),
                     ("thumb_C_scale", variant_c)):
        p = os.path.join(OUT, f"{name}_1280x720.jpg")
        fn().save(p, quality=93, optimize=True)
        print("wrote", p)
