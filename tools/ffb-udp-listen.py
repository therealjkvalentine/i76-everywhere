#!/usr/bin/env python3
"""Listen to the FFB shim's UDP telemetry and show it live (or log it).

The ffb-shim (../ffb-shim/) sends one key=value datagram per sim tick to
127.0.0.1:17676 — the game's own force-feedback stream (engine, speed, terrain,
skid/air/oil flags, the ForceX/ForceY body-frame vector, weapon fire, tires,
and the mixed rumble motor levels). This is:

  * the "prove the wire works" tool — run it, install the shim, drive, and you
    should see numbers move (no motion rig or SimHub needed);
  * a stand-in visualizer until a SimTools/SimHub plugin consumes the same
    datagram (the industry-standard receivers whose axis-testers become the
    real visualizer — see docs/MOTION-SIM.md);
  * a recorder (--csv) so a field run can be analyzed / tuned offline.

Usage:
  ffb-udp-listen.py                 # live text dashboard on 127.0.0.1:17676
  ffb-udp-listen.py --port 17676
  ffb-udp-listen.py --raw           # print each datagram verbatim
  ffb-udp-listen.py --csv run.csv   # also append parsed rows to a CSV

Surge/sway note: for a motion rig, fx1000/1000 ≈ longitudinal force (surge),
fy1000/1000 ≈ lateral (sway). Roll/pitch/heave need the entity transform matrix
from memory (docs/MEMORY-MAP-INDEX.md Tier 2) — not in this stream yet.
"""
import argparse, re, socket, sys, time

FIELDS = ("tick", "on", "spd10", "surf", "run", "pitch", "air", "skid",
          "slide", "oil", "steer", "fx1000", "fy1000", "fy2_1000",
          "gain", "low100", "high100")
# surface id -> name; ORDER IS A GUESS (docs/FFB-DEEP-DIVE.md open item) — the
# telemetry is exactly how you confirm it: drive on pavement vs dirt and watch.
SURFACES = {0: "stopped", 1: "dirt-x?", 2: "parking?", 3: "rocky?", 4: "wash?",
            5: "dirt-rd?", 6: "paved?", 7: "veg?", 8: "packed?", 9: "in-air?"}


def parse(line):
    d = {}
    for k, v in re.findall(r"(\w+)=(-?[\d,]+)", line):
        d[k] = v
    return d


def bar(v01, width=20):
    v01 = max(0.0, min(1.0, v01))
    fill = int(round(v01 * width))
    return "#" * fill + "-" * (width - fill)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=17676)
    ap.add_argument("--raw", action="store_true")
    ap.add_argument("--csv", default="")
    args = ap.parse_args()

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", args.port))
    s.settimeout(2.0)
    print(f"listening on 127.0.0.1:{args.port} — install + run the shim, then drive")

    csv = open(args.csv, "w") if args.csv else None
    if csv:
        csv.write(",".join(FIELDS) + "\n")
    pkts = 0
    last = time.time()
    while True:
        try:
            data, _ = s.recvfrom(1024)
        except socket.timeout:
            if pkts == 0:
                print("...no packets yet (is the shim installed and the game in a mission?)")
            continue
        line = data.decode("ascii", "replace").strip()
        pkts += 1
        d = parse(line)
        if csv:
            csv.write(",".join(d.get(f, "").replace(",", ";") for f in FIELDS) + "\n")
            csv.flush()
        if args.raw:
            print(line)
            continue

        now = time.time()
        if now - last < 0.08:          # throttle the redraw to ~12 Hz
            continue
        last = now
        gi = lambda k: int(d.get(k, "0") or "0")
        spd = gi("spd10") / 10.0
        fx = gi("fx1000") / 1000.0
        fy = gi("fy1000") / 1000.0
        surf = SURFACES.get(gi("surf"), f"id{gi('surf')}")
        flags = " ".join(f for f, k in
                         (("AIR", "air"), ("SKID", "skid"), ("SLIDE", "slide"),
                          ("OIL", "oil")) if gi(k)) or "-"
        sys.stdout.write("\x1b[2J\x1b[H")   # clear + home
        print(f"tick {d.get('tick','?')}   forces {'ON' if gi('on') else 'off'}\n")
        print(f"  left  (impact/engine) [{bar(gi('low100')/100)}] {gi('low100'):3d}")
        print(f"  right (weapons)       [{bar(gi('high100')/100)}] {gi('high100'):3d}\n")
        print(f"  speed   {spd:6.1f} mph  [{bar(min(spd/165,1))}]")
        print(f"  surge fx {fx:+.2f}   sway fy {fy:+.2f}   steer {gi('steer'):+d}")
        print(f"  engine  {'run' if gi('run') else 'off':>3}  pitch {gi('pitch')}   surface {surf}")
        print(f"  flags   {flags}")
        print(f"  tires   {d.get('tires','?')}    firing {d.get('fire','?')} gain {gi('gain')}")
        print(f"\n  {pkts} packets")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
