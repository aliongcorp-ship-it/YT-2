"""KALDERA brand palette — a deliberately limited, warm-paper ink palette.

No glowing blues, no neon gradients, no HDR bloom: this is the visual
signature that keeps generated art away from the generic "AI look".
"""

# Core ink + paper
INK        = (25, 22, 20)
INK_SOFT   = (44, 39, 35)
PAPER      = (243, 234, 219)
PAPER_WARM = (235, 222, 201)
PAPER_DARK = (219, 203, 178)
CREAM      = (251, 246, 236)

# Accents
AMBER      = (232, 163, 61)
AMBER_DEEP = (196, 112, 31)
GLOW       = (246, 208, 106)
RUST       = (166, 67, 44)
RUST_DEEP  = (122, 46, 31)

# Neutrals
ASH        = (139, 131, 120)
SMOKE      = (91, 88, 84)
BASALT     = (59, 58, 60)
BASALT_DEEP= (33, 32, 34)

# Cold counterpoints (used sparingly for night / water / science)
SLATE      = (74, 88, 94)
DEEP_WATER = (43, 58, 64)


def rgba(color, alpha=255):
    if len(color) == 4:
        return color
    return (color[0], color[1], color[2], int(alpha))


def mix(a, b, t):
    """Linear mix of two RGB(A) colours."""
    n = min(len(a), len(b), 4)
    return tuple(int(round(a[i] * (1 - t) + b[i] * t)) for i in range(n))


def shade(color, factor):
    """Multiply brightness (factor < 1 darkens)."""
    return tuple(max(0, min(255, int(round(c * factor)))) for c in color[:3]) + tuple(color[3:])


def desaturate(color, t):
    lum = int(0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2])
    return mix(color, (lum, lum, lum), t)


PALETTE = {
    "ink": INK, "paper": PAPER, "amber": AMBER, "rust": RUST,
    "ash": ASH, "basalt": BASALT, "cream": CREAM,
}
