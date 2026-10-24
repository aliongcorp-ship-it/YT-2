"""KAL — the KALDERA stickman.

A small hand-inked character rig: forward kinematics + expressions, rendered
with PIL in a local unit space (1 unit ≈ 1% of body height, y up, hip origin,
facing +x, mirrored on composite). Because the character is *drawn* and not
generated, he is pixel-identical across the avatar, thumbnails, every episode
and every future video.

Signature elements (never change these):
  * amber field cap with a short brim
  * rust scarf that always trails, animated by `Pose.scarf`
  * cream face disc, marker-weight ink limbs
  * small rust satchel at the hip
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace

from PIL import Image, ImageDraw

from . import ink
from . import palette as P

# ------------------------------------------------------------------ geometry
X0, X1 = -58.0, 60.0
Y0, Y1 = -48.0, 74.0

HEAD_R = 15.8
NECK_Y = 30.0
HEAD_CY = NECK_Y + 4.0 + HEAD_R
UPPER_ARM, FOREARM = 15.5, 15.0
THIGH, SHIN = 20.0, 20.0
HIP_DX = 2.4
STROKE = 3.3
CAP_R = HEAD_R + 1.45
INK = P.rgba(P.INK)
BAND_Y = HEAD_CY + 3.9


def _dir(deg: float) -> tuple[float, float]:
    """0° = straight down, positive rotates toward the facing (+x) direction."""
    r = math.radians(deg)
    return math.sin(r), -math.cos(r)


def _fk(origin, deg, length):
    dx, dy = _dir(deg)
    return origin[0] + dx * length, origin[1] + dy * length


@dataclass
class Pose:
    lean: float = 0.0
    head_tilt: float = 0.0
    head_dx: float = 0.0
    bob: float = 0.0
    sway: float = 0.0
    arm_near: tuple[float, float] = (8, 12)
    arm_far: tuple[float, float] = (-8, 12)
    leg_near: tuple[float, float] = (5, 3)
    leg_far: tuple[float, float] = (-5, 4)
    expr: str = "neutral"
    mouth_open: float = 0.0
    mouth_wide: float = 0.35
    eye_wide: float = 0.0
    blink: float = 0.0
    look: tuple[float, float] = (0.0, 0.0)
    brow: float = 0.0
    scarf: float = 0.0
    scarf_amp: float = 1.0
    hat: bool = True
    hat_tilt: float = 0.0
    bag: bool = True
    shadow: float = 1.0
    sweat: float = 0.0
    ink_seed: int = 11

    def with_(self, **kw) -> "Pose":
        return replace(self, **kw)


class Rig:
    def __init__(self, supersample: int = 2):
        self.ss = supersample

    # ------------------------------------------------------------------ core
    def render(self, pose: Pose, scale: float, shadow: bool = True):
        s = scale * self.ss
        W = int(math.ceil((X1 - X0) * s))
        H = int(math.ceil((Y1 - Y0) * s))
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        seed = pose.ink_seed

        def T(p):
            return ((p[0] - X0) * s, (Y1 - p[1]) * s)

        def W_(u):
            return max(1, int(round(u * s)))

        def stroke(pts, w0, w1=None, col=None, wob=0.4, sd=0):
            ink.stroke(d, [T(p) for p in pts], max(1.0, w0 * s),
                       max(1.0, (w1 if w1 is not None else w0) * s),
                       fill=col or INK, wobble=wob, seed=sd, step=4.2 * self.ss)

        def poly(pts, fill, outline=None, ow=1.5):
            pp = [T(p) for p in pts]
            d.polygon(pp, fill=fill)
            if outline:
                d.line(pp + [pp[0]], fill=outline, width=W_(ow))

        def ell(cx, cy, rx, ry, fill=None, outline=None, ow=1.5):
            p = T((cx, cy))
            box = [p[0] - rx * s, p[1] - ry * s, p[0] + rx * s, p[1] + ry * s]
            d.ellipse(box, fill=fill, outline=outline, width=W_(ow))

        # ---------------------------------------------------------- skeleton
        hip = (pose.sway, pose.bob)
        ln = math.radians(pose.lean)
        neck = (hip[0] + math.sin(ln) * NECK_Y, hip[1] + math.cos(ln) * NECK_Y)
        chest = (hip[0] + math.sin(ln) * NECK_Y * 0.55, hip[1] + math.cos(ln) * NECK_Y * 0.55)
        ht = math.radians(pose.lean + pose.head_tilt)
        head = (neck[0] + pose.head_dx + math.sin(ht) * (4 + HEAD_R),
                neck[1] + math.cos(ht) * (4 + HEAD_R))

        # ------------------------------------------------------------- shadow
        if shadow and pose.shadow > 0:
            ell(hip[0] + 5, Y0 + 3.0, 21, 3.9, fill=(22, 18, 14, int(54 * pose.shadow)))

        # --------------------------------------------------------------- legs
        for near, (ang, dx) in ((False, (pose.leg_far, -HIP_DX)), (True, (pose.leg_near, HIP_DX))):
            hip_a, knee_a = ang
            base = (hip[0] + dx, hip[1] - 1.2)
            knee = _fk(base, hip_a + pose.lean * 0.22, THIGH)
            ankle = _fk(knee, hip_a - knee_a, SHIN)
            col = INK if near else (48, 43, 38, 236)
            w = STROKE * (1.0 if near else 0.90)
            stroke([base, knee, ankle], w, w * 0.94, col, 0.5, seed + 3)
            # shoe
            toe = (ankle[0] + 7.4, ankle[1] - 1.6)
            stroke([(ankle[0] - 1.8, ankle[1] + 0.1), (ankle[0] + 1.0, ankle[1] - 0.9), toe],
                   w * 1.22, w * 0.86, col, 0.25, seed + 5)

        # -------------------------------------------------------------- torso
        stroke([hip, chest, neck], STROKE * 1.04, STROKE * 0.97, INK, 0.45, seed)

        # -------------------------------------------------------------- bag
        if pose.bag:
            bx, by = hip[0] - 8.4, hip[1] + 8.6
            body = [(bx - 4.9, by + 4.4), (bx + 5.1, by + 4.4), (bx + 4.3, by - 4.6), (bx - 4.3, by - 4.6)]
            poly(body, P.rgba(P.RUST_DEEP), outline=P.rgba(P.INK), ow=1.5)
            flap = [(bx - 5.0, by + 4.5), (bx + 5.2, by + 4.5), (bx + 4.7, by - 0.4),
                    (bx + 0.2, by - 2.1), (bx - 4.4, by - 0.4)]
            poly(flap, P.rgba(P.RUST), outline=P.rgba(P.INK), ow=1.2)
            ell(bx + 0.2, by - 0.2, 1.25, 1.25, fill=P.rgba(P.AMBER))
            # strap across the chest
            stroke([(neck[0] - 1.4, neck[1] - 2.6), (hip[0] - 3.2, hip[1] + 15.0),
                    (bx + 2.0, by + 4.2)], STROKE * 0.46, STROKE * 0.46,
                   P.rgba(P.RUST_DEEP), 0.3, seed + 8)

        # --------------------------------------------------------- far arm
        self._arm(stroke, ell, neck, pose.arm_far, STROKE * 0.90, (48, 43, 38, 236), seed + 21)

        # ------------------------------------------------------------ scarf
        self._scarf(stroke, poly, ell, pose, neck, seed)

        # ------------------------------------------------------------- head
        self._head(d, T, s, W_, ell, poly, stroke, head, pose, seed)

        # --------------------------------------------------------- near arm
        self._arm(stroke, ell, neck, pose.arm_near, STROKE, INK, seed + 11)

        # ------------------------------------------------------------- sweat
        if pose.sweat > 0:
            a = (head[0] + 17.5, head[1] + 9 + 3 * pose.sweat)
            r = 2.3
            poly([(a[0], a[1] + r * 2.2), (a[0] + r, a[1] - r * 0.2),
                  (a[0] + r * 0.6, a[1] - r * 1.15), (a[0] - r * 0.6, a[1] - r * 1.15),
                  (a[0] - r, a[1] - r * 0.2)], (128, 174, 192, 230),
                 outline=P.rgba(P.INK), ow=1.1)

        if self.ss > 1:
            img = img.resize((int(W / self.ss), int(H / self.ss)), Image.LANCZOS)
        return img, ((hip[0] - X0) * scale, (Y1 - hip[1]) * scale)

    # ---------------------------------------------------------------- pieces
    def _arm(self, stroke, ell, neck, angles, w, col, seed):
        sh_a, el_a = angles
        shoulder = (neck[0] - 1.2, neck[1] - 2.2)
        elbow = _fk(shoulder, sh_a, UPPER_ARM)
        wrist = _fk(elbow, sh_a + el_a, FOREARM)
        stroke([shoulder, elbow, wrist], w, w * 0.84, col, 0.5, seed)
        r = w * 0.58
        ell(wrist[0], wrist[1], r, r, fill=col)

    def _scarf(self, stroke, poly, ell, pose, neck, seed):
        base = (neck[0] - 1.6, neck[1] - 0.6)
        for k, (ln, wid, off, alpha, drop) in enumerate(
                ((22.5, 4.4, 0.0, 255, 2.2), (16.5, 3.1, 2.0, 215, 5.0))):
            s1 = math.sin(pose.scarf + off) * 4.6 * pose.scarf_amp
            s2 = math.cos(pose.scarf * 0.85 + off) * 6.6 * pose.scarf_amp
            pts = ink.bezier(
                base,
                (base[0] - ln * 0.34, base[1] - 5.5 + s1 * 0.7),
                (base[0] - ln * 0.74, base[1] - drop + s2),
                (base[0] - ln, base[1] - drop * 1.6 + s1),
                steps=16)
            stroke(pts, wid, wid * 0.42, P.rgba(P.RUST, alpha), 0.25, seed + 30 + k)
        # knot
        ell(base[0] + 0.6, base[1] - 0.4, 4.7, 3.6, fill=P.rgba(P.RUST),
            outline=P.rgba(P.INK), ow=1.5)
        ell(base[0] + 0.6, base[1] - 0.4, 1.5, 1.4, fill=P.rgba(P.RUST_DEEP))

    def _head(self, d, T, s, W_, ell, poly, stroke, head, pose, seed):
        cx, cy = head
        r = HEAD_R
        INKC = P.rgba(P.INK)

        # face
        ell(cx, cy, r, r, fill=P.rgba(P.CREAM, 249))

        # ---- brows
        br = pose.brow
        by = cy + 1.6
        for i, ex in enumerate((cx + 1.9, cx + 10.9)):
            raise_ = 1.5 * br + 2.6 * max(0.0, -br)      # + = surprised, - = focused
            ang = -1.5 * max(0.0, -br) + 0.6 * br
            stroke([(ex - 2.7, by - 0.5 + ang), (ex, by + raise_ * 0.55), (ex + 2.7, by - 0.4 - ang)],
                   STROKE * 0.50, STROKE * 0.50, INKC, 0.16, seed + 13 + i)

        # ---- eyes
        ey = cy - 4.4
        wide = 1.0 + 0.30 * pose.eye_wide
        for ex in (cx + 1.9, cx + 10.9):
            if pose.blink > 0.55:
                stroke([(ex - 2.9, ey - 0.3), (ex, ey - 1.1), (ex + 2.9, ey - 0.3)],
                       STROKE * 0.46, STROKE * 0.46, INKC, 0.15, seed + 9)
                continue
            rw, rh = 2.75 * wide, 3.35 * wide * (1 - 0.30 * pose.blink)
            ell(ex, ey, rw, rh, fill=P.rgba(P.PAPER, 255))
            lx, ly = pose.look
            ell(ex + lx * rw * 0.34, ey + ly * rh * 0.32, rw * 0.54, rh * 0.50, fill=INKC)
            ell(ex, ey, rw, rh, outline=INKC, ow=0.9)

        # ---- mouth
        self._mouth(stroke, ell, cx, cy, pose, INKC, seed)

        # ---- jaw (lower arc only, keeps the cap clean)
        pts = [(cx + math.cos(math.radians(a)) * r, cy + math.sin(math.radians(a)) * r)
               for a in range(-6, 187, 12)]
        stroke(pts, STROKE * 0.86, STROKE * 0.86, INKC, 0.32, seed + 7)

        # ---- field cap
        if pose.hat:
            tilt = pose.hat_tilt
            h = BAND_Y - cy                       # chord height above head centre
            xw = math.sqrt(max(0.0, CAP_R ** 2 - h ** 2))
            arc = []
            N = 22
            for i in range(N + 1):
                phi = math.pi * i / N             # 0..pi across the chord
                x = cx - xw + 2 * xw * (i / N)
                y = cy + math.sqrt(max(0.0, CAP_R ** 2 - (x - cx) ** 2))
                arc.append((x, y))
            crown = [(cx - xw, BAND_Y)] + arc[::-1] + [(cx + xw, BAND_Y)]
            poly(crown, P.rgba(P.AMBER))
            # shading on the shadow side
            shade_pts = [(cx - xw, BAND_Y)] + [p for p in arc if p[0] <= cx - xw * 0.15] + [(cx - xw * 0.15, BAND_Y)]
            poly(shade_pts, P.rgba(P.AMBER_DEEP, 115))
            # band
            poly([(cx - xw, BAND_Y + 1.5), (cx + xw, BAND_Y + 1.5),
                  (cx + xw, BAND_Y - 1.9), (cx - xw, BAND_Y - 1.9)], P.rgba(P.RUST_DEEP))
            # brim: tapered lens angled slightly down toward the facing side
            b0x, b0y = cx + xw * 0.16, BAND_Y + 1.9
            b1 = (cx + xw + 13.0, BAND_Y - 1.0)
            brim = [(b0x, b0y + 0.2), (b0x + (b1[0] - b0x) * 0.5, b0y + 0.9),
                    (b1[0], b1[1] + 0.9), (b1[0] - 0.4, b1[1] - 0.6),
                    (b0x + (b1[0] - b0x) * 0.45, b0y - 3.1), (b0x, b0y - 2.9)]
            poly(brim, P.rgba(P.AMBER_DEEP), outline=INKC, ow=1.15)
            # crown outline
            stroke(crown + [(cx - xw, BAND_Y)], STROKE * 0.58, STROKE * 0.58, INKC, 0.35, seed + 42)

    def _mouth(self, stroke, ell, cx, cy, pose, INKC, seed):
        mx, my = cx + 5.6, cy - 7.9
        op = max(0.0, min(1.0, pose.mouth_open))
        wide = 0.55 + 0.85 * pose.mouth_wide
        expr = pose.expr

        if op > 0.08:
            mw = 1.85 + 1.85 * wide
            mh = 0.65 + 2.35 * op
            ell(mx, my, mw, mh, fill=P.rgba(P.RUST_DEEP))
            ell(mx, my + mh * 0.46, mw * 0.48, mh * 0.26, fill=P.rgba(P.RUST))
            ell(mx, my, mw, mh, outline=INKC, ow=1.1)
        elif expr == "shock":
            ell(mx, my, 1.9, 2.3, fill=P.rgba(P.RUST_DEEP), outline=INKC, ow=1.2)
        elif expr == "smile":
            stroke([(mx - 3.6 * wide, my - 0.5), (mx, my + 1.5), (mx + 3.6 * wide, my - 0.6)],
                   STROKE * 0.50, STROKE * 0.50, INKC, 0.16, seed + 17)
        elif expr == "frown":
            stroke([(mx - 3.4 * wide, my + 1.1), (mx, my - 1.4), (mx + 3.4 * wide, my + 1.0)],
                   STROKE * 0.50, STROKE * 0.50, INKC, 0.16, seed + 18)
        elif expr == "smirk":
            stroke([(mx - 3.3, my - 0.2), (mx + 0.8, my + 0.9), (mx + 4.2, my + 2.3)],
                   STROKE * 0.52, STROKE * 0.46, INKC, 0.16, seed + 19)
        else:
            stroke([(mx - 3.4 * wide, my - 0.2), (mx + 0.4, my + 0.4), (mx + 3.8 * wide, my - 0.3)],
                   STROKE * 0.48, STROKE * 0.42, INKC, 0.16, seed + 20)


# --------------------------------------------------------------------- poses
def P_idle(t=0.0):
    b = math.sin(t * 1.1)
    return Pose(bob=0.35 * b, lean=1.0, head_tilt=0.7 * b,
                arm_near=(7 + 1.6 * b, 14), arm_far=(-6 - 1.4 * b, 12),
                leg_near=(5, 3), leg_far=(-5, 4),
                scarf=t * 1.4, scarf_amp=0.5, expr="smile", brow=0.18, look=(0.2, 0.05))


def P_talk(t=0.0):
    b = math.sin(t * 1.3)
    g = math.sin(t * 2.2)
    return Pose(bob=0.4 * b, lean=1.8, head_tilt=1.0 * b,
                arm_near=(42 + 10 * g, 44 - 13 * g), arm_far=(15 + 6 * b, 33),
                leg_near=(4, 3), leg_far=(-6, 5),
                expr="neutral", mouth_open=0.34 + 0.22 * math.sin(t * 7.1),
                mouth_wide=0.5, brow=0.32 + 0.24 * g, scarf=t * 1.6, scarf_amp=0.6)


def P_point(t=0.0):
    b = math.sin(t * 1.2)
    return Pose(bob=0.3 * b, lean=2.4, head_tilt=1.2,
                arm_near=(97 + 3 * b, 5), arm_far=(11, 25),
                leg_near=(7, 3), leg_far=(-7, 5),
                expr="smile", brow=0.5, look=(0.65, 0.15), scarf=t * 1.5, scarf_amp=0.8)


def P_present(t=0.0):
    b = math.sin(t * 1.1)
    return Pose(bob=0.25 * b, lean=-1.2, head_tilt=-1.0,
                arm_near=(57 + 3 * b, 15), arm_far=(-44, 20),
                leg_near=(6, 3), leg_far=(-8, 6),
                expr="smile", brow=0.6, look=(-0.45, 0.1), scarf=t * 1.3, scarf_amp=0.7)


def P_shock(t=0.0):
    return Pose(lean=-4.5, head_tilt=-3.0, bob=0.9,
                arm_near=(124, 24), arm_far=(104, 32),
                leg_near=(10, 2), leg_far=(-11, 8),
                expr="shock", eye_wide=1.0, brow=1.0,
                scarf=t * 2.2, scarf_amp=1.3, sweat=0.8)


def P_think(t=0.0):
    b = math.sin(t * 1.0)
    return Pose(bob=0.2 * b, lean=2.0, head_tilt=3.0,
                arm_near=(46, 116), arm_far=(-28, 14),
                leg_near=(5, 3), leg_far=(-6, 5),
                expr="smirk", brow=-0.3, look=(-0.5, -0.35), scarf=t * 1.0, scarf_amp=0.3)


def P_walk(t=0.0, speed=1.0):
    ph = t * 6.0 * speed
    return Pose(bob=1.8 * abs(math.cos(ph)) - 0.5, lean=5.0, head_tilt=-1.5, head_dx=0.6,
                arm_near=(-24 * math.sin(ph), 22 + 10 * abs(math.sin(ph))),
                arm_far=(24 * math.sin(ph), 22 + 10 * abs(math.sin(ph))),
                leg_near=(26 * math.sin(ph), max(0.0, 34 * math.sin(ph - 1.1))),
                leg_far=(26 * math.sin(ph + math.pi), max(0.0, 34 * math.sin(ph + math.pi - 1.1))),
                expr="smile", brow=0.2, scarf=t * 3.0, scarf_amp=1.4, look=(0.5, 0.0))


def P_run(t=0.0):
    ph = t * 9.0
    return Pose(bob=2.5 * abs(math.cos(ph)) + 0.5, lean=13.0, head_tilt=-5.0, head_dx=1.4,
                arm_near=(-46 * math.sin(ph) + 10, 74), arm_far=(46 * math.sin(ph) + 10, 74),
                leg_near=(44 * math.sin(ph), max(0.0, 62 * math.sin(ph - 1.0))),
                leg_far=(44 * math.sin(ph + math.pi), max(0.0, 62 * math.sin(ph + math.pi - 1.0))),
                expr="smile", brow=0.6, scarf=t * 4.2, scarf_amp=1.9, look=(0.7, 0.0))


def P_crouch(t=0.0):
    b = math.sin(t * 1.2)
    return Pose(bob=-7.0 + 0.4 * b, lean=16.0, head_tilt=-8.0,
                arm_near=(64, 46), arm_far=(50, 60),
                leg_near=(58, 96), leg_far=(40, 104),
                expr="neutral", brow=0.4, look=(0.5, -0.5), scarf=t * 1.2, scarf_amp=0.5)


def P_lookup(t=0.0):
    b = math.sin(t * 1.1)
    return Pose(bob=0.3 * b, lean=-3.0, head_tilt=-11.0,
                arm_near=(20, 8), arm_far=(-18, 8),
                leg_near=(4, 3), leg_far=(-5, 4),
                expr="smile", eye_wide=0.35, brow=0.7, look=(0.25, -0.8),
                scarf=t * 1.2, scarf_amp=0.7)


def P_listen(t=0.0):
    b = math.sin(t * 1.1)
    return Pose(bob=0.3 * b, lean=0.0, head_tilt=1.5,
                arm_near=(6, 14), arm_far=(-5, 11),
                leg_near=(5, 3), leg_far=(-5, 4),
                expr="neutral", brow=0.35, look=(-0.3, 0.1), scarf=t * 1.2, scarf_amp=0.5)


def P_brave(t=0.0):
    b = math.sin(t * 1.4)
    return Pose(bob=0.3 * b, lean=6.0, head_tilt=-2.0,
                arm_near=(30 + 3 * b, 18), arm_far=(-22, 16),
                leg_near=(8, 4), leg_far=(-8, 6),
                expr="smirk", brow=0.6, look=(0.5, 0.0), scarf=t * 2.4, scarf_amp=1.2)


POSES = {
    "idle": P_idle, "talk": P_talk, "point": P_point, "present": P_present,
    "shock": P_shock, "think": P_think, "walk": P_walk, "run": P_run,
    "crouch": P_crouch, "lookup": P_lookup, "listen": P_listen, "brave": P_brave,
}


def pose(name: str, t: float = 0.0, **kw) -> Pose:
    p = POSES[name](t)
    return p.with_(**kw) if kw else p


def render_pose(name: str, t: float, scale: float, ss: int = 2, **kw):
    return Rig(ss).render(pose(name, t, **kw), scale)
