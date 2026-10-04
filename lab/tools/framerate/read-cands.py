"""read-cands.py - print live value + stored per-frame rate for the current sky-candidates set.
Read-only. Used to identify an animation by its value shape (e.g. a radar sweep is an angle
that cycles 0..2pi at a steady rate) without freeze-testing every one."""
import json, os, struct, ctypes, ctypes.wintypes as w, subprocess, math

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
CAND = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    '..', '..', 'captures', 'sky', 'sky-candidates.json')


def pid():
    out = subprocess.check_output(['tasklist', '/FI', 'IMAGENAME eq i76.exe', '/FO', 'CSV'],
                                  text=True, errors='ignore')
    for ln in out.splitlines()[1:]:
        p = [x.strip('"') for x in ln.split('","')]
        if len(p) > 1 and p[0].lower() == 'i76.exe':
            return int(p[1])
    raise SystemExit('i76.exe not running')


h = k32.OpenProcess(0x0410, False, pid())


def rf(a):
    b = ctypes.create_string_buffer(4)
    g = ctypes.c_size_t(0)
    k32.ReadProcessMemory(h, ctypes.c_void_p(a), b, 4, ctypes.byref(g))
    return struct.unpack('<f', b.raw)[0] if g.value == 4 else None


cands = sorted(json.load(open(CAND))['cands'])
print('idx  addr           value         deg(if<=2pi)   per_frame_rate    deg/frame')
for i, (a, rate) in enumerate(cands):
    a = int(a)
    v = rf(a)
    if v is None:
        continue
    deg = ('%.1f' % math.degrees(v)) if abs(v) <= 7 else '-'
    dpf = ('%.3f' % math.degrees(rate)) if abs(rate) < 10 else '-'
    print('%2d  0x%09X  %12.4f  %12s  %14.5f  %9s' % (i, a, v, deg, rate, dpf))
