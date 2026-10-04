"""modules32.py - list the 32-bit modules of a WOW64 process (name, base, size), and optionally map addresses.

Get-Process .Modules from 64-bit PowerShell shows only the 64-bit side of a WOW64 process, which is why
where-spinning.ps1 reports 'UNKNOWN' for every DLL. This uses EnumProcessModulesEx(LIST_MODULES_32BIT).

    python modules32.py                 # the running i76 process
    python modules32.py 0x7701352C 0x6938F60C   # also map these addresses to module+offset
"""
import ctypes, ctypes.wintypes as wt, sys

k32 = ctypes.WinDLL("kernel32", use_last_error=True); psapi = ctypes.WinDLL("psapi")
LIST_MODULES_32BIT = 1

class MODULEINFO(ctypes.Structure):
    _fields_ = [("lpBaseOfDll", ctypes.c_void_p), ("SizeOfImage", wt.DWORD), ("EntryPoint", ctypes.c_void_p)]

def find_pid(prefix="i76"):
    arr = (wt.DWORD * 4096)(); got = wt.DWORD()
    psapi.EnumProcesses(arr, ctypes.sizeof(arr), ctypes.byref(got))
    for pid in arr[:got.value // 4]:
        h = k32.OpenProcess(0x1000, False, pid)
        if not h: continue
        buf = ctypes.create_unicode_buffer(1024); n = wt.DWORD(1024)
        ok = k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)); k32.CloseHandle(h)
        if ok and buf.value.lower().rsplit("\\", 1)[-1].startswith(prefix) and "wheel" not in buf.value.lower():
            return pid
    sys.exit("no i76 process")

def modules(pid):
    h = k32.OpenProcess(0x0410, False, pid)                      # QUERY_INFORMATION | VM_READ
    if not h: sys.exit("OpenProcess failed %d" % ctypes.get_last_error())
    mods = (wt.HMODULE * 1024)(); need = wt.DWORD()
    if not psapi.EnumProcessModulesEx(h, mods, ctypes.sizeof(mods), ctypes.byref(need), LIST_MODULES_32BIT):
        sys.exit("EnumProcessModulesEx failed %d" % ctypes.get_last_error())
    out = []
    for i in range(need.value // ctypes.sizeof(wt.HMODULE)):
        name = ctypes.create_unicode_buffer(260)
        psapi.GetModuleBaseNameW(h, mods[i], name, 260)
        mi = MODULEINFO()
        psapi.GetModuleInformation(h, mods[i], ctypes.byref(mi), ctypes.sizeof(mi))
        out.append((name.value, mi.lpBaseOfDll or 0, mi.SizeOfImage))
    k32.CloseHandle(h)
    return sorted(out, key=lambda m: m[1])

if __name__ == "__main__":
    pid = find_pid()
    ms = modules(pid)
    print("pid %d, %d 32-bit modules" % (pid, len(ms)))
    for n, b, s in ms:
        print("  %-28s 0x%08X  0x%X" % (n, b, s))
    for a in sys.argv[1:]:
        v = int(a, 16)
        hit = [m for m in ms if m[1] <= v < m[1] + m[2]]
        print("%s -> %s" % (a, "%s+0x%X" % (hit[0][0], v - hit[0][1]) if hit else "unmapped"))
