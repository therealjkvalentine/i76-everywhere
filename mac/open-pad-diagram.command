#!/bin/sh
# Regenerate the controller-layout page from the LIVE configs and open it.
# Always current - parses the prefix input.map + i76-remap.ahk on every run.
cd "$(dirname "$0")/.."   # the repo root (this script lives in mac/)
OUT=$(python3 tools/pad-diagram.py) && open "$OUT"
