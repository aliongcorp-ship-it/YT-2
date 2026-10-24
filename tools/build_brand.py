"""Build the KALDERA brand kit: avatar, channel banner, logo lockup.

Everything is drawn deterministically from the engine, so re-running this
reproduces byte-similar assets and future art stays on-brand.
"""
from __future__ import annotations

import os
import sys

from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import ink, palette as P, stickman as S  # noqa: E402
from engine.fonts import draw_tracked, font, tracked_width  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "brand")
VB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "video")


def paper_bg(w, h, seed=7, base=P.PAPER):
    img = ink.make_paper(w, h, seed=seed, base=base)
    return img.convert("RGBA")


def strata(img, y0, y1, seed=12, alpha=46, count=7, color=P.INK_SOFT):
    """Hand-inked horizontal strata — the KALDERA signature background motif."""
    d = ImageDraw.Draw(img, "RGBA")
    for i in range(count):
        t = i / max(1, count - 1)
        y = y0 + (y1 - y0) * t
        pts = []
        for x in range(-20, img.width + 21, 26):
            yy = y + ink.smooth_noise(x * 0.004 + i * 5.3, seed + i) * 9
            pts.append((x, yy))
        ink.stroke(d, pts, 1.3 + 1.1 * (1 - abs(t - 0.5) * 2), 0.9,
                   fill=P.rgba(color, int(alpha * 0.62)), wobble=1.6, seed=seed + i * 7, step=9)
    return img


def halftone_burst(img, cx, cy, r, color=P.AMBER, alpha=54):
    """Dotted print gradient behind the character."""
    d = ImageDraw.Draw(img, "RGBA")
    gap = max(7, int(r / 22))
    for y in range(int(cy - r), int(cy + r), gap):
        for x in range(int(cx - r), int(cx + r), gap):
            dist = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
            if dist > r:
                continue
            fall = 1.0 - (dist / r) ** 1.5
            rr = gap * 0.42 * (0.35 + 0.85 * fall)
            d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=P.rgba(color, int(alpha * fall)))


# ---------------------------------------------------------------- avatar
def build_avatar(size=800):
    img = paper_bg(size, size, seed=21, base=P.PAPER_WARM)
    halftone_burst(img, size * 0.50, size * 0.44, size * 0.42, P.AMBER, 52)

    d = ImageDraw.Draw(img, "RGBA")
    cx, cy = size * 0.50, size * 0.48
    r = size * 0.392
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(232, 163, 61, 240))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=P.rgba(P.INK), width=int(size * 0.014))

    pose = S.P_brave(1.2).with_(expr="smirk", brow=0.55, look=(0.6, 0.0),
                                scarf_amp=1.3, scarf=1.05)
    scale = size * 0.0126
    sprite, anchor = S.Rig(2).render(pose, scale)
    img.alpha_composite(sprite, (int(cx - anchor[0] - size * 0.012),
                                 int(size * 1.062 - anchor[1])))

    # strata only in the lower band, clipped to the disc
    band = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    strata(band, size * 0.74, size * 0.97, seed=31, alpha=60, count=5)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
    img.paste(Image.alpha_composite(img.crop((0, 0, size, size)).convert("RGBA"),
                                    Image.composite(band, Image.new("RGBA", (size, size), (0, 0, 0, 0)), mask)),
              (0, 0))

    ring = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    dr = ImageDraw.Draw(ring)
    pad = int(size * 0.032)
    dr.ellipse([pad, pad, size - pad, size - pad], outline=P.rgba(P.INK), width=int(size * 0.020))
    img.alpha_composite(ring)

    out = ink.vignette(img.convert("RGB"), 0.14)
    out = ink.add_grain(out, 2.2, seed=5)
    p = os.path.join(OUT, f"avatar_{size}.png")
    out.save(p, optimize=True)
    return p


# ---------------------------------------------------------------- banner
def build_banner(w=2560, h=1440):
    img = paper_bg(w, h, seed=44, base=P.PAPER)
    strata(img, h * 0.62, h * 0.99, seed=51, alpha=46, count=8)
    strata(img, h * 0.20, h * 0.30, seed=57, alpha=20, count=2)

    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([w * 0.30, h * 0.02, w * 0.86, h * 1.02], fill=(232, 163, 61, 66))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(70)))
    halftone_burst(img, w * 0.745, h * 0.58, w * 0.215, P.AMBER_DEEP, 44)

    # character
    pose = S.P_point(1.1).with_(scarf_amp=1.25, brow=0.6, look=(0.6, 0.0))
    sprite, anchor = S.Rig(2).render(pose, 11.2)
    img.alpha_composite(sprite, (int(w * 0.735 - anchor[0]), int(h * 0.985 - anchor[1])))

    # wordmark plate
    d = ImageDraw.Draw(img, "RGBA")
    f = font("display", 226)
    txt, track = "KALDERA", 14
    tw = tracked_width(d, txt, f, track)
    x0 = w * 0.5 - tw / 2 - w * 0.115
    y0 = h * 0.315
    d.rectangle([x0 - 44, y0 - 40, x0 + tw + 40, y0 + 236], fill=(243, 234, 219, 208))
    draw_tracked(d, (x0, y0), txt, f, P.rgba(P.INK), tracking=track)
    ry = y0 + 244
    d.line([x0 - 2, ry, x0 + tw + 12, ry], fill=P.rgba(P.RUST_DEEP), width=6)
    ft = font("mono", 50)
    tag = "SEJARAH BUMI  &  MANUSIA NUSANTARA"
    ttag = tracked_width(d, tag, ft, 7)
    tx = x0 + 2
    d.rectangle([tx - 16, ry + 16, tx + ttag + 18, ry + 84], fill=(243, 234, 219, 252))
    draw_tracked(d, (tx, ry + 24), tag, ft, P.rgba(P.RUST_DEEP), tracking=7)

    out = ink.vignette(img.convert("RGB"), 0.16)
    out = ink.add_grain(out, 2.4, seed=9)
    p = os.path.join(OUT, "banner_2560x1440.png")
    out.save(p, optimize=True)
    return p


def build_lockup(w=1920, h=1080):
    img = paper_bg(w, h, seed=63)
    strata(img, h * 0.58, h * 0.92, seed=71, alpha=40, count=7)
    d = ImageDraw.Draw(img, "RGBA")
    f = font("display", 300)
    draw_tracked(d, (w * 0.5 - tracked_width(d, "KALDERA", f, 16) / 2, h * 0.30),
                 "KALDERA", f, P.rgba(P.INK), tracking=16)
    sprite, anchor = S.Rig(2).render(S.P_present(1.0), 8.4)
    img.alpha_composite(sprite, (int(w * 0.5 - anchor[0]), int(h * 0.99 - anchor[1])))
    out = ink.add_grain(img.convert("RGB"), 2.0, seed=3)
    p = os.path.join(OUT, "lockup_1920x1080.png")
    out.save(p, optimize=True)
    return p


if __name__ == "__main__":
    for fn in (build_avatar, build_banner, build_lockup):
        print("wrote", fn())
