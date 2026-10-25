#!/usr/bin/env python3
"""compose.py - launch-video lane: build the cut from a timeline file (docs/LAUNCH-VIDEO-2026-10-25.md s.2).

  python compose.py --timeline timeline-v1.json --out <dir>\\draft-v1.mp4 [--theme <music\\2.mp3>] [--music <groove.wav>]

Every segment is rendered to a 1920x1080 / 60 fps / yuv420p H.264 file (libx264 crf 18), then concatenated (stream copy), then
muxed with the music: --music gives <out>, --theme gives <out stem>-theme.mp4 (both when both are given). Text is drawn with
libass from generated .ass files (fonts Impact / Arial Black / Consolas, all stock Windows fonts).

Segment types (the "type" key):
  card   : lines [[text, style], ...] on a solid background, dur
  clip   : src (a file, or "shot:<name>" = the newest raw capture of that shot), in, out, speed (0.5 = slow motion), crop
           [x, y, w, h] in source pixels, caption, title, counters (true = fps / mph from that run's overlay.json)
  sbs    : a, b = two clip specs (src / in / out / crop / speed / label / counters / tag); side by side 960x540 each; title, caption
  still  : img, dur, zoom_to [cx, cy, z] (zoom from the whole picture to centre cx, cy (0..1) at zoom z), caption, title
  panel  : game = clip spec scaled 1280x720 at the left, panel = the FFB page recording (640 wide at the right), caption, title
  crawl  : file (one improvement per line), dur, title
"""
import argparse, glob, json, os, subprocess, sys

ap = argparse.ArgumentParser()
ap.add_argument("--timeline", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--music", default="")
ap.add_argument("--theme", default="")
ap.add_argument("--ffmpeg", default="ffmpeg")
ap.add_argument("--raw", default=r"C:\Users\james\i76-uncap-lab\captures\launch-video\raw")
ap.add_argument("--only", default="", help="render only these segment numbers (comma list) - for previews")
a = ap.parse_args()
HERE = os.path.dirname(os.path.abspath(__file__))
TL = json.load(open(a.timeline, encoding="utf-8"))
work = os.path.join(os.path.dirname(os.path.abspath(a.out)), "work-" + os.path.splitext(os.path.basename(a.out))[0])
os.makedirs(work, exist_ok=True)
FPS = 60
BG = TL.get("bg", "0x140c08")
ENC = ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(FPS), "-an"]


def ff(args):
    cmd = [a.ffmpeg, "-hide_banner", "-loglevel", "error", "-y"] + args
    r = subprocess.run(cmd, cwd=work)
    if r.returncode:
        print("ffmpeg failed:", " ".join(cmd)); sys.exit(1)


def probe_dur(p):
    r = subprocess.run([a.ffmpeg.replace("ffmpeg.exe", "ffprobe.exe").replace("ffmpeg", "ffprobe") if a.ffmpeg != "ffmpeg" else "ffprobe",
                        "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", p], capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def src_path(s):
    if s.startswith("shot:"):
        c = sorted(glob.glob(os.path.join(a.raw, s[5:], "*", "video.mp4")))
        if not c:
            raise SystemExit("no capture for %s" % s)
        return c[-1]
    return s if os.path.isabs(s) else os.path.join(HERE, s)


def overlay_for(path):
    p = os.path.join(os.path.dirname(path), "overlay.json")
    return json.load(open(p))["series"] if os.path.exists(p) else []


# ---------------- ASS
HEAD = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Title,Impact,120,&H0030A8FF,&H00FFFFFF,&H00101010,&H80000000,0,0,0,0,100,100,2,0,1,5,3,5,40,40,40,1
Style: Big,Impact,84,&H00FFFFFF,&H00FFFFFF,&H00101010,&H80000000,0,0,0,0,100,100,1,0,1,4,2,5,40,40,40,1
Style: Sub,Arial Black,44,&H00D8E8F0,&H00FFFFFF,&H00101010,&H80000000,0,0,0,0,100,100,0,0,1,3,1,5,40,40,40,1
Style: Head,Impact,64,&H0030A8FF,&H00FFFFFF,&H00101010,&H80000000,0,0,0,0,100,100,1,0,1,4,2,8,40,40,40,1
Style: Cap,Arial Black,40,&H00FFFFFF,&H00FFFFFF,&H00101010,&H90000000,0,0,0,0,100,100,0,0,1,3,1,2,60,60,40,1
Style: Label,Impact,54,&H00FFFFFF,&H00FFFFFF,&H00101010,&H80000000,0,0,0,0,100,100,1,0,1,4,1,5,20,20,20,1
Style: Mono,Consolas,40,&H0060F0FF,&H00FFFFFF,&H00101010,&HA0000000,1,0,0,0,100,100,0,0,3,3,0,5,20,20,20,1
Style: Crawl,Arial Black,38,&H00FFFFFF,&H00FFFFFF,&H00101010,&H80000000,0,0,0,0,100,100,0,0,1,2,1,8,80,80,0,1
Style: Small,Arial,30,&H00C0C8D0,&H00FFFFFF,&H00101010,&H80000000,0,0,0,0,100,100,0,0,1,2,0,5,40,40,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def ts(t):
    t = max(0.0, t); h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return "%d:%02d:%05.2f" % (h, m, s)


class Ass:
    def __init__(self):
        self.ev = []

    def add(self, t0, t1, style, text, pos=None, fade=(250, 250), extra=""):
        tags = "{\\fad(%d,%d)%s%s}" % (fade[0], fade[1], ("\\pos(%d,%d)" % pos) if pos else "", extra)
        self.ev.append("Dialogue: 0,%s,%s,%s,,0,0,0,,%s%s" % (ts(t0), ts(t1), style, tags, text))

    def write(self, name):
        p = os.path.join(work, name)
        with open(p, "w", encoding="utf-8") as f:
            f.write(HEAD + "\n".join(self.ev) + "\n")
        return name


def counters(ass, series, t_in, speed, dur, pos, tag):
    """fps / mph per 0.25 s of the output, from the shot's own telemetry (overlay.json)."""
    if not series:
        return
    step = 0.25
    t = 0.0
    while t < dur - 1e-6:
        st = t_in + t * speed
        smp = min(series, key=lambda s: abs(s["t"] - st))
        fps = smp["fps"]
        txt = "%s FPS   %3d MPH   %s" % (("%3d" % fps) if fps is not None else "  -", int(round(smp["mph"])), tag)
        ass.add(t, min(dur, t + step), "Mono", txt.replace(" ", "\\h"), pos=pos, fade=(0, 0))
        t += step


def clip_chain(spec, w, h, label):
    """filter chain for one clip input -> w x h (letterboxed), returns (input args, filter text, out duration)."""
    p = src_path(spec["src"])
    tin, tout = float(spec.get("in", 0)), float(spec["out"])
    sp = float(spec.get("speed", 1.0))
    f = []
    if spec.get("crop"):
        x, y, cw, ch = spec["crop"]; f.append("crop=%d:%d:%d:%d" % (cw, ch, x, y))
    f.append("setpts=(PTS-STARTPTS)/%g" % sp)
    f.append("scale=%d:%d:force_original_aspect_ratio=decrease:flags=lanczos" % (w, h))
    f.append("pad=%d:%d:(ow-iw)/2:(oh-ih)/2:color=%s" % (w, h, BG))
    f.append("fps=%d" % FPS)
    return ["-ss", str(tin), "-t", str(tout - tin), "-i", p], ",".join(f), (tout - tin) / sp, p


def seg_card(i, s):
    dur = float(s["dur"]); ass = Ass()
    lines = s["lines"]; n = len(lines)
    y0 = 540 - (n - 1) * 70
    for k, (txt, style) in enumerate(lines):
        ass.add(0, dur, style, txt, pos=(960, y0 + k * 140))
    sub = ass.write("s%02d.ass" % i)
    ff(["-f", "lavfi", "-i", "color=c=%s:s=1920x1080:r=%d:d=%g" % (s.get("bg", BG), FPS, dur), "-vf", "subtitles=%s,fade=in:0:15,fade=out:st=%g:d=0.25" % (sub, dur - 0.25)] + ENC + ["s%02d.mp4" % i])


def text_layer(ass, s, dur):
    if s.get("title"):
        ass.add(0, dur, "Head", s["title"], pos=(960, 40))
    if s.get("caption"):
        ass.add(0.3, dur, "Cap", s["caption"])


def seg_clip(i, s):
    inp, chain, dur, p = clip_chain(s, 1920, 1080, None)
    ass = Ass(); text_layer(ass, s, dur)
    if s.get("counters"):
        counters(ass, overlay_for(p), float(s.get("in", 0)), float(s.get("speed", 1.0)), dur, (960, 130), s.get("tag", ""))
    if s.get("speed", 1.0) != 1.0:
        ass.add(0, dur, "Label", "%gx SPEED" % float(s["speed"]), pos=(1780, 980), fade=(0, 0))
    sub = ass.write("s%02d.ass" % i)
    ff(inp + ["-vf", "%s,subtitles=%s,fade=in:0:12,fade=out:st=%g:d=0.2" % (chain, sub, dur - 0.2)] + ENC + ["s%02d.mp4" % i])


def seg_sbs(i, s):
    ia, ca, da, pa = clip_chain(s["a"], 960, 540, None)
    ib, cb, db, pb = clip_chain(s["b"], 960, 540, None)
    dur = min(da, db)
    ass = Ass(); text_layer(ass, s, dur)
    for k, (spec, p) in enumerate(((s["a"], pa), (s["b"], pb))):
        cx = 480 + 960 * k
        ass.add(0, dur, "Label", spec.get("label", ""), pos=(cx, 222))
        if spec.get("counters"):
            counters(ass, overlay_for(p), float(spec.get("in", 0)), float(spec.get("speed", 1.0)), dur, (cx, 858), spec.get("tag", ""))
        elif spec.get("sub"):
            ass.add(0, dur, "Mono", spec["sub"].replace(" ", "\\h"), pos=(cx, 858))
    if s["a"].get("speed", 1.0) != 1.0:
        ass.add(0, dur, "Label", "%gx SPEED" % float(s["a"]["speed"]), pos=(1780, 1030), fade=(0, 0))
    sub = ass.write("s%02d.ass" % i)
    fc = "[0:v]%s[a];[1:v]%s[b];[a][b]hstack=2,pad=1920:1080:0:270:color=%s,subtitles=%s,fade=in:0:12,fade=out:st=%g:d=0.2[v]" % (ca, cb, BG, sub, dur - 0.2)
    ff(ia + ib + ["-filter_complex", fc, "-map", "[v]", "-t", str(dur)] + ENC + ["s%02d.mp4" % i])


def seg_still(i, s):
    dur = float(s["dur"]); n = int(dur * FPS)
    cx, cy, z = s.get("zoom_to", [0.5, 0.5, 1.0])
    img = s["img"]
    zexp = "1+(%g-1)*min(1,on/%d)" % (z, int(n * 0.8))
    xexp = "(iw*(0.5+(%g-0.5)*min(1,on/%d)))-(iw/zoom/2)" % (cx, int(n * 0.8))
    yexp = "(ih*(0.5+(%g-0.5)*min(1,on/%d)))-(ih/zoom/2)" % (cy, int(n * 0.8))
    ass = Ass(); text_layer(ass, s, dur)
    for k, ln in enumerate(s.get("notes", [])):
        ass.add(0.5 + 0.6 * k, dur, "Sub", ln, pos=(1700, 330 + 150 * k), extra="\\fs40\\q2")
    sub = ass.write("s%02d.ass" % i)
    vf = ("scale=2560:1920:flags=lanczos,zoompan=z='%s':x='%s':y='%s':d=%d:s=1440x1080:fps=%d,pad=1920:1080:%d:0:color=%s,subtitles=%s,fade=in:0:12,fade=out:st=%g:d=0.2"
          % (zexp, xexp, yexp, n, FPS, s.get("x", 0), BG, sub, dur - 0.2))
    ff(["-loop", "1", "-i", img, "-vf", vf, "-frames:v", str(n)] + ENC + ["s%02d.mp4" % i])


def seg_panel(i, s):
    ig, cg, dg, pg = clip_chain(s["game"], 1280, 720, None)
    pp = src_path(s["panel"]["src"])
    pin = float(s["panel"].get("in", 0))
    dur = min(dg, float(s.get("dur", dg)))
    ass = Ass(); text_layer(ass, s, dur)
    if s["game"].get("counters"):
        counters(ass, overlay_for(pg), float(s["game"].get("in", 0)), 1.0, dur, (640, 940), s["game"].get("tag", ""))
    sub = ass.write("s%02d.ass" % i)
    fc = ("[0:v]%s[g];[1:v]scale=640:1080:force_original_aspect_ratio=decrease:flags=lanczos,pad=640:1080:0:0:color=%s,fps=%d,setpts=PTS-STARTPTS[p];"
          "color=c=%s:s=1920x1080:r=%d[bg];[bg][g]overlay=0:180[t];[t][p]overlay=1280:0:shortest=1,subtitles=%s,fade=in:0:12,fade=out:st=%g:d=0.2[v]"
          % (cg, BG, FPS, BG, FPS, sub, dur - 0.2))
    ff(ig + ["-ss", str(pin), "-t", str(dur), "-i", pp, "-filter_complex", fc, "-map", "[v]", "-t", str(dur)] + ENC + ["s%02d.mp4" % i])


def seg_crawl(i, s):
    dur = float(s["dur"])
    lines = [l.strip() for l in open(src_path(s["file"]), encoding="utf-8") if l.strip()]
    lines = ["%d. %s" % (k + 1, l) for k, l in enumerate(lines)]
    lh = 50; H = len(lines) * lh
    ass = Ass()
    body = "\\N".join(x.replace("{", "(").replace("}", ")") for x in lines)
    ass.add(0, dur, "Crawl", body, fade=(0, 0), extra="\\an8\\move(960,1080,960,%d)" % (-H))
    sub = ass.write("s%02d.ass" % i)
    top = Ass()
    top.add(0, dur, "Head", s.get("title", ""), pos=(960, 30), fade=(0, 0), extra="\\bord6")
    top.add(0, dur, "Small", "%d improvements, %g seconds" % (len(lines), dur), pos=(960, 112), fade=(0, 0))
    if s.get("aside"):
        top.add(1.0, dur, "Small", s["aside"], pos=(1700, 1040), fade=(200, 0))
    sub2 = top.write("s%02db.ass" % i)
    ff(["-f", "lavfi", "-i", "color=c=%s:s=1920x1080:r=%d:d=%g" % (BG, FPS, dur), "-vf",
        "subtitles=%s,drawbox=x=0:y=0:w=1920:h=140:color=%s@1:t=fill,subtitles=%s,fade=in:0:10,fade=out:st=%g:d=0.25" % (sub, BG, sub2, dur - 0.25)] + ENC + ["s%02d.mp4" % i])


R = {"card": seg_card, "clip": seg_clip, "sbs": seg_sbs, "still": seg_still, "panel": seg_panel, "crawl": seg_crawl}
only = set(int(x) for x in a.only.split(",") if x)
segs = TL["segments"]
for i, s in enumerate(segs):
    if only and i not in only:
        continue
    print("segment %02d %s %s" % (i, s["type"], s.get("title") or s.get("caption") or ""))
    R[s["type"]](i, s)
if only:
    sys.exit(0)
with open(os.path.join(work, "concat.txt"), "w") as f:
    for i in range(len(segs)):
        f.write("file 's%02d.mp4'\n" % i)
ff(["-f", "concat", "-safe", "0", "-i", "concat.txt", "-c", "copy", "video.mp4"])
vid = os.path.join(work, "video.mp4")
D = probe_dur(vid)
outs = []
if a.music:
    outs.append((a.music, a.out, TL.get("music_in", 0)))
if a.theme:
    outs.append((a.theme, os.path.splitext(a.out)[0] + "-theme.mp4", TL.get("theme_in", 0)))
if not outs:
    outs.append(("", a.out, 0))
for mus, out, mi in outs:
    if mus:
        ff(["-i", "video.mp4", "-ss", str(mi), "-i", mus, "-filter_complex",
            "[1:a]atrim=0:%g,asetpts=PTS-STARTPTS,afade=in:0:d=0.5,afade=out:st=%g:d=2.5,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[a]" % (D, D - 2.5),
            "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", os.path.abspath(out)])
    else:
        ff(["-i", "video.mp4", "-c", "copy", "-movflags", "+faststart", os.path.abspath(out)])
    print("compose: %s (%.1f s)" % (out, D))
