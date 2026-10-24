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


def loop_to(x: np.ndarray, n: int, fade=1.2) -> np.ndarray:
    out = np.zeros(n, dtype=np.float32)
    i = 0
    while i < n:
        seg = x[: min(len(x), n - i)]
        out[i:i + len(seg)] += seg * np.hanning(len(seg) * 2 + 2)[:len(seg)].astype(np.float32) ** 0.15
        i += len(x) - int(fade * SR)
    return out


def duck(music: np.ndarray, vo: np.ndarray, depth=0.55, attack=0.18, release=0.75):
    """Sidechain-style ducking driven by the voice envelope."""
    env = np.abs(vo)
    # smooth envelope
    k = int(0.12 * SR)
    env = np.convolve(env, np.ones(k) / k, mode="same")
    env = np.clip(env / (np.percentile(env[env > 1e-4], 90) + 1e-6), 0, 1)
    # attack/release smoothing
    out = np.empty_like(env)
    a = np.exp(-1 / (attack * SR))
    r = np.exp(-1 / (release * SR))
    prev = 0.0
    for i in range(0, len(env), 1):
        c = a if env[i] > prev else r
        prev = c * prev + (1 - c) * env[i]
        out[i] = prev
    return music * (1.0 - depth * out)


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
    pieces = sorted(glob.glob(os.path.join(VO, "pc_*.mp3")))
    if not pieces:
        pieces = sorted(glob.glob(os.path.join(VO, "*.mp3")))
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
    # act boundaries in seconds (from the shot plan)
    shots = tl["shots"]
    marks = {s["label"]: s["start"] for s in shots if s.get("label")}
    acts = [
        (0.0, shots[1]["start"] + 4, "A", 0.30),
        (shots[1]["start"] + 4, shots[4]["start"], "A", 0.24),
        (shots[4]["start"], shots[6]["start"], "B1", 0.34),
        (shots[6]["start"], shots[7]["start"], "B2", 0.40),
        (shots[7]["start"], shots[9]["start"], "B1", 0.26),
        (shots[9]["start"], shots[12]["start"], "A", 0.20),
        (shots[12]["start"], total, "C", 0.34),
    ]
    music = np.zeros(n, dtype=np.float32)
    for t0, t1, key, gain in acts:
        if t1 <= t0:
            continue
        seg_n = int((t1 - t0) * SR)
        bed = loop_to(beds[key], seg_n + int(2.5 * SR))
        # crossfade edges
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
    # transitions: torn paper + marker, on every cut
    for s in shots[1:]:
        place(cues, sfx["paper"], s["start"] - 0.30, 0.5)
        place(cues, sfx["marker"], s["start"] - 0.18, 0.34)
    # opening impact and hook riser
    place(cues, sfx["impact"], 0.02, 0.75)
    place(cues, sfx["riser"], max(0.2, shots[1]["start"] - 3.2), 0.5)
    # act-specific textures
    place(cues, sfx["rumble"], shots[4]["start"] - 1.0, 0.55)
    place(cues, sfx["eruption"], shots[5]["start"] - 0.6, 0.85)
    place(cues, sfx["wind"], shots[7]["start"], 0.5)
    place(cues, sfx["ash"], shots[7]["start"] + 6, 0.45)
    place(cues, sfx["heart"], shots[9]["start"] + 2, 0.4)
    place(cues, sfx["wind"], shots[9]["start"], 0.3)
    place(cues, sfx["fire"], shots[9]["start"] + 8, 0.35)
    place(cues, sfx["stone"], shots[8]["start"], 0.45)
    place(cues, sfx["water"], shots[12]["start"], 0.35)
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
