#!/usr/bin/env python3
"""make-stills.py - launch-video lane: announcement / README stills (1920x1080 PNG) from the raw shots and the rendered segments.

  python make-stills.py --list stills-v1.json --out <lab>\\captures\\launch-video\\stills [--ffmpeg <ffmpeg.exe>]

List entries: {"name": "...", "src": "shot:<name>" | "seg:<draft work folder>/sNN.mp4" | <file>, "t": seconds, "crop": [x,y,w,h]}
A crop is scaled up to fit 1920x1080 (lanczos, letterboxed). Missing shots are skipped and listed."""
import argparse, glob, json, os, subprocess

LAB = os.environ.get("I76_LAB") or os.path.join(os.path.expanduser("~"), "i76-uncap-lab")  # lab folder; "${LAB}" in timeline/list paths expands to it


def lab(s):
    return s.replace("${LAB}", LAB)


ap = argparse.ArgumentParser()
ap.add_argument("--list", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--ffmpeg", default="ffmpeg")
ap.add_argument("--raw", default=os.path.join(LAB, "captures", "launch-video", "raw"))
ap.add_argument("--cap", default=os.path.join(LAB, "captures", "launch-video"))
a = ap.parse_args()
os.makedirs(a.out, exist_ok=True)
HERE = os.path.dirname(os.path.abspath(__file__))
done, skipped = [], []
for e in json.load(open(os.path.join(HERE, a.list) if not os.path.isabs(a.list) else a.list, encoding="utf-8")):
    s = e["src"]
    if s.startswith("shot:"):
        c = sorted(glob.glob(os.path.join(a.raw, s[5:], "*", "video.mp4")))
        p = c[-1] if c else None
    elif s.startswith("seg:"):
        p = os.path.join(a.cap, s[4:])
    else:
        p = lab(s)
    if not p or not os.path.exists(p):
        skipped.append(e["name"]); continue
    vf = []
    if e.get("crop"):
        x, y, w, h = e["crop"]; vf.append("crop=%d:%d:%d:%d" % (w, h, x, y))
    vf += ["scale=1920:1080:force_original_aspect_ratio=decrease:flags=lanczos", "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0x140c08"]
    args = [a.ffmpeg, "-hide_banner", "-loglevel", "error", "-y"]
    if p.lower().endswith((".png", ".jpg")):
        args += ["-i", p]
    else:
        args += ["-ss", str(e.get("t", 0)), "-i", p]
    out = os.path.join(a.out, e["name"] + ".png")
    subprocess.run(args + ["-frames:v", "1", "-vf", ",".join(vf), out], check=True)
    done.append(out)
print("stills: %d written to %s" % (len(done), a.out))
for n in skipped:
    print("skipped (no capture yet): " + n)
