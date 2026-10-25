#!/usr/bin/env python3
"""tel-udp.py - launch-video lane: log the proxy's per-frame telemetry (I76_TELEMETRY=<port>) with the HOST clock, so the
overlay counters (render fps, sim time, speed) can be lined up with an ffmpeg capture started at a known host time.

  python tel-udp.py --port 27760 --out run.tel.csv --seconds 400

Columns: host_t (time.time()), seq, frame, proxy_frame, sim_time, dt, step_count, speed (m/s). Stops after --seconds or when
--stop-file appears. Decodes through tools/telemetry/i76tel.py (any frame version it knows)."""
import argparse, os, socket, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "telemetry"))
import i76tel  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--port", type=int, required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--seconds", type=float, default=600)
ap.add_argument("--stop-file", default="")
a = ap.parse_args()

h = i76tel.Header()
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(("127.0.0.1", a.port))
s.settimeout(0.5)
t0 = time.time(); n = 0
with open(a.out, "w", newline="") as f:
    f.write("host_t,seq,frame,proxy_frame,sim_time,dt,step_count,speed\n")
    while time.time() - t0 < a.seconds:
        if a.stop_file and os.path.exists(a.stop_file):
            break
        try:
            data, _ = s.recvfrom(65536)
        except socket.timeout:
            continue
        now = time.time()
        fr, _ev = i76tel.decode_datagram(h, data)
        if not fr:
            continue
        n += 1
        f.write("%.4f,%d,%d,%d,%.4f,%.5f,%d,%.3f\n" % (now, fr.get("seq", 0), fr.get("frame", 0), fr.get("proxy_frame", 0),
                                                       fr.get("sim_time", 0.0), fr.get("dt", 0.0), fr.get("step_count", -1), fr.get("speed", 0.0)))
        if n % 600 == 0:
            f.flush()
print("tel-udp: %d frames -> %s" % (n, a.out))
