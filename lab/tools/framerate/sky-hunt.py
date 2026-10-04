"""sky-hunt.py - find the sky animation driver with a human watching the screen.

Every static-range candidate was freeze-tested and the sky never blinked (two passes,
user-observed), so the driver lives where cross-run scans cannot see: the heap or the renderer
DLL's data. Both are reachable in a SINGLE run, which is all a freeze test needs.

  scan    snapshot all writable memory 3 times, keep float32 values that advance LINEARLY WITH
          THE FRAME COUNT (three points, consistent per-frame step) -> candidates.json
  freeze  non-adaptive group test: ceil(log2(N)) rounds; round b freezes every candidate whose
          index has bit b set, 5 s hold, 3 s gap. The observer notes WHICH ROUNDS the sky
          stopped; that yes/no pattern read as binary IS the candidate's index. One pass, no
          feedback needed between rounds. (If several linked values drive the sky the pattern is
          an OR of their indices - still narrows to a handful for a quick adaptive follow-up.)
  test    freeze one address (or a comma list) for N seconds - the confirmation step.

The observer should watch ONLY the cloud drift: with half the candidate set frozen each round,
other things (HUD timers, effects) may stutter. That is expected and irrelevant.

    python sky-hunt.py scan
    python sky-hunt.py freeze
    python sky-hunt.py test 0xADDR[,0xADDR2] 8
"""
import ctypes, ctypes.wintypes as w, struct, sys, os, json, time, subprocess, math

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
HERE = os.path.dirname(os.path.abspath(__file__))
CAND = os.path.join(HERE, '..', '..', 'captures', 'sky', 'sky-candidates.json')
FRAME_COUNTER = 0x5A7E1C


class MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", w.DWORD), ("RegionSize", ctypes.c_size_t),
                ("State", w.DWORD), ("Protect", w.DWORD), ("Type", w.DWORD)]


def find_pid():
    out = subprocess.check_output(['tasklist', '/FI', 'IMAGENAME eq i76.exe', '/FO', 'CSV'],
                                  text=True, errors='ignore')
    for line in out.splitlines()[1:]:
        parts = [p.strip('"') for p in line.split('","')]
        if len(parts) > 1 and parts[0].lower() == 'i76.exe':
            return int(parts[1])
    raise SystemExit('i76.exe not running')


class Proc:
    def __init__(self):
        self.h = k32.OpenProcess(0x0438, False, find_pid())   # QUERY|VM_READ|VM_WRITE|VM_OPERATION
        if not self.h:
            raise SystemExit('OpenProcess failed (%d)' % ctypes.get_last_error())

    def read(self, a, n):
        b = ctypes.create_string_buffer(n)
        got = ctypes.c_size_t(0)
        k32.ReadProcessMemory(self.h, ctypes.c_void_p(a), b, n, ctypes.byref(got))
        return b.raw[:got.value]

    def u32(self, a):
        d = self.read(a, 4)
        return struct.unpack('<I', d)[0] if len(d) == 4 else None

    def write4(self, a, raw):
        got = ctypes.c_size_t(0)
        k32.WriteProcessMemory(self.h, ctypes.c_void_p(a), raw, 4, ctypes.byref(got))

    def regions(self):
        addr, out, mbi = 0, [], MBI()
        RW = (0x04, 0x40)          # PAGE_READWRITE, PAGE_EXECUTE_READWRITE
        while addr < 0x7FFF0000:
            if not k32.VirtualQueryEx(self.h, ctypes.c_void_p(addr), ctypes.byref(mbi),
                                      ctypes.sizeof(mbi)):
                break
            size = mbi.RegionSize or 0x1000
            if mbi.State == 0x1000 and mbi.Protect in RW and size <= 64 * 1024 * 1024:
                out.append((mbi.BaseAddress or 0, size))
            addr = (mbi.BaseAddress or 0) + size
        return out


def snap(p, regs):
    frames = p.u32(FRAME_COUNTER)
    data = {}
    for base, size in regs:
        d = p.read(base, size)
        if d:
            data[base] = d
    return frames, data


def scan():
    p = Proc()
    regs = p.regions()
    total = sum(s for _, s in regs)
    print('snapshotting %d regions, %.0f MB, three passes...' % (len(regs), total / 1e6))
    fA, A = snap(p, regs)
    time.sleep(1.2)
    fB, B = snap(p, regs)
    time.sleep(1.2)
    fC, C = snap(p, regs)
    dfab, dfbc = fB - fA, fC - fB
    print('frames: %d -> %d -> %d  (deltas %d, %d)' % (fA, fB, fC, dfab, dfbc))
    if dfab < 5 or dfbc < 5:
        raise SystemExit('game not advancing - is it focused/unpaused?')

    def linear(va, vb, vc):
        """True if va->vb->vc is a steady advance (same sign, consistent per-frame step)."""
        d1, d2 = vb - va, vc - vb
        if d1 == 0 or d2 == 0 or (d1 > 0) != (d2 > 0):
            return None
        s1, s2 = d1 / dfab, d2 / dfbc
        r = s2 / s1
        if 0.8 <= r <= 1.25:
            return s1
        return None

    cands = []
    for base, da in A.items():
        db, dc = B.get(base), C.get(base)
        if db is None or dc is None:
            continue
        n = min(len(da), len(db), len(dc)) & ~3
        for o in range(0, n, 4):
            wa = da[o:o + 4]
            wb = db[o:o + 4]
            if wa == wb:
                continue
            wc = dc[o:o + 4]
            if wb == wc:
                continue
            # FLOAT interpretation
            fa = struct.unpack('<f', wa)[0]
            fb = struct.unpack('<f', wb)[0]
            fc = struct.unpack('<f', wc)[0]
            if (math.isfinite(fa) and math.isfinite(fb) and math.isfinite(fc)
                    and abs(fa) <= 1e7 and abs(fc) <= 1e7):
                s = linear(fa, fb, fc)
                if s is not None and 1e-5 <= abs(s) <= 50:
                    cands.append((base + o, s, 'f'))
                    continue
            # INT interpretation (texel/pixel scroll offsets, fixed-point counters).
            # Skip pointer-looking values (huge magnitude) so we do not flag heap churn.
            ia = struct.unpack('<i', wa)[0]
            ib = struct.unpack('<i', wb)[0]
            ic = struct.unpack('<i', wc)[0]
            if abs(ia) < 5_000_000 and abs(ic) < 5_000_000:
                s = linear(ia, ib, ic)
                if s is not None and 0.1 <= abs(s) <= 5000:
                    cands.append((base + o, s, 'i'))
    os.makedirs(os.path.dirname(CAND), exist_ok=True)
    json.dump({'cands': [[a, s, k] for a, s, k in cands]}, open(CAND, 'w'))
    nf = sum(1 for _, _, k in cands if k == 'f')
    ni = len(cands) - nf
    print('%d values advance linearly with the frame count (%d float, %d int) -> sky-candidates.json'
          % (len(cands), nf, ni))
    rounds = max(1, math.ceil(math.log2(max(2, len(cands)))))
    print('group test needs %d rounds (%.0f s with the observer watching)' % (rounds, rounds * 8))


def freeze_set(p, addrs_vals, seconds):
    end = time.time() + seconds
    while time.time() < end:
        for a, raw in addrs_vals:
            p.write4(a, raw)


def alive(p):
    f0 = p.u32(FRAME_COUNTER)
    if f0 is None:
        return False
    time.sleep(0.25)
    f1 = p.u32(FRAME_COUNTER)
    return f1 is not None and f1 > f0


def freeze():
    """Region-ordered GROUP pass. A bit-pattern pass froze 548 arbitrary values at once and
    killed the game in round 1 - half of everything includes something load-bearing. Groups of
    ~70, contiguous in address order (so a group stays within one subsystem's data), with a
    liveness check after every round so a crash is attributed to its group instead of silently
    zeroing the rest of the pass."""
    cands = sorted(json.load(open(CAND))['cands'])
    n = len(cands)
    if not n:
        raise SystemExit('no candidates - run scan first')
    gsize = int(sys.argv[2]) if len(sys.argv) > 2 else 70
    groups = [cands[i:i + gsize] for i in range(0, n, gsize)]
    p = Proc()
    if not alive(p):
        raise SystemExit('game is not running/advancing - relaunch and rescan first')
    print('%d candidates in %d groups of <=%d. WATCH ONLY THE CLOUD DRIFT.' % (n, len(groups), gsize))
    print('note the group numbers where the sky STOPS or SLOWS.\n')
    time.sleep(4)
    for gi, g in enumerate(groups):
        av = []
        for a, _ in g:
            d = p.read(int(a), 4)
            if len(d) == 4:
                av.append((int(a), d))
        lo, hi = hex(int(g[0][0])), hex(int(g[-1][0]))
        print('[%s] >>> GROUP %d/%d  (%d values, %s..%s, 4s)'
              % (time.strftime('%H:%M:%S'), gi + 1, len(groups), len(av), lo, hi), flush=True)
        freeze_set(p, av, 4.0)
        print('[%s]     released' % time.strftime('%H:%M:%S'), flush=True)
        time.sleep(2)
        if not alive(p):
            print('*** GAME DIED during group %d (%s..%s) - that group contains fatal state.'
                  % (gi + 1, lo, hi))
            print('    relaunch, rescan, and rerun with that range excluded or subdivided.')
            return
    print('\ndone. reply with the group numbers where the sky stopped (e.g. "7").')


def test():
    addrs = [int(x, 16) for x in sys.argv[2].split(',')]
    secs = float(sys.argv[3]) if len(sys.argv) > 3 else 8.0
    p = Proc()
    av = [(a, p.read(a, 4)) for a in addrs]
    print('freezing %s for %.0fs - watch the sky' % (','.join(hex(a) for a in addrs), secs))
    freeze_set(p, av, secs)
    print('released')


def rng():
    """Freeze candidates[i:j] for one long uninterrupted hold - the binary-search step.
    No group numbers to read: the observer just says stopped / still-moving.
        python sky-hunt.py rng I J [SECONDS]"""
    cands = sorted(json.load(open(CAND))['cands'])
    i, j = int(sys.argv[2]), int(sys.argv[3])
    secs = float(sys.argv[4]) if len(sys.argv) > 4 else 8.0
    sub = cands[i:j]
    p = Proc()
    av = [(int(a), p.read(int(a), 4)) for a, _ in sub if len(p.read(int(a), 4)) == 4]
    print('candidates[%d:%d] = %d values, %s..%s'
          % (i, j, len(av), hex(int(sub[0][0])), hex(int(sub[-1][0]))))
    print('FREEZING for %.0fs - watch the sky, then say stopped / still-moving' % secs, flush=True)
    freeze_set(p, av, secs)
    print('released', flush=True)
    if not alive(p):
        print('*** game died - this range holds fatal state; subdivide it')


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'scan':
        scan()
    elif cmd == 'freeze':
        freeze()
    elif cmd == 'rng':
        rng()
    elif cmd == 'test':
        test()
    else:
        print(__doc__)
