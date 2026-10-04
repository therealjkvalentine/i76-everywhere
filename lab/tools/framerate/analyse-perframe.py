#!/usr/bin/env python3
"""analyse-perframe.py pf20.csv pf60.csv - which values are advanced PER FRAME?

Both runs cover the same WALL-CLOCK time with the car parked. So for each address:

    delta60 / delta20 ~ 1   -> driven by real time (correct)
    delta60 / delta20 ~ 3   -> advanced once per FRAME  <-- the bug class

Reports the per-frame candidates, which is where the sky-scroll, death-camera-spin and any
other frame-coupled animation will show up.
"""
import csv, sys

def load(p):
    fps = None
    rows = {}
    with open(p) as f:
        for line in f:
            line = line.strip()
            if line.startswith('#'):
                for tok in line.split():
                    if tok.startswith('fps='): fps = float(tok.split('=')[1])
                continue
            if line.startswith('addr'): continue
            if not line: continue
            a, df, di = line.split(',')
            rows[a] = (float(df) if df not in ('NaN','') else float('nan'), int(di))
    return fps, rows

f20, r20 = load(sys.argv[1])
f60, r60 = load(sys.argv[2])
print("run A: %.1f fps, %d changed   run B: %.1f fps, %d changed" % (f20, len(r20), f60, len(r60)))
frame_ratio = f60 / f20 if f20 else 0
print("frame-rate ratio B/A = %.2f  (per-frame values should show this ratio)\n" % frame_ratio)

cands = []
for a in r20:
    if a not in r60: continue
    d20f, d20i = r20[a]
    d60f, d60i = r60[a]
    # use the float delta when it is sane, else the int delta
    x, y = (d20f, d60f) if (d20f == d20f and d60f == d60f and abs(d20f) > 1e-6) else (float(d20i), float(d60i))
    if abs(x) < 1e-6: continue
    ratio = y / x
    if ratio <= 0: continue
    cands.append((abs(ratio - frame_ratio), ratio, a, x, y))

cands.sort()
print("%-12s %10s %12s %12s  %s" % ("addr", "ratio", "delta@A", "delta@B", "verdict"))
shown = 0
for err, ratio, a, x, y in cands:
    if shown >= 25: break
    verdict = "PER-FRAME" if abs(ratio - frame_ratio) < frame_ratio*0.35 else ""
    if not verdict: continue
    print("%-12s %10.2f %12.4f %12.4f  %s" % (a, ratio, x, y, verdict))
    shown += 1
if shown == 0:
    print("(no address showed the frame-rate ratio - widen the scan range or the duration)")
print("\nCross-reference against known addresses: camera Euler 0x4C2964/6C/70/74,")
print("camera FSM 0x4C2728, frame counter 0x5A7E1C (expected to be per-frame by definition).")
