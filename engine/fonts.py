"""Font loading + text helpers with accurate metrics and manual wrapping."""
from __future__ import annotations

import os
from functools import lru_cache

from PIL import ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(os.path.dirname(HERE), "brand", "fonts")

FILES = {
    "display":   ("Anton-Regular.ttf", None),
    "condensed": ("BebasNeue-Regular.ttf", None),
    "sans":      ("Archivo-VF.ttf", None),
    "serif":     ("Spectral-Regular.ttf", None),
    "serif_b":   ("Spectral-SemiBold.ttf", None),
    "title_serif": ("InstrumentSerif-Regular.ttf", None),
    "mono":      ("IBMPlexMono-Medium.ttf", None),
    "type":      ("CourierPrime-Regular.ttf", None),
    "type_b":    ("CourierPrime-Bold.ttf", None),
    "hand":      ("Caveat-VF.ttf", None),
}


@lru_cache(maxsize=256)
def font(name: str, size: int, weight: str | None = None) -> ImageFont.FreeTypeFont:
    """Load a font by role. `weight` applies to variable fonts (Archivo, Caveat)."""
    fname, _ = FILES[name]
    path = os.path.join(FONT_DIR, fname)
    f = ImageFont.truetype(path, size)
    if weight:
        try:
            f.set_variation_by_name(weight)
        except Exception:
            pass
    return f


def text_size(draw, txt, f) -> tuple[int, int]:
    box = draw.textbbox((0, 0), txt, font=f)
    return box[2] - box[0], box[3] - box[1]


def wrap(draw, txt: str, f, max_w: int) -> list[str]:
    """Greedy word wrap that respects real glyph widths."""
    words = txt.split()
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=f) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def draw_tracked(draw, xy, txt, f, fill, tracking=0, anchor_y="la"):
    """Draw text with letter-spacing (tracking). Returns drawn width."""
    x, y = xy
    for ch in txt:
        draw.text((x, y), ch, font=f, fill=fill, anchor="l" + anchor_y[1])
        x += draw.textlength(ch, font=f) + tracking
    return x - xy[0]


def tracked_width(draw, txt, f, tracking=0):
    if not txt:
        return 0
    return sum(draw.textlength(c, font=f) for c in txt) + tracking * (len(txt) - 1)
