"""frame_stats.py - frame-rate quality from Local\\I76Telemetry over N seconds (default 10).

Prints: frames/s, frame dt mean / sd / p99 and the two most common 1 ms bins, physics substeps per second
(step_count), motionless frames (position unchanged from the previous frame while the car moves faster than
1 m/s: the judder the render interpolation removes), telemetry faults. Use it to compare 60 and 120 fps runs.

    python frame_stats.py [seconds] [label]
"""
import mmap, struct, sys, time, math
sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import i76tel

secs = float(sys.argv[1]) if len(sys.argv) > 1 else 10.0
label = sys.argv[2] if len(sys.argv) > 2 else ""
h = i76tel.Header()
size = h.structs["i76tel_shm_t"][1]; off = h.offset("i76tel_shm_t", "frame")
m = mmap.mmap(-1, size, tagname=h.consts["I76TEL_SHM_NAME"])
last = None; dts = []; steps = 0; frames = 0; still = 0; moving = 0; prev_pos = None; faults0 = None
t0 = time.time(); deadline = t0 + secs
while time.time() < deadline:
    s0 = struct.unpack_from("<I", m, 0)[0]
    if s0 == 0 or s0 & 1 or s0 == last:
        time.sleep(0.0005); continue
    buf = m[:size]
    if struct.unpack_from("<I", m, 0)[0] != s0:
        continue
    last = s0
    fr = i76tel.decode_frame(h, buf[off:off + h.frame_size])
    frames += 1
    dts.append(fr["dt"]); steps += max(fr["step_count"], 0)
    if fr["player_present"]:
        pos = (fr["pos_0"], fr["pos_1"], fr["pos_2"])
        if prev_pos is not None and fr["speed"] > 1.0:
            moving += 1
            if pos == prev_pos: still += 1
        prev_pos = pos
elapsed = time.time() - t0
if not dts:
    sys.exit("no frames (telemetry off or no mission)")
mean = sum(dts) / len(dts); sd = math.sqrt(sum((d - mean) ** 2 for d in dts) / len(dts))
srt = sorted(dts); p99 = srt[int(0.99 * (len(srt) - 1))]
bins = {}
for d in dts:
    k = round(d * 1000); bins[k] = bins.get(k, 0) + 1
top = sorted(bins.items(), key=lambda kv: -kv[1])[:3]
print("%s%d frames in %.1f s = %.1f fps | dt mean %.2f ms sd %.2f p99 %.2f | bins(ms:n) %s | steps %.1f/s | motionless %d/%d moving frames (%.1f%%) | speed %.1f m/s" % (
    (label + ": ") if label else "", frames, elapsed, frames / elapsed, mean * 1000, sd * 1000, p99 * 1000,
    " ".join("%d:%d" % kv for kv in top), steps / elapsed, still, moving, 100.0 * still / max(moving, 1), fr["speed"]))
