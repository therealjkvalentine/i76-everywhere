"""phase_stats.py - one soak phase: frame times from Local\\I76Telemetry plus the terrain vertex count and camera mode
read from the game's memory, over N seconds.

    python phase_stats.py <pid> <seconds> <label>

Prints one line:
  <label>: <frames> frames <fps> fps | dt mean <ms> p99 <ms> max <ms> | verts peak <n> (<pct>% of 32767) | cam <modes> | alive|DIED

- verts = [0x6442ec], the per-frame transformed-terrain-vertex count (reset to 0 by renderer_QueueTerrain 0x490a00 each
  frame; renderer_SplitTerrainEdge 0x4918f0 stores it as an int16 -> 32,767 is the crash ceiling,
  i76-everywhere docs/records/FARCLIP-CAMERA-CRASH.md). Sampled read-only, as fast as the loop runs (~1 kHz).
- cam = camera_mode 0x4c2728 (0 cockpit, 1 hood F6, 2 binoculars B), the set of values seen: proves the view key landed.
- nodes = [0x6543b8] - [0x654390]: the depth-bucket span-node pool (0x490470 takes one 16-byte node per 1 m bucket a
  record spans; 0x1f400 B = 8,000 nodes, unbounded, NOT enlarged by I76_FAR_CLIP or I76_CLUTTER_DIST). Overflow =
  CRASH write at exe+0x9051B (found by this soak, 2026-10-03). records = [0x6543c0] - [0x654398], the draw-record pool.
- frames = the proxy frame counter range of the phase (matches the frame number in a proxy CRASH line).
- Frames are counted only when the telemetry seq advances (a stale block left by a dead game counts nothing).
"""
import ctypes, ctypes.wintypes as wt, math, mmap, struct, sys, time
sys.path.insert(0, r"C:\Users\james\i76-everywhere\tools\telemetry")
import i76tel

pid = int(sys.argv[1]); secs = float(sys.argv[2]); label = sys.argv[3] if len(sys.argv) > 3 else "phase"
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype = wt.HANDLE
k32.ReadProcessMemory.argtypes = [wt.HANDLE, wt.LPCVOID, wt.LPVOID, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.GetExitCodeProcess.argtypes = [wt.HANDLE, ctypes.POINTER(wt.DWORD)]
hp = k32.OpenProcess(0x0410 | 0x1000, False, pid)   # VM_READ | QUERY_INFORMATION | QUERY_LIMITED
buf4 = ctypes.c_uint32(); got = ctypes.c_size_t()


def rd(addr):
    if not hp or not k32.ReadProcessMemory(hp, addr, ctypes.byref(buf4), 4, ctypes.byref(got)):
        return None
    return buf4.value


def alive():
    code = wt.DWORD()
    return bool(hp) and k32.GetExitCodeProcess(hp, ctypes.byref(code)) and code.value == 259


h = i76tel.Header()
size = h.structs["i76tel_shm_t"][1]; off = h.offset("i76tel_shm_t", "frame")
try:
    m = mmap.mmap(-1, size, tagname=h.consts["I76TEL_SHM_NAME"])
except Exception:
    m = None
last = None; dts = []; vpeak = 0; cams = {}; died = False; f0 = f1 = None
nbase = rd(0x654390); npeak = 0; NCAP = 0x1f400          # depth-bucket span nodes (16 B), pool 0x1f400 B (push at 0x48f9d6)
rbase = rd(0x654398); rpeak = 0; RCAP = rd(0x48f9b6) or 0x5a550   # draw records; size = the push imm at 0x48f9b5 (clutter patches it)
t0 = time.time(); deadline = t0 + secs
while time.time() < deadline:
    if not alive():
        died = True; break
    v = rd(0x6442ec)
    if v is not None and v < 0x7fffffff:
        vpeak = max(vpeak, v)
    if nbase:
        n = rd(0x6543b8)
        if n is not None and nbase <= n < nbase + 0x100000:
            npeak = max(npeak, n - nbase)
    if rbase:
        r = rd(0x6543c0)
        if r is not None and rbase <= r < rbase + 0x1000000:
            rpeak = max(rpeak, r - rbase)
    c = rd(0x4c2728)
    if c is not None:
        cams[c] = cams.get(c, 0) + 1
    if m is not None:
        s0 = struct.unpack_from("<I", m, 0)[0]
        if s0 and not (s0 & 1) and s0 != last:
            b = m[:size]
            if struct.unpack_from("<I", m, 0)[0] == s0:
                last = s0
                fr = i76tel.decode_frame(h, b[off:off + h.frame_size])
                dts.append(fr["dt"])
                if f0 is None: f0 = fr["proxy_frame"]
                f1 = fr["proxy_frame"]
    time.sleep(0.0005)
elapsed = time.time() - t0
camtxt = ",".join("%d:%d%%" % (k, round(100.0 * n / max(sum(cams.values()), 1))) for k, n in sorted(cams.items()))
if dts:
    mean = sum(dts) / len(dts); srt = sorted(dts); p99 = srt[int(0.99 * (len(srt) - 1))]
    ft = "%d frames %.1f fps | dt mean %.2f p99 %.2f max %.2f ms" % (len(dts), len(dts) / elapsed, mean * 1000, p99 * 1000, srt[-1] * 1000)
else:
    ft = "0 frames"
print("%s: %s | verts peak %d (%.0f%% of 32767) | nodes peak %d (%.0f%% of %d B) | records peak %d (%.0f%% of %d B) | cam %s | frames %s-%s | %s" % (
    label, ft, vpeak, 100.0 * vpeak / 32767, npeak, 100.0 * npeak / NCAP, NCAP, rpeak, 100.0 * rpeak / max(RCAP, 1), RCAP,
    camtxt or "-", f0, f1, "DIED" if died else "alive"))
