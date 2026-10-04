"""stackscan.py - for a hung 32-bit game: every thread's EIP and the return addresses on its stack, mapped to
module+offset (WOW64 context + EnumProcessModulesEx 32-bit). A poor man's `k` without a debugger: a stack dword
counts as a return address when it points into a module and the bytes before it decode as a call (E8 rel32,
FF /2 forms). Read-only apart from the brief suspend.

    python stackscan.py [--depth 600] [--threads all|main]
"""
import ctypes, ctypes.wintypes as wt, sys
sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import modules32

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
depth = int(sys.argv[sys.argv.index("--depth") + 1]) if "--depth" in sys.argv else 600
only_main = "--threads" in sys.argv and sys.argv[sys.argv.index("--threads") + 1] == "main"

class THREADENTRY32(ctypes.Structure):
    _fields_ = [("dwSize", wt.DWORD), ("cntUsage", wt.DWORD), ("th32ThreadID", wt.DWORD), ("th32OwnerProcessID", wt.DWORD),
                ("tpBasePri", wt.LONG), ("tpDeltaPri", wt.LONG), ("dwFlags", wt.DWORD)]

pid = modules32.find_pid()
mods = modules32.modules(pid)
hp = k32.OpenProcess(0x0410, False, pid)

def rd(a, n):
    b = ctypes.create_string_buffer(n); got = ctypes.c_size_t()
    return b.raw if k32.ReadProcessMemory(hp, ctypes.c_void_p(a), b, n, ctypes.byref(got)) and got.value == n else None

def where(a):
    for n, b, s in mods:
        if b <= a < b + s:
            return "%s+0x%X" % (n, a - b)
    return None

def is_ret(a):
    b = rd(a - 7, 7)
    if not b: return False
    return b[2] == 0xE8 or (b[5] == 0xFF and (b[6] >> 3) & 7 == 2) or (b[4] == 0xFF and (b[5] >> 3) & 7 == 2) or \
           (b[1] == 0xFF and (b[2] >> 3) & 7 == 2) or (b[0] == 0xFF and b[1] in (0x15, 0x14, 0x94))

snap = k32.CreateToolhelp32Snapshot(4, 0)
te = THREADENTRY32(); te.dwSize = ctypes.sizeof(te)
tids = []
ok = k32.Thread32First(snap, ctypes.byref(te))
while ok:
    if te.th32OwnerProcessID == pid: tids.append(te.th32ThreadID)
    ok = k32.Thread32Next(snap, ctypes.byref(te))
k32.CloseHandle(snap)
print("pid %d, %d threads" % (pid, len(tids)))
for i, tid in enumerate(tids):
    if only_main and i: break
    ht = k32.OpenThread(0x004A, False, tid)                 # SUSPEND_RESUME | GET_CONTEXT | QUERY_INFORMATION
    if not ht: continue
    ctx = ctypes.create_string_buffer(716); ctypes.memmove(ctx, (0x10007).to_bytes(4, "little"), 4)   # WOW64_CONTEXT_FULL
    k32.Wow64SuspendThread(ht)
    got = k32.Wow64GetThreadContext(ht, ctx)
    eip = int.from_bytes(ctx.raw[0xB8:0xBC], "little"); esp = int.from_bytes(ctx.raw[0xC4:0xC8], "little")
    stack = rd(esp, depth * 4) if got else None
    k32.ResumeThread(ht); k32.CloseHandle(ht)
    if not got or not stack:
        continue
    frames = []
    for j in range(0, len(stack), 4):
        v = int.from_bytes(stack[j:j + 4], "little")
        w = where(v)
        if w and is_ret(v):
            frames.append(w)
    # collapse runs inside system DLLs for readability but keep order
    print("thread %d%s: eip %s | %s" % (tid, " (first)" if i == 0 else "", where(eip) or hex(eip), " <- ".join(frames[:28])))
