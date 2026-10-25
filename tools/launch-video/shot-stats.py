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
                rows.append((float(r["host_t"]) - t0, float(r["speed"]), float(r["sim_time"]), float(r["dt"])))
            except (ValueError, KeyError):
                pass
win = [r for r in rows if 0 <= r[0] <= dur]
series = []
t = 0.0
j0 = 0
while t <= dur + 1e-6:
    n = sum(1 for r in win if t - 1.0 < r[0] <= t) if t >= 1.0 else None
    near = [r for r in win if r[0] <= t]
    sp = near[-1][1] if near else 0.0
    series.append({"t": round(t, 2), "fps": n, "mph": round(sp * 2.23694, 1), "sim": round(near[-1][2], 2) if near else None})
    t += 0.25
json.dump({"series": series, "frames_in_capture": len(win)}, open(os.path.join(d, "overlay.json"), "w"), indent=0)
fps_all = len(win) / dur if dur else 0
drive = [r for r in win if r[0] >= float(cap["still"])]
dist = 0.0
for a, b in zip(drive, drive[1:]):
    dist += b[1] * (b[0] - a[0])
fps_drive = (len(drive) / (dur - float(cap["still"]))) if dur > float(cap["still"]) else 0
print("telemetry: %d frames in the %.0f s capture = %.1f fps (drive part %.1f fps), ~%.0f m driven, top %.0f mph"
      % (len(win), dur, fps_all, fps_drive, dist, max([r[1] for r in win] or [0]) * 2.23694))
