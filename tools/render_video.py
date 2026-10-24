"""KALDERA video renderer.

Turns the ten plates into a 1080p documentary cut:
  * camera moves per shot (Ken Burns with parallax-correct KAL)
  * torn-paper wipes with an inked edge (the channel's transition)
  * KAL animated frame-by-frame, glued to the ground of each plate
  * chapter lower-thirds, hook title, brand outro
  * audio: narration + synthesised score + sfx, loudness-normalised

    python env/bin/python tools/render_video.py --plan     # print the timeline
    python env/bin/python tools/render_video.py --audio    # build final mix wav
    python env/bin/python tools/render_video.py --render   # render (long)
    python env/bin/python tools/render_video.py --mux      # attach audio
"""
from __future__ import annotations

import glob
import json
import math
import os
import subprocess
import sys
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import ink, palette as P, stickman as S  # noqa: E402
S.FOOT_Y = -46.0
from engine.fonts import draw_tracked, font, tracked_width  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(ROOT, "art", "final")
RAW = os.path.join(ROOT, "art", "raw")
VO = os.path.join(ROOT, "audio", "vo")
AUD = os.path.join(ROOT, "audio")
VID = os.path.join(ROOT, "video")
SCR = os.path.join(ROOT, "scripts")
W, H, FPS = 1920, 1080, 24
KAL_H = S.Y1 - S.FOOT_Y      # authored character height in local units
OVER = 1.30                      # pre-scale factor for camera headroom
TRANS = 0.85                     # transition seconds

import imageio_ffmpeg  # noqa: E402
FF = imageio_ffmpeg.get_ffmpeg_exe()

# ----------------------------------------------------------------- timeline
# Each shot: plates, VO pieces covered, KAL pose, camera start/end, KAL anchor
# (anchor is in final-frame coords and is parallaxed by the camera).
SHOTS = [
    # sx / sy = KAL's horizontal spot and ground line on screen (0..1)
    dict(plate="img-05", pos="shock",   h=384, sx=0.18, sy=0.90,
         zoom=(1.00, 1.13), cxy=(0.50, 0.56), label=None),
    dict(plate="img-01", pos="present", h=409, sx=0.22, sy=0.90,
         zoom=(1.16, 1.02), cxy=(0.52, 0.55), label="BAB 1 · LEGENDA DI TEPI DANAU"),
    dict(plate="img-02", pos="lookup",  h=320, sx=0.26, sy=0.93,
         zoom=(1.02, 1.17), cxy=(0.46, 0.50), label="BAB 2 · BENTUK YANG TIDAK MUNGKIN"),
    dict(plate="img-03", pos="brave",   h=384, sx=0.20, sy=0.94,
         zoom=(1.14, 1.00), cxy=(0.55, 0.48), label="BAB 3 · GUNUNG YANG TIDAK ADA LAGI"),
    dict(plate="img-04", pos="crouch",  h=345, sx=0.30, sy=0.90,
         zoom=(1.00, 1.15), cxy=(0.42, 0.55), label="BAB 4 · TANDA-TANDA"),
    dict(plate="img-05", pos="shock",   h=358, sx=0.78, sy=0.90,
         zoom=(1.22, 1.06), cxy=(0.55, 0.50), label=None),
    dict(plate="img-06", pos="run",     h=409, sx=0.74, sy=0.92,
         zoom=(1.03, 1.18), cxy=(0.50, 0.52), label="BAB 5 · NERAKA YANG BERGERAK"),
    dict(plate="img-07", pos="walk",    h=384, sx=0.24, sy=0.93,
         zoom=(1.15, 1.01), cxy=(0.48, 0.56), label="BAB 6 · DUNIA TANPA MATAHARI"),
    dict(plate="img-09", pos="point",   h=384, sx=0.20, sy=0.93,
         zoom=(1.00, 1.14), cxy=(0.52, 0.48), label="BAB 7 · KOTA YANG RUNTUH"),
    dict(plate="img-08", pos="crouch",  h=422, sx=0.40, sy=0.94,
         zoom=(1.12, 1.00), cxy=(0.44, 0.54), label="BAB 8 · APAKAH KITA HAMPIR PUNAH?"),
    dict(plate="img-08", pos="listen",  h=422, sx=0.40, sy=0.94,
         zoom=(1.00, 1.10), cxy=(0.52, 0.52), label=None),
    dict(plate="img-02", pos="present", h=320, sx=0.26, sy=0.93,
         zoom=(1.20, 1.04), cxy=(0.50, 0.52), label=None),
    dict(plate="img-10", pos="lookup",  h=345, sx=0.30, sy=0.92,
         zoom=(1.02, 1.16), cxy=(0.46, 0.56), label="BAB 9 · KENAPA KITA MASIH ADA"),
]

# which VO piece index starts which shot (piece indices refer to scripts/vo_pieces.json)
SHOT_VO = [0, 2, 3, 5, 6, 8, 9, 11, 13, 15, 17, 18, 19]
PIECE_GAP = 0.42        # breath between narration pieces
OUTRO = 11.0            # brand outro after narration ends
HOOK_TITLE = (1.6, 7.2)  # hook title visible window


# ------------------------------------------------------------------- utils
def ff_duration(path: str) -> float:
    out = subprocess.run([FF, "-i", path], capture_output=True, text=True).stderr
    for line in out.splitlines():
        if "Duration:" in line:
            hms = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = hms.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    return 0.0


def wav_duration(path: str) -> float:
    with wave.open(path, "rb") as w:
        return w.getnframes() / w.getframerate()


PLATE_MAP = {
    "img-01": "img01_legend.png", "img-02": "img02_lake_today.png",
    "img-03": "img03_old_mountain.png", "img-04": "img04_fumaroles.png",
    "img-05": "img05_column.png", "img-06": "img06_pyroclastic.png",
    "img-07": "img07_long_night.png", "img-08": "img08_cave_shelter.png",
    "img-09": "img09_caldera_collapse.png", "img-10": "img10_samosir_today.png",
}


def _autocrop(im: Image.Image) -> Image.Image:
    a = np.asarray(im.convert("RGB"), dtype=np.int16)
    m = np.abs(a - np.array([243, 234, 219], dtype=np.int16)).sum(axis=2) > 46
    rows = np.where(m.mean(axis=1) > 0.42)[0]
    cols = np.where(m.mean(axis=0) > 0.42)[0]
    if len(rows) < 10 or len(cols) < 10:
        return im
    return im.crop((int(cols[0]) + 4, int(rows[0]) + 4, int(cols[-1]) - 4, int(rows[-1]) - 4))


def _grade(im: Image.Image) -> Image.Image:
    a = np.clip(np.asarray(im.convert("RGB"), dtype=np.float32) / 255.0, 0, 1) ** 1.045
    a[..., 0] *= 1.012
    a[..., 2] *= 0.985
    lum = (0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2])[..., None]
    a = lum + (a - lum) * 0.94
    out = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8), "RGB")
    out = ink.edge_burn(out, amount=18, seed=17)
    return ink.vignette(out, 0.24, power=1.55)


def load_plates() -> dict[str, Image.Image]:
    """Load the RAW generated plates (no figures) and grade them.

    KAL is added by the renderer, never baked into the plates, so he can move.
    """
    out = {}
    for key, fname in PLATE_MAP.items():
        im = _autocrop(Image.open(os.path.join(RAW, fname)).convert("RGB"))
        tar = W / H
        ar = im.width / im.height
        if ar > tar:
            nw = int(im.height * tar)
            im = im.crop(((im.width - nw) // 2, 0, (im.width + nw) // 2, im.height))
        else:
            nh = int(im.width / tar)
            im = im.crop((0, (im.height - nh) // 2, im.width, (im.height + nh) // 2))
        im = im.resize((int(W * OVER), int(H * OVER)), Image.LANCZOS)
        out[key] = ink.add_grain(_grade(im), 1.6, seed=abs(hash(key)) % 500)
    return out


def build_timeline():
    pieces = sorted(glob.glob(os.path.join(VO, "pc_*.mp3")))
    if not pieces:
        pieces = sorted(glob.glob(os.path.join(VO, "*.mp3")))
    if not pieces:
        raise SystemExit("no narration clips found in audio/vo")
    durs = [ff_duration(p) for p in pieces]
    starts, t = [], 0.0
    for d in durs:
        starts.append(t)
        t += d + PIECE_GAP
    vo_total = t
    idxs = [min(i, len(starts) - 1) for i in SHOT_VO]
    cuts = [starts[i] for i in idxs] + [vo_total]
    shots = []
    for i, spec in enumerate(SHOTS):
        s, e = cuts[i], cuts[i + 1]
        shots.append(dict(spec, start=s, end=e, dur=max(2.0, e - s),
                          camera="in" if spec["zoom"][1] > spec["zoom"][0] else "out"))
    total = vo_total + OUTRO
    tl = dict(pieces=pieces, durs=durs, starts=starts, vo_total=vo_total,
              total=total, shots=shots, fps=FPS, w=W, h=H, gap=PIECE_GAP)
    os.makedirs(SCR, exist_ok=True)
    with open(os.path.join(SCR, "timeline.json"), "w") as f:
        json.dump({k: v for k, v in tl.items() if k != "pieces"} | {
            "pieces": [os.path.basename(p) for p in pieces]}, f, indent=1)
    return tl


# ----------------------------------------------------------------- camera
def camera(plate: Image.Image, u: float, zoom: tuple, cxy: tuple):
    """Crop+resize a plate for shot progress u.

    zoom z > 1 means a wider view (objects appear smaller): the crop is W*z.
    Returns the screen frame and a project(plate_px) -> (screen_x, screen_y, k)
    where k is the plate-px to screen-px factor (1/z).
    """
    z = zoom[0] + (zoom[1] - zoom[0]) * u
    bw, bh = plate.size
    cw, ch = W * z, H * z
    cx, cy = cxy[0] * bw, cxy[1] * bh
    x0 = min(max(0.0, cx - cw / 2), bw - cw)
    y0 = min(max(0.0, cy - ch / 2), bh - ch)
    frame = plate.crop((int(round(x0)), int(round(y0)),
                        int(round(x0 + cw)), int(round(y0 + ch)))).resize((W, H), Image.BILINEAR)
    k = W / cw

    def project(px, py):
        return (px - x0) * k, (py - y0) * k, k

    return frame, project


def tear_mask(progress: float, seed: int = 5) -> tuple[np.ndarray, np.ndarray]:
    """Torn-paper wipe: returns (blend alpha, ink edge alpha)."""
    xs = np.arange(W, dtype=np.float32)[None, :]
    n = np.random.default_rng(seed).normal(0, 1, H).astype(np.float32)
    n = np.convolve(n, np.ones(37) / 37, mode="same") * 2
    ys = np.arange(H, dtype=np.float32)[:, None]
    wob = n[:, None] * 26 + np.sin(ys * 0.035) * 14
    edge = progress * (W + 220) - 110
    d = (xs + wob) - edge
    alpha = np.clip(0.5 - d / 26.0, 0, 1).astype(np.float32)
    inkline = np.clip(1.0 - np.abs(d) / 9.0, 0, 1) ** 1.4
    return alpha, inkline


# --------------------------------------------------------------- overlays
def hook_title() -> Image.Image:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f1 = font("display", 132)
    f2 = font("condensed", 74)
    line1 = "74.000 TAHUN LALU"
    line2 = "SUMATERA MELEDAK"
    y = 132
    tw = tracked_width(d, line1, f1, 6)
    x = 108
    d.rectangle([x - 30, y - 26, x + max(tw, tracked_width(d, line2, f2, 4)) + 34, y + 236],
                fill=(243, 234, 219, 214))
    draw_tracked(d, (x, y), line1, f1, P.rgba(P.INK), 6)
    draw_tracked(d, (x + 2, y + 152), line2, f2, P.rgba(P.RUST_DEEP), 5)
    d.rectangle([x - 30, y - 26, x + 12, y + 236], fill=P.rgba(P.AMBER))
    return img


def chapter_label(text: str, right: bool = False) -> Image.Image:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = font("sans", 34, "SemiBold")
    tw = tracked_width(d, text, f, 5)
    x, y = (W - 96 - tw if right else 96), H - 118
    d.rectangle([x - 22, y - 20, x + tw + 26, y + 58], fill=(243, 234, 219, 226))
    bar = [x + tw + 14, y - 20, x + tw + 26, y + 58] if right else [x - 22, y - 20, x - 12, y + 58]
    d.rectangle(bar, fill=P.rgba(P.RUST))
    draw_tracked(d, (x, y - 4), text, f, P.rgba(P.INK_SOFT), 5)
    return img


def outro_card() -> Image.Image:
    base = ink.make_paper(W, H, seed=77).convert("RGBA")
    d = ImageDraw.Draw(base)
    f = font("display", 210)
    txt = "KALDERA"
    tw = tracked_width(d, txt, f, 12)
    draw_tracked(d, (W * 0.5 - tw / 2, H * 0.30), txt, f, P.rgba(P.INK), 12)
    f2 = font("mono", 44)
    sub = "SEJARAH BUMI  &  MANUSIA NUSANTARA"
    sw = tracked_width(d, sub, f2, 7)
    draw_tracked(d, (W * 0.5 - sw / 2, H * 0.52), sub, f2, P.rgba(P.RUST_DEEP), 7)
    f3 = font("sans", 40, "Medium")
    nxt = "EPISODE BERIKUTNYA: TAMBORA"
    nw = tracked_width(d, nxt, f3, 4)
    d.rectangle([W * 0.5 - nw / 2 - 30, H * 0.65, W * 0.5 + nw / 2 + 30, H * 0.65 + 78],
                outline=P.rgba(P.INK), width=3)
    draw_tracked(d, (W * 0.5 - nw / 2, H * 0.65 + 16), nxt, f3, P.rgba(P.INK_SOFT), 4)
    sprite, anchor = S.Rig(2).render(S.P_lookup(1.1), 3.4)
    base.alpha_composite(sprite, (int(W * 0.5 - anchor[0]), int(H * 0.99 - anchor[1])))
    return base.convert("RGB")


# --------------------------------------------------------------- rendering
class Renderer:
    def __init__(self, tl):
        self.tl = tl
        self.plates = load_plates()
        self.cache: dict = {}
        # convert each shot's screen-space anchor into plate coords at mid-zoom
        for sh in tl["shots"]:
            plate = self.plates[sh["plate"]]
            bw, bh = plate.size
            zm = (sh["zoom"][0] + sh["zoom"][1]) / 2
            x0 = min(max(0.0, sh["cxy"][0] * bw - W * zm / 2), bw - W * zm)
            y0 = min(max(0.0, sh["cxy"][1] * bh - H * zm / 2), bh - H * zm)
            sh["gx"] = (x0 + sh["sx"] * W * zm) / bw
            sh["gy"] = (y0 + sh["sy"] * H * zm) / bh
        self._title = hook_title()
        self._outro = outro_card()
        self._labels = {}
        for sh in tl["shots"]:
            if sh.get("label"):
                self._labels[sh["label"]] = chapter_label(sh["label"], right=sh["sx"] < 0.5)

    def kal(self, pose: str, t: float, hpx: float):
        """Sprite for KAL at an on-screen height hpx, cached on a coarse grid."""
        tq = round(t * 12) / 12
        hq = max(40, round(hpx / 6) * 6)
        key = (pose, tq, hq)
        hit = self.cache.get(key)
        if hit is None:
            scale = hq / KAL_H
            sprite, anchor = S.Rig(2).render(S.POSES[pose](tq), scale)
            if len(self.cache) > 700:
                self.cache.clear()
            hit = self.cache[key] = (sprite, anchor, hq)
        return hit

    def shot_parts(self, sh, t):
        """Background frame plus KAL composited as a separate, maskable layer."""
        u = min(1.0, max(0.0, (t - sh["start"]) / sh["dur"]))
        plate = self.plates[sh["plate"]]
        frame, project = camera(plate, u, sh["zoom"], sh["cxy"])
        canvas = frame.convert("RGBA")
        bw, bh = plate.size
        gx, gy, k = project(sh["gx"] * bw, sh["gy"] * bh)
        hpx = sh["h"] * k * ((sh["zoom"][0] + sh["zoom"][1]) / 2)
        sprite, anchor, hq = self.kal(sh["pos"], t, hpx)
        soles = (S.Y1 - S.FOOT_Y) / (S.Y1 - S.Y0) * sprite.height
        x = int(gx - anchor[0])
        y = int(gy - soles)

        # contact shadow baked into the background so it never gets masked oddly
        sw = int(hq * 0.26)
        sh_h = max(4, int(hq * 0.05))
        shadow = Image.new("RGBA", (sw * 2, sh_h * 3), (0, 0, 0, 0))
        ImageDraw.Draw(shadow).ellipse([0, sh_h, sw * 2, sh_h * 3], fill=(18, 15, 12, 120))
        shadow = shadow.filter(ImageFilter.GaussianBlur(sh_h * 0.8))
        canvas.alpha_composite(shadow, (int(gx - sw), int(gy - sh_h * 1.2)))
        return canvas, (sprite, x, y)

    def shot_frame(self, sh, t):
        canvas, (sprite, x, y) = self.shot_parts(sh, t)
        canvas.alpha_composite(sprite, (x, y))
        return canvas

    def _masked(self, sprite, x, y, mask: np.ndarray):
        """Return (layer, pos) with the sprite's alpha multiplied by a mask."""
        h, w = sprite.height, sprite.width
        m = np.zeros((h, w), dtype=np.float32)
        fx0, fy0 = max(0, x), max(0, y)
        fx1, fy1 = min(W, x + w), min(H, y + h)
        if fx1 <= fx0 or fy1 <= fy0:
            return None
        m[fy0 - y:fy1 - y, fx0 - x:fx1 - x] = mask[fy0:fy1, fx0:fx1]
        a = np.asarray(sprite.split()[-1], dtype=np.float32) * m
        lay = sprite.copy()
        lay.putalpha(Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "L"))
        return lay

    def frame(self, t):
        shots = self.tl["shots"]
        if t >= self.tl["vo_total"]:
            return self._outro_frame(t)
        idx = 0
        for i, sh in enumerate(shots):
            if t >= sh["start"]:
                idx = i
        sh = shots[idx]
        in_wipe = idx + 1 < len(shots) and sh["end"] - t < TRANS and t > sh["start"]

        if not in_wipe:
            img = self.shot_frame(sh, t)
        else:
            p = 1.0 - (sh["end"] - t) / TRANS
            a, edge = tear_mask(p, seed=3 + idx)
            base_a, k_a = self.shot_parts(sh, t)
            base_b, k_b = self.shot_parts(shots[idx + 1], t)
            aa = a[:, :, None]
            arr = (np.asarray(base_a, dtype=np.float32) * aa
                   + np.asarray(base_b, dtype=np.float32) * (1 - aa))
            ink_a = (edge * 200)[:, :, None]
            ink_rgb = np.array([24, 20, 17], dtype=np.float32)[None, None, :]
            arr[..., :3] = arr[..., :3] * (1 - ink_a / 255.0) + ink_rgb * (ink_a / 255.0)
            img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA")
            for (sprite, x, y), mask in ((k_a, a), (k_b, 1.0 - a)):
                lay = self._masked(sprite, x, y, mask)
                if lay is not None:
                    img.alpha_composite(lay, (x, y))

        # chapter lower third
        if sh.get("label") and 0.5 < (t - sh["start"]) < 4.6:
            lt = (t - sh["start"]) - 0.5
            alpha = min(1.0, lt / 0.45, max(0.0, (4.6 - 0.5 - lt) / 0.6))
            lab = self._labels[sh["label"]].copy()
            lab.putalpha(lab.split()[-1].point(lambda v: int(v * alpha)))
            img.alpha_composite(lab)
        # hook title
        if HOOK_TITLE[0] < t < HOOK_TITLE[1]:
            a2 = min(1.0, (t - HOOK_TITLE[0]) / 0.5, max(0.0, (HOOK_TITLE[1] - t) / 0.6))
            tt = self._title.copy()
            tt.putalpha(tt.split()[-1].point(lambda v: int(v * a2)))
            img.alpha_composite(tt)
        return img

    def _outro_frame(self, t):
        base = self._outro.convert("RGBA")
        a = min(1.0, (t - self.tl["vo_total"]) / 0.6, max(0.0, (self.tl["total"] - t) / 0.8))
        if a < 1.0:
            paper = ink.make_paper(W, H, seed=77).convert("RGBA")
            base = Image.blend(paper, base, a)
        return base


def render(tl, out_path: str, start=0.0, end=None, fps=FPS):
    end = tl["total"] if end is None else end
    n = int(round((end - start) * fps))
    r = Renderer(tl)
    cmd = [FF, "-y", "-hide_banner", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
           "-vf", "noise=c0s=5:c0f=t+u,vignette=PI/5",
           "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
           "-movflags", "+faststart", out_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        for i in range(n):
            t = start + i / fps
            fr = r.frame(t)
            if fr.mode != "RGB":
                fr = fr.convert("RGB")
            proc.stdin.write(fr.tobytes())
            if i % (fps * 20) == 0:
                print(f"  {i}/{n} frames  t={t:6.1f}s", flush=True)
    finally:
        proc.stdin.close()
        proc.wait()


if __name__ == "__main__":
    os.makedirs(VID, exist_ok=True)
    args = sys.argv[1:]
    tl = build_timeline()
    if "--plan" in args:
        print(f"narration {tl['vo_total']:.1f}s  total {tl['total']:.1f}s  "
              f"({tl['total']/60:.1f} min)  shots {len(tl['shots'])}")
        for sh in tl["shots"]:
            print(f"  {sh['start']:7.1f} → {sh['end']:7.1f}  {sh['plate']:7s} "
                  f"{sh['pos']:8s} {sh.get('label') or ''}")
    if "--render" in args:
        render(tl, os.path.join(VID, "kaldera_bab1_silent.mp4"))
    if "--test" in args:
        # render inspection frames from a synthetic timetable
        fake = dict(pieces=[], durs=[8.0] * len(SHOTS), starts=[i * 8.0 for i in range(len(SHOTS))],
                    vo_total=8.0 * len(SHOTS), total=8.0 * len(SHOTS) + OUTRO, gap=0.0,
                    shots=[dict(sp, start=i * 8.0, end=(i + 1) * 8.0, dur=8.0, camera="in")
                           for i, sp in enumerate(SHOTS)])
        r = Renderer(fake)
        os.makedirs("/tmp/frames", exist_ok=True)
        picks = [0.5, 7.6, 9.0, 20.5, 33.0, 44.0, 55.0, 66.0, 77.0, 88.0, 99.0, 102.0]
        for i, tt in enumerate(picks):
            fr = r.frame(tt)
            fr.convert("RGB").resize((960, 540)).save(f"/tmp/frames/f{i:02d}.png")
        print("test frames written to /tmp/frames")
    if "--mux" in args:
        src = os.path.join(VID, "kaldera_bab1_silent.mp4")
        mix = os.path.join(AUD, "final_mix.wav")
        out = os.path.join(VID, "KALDERA_Bab1_Toba_1080p.mp4")
        subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error", "-i", src, "-i", mix,
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest",
                        "-movflags", "+faststart", out], check=True)
        print("wrote", out)
