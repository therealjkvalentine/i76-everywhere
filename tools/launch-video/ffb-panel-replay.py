#!/usr/bin/env python3
"""ffb-panel-replay.py - launch-video lane: the FFB tuning page (tools/ffb/ffb-panel.py) fed with a RECORDED interposer session
and filmed headless with Playwright (Edge), no game, no wheel, no console.

  python ffb-panel-replay.py --states <lab>\\captures\\ffb-panel-20261025\\p3.states.jsonl --out <dir> [--from 20 --seconds 30]

The states file is the panel lane's /api/state log of a real DryRun drive (panel-live-test.ps1, private desktop, the RC twin,
OWNER-2300-ALL, 2026-10-25). Each logged snapshot's 'meta' and 'state' are the interposer's own datagrams; they are re-sent to
a private ffb-panel.py instance (free ports, a temp tune file) at the logged pace, numeric fields linearly interpolated to 30 Hz
between the 5 Hz snapshots so the meters move smoothly. Output: <out>/panel.webm (viewport 880 x 1485 = the page at its own
width, 640 x 1080 once scaled into the 1080p frame) and panel.mp4 (60 fps CFR)."""
import argparse, json, os, shutil, socket, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
PANEL = os.path.join(HERE, "..", "ffb", "ffb-panel.py")
ap = argparse.ArgumentParser()
ap.add_argument("--states", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--from", dest="t_from", type=float, default=15.0, help="start offset into the logged session, s")
ap.add_argument("--seconds", type=float, default=30.0)
ap.add_argument("--width", type=int, default=880)
ap.add_argument("--height", type=int, default=1485)
ap.add_argument("--ffmpeg", default="ffmpeg")
a = ap.parse_args()
os.makedirs(a.out, exist_ok=True)


def free(kind):
    s = socket.socket(socket.AF_INET, kind); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def lerp(x, y, f):
    if isinstance(x, bool) or isinstance(y, bool):
        return y if f >= 0.5 else x
    if isinstance(x, int) and isinstance(y, int):
        return int(round(x + (y - x) * f))
    if isinstance(x, (int, float)) and isinstance(y, (int, float)):
        return round(x + (y - x) * f, 3)
    if isinstance(x, dict) and isinstance(y, dict):
        return {k: (lerp(x[k], y[k], f) if k in x else y[k]) for k in y}
    return y if f >= 0.5 else x


snaps = [json.loads(l) for l in open(a.states, encoding="utf-8")]
snaps = [s for s in snaps if s.get("state")]
w0 = snaps[0]["_wall"]
snaps = [s for s in snaps if a.t_from <= s["_wall"] - w0 <= a.t_from + a.seconds + 1]
tmp = tempfile.mkdtemp(prefix="lv-ffbpanel-")
tune = os.path.join(tmp, "ffb-tune-owner.json")
with open(tune, "w") as f:
    f.write("{}\n")
http, udp, ctl = free(socket.SOCK_STREAM), free(socket.SOCK_DGRAM), free(socket.SOCK_DGRAM)
srv = subprocess.Popen([sys.executable, PANEL, "--no-browser", "--http-port", str(http), "--udp-port", str(udp), "--ctl-port", str(ctl),
                        "--seconds", str(a.seconds + 60)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
sink = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); sink.bind(("127.0.0.1", ctl))   # commands from the page go nowhere
tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


def send(obj):
    tx.sendto(json.dumps(obj).encode(), ("127.0.0.1", udp))


try:
    time.sleep(1.0)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge")
        ctx = b.new_context(viewport={"width": a.width, "height": a.height}, record_video_dir=tmp,
                            record_video_size={"width": a.width, "height": a.height}, color_scheme="dark")
        page = ctx.new_page()
        meta = dict(snaps[0].get("meta") or {}); meta["tune_file"] = tune
        send(meta); send(snaps[0]["state"])
        page.goto("http://127.0.0.1:%d/" % http)
        time.sleep(2.0)
        t_start = time.time(); lead_in = time.time() - t_start
        base = snaps[0]["_wall"]; i = 0
        while True:
            el = time.time() - t_start
            tw = base + el
            while i + 1 < len(snaps) and snaps[i + 1]["_wall"] <= tw:
                i += 1
            if i + 1 >= len(snaps):
                break
            s0, s1 = snaps[i], snaps[i + 1]
            f = (tw - s0["_wall"]) / max(1e-6, s1["_wall"] - s0["_wall"])
            st = lerp(s0["state"], s1["state"], f)
            st["ev"] = s0["state"].get("ev", []); st["ev_last"] = s0["state"].get("ev_last", 0); st["seq"] = int(1e6 + el * 30)
            send(st)
            if int(el) % 2 == 0 and el - int(el) < 0.04:
                send(meta)
            time.sleep(1 / 30)
        vid = page.video.path()
        ctx.close(); b.close()
    shutil.copy(vid, os.path.join(a.out, "panel.webm"))
    subprocess.run([a.ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-ss", "2.2", "-i", os.path.join(a.out, "panel.webm"),
                    "-vf", "fps=60", "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", os.path.join(a.out, "panel.mp4")], check=True)
    print("ffb-panel-replay: %s (%d snapshots, %.0f s from %.0f s)" % (os.path.join(a.out, "panel.mp4"), len(snaps), a.seconds, a.t_from))
finally:
    srv.terminate()
    shutil.rmtree(tmp, ignore_errors=True)
