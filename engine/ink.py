"""Ink, paper and print-texture primitives.

Everything here is deterministic given a seed, so a frame rendered twice
looks identical — important for chunked rendering and for re-renders.
"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy.ndimage import gaussian_filter

from . import palette as P


# ---------------------------------------------------------------- noise utils
def smooth_noise(t: float, seed: int = 0, octaves: int = 3) -> float:
    """Deterministic smooth 1-D noise in [-1, 1], used for hand-drawn wobble."""
    rng = np.random.default_rng(seed)
    v = 0.0
    amp = 1.0
    tot = 0.0
    for o in range(octaves):
        f = 0.5 * (2 ** o)
        ph = rng.uniform(0, math.tau)
        v += amp * math.sin(t * f + ph)
        tot += amp
        amp *= 0.5
    return v / tot


def value_noise_2d(h: int, w: int, cell: int, seed: int = 0) -> np.ndarray:
    """Smooth 2-D value noise in [0,1] (bilinear upsampled random lattice)."""
    rng = np.random.default_rng(seed)
    gh, gw = h // cell + 2, w // cell + 2
    g = rng.random((gh, gw)).astype(np.float32)
    img = Image.fromarray((g * 255).astype(np.uint8), "L").resize((w, h), Image.BICUBIC)
    return np.asarray(img, dtype=np.float32) / 255.0


# ------------------------------------------------------------------- paper
def make_paper(w: int, h: int, seed: int = 7, base=P.PAPER, fiber: float = 1.0,
               stain: float = 1.0) -> Image.Image:
    """Warm paper: low-frequency stain, fibre grain, and a faint vignette."""
    rng = np.random.default_rng(seed)
    low = value_noise_2d(h, w, max(24, w // 6), seed) * 0.55 + value_noise_2d(h, w, max(8, w // 20), seed + 1) * 0.45
    fibre = rng.normal(0, 1, (h, w)).astype(np.float32)
    fibre = gaussian_filter(fibre, 0.6)

    tone = np.array(base, dtype=np.float32)
    shade = 0.94 + 0.10 * low
    img = tone[None, None, :] * shade[:, :, None]
    img += (fibre * 2.6 * fiber)[:, :, None]
    img -= (np.clip(low - 0.62, 0, 1) * 12.0 * stain)[:, :, None]

    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = w / 2.0, h / 2.0
    r = np.sqrt(((xx - cx) / cx) ** 2 + ((yy - cy) / cy) ** 2) / 1.4142
    img *= (1.0 - 0.10 * np.clip(r, 0, 1) ** 1.6)[:, :, None]

    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB")


def add_grain(img: Image.Image, amount: float = 3.0, seed: int = 0) -> Image.Image:
    a = np.asarray(img.convert("RGB"), dtype=np.float32)
    rng = np.random.default_rng(seed)
    n = rng.normal(0, amount, a.shape[:2]).astype(np.float32)
    a += n[:, :, None]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB")


def vignette(img: Image.Image, strength: float = 0.28, power: float = 1.8) -> Image.Image:
    a = np.asarray(img.convert("RGB"), dtype=np.float32)
    h, w = a.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2) / 1.4142
    m = 1.0 - strength * np.clip(r, 0, 1) ** power
    a *= m[:, :, None]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB")


# -------------------------------------------------------------- ink strokes
def _quad_pts(p0, p1, w0, w1):
    (x0, y0), (x1, y1) = p0, p1
    dx, dy = x1 - x0, y1 - y0
    L = math.hypot(dx, dy) or 1e-6
    nx, ny = -dy / L, dx / L
    return [
        (x0 + nx * w0 / 2, y0 + ny * w0 / 2),
        (x1 + nx * w1 / 2, y1 + ny * w1 / 2),
        (x1 - nx * w1 / 2, y1 - ny * w1 / 2),
        (x0 - nx * w0 / 2, y0 - ny * w0 / 2),
    ]


def stroke(draw: ImageDraw.ImageDraw, pts, w0: float, w1: float | None = None,
           fill=P.INK, wobble: float = 0.0, seed: int = 0, step: float = 5.0,
           taper: bool = True):
    """Hand-inked polyline: tapered ribbon with round caps and optional wobble."""
    if w1 is None:
        w1 = w0
    if len(pts) < 2:
        return
    # resample with wobble for the hand-made feel
    rs: list[tuple[float, float]] = []
    arc = 0.0
    for i in range(len(pts) - 1):
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]
        seg = math.hypot(x1 - x0, y1 - y0)
        n = max(1, int(seg / step))
        for k in range(n):
            t = k / n
            x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
            if wobble:
                d = math.hypot(x1 - x0, y1 - y0) or 1
                nx, ny = -(y1 - y0) / d, (x1 - x0) / d
                o = wobble * smooth_noise(arc * 0.02 + i * 3.1, seed)
                x += nx * o
                y += ny * o
            rs.append((x, y))
            arc += seg / n
    rs.append(pts[-1])

    n = len(rs)
    widths = []
    for i in range(n):
        t = i / max(1, n - 1)
        base = w0 + (w1 - w0) * t
        if taper:  # slight swell in the middle, like a brush
            base *= 0.82 + 0.36 * math.sin(math.pi * min(1.0, max(0.0, t))) ** 0.6
        widths.append(base)

    for i in range(n - 1):
        draw.polygon(_quad_pts(rs[i], rs[i + 1], widths[i], widths[i + 1]), fill=fill)
    for i in range(n):
        r = widths[i] / 2
        if r <= 0:
            continue
        draw.ellipse([rs[i][0] - r, rs[i][1] - r, rs[i][0] + r, rs[i][1] + r], fill=fill)


def bezier(p0, p1, p2, p3=None, steps: int = 24):
    out = []
    for i in range(steps + 1):
        t = i / steps
        if p3 is None:
            x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * p2[0]
            y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * p2[1]
        else:
            x = ((1 - t) ** 3 * p0[0] + 3 * (1 - t) ** 2 * t * p1[0]
                 + 3 * (1 - t) * t ** 2 * p2[0] + t ** 3 * p3[0])
            y = ((1 - t) ** 3 * p0[1] + 3 * (1 - t) ** 2 * t * p1[1]
                 + 3 * (1 - t) * t ** 2 * p2[1] + t ** 3 * p3[1])
        out.append((x, y))
    return out


def hatch(draw, box, angle=-38, gap=9, width=1.6, fill=P.INK, alpha=200):
    """Diagonal hatching inside a box — the classic engraving shadow."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    diag = math.hypot(w, h)
    dx, dy = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    n = int(diag / gap) + 2
    col = P.rgba(fill, alpha)
    for i in range(n):
        t = -diag + i * gap
        cx, cy = x0 + w / 2 + dx * t, y0 + h / 2 + dy * t
        draw.line([(cx - dx * diag, cy - dy * diag), (cx + dx * diag, cy + dy * diag)],
                  fill=col, width=max(1, int(width)))


def soft_shadow(img: Image.Image, mask: Image.Image, offset=(8, 14), blur=18,
                color=(0, 0, 0), alpha=110) -> Image.Image:
    """Drop shadow from an L mask; returns a new RGBA image with shadow under img."""
    sh = Image.new("L", mask.size, 0)
    sh.paste(mask, offset)
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    layer = Image.new("RGBA", img.size, color + (0,))
    layer.putalpha(sh.point(lambda v: int(v * alpha / 255)))
    out = layer.copy()
    out.alpha_composite(img.convert("RGBA"))
    return out


# ------------------------------------------------------------------ halftone
def halftone(size, dot=6, color=P.INK, alpha=70, ramp=None):
    """Dot-screen overlay; optional `ramp` (L image) modulates dot size."""
    w, h = size
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for yy in range(0, h, dot):
        for xx in range(0, w, dot):
            r = dot * 0.34
            if ramp is not None:
                r *= ramp.getpixel((min(w - 1, xx), min(h - 1, yy))) / 255.0
            if r > 0.4:
                d.ellipse([xx - r, yy - r, xx + r, yy + r], fill=P.rgba(color, alpha))
    return img


def edge_burn(img: Image.Image, amount=26, seed=3) -> Image.Image:
    """Uneven darkening at the borders, like a printed plate."""
    a = np.asarray(img.convert("RGB"), dtype=np.float32)
    h, w = a.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    edge = np.minimum.reduce([xx, yy, w - 1 - xx, h - 1 - yy])
    m = np.clip(edge / (min(w, h) * 0.16), 0, 1)
    n = value_noise_2d(h, w, 90, seed)
    a *= (1 - (1 - m) * (amount / 100.0) * (0.7 + 0.6 * n))[:, :, None]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB")
