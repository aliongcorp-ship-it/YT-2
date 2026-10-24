"""KALDERA Short #1 — vertical 9:16 cut in the Mr Sticky style.

art     -> art/short2/f/*.png   exact 1080x1920 frames
thumb   -> social/SHORT_Toba_*.jpg
render  -> video/short_Toba_silent.mp4
mux     -> video/KALDERA_Short_Toba_1080x1920.mp4
"""
from __future__ import annotations

import glob
import math
import os
import subprocess
import sys
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine import palette as P
from engine import fonts as F
import imageio_ffmpeg

SRC = os.path.join(ROOT, "art", "short2")
OUT = os.path.join(SRC, "f")
SOC = os.path.join(ROOT, "social")
VID = os.path.join(ROOT, "video")
AUD = os.path.join(ROOT, "audio")
W, H, FPS = 1080, 1920, 30
RATIO = W / H

FF = imageio_ffmpeg.get_ffmpeg_exe()


# ------------------------------------------------------------------ helpers
def ff_duration(path: str) -> float:
    err = subprocess.run([FF, "-hide_banner", "-i", path],
                         capture_output=True, text=True).stderr
    import re
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", err)
    if not m:
        raise SystemExit(f"cannot read duration of {path}")
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def fit916(im: Image.Image, cxy=(0.5, 0.5)) -> Image.Image:
    """Crop to an exact 9:16 window, then scale to 1080x1920."""
    im = im.convert("RGB")
    w, h = im.size
    if w / h > RATIO:                      # too wide -> trim sides
        nw = int(round(h * RATIO))
        nh = h
    else:                                  # too tall -> trim top/bottom
        nw = w
        nh = int(round(w / RATIO))
    x = int(round((w - nw) * cxy[0]))
    y = int(round((h - nh) * cxy[1]))
    im = im.crop((x, y, x + nw, y + nh))
    return im.resize((W, H), Image.LANCZOS)


def square(im: Image.Image) -> Image.Image:
    """Neutral, flat grade: keeps the cartoon look, kills digital fizz."""
    a = np.asarray(im, dtype=np.float32) / 255.0
    lum = (0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2])[..., None]
    a = lum + (a - lum) * 1.02                      # tiny saturation lift
    a = np.clip(a, 0, 1) ** (1 / 1.01)
    return Image.fromarray((a * 255).astype(np.uint8), "RGB")


def torn_band(w: int, h: int, color, alpha=232, seed=11) -> Image.Image:
    """Flat ink band with a torn lower edge (paper collage feel)."""
    band = Image.new("RGBA", (w, h), (*color, alpha))
    rng = np.random.default_rng(seed)
    base = h - 34
    xs = np.arange(w, dtype=np.float32)
    wob = (np.sin(xs * 0.011 + 1.3) * 9 + np.sin(xs * 0.037) * 5
           + rng.normal(0, 1.6, w))
    m = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(m)
    for x in range(w):
        md.line([(x, 0), (x, base + wob[x])], fill=255)
    band.putalpha(Image.composite(band.getchannel("A"), Image.new("L", (w, h), 0), m))
    return band


def outlined(draw, xy, txt, fnt, fill, stroke=P.INK, sw=10, anchor="ma"):
    draw.text(xy, txt, font=fnt, fill=fill, anchor=anchor,
              stroke_width=sw, stroke_fill=stroke)


# --------------------------------------------------------------------- art
def cmd_art():
    os.makedirs(OUT, exist_ok=True)
    for p in sorted(glob.glob(os.path.join(SRC, "t*.png"))):
        n = os.path.basename(p)[:2]                       # t1 .. t6
        im = square(fit916(Image.open(p)))
        im.save(os.path.join(OUT, f"{n}.png"))
        print("frame", n, im.size)
    # contact sheet
    files = sorted(glob.glob(os.path.join(OUT, "t*.png")))
    tw, th = 300, 533
    sheet = Image.new("RGB", (tw * 3, th * 2), (18, 18, 18))
    for i, f in enumerate(files):
        sheet.paste(Image.open(f).resize((tw, th), Image.LANCZOS),
                    ((i % 3) * tw, (i // 3) * th))
    sheet.save(os.path.join(SRC, "_sheet.png"))
    print("ok", len(files), "frames")


# ------------------------------------------------------------------- thumb
KICK = "TOBA  ·  74.000 TAHUN LALU"


def make_cover() -> Image.Image:
    base = Image.open(os.path.join(OUT, "t1.png")).convert("RGB")
    base = base.crop((0, 0, W, H)).filter(ImageFilter.SMOOTH)
    cv = base.copy()
    cv.alpha_composite if False else None
    cv = cv.convert("RGBA")
    band = torn_band(W, 560, P.INK, alpha=236, seed=7)
    cv.alpha_composite(band, (0, 0))
    d = ImageDraw.Draw(cv)
    d.text((W // 2, 96), KICK, font=F.font("mono", 40), fill=P.PAPER, anchor="ma")
    outlined(d, (W // 2, 168), "9 HARI", F.font("display", 232), P.PAPER, sw=14)
    outlined(d, (W // 2, 412), "TANPA MATAHARI", F.font("display", 96), P.AMBER, sw=11)
    # bottom small brand mark
    d.text((W // 2, H - 74), "KALDERA", font=F.font("display", 54),
           fill=P.PAPER, anchor="ma", stroke_width=8, stroke_fill=P.INK)
    return cv.convert("RGB")


def fit_font(d, txt, role, size, max_w, weight=None, lo=16):
    """Shrink `size` until `txt` fits inside `max_w`."""
    while size > lo:
        f = F.font(role, size, weight)
        if d.textlength(txt, font=f) <= max_w:
            return f
        size -= 2
    return F.font(role, lo, weight)


def make_wide() -> Image.Image:
    """1280x720 upload thumbnail: ink panel left, column right."""
    w, h = 1280, 720
    cv = Image.new("RGB", (w, h), P.INK)
    d = ImageDraw.Draw(cv)
    panel_w = int(w * 0.44)
    src = Image.open(os.path.join(OUT, "t1.png")).convert("RGB")
    crop = src.crop((40, 0, W - 40, H)).resize((panel_w, h), Image.LANCZOS)
    cv.paste(crop, (w - panel_w, 0))
    d.rectangle([w - panel_w - 5, 0, w - panel_w + 5, h], fill=P.PAPER)

    lw = w - panel_w - 110                      # usable text width
    x = 54
    d.text((x, 62), "TOBA · 74.000 TAHUN LALU", font=F.font("mono", 26),
           fill=P.AMBER, anchor="la")
    f1 = fit_font(d, "SEBESAR", "display", 86, lw)
    f2 = fit_font(d, "APA TOBA?", "display", 104, lw)
    d.text((x, 108), "SEBESAR", font=f1, fill=P.PAPER, anchor="la")
    d.text((x, 108 + int(f1.size * 0.98)), "APA TOBA?", font=f2, fill=P.AMBER, anchor="la")
    y = 108 + int(f1.size * 0.98) + int(f2.size * 1.18)
    d.rectangle([x, y + 12, x + lw - 90, y + 21], fill=P.RUST)
    y += 52
    for ln in ("Kolom abu 32 km.", "4× tinggi Everest.", "9 hari gelap total."):
        f = fit_font(d, ln, "sans", 38, lw)
        d.text((x, y), ln, font=f, fill=P.PAPER_WARM, anchor="la")
        y += int(f.size * 1.5)
    d.text((x, h - 62), "KALDERA", font=F.font("display", 40), fill=P.AMBER, anchor="la")
    return cv


def cmd_thumb():
    os.makedirs(SOC, exist_ok=True)
    a = make_cover()
    pa = os.path.join(SOC, "SHORT_Toba_cover_1080x1920.jpg")
    a.save(pa, quality=92, optimize=True)
    b = make_wide()
    pb = os.path.join(SOC, "SHORT_Toba_thumb_1280x720.jpg")
    b.save(pb, quality=92, optimize=True)
    # legibility check at shelf size (168 px wide)
    for p in (pa, pb):
        im = Image.open(p)
        im.resize((168, int(168 * im.size[1] / im.size[0])), Image.LANCZOS).save(
            "/tmp/chk_" + os.path.basename(p))
    print("thumb", pa, a.size)
    print("thumb", pb, b.size)


# ------------------------------------------------------------------- audio
SR = 48000


def read_any(path: str) -> np.ndarray:
    """Read a wav, or decode anything else (mp3) to 48 kHz mono float."""
    if path.lower().endswith(".wav"):
        with wave.open(path) as w:
            n, ch, sw = w.getnframes(), w.getnchannels(), w.getsampwidth()
            raw = w.readframes(n)
        a = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768
        if ch > 1:
            a = a.reshape(-1, ch).mean(axis=1)
        return a
    raw = subprocess.run([FF, "-v", "error", "-i", path, "-f", "s16le",
                          "-ac", "1", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768


def place(dst: np.ndarray, src: np.ndarray, t: float, gain: float = 1.0):
    i = int(t * SR)
    if i >= len(dst):
        return
    n = min(len(src), len(dst) - i)
    if n > 0:
        dst[i:i + n] += src[:n] * gain


def build_audio(vo_total: float, total: float) -> str:
    n = int(total * SR) + SR
    mix = np.zeros(n, dtype=np.float32)

    vo = read_any(os.path.join(AUD, "vo_short", "vo_short.mp3"))
    place(mix, vo, 0.55, 1.0)
    # music beds: tension under the eruption, hope at the end
    beds = [("mus_b_eruption.wav", 0.0, 46.0, 0.20),
            ("mus_c_hope.wav", vo_total - 9.0, 12.0, 0.24)]
    for name, t0, dur, g in beds:
        p = os.path.join(AUD, name)
        if not os.path.exists(p):
            continue
        bed = read_any(p)
        seg_n = int(dur * SR)
        reps = int(math.ceil(seg_n / max(1, len(bed))))
        bed = np.tile(bed, reps)[:seg_n]
        f = int(1.6 * SR)
        bed[:f] *= np.linspace(0, 1, f)
        bed[-f:] *= np.linspace(1, 0, f)
        place(mix, bed, t0, g)

    cues = [("impact", 0.0, 0.7), ("rumble", 0.6, 0.55), ("eruption", 9.2, 0.75),
            ("wind", 19.2, 0.45), ("ash", 25.0, 0.4), ("fire", 35.2, 0.4),
            ("stone", 41.0, 0.35), ("water", 43.2, 0.4), ("impact", vo_total, 0.5)]
    for name, t0, g in cues:
        p = os.path.join(AUD, f"sfx_{name}.wav")
        if os.path.exists(p):
            place(mix, read_any(p), t0, g)

    # duck music is unnecessary here (beds already low); gentle limiter
    mix = np.tanh(mix * 1.02) * 0.92
    peak = float(np.abs(mix).max()) or 1.0
    mix *= min(1.0, 0.89 / peak)
    out = os.path.join(AUD, "short_mix.wav")
    st = np.stack([mix, mix], axis=1)
    with wave.open(out, "w") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(st, -1, 1) * 32767).astype("<i2").tobytes())
    return out


# ------------------------------------------------------------------ render
SHOTS = [("t1", 9.5), ("t2", 8.0), ("t4", 8.0), ("t3", 8.0), ("t5", 10.0), ("t6", 8.0)]


def end_card() -> Image.Image:
    cv = Image.new("RGB", (W, H), P.INK)
    d = ImageDraw.Draw(cv)
    d.text((W // 2, 780), "KALDERA", font=F.font("display", 150), fill=P.PAPER, anchor="mm")
    d.rectangle([W // 2 - 150, 880, W // 2 + 150, 886], fill=P.AMBER)
    d.text((W // 2, 960), "EPISODE LENGKAP DI KANAL INI",
           font=F.font("mono", 40), fill=P.AMBER, anchor="mm")
    d.text((W // 2, 1050), "sejarah bumi & manusia nusantara",
           font=F.font("serif", 40), fill=P.PAPER_WARM, anchor="mm")
    return cv


PLATE_SCALE = 1.12          # plates are pre-scaled to give the camera headroom


def frame_at(t: float, plates, tl) -> np.ndarray:
    if t >= tl["card"]:
        return np.asarray(tl["card_img"])
    for (name, _), (t0, t1) in zip(SHOTS, tl["spans"]):
        if t0 <= t < t1:
            u = (t - t0) / max(1e-6, (t1 - t0))
            z = 1.0 + 0.06 * u                       # effective zoom 1.00 -> 1.06
            im = plates[name]
            PW, PH = im.size
            # visible fraction of the ORIGINAL frame, expressed in plate pixels
            bw = int(PW / z / PLATE_SCALE)
            bh = int(PH / z / PLATE_SCALE)
            cx = int((PW - bw) / 2)
            cy = int((PH - bh) / 2 + (u - 0.5) * 0.02 * PH)   # 2% vertical drift
            win = im.crop((cx, cy, cx + bw, cy + bh)).resize((W, H), Image.BILINEAR)
            return np.asarray(win)
    return np.asarray(tl["card_img"])


def cmd_render():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(VID, exist_ok=True)
    plates = {n: Image.open(os.path.join(OUT, f"{n}.png")).convert("RGB")
              .resize((int(W * 1.12), int(H * 1.12)), Image.LANCZOS)
              for n in ("t1", "t2", "t3", "t4", "t5", "t6")}
    vo_total = ff_duration(os.path.join(AUD, "vo_short", "vo_short.mp3"))
    total = vo_total + 4.2
    card_t = vo_total + 0.3
    spans = []
    t = 0.0
    scale = (vo_total + 0.3) / sum(d for _, d in SHOTS)
    for _, d in SHOTS:
        dd = d * scale
        spans.append((t, t + dd))
        t += dd
    tl = dict(vo_total=vo_total, total=total, card=card_t, spans=spans,
              card_img=end_card())
    mix = build_audio(vo_total, total)

    nfr = int(round(total * FPS))
    out = os.path.join(VID, "short_Toba_silent.mp4")
    cmd = [FF, "-y", "-hide_banner", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-",
           "-i", mix,
           "-c:v", "libx264", "-preset", "medium", "-crf", "21",
           "-pix_fmt", "yuv420p", "-g", "60", "-movflags", "+faststart",
           "-c:a", "aac", "-b:a", "160k", "-shortest", out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(nfr):
        a = frame_at(i / FPS, plates, tl)
        proc.stdin.write(a.tobytes())
        if i % 150 == 0:
            print(f"  {i}/{nfr}  t={i/FPS:5.1f}s", flush=True)
    proc.stdin.close()
    proc.wait()
    print("wrote", out, round(os.path.getsize(out) / 1e6, 2), "MB")
    return out


def cmd_mux():
    src = os.path.join(VID, "short_Toba_silent.mp4")
    dst = os.path.join(VID, "KALDERA_Short_Toba_1080x1920.mp4")
    subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error", "-i", src,
                    "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1.5:LRA=9",
                    "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
                    "-movflags", "+faststart", dst], check=True)
    print("wrote", dst, round(os.path.getsize(dst) / 1e6, 2), "MB")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "art"
    {"art": cmd_art, "thumb": cmd_thumb, "render": cmd_render,
     "mux": cmd_mux}[cmd]()
