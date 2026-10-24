#!/usr/bin/env bash
# Full episode build: plan -> mix -> subtitles -> render -> mux.
# Run from the repo root:  bash tools/build_all.sh
set -euo pipefail
cd "$(dirname "$0")/.."
PY=env/bin/python

echo "== 1/5  plan ==============================================="
$PY tools/render_video.py --plan

echo "== 2/5  audio mix =========================================="
$PY tools/mix.py

echo "== 3/5  subtitles =========================================="
$PY tools/make_srt.py

echo "== 4/5  video render (this is the long one) ================="
$PY tools/render_video.py --render

echo "== 5/5  mux ================================================"
$PY tools/render_video.py --mux

ls -lh video/*.mp4
