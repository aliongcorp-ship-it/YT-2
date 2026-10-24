"""KALDERA audio engine — every sound in the episode is synthesised here.

No stock music, no sample packs, no generic "AI whoosh". Each sound is built
from physical primitives (noise, tuned partials, envelopes through filters) so
transitions sound like paper and stone, not like a plugin preset.

    python env/bin/python tools/audio.py music      # render music beds
    python env/bin/python tools/audio.py sfx        # render sfx palette
    python env/bin/python tools/audio.py preview    # 25 s demo mix
"""
from __future__ import annotations

import os
import sys

import numpy as np
from scipy.signal import butter, fftconvolve, sosfilt

SR = 48000
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUD = os.path.join(ROOT, "audio")
RNG = np.random.default_rng(20260724)


# ------------------------------------------------------------------ helpers
def t_axis(sec: float) -> np.ndarray:
    return np.arange(int(sec * SR), dtype=np.float32) / SR


def env_ad(n: int, attack: float, decay: float, curve: float = 2.0) -> np.ndarray:
    a = max(1, int(attack * SR))
    d = max(1, n - a)
    e = np.concatenate([
        np.linspace(0, 1, a, endpoint=False) ** 0.6,
        np.exp(-np.linspace(0, 6.5, d) * (1.0 / max(0.15, decay))) ** curve,
    ])
    return e[:n].astype(np.float32)


def env_asr(n: int, attack: float, sustain: float, release: float) -> np.ndarray:
    a = int(attack * SR)
    r = int(release * SR)
    s = max(1, n - a - r)
    e = np.concatenate([
        np.linspace(0, 1, a, endpoint=False) ** 0.7,
        np.ones(s),
        np.linspace(1, 0, r) ** 1.6,
    ])
    if len(e) < n:
        e = np.pad(e, (0, n - len(e)))
    return e[:n].astype(np.float32)


def lp(x, fc, order=2):
    sos = butter(order, min(fc, SR * 0.49), btype="low", fs=SR, output="sos")
    return sosfilt(sos, x).astype(np.float32)


def hp(x, fc, order=2):
    sos = butter(order, max(20, fc), btype="high", fs=SR, output="sos")
    return sosfilt(sos, x).astype(np.float32)


def bp(x, lo, hi, order=2):
    sos = butter(order, [max(20, lo), min(hi, SR * 0.49)], btype="band", fs=SR, output="sos")
    return sosfilt(sos, x).astype(np.float32)


def noise(n: int, seed=None) -> np.ndarray:
    return (RNG if seed is None else np.random.default_rng(seed)).normal(0, 0.32, n).astype(np.float32)


def brown(n: int, seed=1) -> np.ndarray:
    r = np.random.default_rng(seed)
    b = np.cumsum(r.normal(0, 1, n)).astype(np.float32)
    b -= lp(b, 8)
    return (b / (np.abs(b).max() + 1e-9)).astype(np.float32)


def sine(n: int, f: float, phase=0.0) -> np.ndarray:
    return np.sin(2 * np.pi * f * np.arange(n, dtype=np.float32) / SR + phase).astype(np.float32)


def saw(n: int, f: float) -> np.ndarray:
    ph = (np.arange(n, dtype=np.float32) * f / SR) % 1.0
    return (2 * ph - 1).astype(np.float32)


def reverb_ir(sec=2.4, seed=7, damp=4200):
    n = int(sec * SR)
    ir = noise(n, seed) * np.exp(-np.linspace(0, 7.5, n)).astype(np.float32)
    ir = lp(ir, damp)
    ir[: int(0.012 * SR)] *= np.linspace(0, 1, int(0.012 * SR))
    return (ir / (np.abs(ir).sum() ** 0.5)).astype(np.float32)


IR_SMALL = reverb_ir(1.5, 11, 5200)
IR_HALL = reverb_ir(3.2, 13, 3000)


def verb(x, ir=IR_SMALL, wet=0.28):
    w = fftconvolve(x, ir)[: len(x)].astype(np.float32)
    w /= (np.abs(w).max() + 1e-9)
    return (x * (1 - wet) + w * wet * (np.abs(x).max() + 1e-9)).astype(np.float32)


def pan2(x, p=0.0):
    """Equal-power pan, p in [-1, 1]. Returns stereo."""
    a = (p + 1) * np.pi / 4
    return np.stack([x * np.cos(a), x * np.sin(a)], axis=1).astype(np.float32)


def fade(x, fin=0.01, fout=0.05):
    n = len(x)
    a = min(int(fin * SR), n // 2)
    b = min(int(fout * SR), n // 2)
    y = x.copy()
    if a:
        y[:a] *= np.linspace(0, 1, a)
    if b:
        y[-b:] *= np.linspace(1, 0, b)
    return y


# -------------------------------------------------------------- instruments
def bell(freq, sec=2.2, bright=1.0, seed=3):
    """Inharmonic struck metal — the gamelan/gong family used in theme A."""
    n = int(sec * SR)
    out = np.zeros(n, dtype=np.float32)
    partials = [(1.0, 0.62), (2.01, 0.24), (2.98, 0.13), (4.07, 0.07), (5.42, 0.045)]
    for i, (mul, amp) in enumerate(partials):
        a = amp * (bright ** i)
        out += a * sine(n, freq * mul, phase=i * 1.7) * np.exp(
            -np.linspace(0, 5.5 + i * 2.2, n)).astype(np.float32)
    for k in range(3):  # slight beating between pairs, like a real gamelan
        out += 0.08 * sine(n, freq * 1.004 + k * 0.7) * np.exp(-np.linspace(0, 7, n)).astype(np.float32)
    out *= env_ad(n, 0.004, 0.8, 1.0)
    return (0.55 * out / (np.abs(out).max() + 1e-9)).astype(np.float32)


def felt_piano(freq, sec=2.6, seed=5):
    n = int(sec * SR)
    out = np.zeros(n, dtype=np.float32)
    for mul, amp, dec in ((1, 0.7, 3.0), (2, 0.22, 4.5), (3, 0.10, 6.5), (4.01, 0.05, 8)):
        out += amp * sine(n, freq * mul) * np.exp(-np.linspace(0, dec, n)).astype(np.float32)
    out *= env_ad(n, 0.018, 1.2, 1.0)
    return (0.5 * out / (np.abs(out).max() + 1e-9)).astype(np.float32)


def pad(freqs, sec, attack=3.0, release=4.0, detune=0.35, seed=9):
    n = int(sec * SR)
    out = np.zeros(n, dtype=np.float32)
    for f in freqs:
        for d in (-detune, 0.0, detune):
            out += saw(n, f + d) * 0.22
    out = lp(out, 1700, 2)
    out = hp(out, 60)
    out *= env_asr(n, attack, max(0.01, sec - attack - release), release)
    return (out / (np.abs(out).max() + 1e-9)).astype(np.float32)


def sub_pulse(sec=0.9, f0=62, f1=34):
    n = int(sec * SR)
    sweep = np.linspace(f0, f1, n).astype(np.float32)
    ph = np.cumsum(2 * np.pi * sweep / SR)
    out = np.sin(ph) * env_ad(n, 0.006, 0.7, 1.4)
    return (0.85 * out).astype(np.float32)


def drum_low(sec=0.55, seed=21):
    """Deep membrane hit — used for heartbeat and 'stakes' moments."""
    n = int(sec * SR)
    body = sub_pulse(sec, 78, 41) * np.exp(-np.linspace(0, 3.2, n)).astype(np.float32)
    skin = lp(noise(n, seed), 320) * np.exp(-np.linspace(0, 16, n)).astype(np.float32)
    out = body * 0.9 + skin * 0.35
    return (out / (np.abs(out).max() + 1e-9) * 0.9).astype(np.float32)


def shaker(sec=0.14, seed=33):
    n = int(sec * SR)
    x = hp(noise(n, seed), 5200) * np.exp(-np.linspace(0, 11, n)).astype(np.float32)
    return (0.5 * x / (np.abs(x).max() + 1e-9)).astype(np.float32)


# --------------------------------------------------------------------- sfx
def sfx_rumble(sec=6.0, seed=41):
    n = int(sec * SR)
    x = lp(brown(n, seed), 90) * 1.0 + lp(brown(n, seed + 1), 55) * 0.7
    mod = 0.65 + 0.35 * np.sin(np.linspace(0, 9, n)).astype(np.float32)
    x = x * mod
    x *= env_asr(n, 1.2, max(0.1, sec - 3), 1.8)
    return (x / (np.abs(x).max() + 1e-9) * 0.9).astype(np.float32)


def sfx_eruption(sec=4.2, seed=51):
    n = int(sec * SR)
    core = lp(noise(n, seed), 900) * env_ad(n, 0.01, 1.4, 0.9)
    blast = lp(brown(n, seed + 2), 160) * env_ad(n, 0.03, 1.0, 1.1)
    sub = sub_pulse(sec, 70, 26) * 0.9
    crack = np.zeros(n, dtype=np.float32)
    for _ in range(14):
        i = int(RNG.integers(0, max(1, n - int(0.05 * SR))))
        ln = int(0.05 * SR)
        crack[i:i + ln] += hp(noise(ln, int(RNG.integers(0, 9999))), 1800) * np.linspace(1, 0, ln) * 0.5
    out = verb(core * 0.6 + blast * 0.7 + sub * 0.5 + crack * 0.5, IR_HALL, 0.22)
    return (out / (np.abs(out).max() + 1e-9) * 0.95).astype(np.float32)


def sfx_ash(sec=8.0, seed=61):
    n = int(sec * SR)
    x = bp(noise(n, seed), 1500, 7000)
    grains = np.ones(n, dtype=np.float32)
    for _ in range(1200):  # individual grains landing = ticks, not hiss
        i = int(RNG.integers(0, n - 400))
        grains[i:i + 220] += np.exp(-np.linspace(0, 8, 220)).astype(np.float32) * 0.8
    x = x * grains * 0.18
    x *= env_asr(n, 0.6, sec - 1.6, 1.0)
    return (x / (np.abs(x).max() + 1e-9) * 0.5).astype(np.float32)


def sfx_wind(sec=10.0, seed=71):
    n = int(sec * SR)
    src = noise(n, seed)
    out = np.zeros(n, dtype=np.float32)
    step = int(0.5 * SR)
    for i in range(0, n, step):
        prog = i / n
        centre = 300 + 900 * (0.5 + 0.5 * np.sin(prog * 5.0))
        seg = bp(src[i:i + step], centre * 0.5, centre * 1.6)
        out[i:i + len(seg)] = seg
    out *= 0.5 + 0.5 * np.abs(np.sin(np.linspace(0, 11, n)).astype(np.float32))
    out *= env_asr(n, 1.5, sec - 3, 1.5)
    return (out / (np.abs(out).max() + 1e-9) * 0.55).astype(np.float32)


def sfx_water(sec=6.0, seed=81):
    n = int(sec * SR)
    x = bp(noise(n, seed), 700, 4200) * 0.5
    lap = 0.4 + 0.6 * np.abs(np.sin(np.linspace(0, 7, n)).astype(np.float32))
    x *= lap
    x *= env_asr(n, 1.0, sec - 2, 1.0)
    return (x / (np.abs(x).max() + 1e-9) * 0.4).astype(np.float32)


def sfx_paper(sec=0.55, seed=91):
    """Transition signature: a sheet of paper being pulled sideways."""
    n = int(sec * SR)
    src = noise(n, seed)
    out = np.zeros(n, dtype=np.float32)
    step = int(0.02 * SR)
    for i in range(0, n, step):
        p = i / n
        c = 900 + 5200 * p ** 0.7
        out[i:i + step] = bp(src[i:i + step], c * 0.6, c * 1.4)
    out *= env_ad(n, 0.012, 0.28, 1.0)
    return (out / (np.abs(out).max() + 1e-9) * 0.55).astype(np.float32)


def sfx_marker(sec=0.34, seed=101):
    """Felt-marker squeak — the channel's audio logo on every transition."""
    n = int(sec * SR)
    base = 620 + 380 * np.sin(np.linspace(0, 6, n))
    ph = np.cumsum(2 * np.pi * base / SR)
    tone = np.sin(ph).astype(np.float32) * 0.5
    tone += bp(noise(n, seed), 1800, 5200) * 0.35
    out = tone * env_ad(n, 0.02, 0.18, 1.0)
    return (out / (np.abs(out).max() + 1e-9) * 0.34).astype(np.float32)


def sfx_stone(sec=0.8, seed=111):
    n = int(sec * SR)
    click = hp(noise(n, seed), 2200) * np.exp(-np.linspace(0, 26, n)).astype(np.float32)
    body = lp(noise(n, seed + 1), 380) * np.exp(-np.linspace(0, 9, n)).astype(np.float32)
    out = verb(click * 0.5 + body * 0.8, IR_SMALL, 0.2)
    return (out / (np.abs(out).max() + 1e-9) * 0.6).astype(np.float32)


def sfx_fire(sec=7.0, seed=121):
    n = int(sec * SR)
    bed = lp(noise(n, seed), 900) * 0.16
    crack = np.zeros(n, dtype=np.float32)
    for _ in range(260):
        i = int(RNG.integers(0, n - 1200))
        ln = int(RNG.integers(200, 1100))
        crack[i:i + ln] += hp(noise(ln, int(RNG.integers(0, 99999))), 1500) * np.exp(
            -np.linspace(0, 9, ln)).astype(np.float32) * RNG.uniform(0.2, 0.9)
    out = bed + crack * 0.35
    out *= env_asr(n, 0.7, sec - 1.4, 0.8)
    return (out / (np.abs(out).max() + 1e-9) * 0.5).astype(np.float32)


def sfx_heart(sec=2.6):
    n = int(sec * SR)
    out = np.zeros(n, dtype=np.float32)
    beat = drum_low(0.5, 5)
    for pos in (0.0, 0.34, 1.3, 1.64):
        i = int(pos * SR)
        if i + len(beat) <= n:
            out[i:i + len(beat)] += beat * (0.85 if pos < 1 else 0.65)
    return out


def sfx_riser(sec=3.0, seed=131):
    n = int(sec * SR)
    src = noise(n, seed)
    out = np.zeros(n, dtype=np.float32)
    step = int(0.05 * SR)
    for i in range(0, n, step):
        p = i / n
        c = 200 * (8 ** p)
        out[i:i + step] = bp(src[i:i + step], c * 0.7, c * 1.4)
    out *= np.linspace(0.05, 1, n) ** 2
    out = fade(out, 0.05, 0.2)
    return (out / (np.abs(out).max() + 1e-9) * 0.45).astype(np.float32)


def sfx_impact(sec=1.8, seed=141):
    n = int(sec * SR)
    sub = sub_pulse(sec, 88, 30) * 0.9
    hit = lp(noise(n, seed), 700) * env_ad(n, 0.004, 0.5, 1.0) * 0.5
    out = verb(sub + hit, IR_HALL, 0.3)
    return (out / (np.abs(out).max() + 1e-9) * 0.9).astype(np.float32)


SFX = {
    "rumble": sfx_rumble, "eruption": sfx_eruption, "ash": sfx_ash, "wind": sfx_wind,
    "water": sfx_water, "paper": sfx_paper, "marker": sfx_marker, "stone": sfx_stone,
    "fire": sfx_fire, "heart": sfx_heart, "riser": sfx_riser, "impact": sfx_impact,
}


# ------------------------------------------------------------------- music
# A minor-ish modal centres keep the whole episode in one key family.
NOTE = {"A1": 55.0, "C2": 65.41, "D2": 73.42, "E2": 82.41, "F2": 87.31, "G2": 98.0,
        "A2": 110.0, "C3": 130.81, "D3": 146.83, "E3": 164.81, "F3": 174.61,
        "G3": 196.0, "A3": 220.0, "C4": 261.63, "D4": 293.66, "E4": 329.63,
        "F4": 349.23, "G4": 392.0, "A4": 440.0, "B4": 493.88, "C5": 523.25,
        "D5": 587.33, "E5": 659.25, "G5": 783.99, "A5": 880.0}


def theme_a(sec=42.0):
    """Legend / mystery — drone, sparse gongs, low breath."""
    n = int(sec * SR)
    out = np.zeros(n, dtype=np.float32)
    drone = pad([NOTE["A1"], NOTE["A1"] * 1.5, NOTE["E2"]], sec, attack=4, release=6, detune=0.2)
    out += drone * 0.5
    beats = [0.0, 4.2, 9.1, 13.0, 18.4, 23.2, 27.6, 32.1, 36.9]
    notes = ["A2", "C3", "E3", "D3", "A2", "G3", "E3", "C3", "A2"]
    for i, b in enumerate(beats):
        g = bell(NOTE[notes[i]], 3.4, bright=0.85, seed=200 + i)
        idx = int(b * SR)
        if idx + len(g) < n:
            out[idx:idx + len(g)] += g * (0.55 if i % 2 else 0.7)
    air = lp(noise(n, 301), 500) * 0.06
    air *= env_asr(n, 3, sec - 6, 3)
    out = out + air
    out = verb(out, IR_HALL, 0.3)
    return (out / (np.abs(out).max() + 1e-9) * 0.7).astype(np.float32)


def theme_b(sec=36.0, intensity=1.0):
    """Tension / eruption — sub pulse grid, membrane hits, scraped metal."""
    n = int(sec * SR)
    out = np.zeros(n, dtype=np.float32)
    bpm = 78
    step = 60.0 / bpm / 2.0
    t = 0.0
    i = 0
    while t < sec - 0.5:
        if i % 4 == 0:
            hit = drum_low(0.6, 400 + i)
            idx = int(t * SR)
            if idx + len(hit) < n:
                out[idx:idx + len(hit)] += hit * 0.8
        if i % 8 == 6:
            p = sub_pulse(0.9, 58, 30)
            idx = int(t * SR)
            if idx + len(p) < n:
                out[idx:idx + len(p)] += p * 0.35
        if i % 2 == 1:
            sh = shaker(0.13, 500 + i)
            idx = int(t * SR)
            if idx + len(sh) < n:
                out[idx:idx + len(sh)] += sh * (0.16 * intensity)
        t += step
        i += 1
    # scrape texture that rises through the section
    scrape = np.zeros(n, dtype=np.float32)
    for k in range(6):
        s0 = int((k * 5.5) * SR)
        ln = int(2.4 * SR)
        if s0 + ln < n:
            scrape[s0:s0 + ln] += bp(noise(ln, 900 + k), 1400, 3600) * np.linspace(
                0.05, 0.35, ln) * np.exp(-np.linspace(0, 3, ln))
    out = out + scrape * 0.5
    drone = pad([NOTE["A1"], NOTE["F2"]], sec, attack=2, release=3, detune=0.5)
    out = out + drone * 0.28
    out = verb(out, IR_HALL, 0.18)
    return (out / (np.abs(out).max() + 1e-9) * 0.8).astype(np.float32)


def theme_c(sec=40.0):
    """Hope / outro — warm pad, felt piano motif, soft shaker."""
    n = int(sec * SR)
    out = np.zeros(n, dtype=np.float32)
    out += pad([NOTE["F2"], NOTE["A2"], NOTE["C3"], NOTE["E3"]], sec,
               attack=5, release=7, detune=0.25) * 0.4
    motif = [(0.6, "C4"), (2.0, "E4"), (3.4, "G4"), (5.0, "E4"),
             (8.2, "A3"), (9.8, "C4"), (11.4, "E4"), (13.0, "D4"),
             (17.0, "F4"), (18.6, "E4"), (20.2, "C4"), (22.0, "A3"),
             (26.0, "G4"), (27.6, "E4"), (29.4, "C4"), (31.0, "D4"),
             (35.0, "C4"), (36.8, "A3")]
    for i, (b, note) in enumerate(motif):
        p = felt_piano(NOTE[note], 3.0, seed=600 + i)
        idx = int(b * SR)
        if idx + len(p) < n:
            out[idx:idx + len(p)] += p * (0.5 if i % 3 else 0.62)
    t = 0.0
    while t < sec - 1:
        sh = shaker(0.12, 700 + int(t))
        idx = int(t * SR)
        if idx + len(sh) < n:
            out[idx:idx + len(sh)] += sh * 0.07
        t += 0.62
    out = verb(out, IR_HALL, 0.32)
    return (out / (np.abs(out).max() + 1e-9) * 0.62).astype(np.float32)


# ------------------------------------------------------------------- output
def write_wav(path: str, mono: np.ndarray, gain_db: float = 0.0, loop_trim=True):
    g = 10 ** (gain_db / 20.0)
    x = np.clip(mono * g, -1, 1)
    if loop_trim:
        x = fade(x, 0.02, 0.08)
    st = np.stack([x, x], axis=1)
    pcm = (st * 32767).astype("<i2")
    import wave
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def build_all():
    os.makedirs(AUD, exist_ok=True)
    jobs = {
        "mus_a_legend.wav": (theme_a(46.0), -16.0),
        "mus_b_tension.wav": (theme_b(40.0, 1.0), -13.0),
        "mus_b_eruption.wav": (theme_b(30.0, 1.35), -11.5),
        "mus_c_hope.wav": (theme_c(44.0), -16.0),
    }
    for name, (x, g) in jobs.items():
        write_wav(os.path.join(AUD, name), x, g)
        print("music:", name, f"{len(x)/SR:.1f}s")
    for name, fn in SFX.items():
        x = fn()
        write_wav(os.path.join(AUD, f"sfx_{name}.wav"), x, -9.0)
        print("sfx:", name, f"{len(x)/SR:.2f}s")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd in ("music", "sfx", "all"):
        build_all()
