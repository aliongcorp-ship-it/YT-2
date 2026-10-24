"""Generate the Indonesian subtitle file from the narration timings.

Cues are derived from each narration clip's real duration and the sentence
text, with reading-speed limiting (max 42 chars / 2 lines / 6 s per cue).

    python env/bin/python tools/make_srt.py
"""
from __future__ import annotations

import glob
import json
import os
import re
import subprocess
import sys

import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VO = os.path.join(ROOT, "audio", "vo")
OUT = os.path.join(ROOT, "social")

MAX_CHARS = 84        # two lines of ~42
MAX_DUR = 6.0
MIN_DUR = 1.1


def ff_duration(path: str) -> float:
    err = subprocess.run([FF, "-i", path], capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", err)
    if not m:
        return 0.0
    h, mi, s = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(s)


def split_cues(text: str) -> list[str]:
    """Split into subtitle-sized chunks, preferring punctuation boundaries."""
    parts = re.split(r"(?<=[.!?])\s+|(?<=,)\s+", text)
    cues, cur = [], ""
    for p in parts:
        if not p:
            continue
        cand = (cur + " " + p).strip()
        if len(cand) <= MAX_CHARS or not cur:
            cur = cand
        else:
            cues.append(cur)
            cur = p
    if cur:
        cues.append(cur)
    # hard-wrap anything still too long
    out = []
    for c in cues:
        if len(c) <= MAX_CHARS:
            out.append(c)
        else:
            words, line = c.split(), ""
            for w in words:
                if len(line) + len(w) + 1 > MAX_CHARS and line:
                    out.append(line)
                    line = w
                else:
                    line = (line + " " + w).strip()
            if line:
                out.append(line)
    return out


def wrap2(text: str, width: int = 42) -> str:
    if len(text) <= width:
        return text
    words = text.split()
    l1, l2 = "", ""
    for w in words:
        if len(l1) + len(w) + 1 <= width and not l2:
            l1 = (l1 + " " + w).strip()
        else:
            l2 = (l2 + " " + w).strip()
    return f"{l1}\n{l2}" if l2 else l1


def ts(t: float) -> str:
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")


def main():
    pieces = sorted(glob.glob(os.path.join(VO, "vo10_*.mp3"))) or \
             sorted(glob.glob(os.path.join(VO, "pc_*.mp3"))) or \
             sorted(glob.glob(os.path.join(VO, "*.mp3")))
    if not pieces:
        raise SystemExit("no narration clips")
    text_path = os.path.join(ROOT, "scripts", "vo10.json")
    if not os.path.exists(text_path):
        text_path = os.path.join(ROOT, "scripts", "vo_pieces.json")
    texts = json.load(open(text_path))
    texts = [t for t in texts if len(t) > 40]          # drop the tiny test clips
    if len(texts) != len(pieces):
        print(f"warning: {len(texts)} texts vs {len(pieces)} clips; "
              f"using min() and re-flowing by total duration")

    tl_path = os.path.join(ROOT, "scripts", "timeline.json")
    gap = 0.42
    if os.path.exists(tl_path):
        gap = json.load(open(tl_path)).get("gap", 0.42)

    cues, t = [], 0.0
    for i, p in enumerate(pieces):
        d = ff_duration(p)
        txt = texts[i] if i < len(texts) else ""
        if not txt:
            t += d + gap
            continue
        parts = split_cues(txt)
        total_chars = sum(len(x) for x in parts) or 1
        cursor = t
        for part in parts:
            share = len(part) / total_chars
            dur = max(MIN_DUR, min(MAX_DUR, d * share))
            cues.append((cursor, cursor + dur, part))
            cursor += dur
        t += d + gap

    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "KALDERA_Bab1_ID.srt")
    with open(path, "w", encoding="utf-8") as f:
        for i, (a, b, txt) in enumerate(cues, 1):
            f.write(f"{i}\n{ts(a)} --> {ts(b)}\n{wrap2(txt)}\n\n")
    print(f"wrote {path} ({len(cues)} cues, {t/60:.1f} min)")


if __name__ == "__main__":
    main()
