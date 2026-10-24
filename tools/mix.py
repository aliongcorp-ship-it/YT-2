"""Mix the episode audio: narration + score + sfx -> audio/final_mix.wav

  * narration pieces placed on the timeline with breath gaps
  * music beds crossfaded per act, ducked under the voice
  * sfx cue list aligned to the shot list (paper+marker on every cut)
  * final loudness pass to -16 LUFS / -1.5 dBTP

    python env/bin/python tools/mix.py
"""
from __future__ import annotations

import glob
import json
import os
import subprocess
import sys
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUD = os.path.join(ROOT, "audio")
VO = os.path.join(AUD, "vo")
SCR = os.path.join(ROOT, "scripts")
SR = 48000

import imageio_ffmpeg  # noqa: E402
FF = imageio_ffmpeg.get_ffmpeg_exe()


def read_wav(path: str) -> np.ndarray:
    with wave.open(path, "rb") as w:
        n, ch, sw = w.getnframes(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(n)
    if sw != 2:
        raise SystemExit(f"{path}: expected 16-bit")
    a = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    return a.reshape(-1, ch).mean(axis=1) if ch > 1 else a


def read_any(path: str) -> np.ndarray:
    """Decode anything ffmpeg understands into mono float32 @ SR."""
    tmp = "/tmp/_mix_tmp.wav"
    subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error", "-i", path,
                    "-ac", "1", "-ar", str(SR), "-c:a", "pcm_s16le", tmp], check=True)
    return read_wav(tmp)


def fit(x: np.ndarray, n: int) -> np.ndarray:
    if len(x) >= n:
        return x[:n]
    return np.pad(x, (0, n - len(x)))


def place(dst: np.ndarray, src: np.ndarray, at: float, gain: float = 1.0):
    i = int(at * SR)
    if i >= len(dst):
        return
    seg = src[: len(dst) - i]
    dst[i:i + len(seg)] += seg * gain


def loop_to(x: np.ndarray, n: int, fade=2.0) -> np.ndarray:
    """Seamless loop with equal-power crossfades at the joins."""
    out = np.zeros(n + int(fade * SR) * 2, dtype=np.float32)
    f = int(fade * SR)
    i = 0
    ramp = np.sqrt(np.linspace(0, 1, f)).astype(np.float32)
    first = True
    while i < len(out):
        seg = x
        room = len(out) - i
        if room <= 0:
            break
        seg = seg[:room]
        if not first and len(seg) >= f:
            seg = seg.copy()
            seg[:f] *= ramp
        out[i:i + len(seg)] += seg
        i += max(1, len(seg) - f)
        first = False
    return out[:n]


def duck(music: np.ndarray, vo: np.ndarray, depth=0.55, attack=0.02, release=0.45):
    """Sidechain ducking: instant-ish attack, slow release, fully vectorised."""
    from scipy.signal import lfilter
    env = np.abs(vo)
    k = int(0.05 * SR)
    env = np.convolve(env, np.ones(k, dtype=np.float32) / k, mode="same")
    ref = np.percentile(env[env > 1e-5], 90) + 1e-6
    env = np.clip(env / ref, 0, 1).astype(np.float32)
    a_fast = float(np.exp(-1.0 / (attack * SR)))
    a_slow = float(np.exp(-1.0 / (release * SR)))
    fast = lfilter([1 - a_fast], [1, -a_fast], env).astype(np.float32)
    slow = lfilter([1 - a_slow], [1, -a_slow], env).astype(np.float32)
    take = np.maximum(fast, slow)
    return (music * (1.0 - depth * take)).astype(np.float32)


def main():
    tl_p = os.path.join(SCR, "timeline.json")
    if not os.path.exists(tl_p):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        from render_video import build_timeline
        build_timeline()
    tl = json.load(open(tl_p))
    total = tl["total"]
    n = int(total * SR) + SR
    print(f"timeline: {total:.1f}s")

    # ---------------------------------------------------------------- voice
    pieces = sorted(glob.glob(os.path.join(VO, "vo10_*.mp3")))
    if not pieces:
        pieces = sorted(glob.glob(os.path.join(VO, "pc_*.mp3")))
    vo_track = np.zeros(n, dtype=np.float32)
    for p, st in zip(pieces, tl["starts"]):
        x = read_any(p)
        # gentle cleanup: remove DC, tiny high-pass, normalise each piece
        x = x - x.mean()
        x = np.convolve(x, np.ones(5) / 5, mode="same")
        x = (x / (np.abs(x).max() + 1e-9)) * 0.72
        place(vo_track, x, st)
    print(f"narration: {len(pieces)} pieces, {tl['vo_total']:.1f}s")

    # ---------------------------------------------------------------- music
    beds = {
        "A": read_any(os.path.join(AUD, "mus_a_legend.wav")),
        "B1": read_any(os.path.join(AUD, "mus_b_tension.wav")),
        "B2": read_any(os.path.join(AUD, "mus_b_eruption.wav")),
        "C": read_any(os.path.join(AUD, "mus_c_hope.wav")),
    }
    # -------------------------------------------------- act boundaries
    shots = tl["shots"]

    def at(label_part: str, default: float) -> float:
        for sh in shots:
            if sh.get("label") and label_part in sh["label"]:
                return sh["start"]
        return default

    t_leg = at("LEGENDA", 0.06 * total)
    t_form = at("BENTUK", 0.17 * total)
    t_mtn = at("GUNUNG YANG", 0.28 * total)
    t_sign = at("TANDA-TANDA", 0.34 * total)
    t_erupt = at("NERAKA", 0.49 * total)
    t_night = at("MATAHARI", 0.60 * total)
    t_coll = at("RUNTUH", 0.70 * total)
    t_punah = at("PUNAH", 0.76 * total)
    t_why = at("MASIH ADA", 0.92 * total)

    acts = [
        (0.0, t_leg, "A", 0.30),
        (t_leg, t_sign, "A", 0.24),
        (t_sign, t_erupt, "B1", 0.34),
        (t_erupt, t_night, "B2", 0.42),
        (t_night, t_punah, "B1", 0.26),
        (t_punah, t_why, "A", 0.20),
        (t_why, total, "C", 0.36),
    ]
    music = np.zeros(n, dtype=np.float32)
    for t0, t1, key, gain in acts:
        if t1 <= t0:
            continue
        seg_n = int((t1 - t0) * SR)
        bed = loop_to(beds[key], seg_n + int(2.5 * SR))
        fade = int(2.0 * SR)
        envl = np.ones(len(bed), dtype=np.float32)
        envl[:fade] *= np.linspace(0, 1, fade)
        envl[-fade:] *= np.linspace(1, 0, fade)
        place(music, bed * envl, t0, gain)
    music = duck(music, vo_track, depth=0.62)

    # ------------------------------------------------------------------ sfx
    sfx = {k: read_any(os.path.join(AUD, f"sfx_{k}.wav")) for k in
           ("paper", "marker", "rumble", "eruption", "ash", "wind", "water",
            "fire", "heart", "riser", "impact", "stone")}
    cues = np.zeros(n, dtype=np.float32)
    for sh in shots[1:]:
        place(cues, sfx["paper"], sh["start"] - 0.30, 0.5)
        place(cues, sfx["marker"], sh["start"] - 0.18, 0.34)
    place(cues, sfx["impact"], 0.02, 0.75)
    place(cues, sfx["riser"], max(0.2, t_leg - 3.2), 0.5)
    place(cues, sfx["rumble"], t_sign - 1.0, 0.55)
    place(cues, sfx["eruption"], t_erupt - 0.6, 0.85)
    place(cues, sfx["wind"], t_night, 0.5)
    place(cues, sfx["ash"], t_night + 6, 0.45)
    place(cues, sfx["heart"], t_punah + 2, 0.4)
    place(cues, sfx["wind"], t_punah, 0.3)
    place(cues, sfx["fire"], t_coll + 4, 0.35)
    place(cues, sfx["stone"], t_coll, 0.45)
    place(cues, sfx["water"], t_why, 0.35)
    place(cues, sfx["impact"], tl["vo_total"], 0.4)

    mix = vo_track * 1.0 + music + cues * 0.9
    # soft limiter then write
    mix = np.tanh(mix * 1.05) * 0.92
    st = np.stack([mix, mix], axis=1)
    out_raw = os.path.join(AUD, "_mix_raw.wav")
    with wave.open(out_raw, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(st, -1, 1) * 32767).astype("<i2").tobytes())

    # loudness normalisation (-16 LUFS, -1.5 dBTP)
    final = os.path.join(AUD, "final_mix.wav")
    r = subprocess.run([FF, "-y", "-hide_banner", "-i", out_raw,
                        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                        "-ar", str(SR), "-c:a", "pcm_s16le", final],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-800:])
        raise SystemExit("loudnorm failed")
    print("wrote", final, f"{os.path.getsize(final)/1e6:.1f} MB")


if __name__ == "__main__":
    main()
