#!/usr/bin/env python3
"""shot-stats.py <raw shot folder> - from tel.csv (host clock) and capture.json: the overlay series the composer draws
(overlay.json: one sample per 0.25 s of video time: render fps over the trailing 1 s, speed mph, sim time) and a summary line.
Render fps here = telemetry frames per host second (one datagram per rendered frame), measured in the same run as the video."""
import csv, json, os, sys

d = sys.argv[1]
cap = json.load(open(os.path.join(d, "capture.json"), encoding="utf-8-sig"))
t0 = float(cap["capture_start_host_t"])
dur = float(cap["still"]) + float(cap["drive"])
rows = []
p = os.path.join(d, "tel.csv")
if os.path.exists(p):
    with open(p) as f:
        for r in csv.DictReader(f):
            try:
                rows.append((float(r["host_t"]) - t0, float(r["speed"]), float(r["sim_time"]), float(r["dt"]), int(r["frame"]), int(r["step_count"])))
            except (ValueError, KeyError):
                pass
win = [r for r in rows if 0 <= r[0] <= dur]
series = []
t = 0.0
j0 = 0
while t <= dur + 1e-6:
    seg = [r for r in rows if t - 1.0 < r[0] <= t]          # telemetry = one datagram per sim tick (tick builds) or per frame (stock)
    fps = ticks = None
    if t >= 1.0 and len(seg) >= 2 and seg[-1][0] > seg[0][0]:
        fps = (seg[-1][4] - seg[0][4]) / (seg[-1][0] - seg[0][0])   # simclock frame counter = rendered frames
        ticks = sum(max(0, r[5]) for r in seg[1:]) / (seg[-1][0] - seg[0][0])   # physics steps per second (1 per tick on the tick builds)
    near = [r for r in win if r[0] <= t]
    sp = near[-1][1] if near else 0.0
    series.append({"t": round(t, 2), "fps": None if fps is None else int(round(fps)), "steps": None if ticks is None else int(round(ticks)), "mph": round(sp * 2.23694, 1),
                   "sim": round(near[-1][2], 2) if near else None})
    t += 0.25
json.dump({"series": series, "frames_in_capture": len(win)}, open(os.path.join(d, "overlay.json"), "w"), indent=0)
fps_all = (win[-1][4] - win[0][4]) / (win[-1][0] - win[0][0]) if len(win) > 1 else 0
drive = [r for r in win if r[0] >= float(cap["still"])]
dist = 0.0
for a, b in zip(drive, drive[1:]):
    dist += b[1] * (b[0] - a[0])
fps_drive = (drive[-1][4] - drive[0][4]) / (drive[-1][0] - drive[0][0]) if len(drive) > 1 else 0
print("telemetry: %d datagrams (%.1f/s = ticks or frames) in the %.0f s capture; rendered %.1f fps (drive part %.1f fps), ~%.0f m driven, top %.0f mph"
      % (len(win), len(win) / dur, dur, fps_all, fps_drive, dist, max([r[1] for r in win] or [0]) * 2.23694))
