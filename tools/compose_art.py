"""Compose final episode artwork: generated plate + drawn KAL + print grade.

The generated plates are deliberately empty of people (see art/prompts.json).
Every figure you see in the finished video is KAL, composited from the rig in
engine/stickman.py, so the character is identical in all ten frames.

    python env/bin/python tools/compose_art.py          # build all + contact sheet
    python env/bin/python tools/compose_art.py --one 3  # rebuild frame 3 only
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy.ndimage import binary_dilation

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import ink, palette as P, stickman as S  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "art", "raw")
FINAL = os.path.join(ROOT, "art", "final")
W, H = 1920, 1080

# id, raw file, pose, facing (+1 right / -1 left), height px, feet x, feet y, halo
#                  id        raw file                 pose     face  height  feetX  groundY  halo
SHOTS = [
    ("IMG-01", "img01_legend.png",           "present", +1, 360,  290,  975, 0.85),
    ("IMG-02", "img02_lake_today.png",       "lookup",  +1, 345,  360,  990, 0.90),
    ("IMG-03", "img03_old_mountain.png",     "brave",   +1, 330,  300, 1010, 0.70),
    ("IMG-04", "img04_fumaroles.png",        "crouch",  +1, 330,  470,  960, 0.90),
    ("IMG-05", "img05_column.png",           "shock",   +1, 300,  330,  985, 0.60),
    ("IMG-06", "img06_pyroclastic.png",      "run",     +1, 330, 1420,  990, 0.80),
    ("IMG-07", "img07_long_night.png",       "walk",    +1, 330,  450, 1000, 0.85),
    ("IMG-08", "img08_cave_shelter.png",     "crouch",  +1, 352,  700, 1012, 0.90),
    ("IMG-09", "img09_caldera_collapse.png", "point",   +1, 300,  330,  995, 0.75),
    ("IMG-10", "img10_samosir_today.png",    "lookup",  +1, 355,  520,  985, 0.95),
]
FOOT_Y = -46.0      # local y of the soles (Y0 in the rig is -48)
TOP_Y = 74.0

T_SECONDS = 1.35   # moment used for the ambient animation of the still


# --------------------------------------------------------------------- grade
def autocrop_art(im: Image.Image) -> Image.Image:
    """Trim the printed paper margin so the plate bleeds to the frame edge."""
    a = np.asarray(im.convert("RGB"), dtype=np.int16)
    paper = np.array([243, 234, 219], dtype=np.int16)
    diff = np.abs(a - paper).sum(axis=2)
    m = diff > 46
    rows = np.where(m.mean(axis=1) > 0.42)[0]
    cols = np.where(m.mean(axis=0) > 0.42)[0]
    if len(rows) < 10 or len(cols) < 10:
        return im
    y0, y1 = int(rows[0]), int(rows[-1]) + 1
    x0, x1 = int(cols[0]), int(cols[-1]) + 1
    inset = 4
    return im.crop((x0 + inset, y0 + inset, x1 - inset, y1 - inset))


def upscale(path: str) -> Image.Image:
    im = Image.open(path).convert("RGB")
    im = autocrop_art(im)
    # centre-crop to 16:9, then resize (keeps the plate full-bleed)
    tw, th = W, H
    ar = im.width / im.height
    tar = tw / th
    if ar > tar:
        nw = int(im.height * tar)
        im = im.crop(((im.width - nw) // 2, 0, (im.width + nw) // 2, im.height))
    else:
        nh = int(im.width / tar)
        im = im.crop((0, (im.height - nh) // 2, im.width, (im.height + nh) // 2))
    return im.resize((tw, th), Image.LANCZOS)


def print_grade(im: Image.Image) -> Image.Image:
    """Unify plates to the brand's printed look."""
    a = np.asarray(im, dtype=np.float32) / 255.0
    # gentle S-curve + warm bias in the highlights
    a = np.clip(a, 0, 1)
    a = a ** 1.045
    a[..., 0] *= 1.012
    a[..., 2] *= 0.985
    # pull saturation back slightly so six different plates feel like one book
    lum = (0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2])[..., None]
    a = lum + (a - lum) * 0.94
    out = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8), "RGB")
    out = ink.edge_burn(out, amount=20, seed=17)
    out = ink.vignette(out, 0.26, power=1.55)
    return out


# ----------------------------------------------------------------------- KAL
def kal_layer(pose: str, height_px: int, ss: int = 3):
    """Render KAL at a given on-screen height, return (sprite, hip_anchor)."""
    scale = height_px / (TOP_Y - FOOT_Y)
    sprite, anchor = S.render_pose(pose, T_SECONDS, scale, ss=ss)
    return sprite, anchor


def paper_halo(sprite: Image.Image, amount: float, colour=P.PAPER_DARK) -> Image.Image:
    """A soft paper cut-out behind KAL so his silhouette never sinks into art."""
    if amount <= 0:
        return None
    a = np.asarray(sprite.split()[-1])
    m = binary_dilation(a > 26, iterations=max(2, int(amount * 5)))
    halo = Image.fromarray((m * 255).astype(np.uint8), "L").filter(
        ImageFilter.GaussianBlur(amount * 26 + 10))
    layer = Image.new("RGBA", sprite.size, colour[:3] + (0,))
    alpha = np.asarray(halo, dtype=np.float32) * (amount * 0.42)
    layer.putalpha(Image.fromarray(np.clip(alpha, 0, 255).astype(np.uint8), "L"))
    return layer


def contact_shadow(size, rx, ry, alpha=95):
    w, h = size
    sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(sh)
    d.ellipse([w / 2 - rx, h / 2 - ry, w / 2 + rx, h / 2 + ry], fill=(24, 20, 16, alpha))
    return sh.filter(ImageFilter.GaussianBlur(ry * 0.55))


def place_kal(canvas: Image.Image, spec) -> Image.Image:
    _, _, pose, facing, hpx, fx, ground, halo_amt = spec
    scale = hpx / (TOP_Y - FOOT_Y)
    sprite, anchor = kal_layer(pose, hpx)
    if facing < 0:
        sprite = sprite.transpose(Image.FLIP_LEFT_RIGHT)
        anchor = (sprite.width - anchor[0], anchor[1])

    # sprite bottom corresponds to local y = Y0 (-48); soles sit at FOOT_Y
    y = int(round(ground + (FOOT_Y - S.Y0) * scale - sprite.height))
    x = int(round(fx - anchor[0]))

    # contact shadow on the ground
    sw, sh = int(hpx * 0.30), int(hpx * 0.055)
    shadow = contact_shadow((sw * 2, sh * 2), sw, sh, alpha=105)
    canvas.alpha_composite(shadow, (int(fx - sw), int(ground - sh * 0.9)))

    if halo_amt > 0:
        halo = paper_halo(sprite, halo_amt)
        if halo is not None:
            canvas.alpha_composite(halo, (x, y))
    canvas.alpha_composite(sprite, (x, y))
    return canvas


def compose(spec) -> str:
    sid, raw, pose, *_ = spec
    img = print_grade(upscale(os.path.join(RAW, raw))).convert("RGBA")
    img = place_kal(img, spec)
    out = ink.add_grain(img.convert("RGB"), 2.6, seed=hash(sid) % 999)
    path = os.path.join(FINAL, f"{sid.lower()}_1080.png")
    out.save(path, optimize=True)
    return path


def contact_sheet(paths, cols=4, tile=(480, 270)):
    rows = (len(paths) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (tile[0] + 8) + 8, rows * (tile[1] + 22) + 8), (238, 234, 226))
    d = ImageDraw.Draw(sheet)
    for i, p in enumerate(paths):
        im = Image.open(p).convert("RGB").resize(tile, Image.LANCZOS)
        x, y = 8 + (i % cols) * (tile[0] + 8), 8 + (i // cols) * (tile[1] + 22)
        sheet.paste(im, (x, y))
        d.text((x, y + tile[1] + 4), os.path.basename(p), fill=(40, 36, 32))
    out = os.path.join(FINAL, "_contact_sheet.png")
    sheet.save(out)
    return out


if __name__ == "__main__":
    os.makedirs(FINAL, exist_ok=True)
    todo = SHOTS
    if "--one" in sys.argv:
        idx = int(sys.argv[sys.argv.index("--one") + 1])
        todo = [SHOTS[idx]]
    paths = [compose(s) for s in todo]
    for p in paths:
        print("wrote", p)
    if "--one" not in sys.argv:
        print("wrote", contact_sheet(paths))
