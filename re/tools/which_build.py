#!/usr/bin/env python3
r"""which_build.py - H0: which build is live? (method doc section 4.5, gate H0)

Reads a running process's image (or, offline, a file) and diffs .text 0x401000-0x4bbe55 and
.rdata 0x4bc000-0x4c1788 against the pristine i76.exe bytes (md5 9a232dcc2c164648cff20c414c1f9698),
reports every differing range with hashes, the import DLL names the live image actually resolved
(u32x / WINMM / WIN32 / USER32), the i76shell.dll timestamp, the command line (WMI Win32_Process),
SessionId vs the console session, the dgVoodoo.conf hash (+ Resolution / FPSLimit), every Z*.DLL
and wrapper md5, and emits a JSON stamp usable as captures\<id>\manifest.json 'build'.

    python tools\which_build.py --name i76.exe            live process by image name
    python tools\which_build.py --pid 1234                 live process by pid
    python tools\which_build.py --file <exe>               offline: diff a file's image against the pristine file
    python tools\which_build.py --selftest                 offline unit test (pristine vs patched i76.exe bytes)
    python tools\which_build.py --gen-diffs                binaries\diff-9a232dcc-vs-<md5>.tsv for the known patched builds
    python tools\which_build.py --diff-file <exe>          the same for one file
    python tools\which_build.py --classify 0x49c920,0x4059de   inside/outside a differing cluster per build (build-shifted)
    options: --ref <pristine file> --game-dir <dir> --allowlist <json|none> --base 0x400000
             --out <manifest.json> (writes/merges the 'build' block) --stamp <class> --json (print the stamp)
             --hooks-json <file> (G-ATTEST fired counters written by the Frida driver; default hooks.json beside --out)

Exit code: 0 = H0 pass (.text/.text-tail/.rdata identical or allowlisted), 1 = differs, 2 = error.
Address classes: every VA printed here is class init/iat (image bytes); .data-init differences are
runtime writes to initialised globals and are reported as data, never as tampering. The IAT
0x4bc000-0x4bc404 (class iat) is its own region (`.rdata-iat`), outside the H0 byte compare, and is
compared by import NAMES instead (live thunk -> containing module vs the descriptor DLL, `iat_by_name`).
0.2 (p2-poke-snapshot-h0): section-aware dgVoodoo.conf (G-CONF), hook fired counters (G-ATTEST),
per-build diff signatures with 64-B clusters and the build-shifted classifier (FOLDIN section 3 H0).
Needs PROCESS_VM_READ | PROCESS_QUERY_INFORMATION on the target (same user is enough).
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import datetime
import glob
import hashlib
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pe_ident  # noqa: E402

VERSION = "0.2"
PRISTINE_MD5 = "9a232dcc2c164648cff20c414c1f9698"
KNOWN_MD5 = {
    PRISTINE_MD5: "pristine",
    "58d9dec00c18a5383820e77e51850b74": "pristine+i76fix-p1",
    "60abf7bc699da72476128ddce991a3d1": "patched-build-only",   # GOG 2019 AiO build (foldin: aio-60abf7bc)
    "4fabc30303c7a327fbe15be58cb868c5": "patched-build-only",   # lab sandbox i76.exe (foldin: sandbox-4fabc303)
    "6319abf7bf96e32f994fe7609cf99a7a": "patched-build-only",   # portable install (foldin: portable-6319abf7)
}
H0_RUNNABLE = {PRISTINE_MD5, "58d9dec00c18a5383820e77e51850b74"}  # the only md5s H0 accepts (i76poke, launch.ps1)
DEFAULT_REF = r"C:\Users\james\i76-uncap-lab\game\i76.exe.2017galaxy"
DEFAULT_GAME = r"C:\Users\james\i76-uncap-lab\game"
DEFAULT_ALLOWLIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "allowlist.json")
IMAGE_BASE = 0x400000
MAP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BINARIES_DIR = os.path.join(MAP_ROOT, "binaries")
IMPORTS_TSV = os.path.join(MAP_ROOT, "symbols", "imports.tsv")
# The builds whose per-section diff signature is generated into binaries\diff-9a232dcc-vs-<md5>.tsv
# (FOLDIN-REPORT section 3, H0 revision). Tag, path; the md5 is measured, never assumed.
DIFF_BUILDS = [
    ("pristine+p1", r"C:\Users\james\i76-uncap-lab\game\i76_pristine_fix.exe"),
    ("aio", r"C:\Users\james\i76-uncap-lab\game\i76.exe.camorig"),
    ("sandbox", r"C:\Users\james\i76-uncap-lab\game\i76.exe"),
    ("portable", r"C:\Users\james\Downloads\Interstate76-i76-everywhere-portable-20260801\Interstate 76\i76.exe"),
]
CLUSTER_GAP = 64  # bytes between differing runs merged into one cluster (build-shifted range)
# dgVoodoo.conf key ownership (G-CONF). Built-in rows are the four keys the gate names; the rest of the
# table is read from the dgVoodooCpl-written template (%APPDATA%\dgVoodoo\dgVoodoo.conf) when present.
# Source for the built-in rows: dgVoodoo 2.8 conf layout as written by dgVoodooCpl (ScalingMode under
# [General], Resolution/EnableInactiveAppState under [Glide], Resolution under [DirectX]) and the
# FPSLimit key documented under [GeneralExt]; AGENTS.md (i76-everywhere) records the weeks-long
# EnableInactiveAppState-in-[General] misplacement.
CONF_KEY_OWNERS = {
    "ScalingMode": ["General"],
    "FPSLimit": ["GeneralExt"],
    "Resolution": ["Glide", "DirectX"],
    "EnableInactiveAppState": ["Glide", "DirectX"],
}
CONF_REPORT_KEYS = ("EnableInactiveAppState", "FPSLimit", "Resolution", "ScalingMode")
CONF_TEMPLATE = os.path.join(os.environ.get("APPDATA", ""), "dgVoodoo", "dgVoodoo.conf")

# name, va_lo, va_hi (exclusive), file_delta (file offset = VA - delta), kind
# VA deltas from the pristine section table (tools\pe_ident.py): .text/.rdata raw follow their VA
# by 0x400c00, .data by 0x401400. (Method doc 2.1 quotes the .rdata/.data deltas as RVA deltas.)
REGIONS = [
    (".text", 0x401000, 0x4bbe55, 0x400c00, "code"),
    (".text-tail", 0x4bbe55, 0x4bc000, 0x400c00, "code-pad"),
    (".rdata-iat", 0x4bc000, 0x4bc404, 0x400c00, "iat"),
    (".rdata", 0x4bc404, 0x4c1788, 0x400c00, "rodata"),
    (".rdata-tail", 0x4c1788, 0x4c1800, 0x400c00, "rodata-pad"),
    (".data-init", 0x4c2000, 0x501800, 0x401400, "data"),
]
H0_REGIONS = (".text", ".text-tail", ".rdata", ".rdata-tail")

WRAPPERS = ["DDraw.dll", "D3DImm.dll", "D3D8.dll", "D3D9.dll", "Glide.dll", "Glide2x.dll", "Glide3x.dll",
            "win32.dll", "u32x.dll", "STRLKUP.DLL", "strlkup_orig.dll", "audiere.dll", "i76wheel.exe",
            "winmm.dll", "i76shell.dll", "i76shell.dll.orig", "I76PATCH.DLL", "I76PATCH.DLL.disabled",
            "ANETDLL.DLL", "i7_sfrce.dll", "SMACKW32.DLL", "msvcr90.dll", "msvcp90.dll"]

# ---------------------------------------------------------------- win32
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)
PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400
LIST_MODULES_32BIT = 0x01
LIST_MODULES_ALL = 0x03

k32.OpenProcess.restype = wt.HANDLE
k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
k32.ReadProcessMemory.restype = wt.BOOL
k32.ReadProcessMemory.argtypes = [wt.HANDLE, wt.LPCVOID, wt.LPVOID, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.CloseHandle.argtypes = [wt.HANDLE]
k32.ProcessIdToSessionId.argtypes = [wt.DWORD, ctypes.POINTER(wt.DWORD)]
k32.WTSGetActiveConsoleSessionId.restype = wt.DWORD
k32.IsWow64Process.argtypes = [wt.HANDLE, ctypes.POINTER(wt.BOOL)]
psapi.EnumProcessModulesEx.argtypes = [wt.HANDLE, ctypes.POINTER(wt.HMODULE), wt.DWORD, ctypes.POINTER(wt.DWORD), wt.DWORD]
psapi.GetModuleFileNameExW.argtypes = [wt.HANDLE, wt.HMODULE, wt.LPWSTR, wt.DWORD]
psapi.GetModuleFileNameExW.restype = wt.DWORD
psapi.EnumProcesses.argtypes = [ctypes.POINTER(wt.DWORD), wt.DWORD, ctypes.POINTER(wt.DWORD)]
psapi.GetProcessImageFileNameW.argtypes = [wt.HANDLE, wt.LPWSTR, wt.DWORD]
psapi.GetProcessImageFileNameW.restype = wt.DWORD


class MODULEINFO(ctypes.Structure):
    _fields_ = [("lpBaseOfDll", ctypes.c_void_p), ("SizeOfImage", wt.DWORD), ("EntryPoint", ctypes.c_void_p)]


psapi.GetModuleInformation.argtypes = [wt.HANDLE, wt.HMODULE, ctypes.POINTER(MODULEINFO), wt.DWORD]


def md5b(b):
    return hashlib.md5(b).hexdigest()


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class LiveImage:
    """ReadProcessMemory-backed byte source."""

    def __init__(self, pid):
        self.pid = pid
        self.h = k32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
        if not self.h:
            raise OSError("OpenProcess(%d) failed: win32 error %d" % (pid, ctypes.get_last_error()))
        self.short_reads = []

    def read(self, va, n):
        buf = ctypes.create_string_buffer(n)
        got = ctypes.c_size_t(0)
        ok = k32.ReadProcessMemory(self.h, ctypes.c_void_p(va), buf, n, ctypes.byref(got))
        if not ok or got.value != n:
            # retry page by page so a partially readable region still yields bytes
            out = bytearray()
            off = 0
            while off < n:
                step = min(0x1000 - ((va + off) & 0xfff), n - off)
                b2 = ctypes.create_string_buffer(step)
                g2 = ctypes.c_size_t(0)
                if k32.ReadProcessMemory(self.h, ctypes.c_void_p(va + off), b2, step, ctypes.byref(g2)) and g2.value == step:
                    out += b2.raw
                    off += step
                else:
                    self.short_reads.append({"va": hex(va + off), "wanted": n, "got": off, "err": ctypes.get_last_error()})
                    break
            return bytes(out)
        return buf.raw

    def modules(self):
        arr = (wt.HMODULE * 1024)()
        needed = wt.DWORD(0)
        if not psapi.EnumProcessModulesEx(self.h, arr, ctypes.sizeof(arr), ctypes.byref(needed), LIST_MODULES_ALL):
            raise OSError("EnumProcessModulesEx failed: %d" % ctypes.get_last_error())
        n = min(needed.value // ctypes.sizeof(wt.HMODULE), 1024)
        mods = []
        for i in range(n):
            name = ctypes.create_unicode_buffer(1024)
            psapi.GetModuleFileNameExW(self.h, arr[i], name, 1024)
            mi = MODULEINFO()
            psapi.GetModuleInformation(self.h, arr[i], ctypes.byref(mi), ctypes.sizeof(mi))
            mods.append({"path": name.value, "base": mi.lpBaseOfDll or 0, "size": mi.SizeOfImage})
        return mods

    def is_wow64(self):
        b = wt.BOOL(0)
        k32.IsWow64Process(self.h, ctypes.byref(b))
        return bool(b.value)

    def session_id(self):
        sid = wt.DWORD(0)
        k32.ProcessIdToSessionId(self.pid, ctypes.byref(sid))
        return sid.value

    def close(self):
        k32.CloseHandle(self.h)


class FileImage:
    """Maps a PE file's sections to their VAs so the same region diff runs offline."""

    def __init__(self, path):
        self.path = path
        with open(path, "rb") as f:
            self.raw = f.read()
        self.ident = pe_ident.identity(path)
        self.base = int(self.ident["image_base"], 16)
        self.secs = [(int(s["va"], 16), s["vsize"], int(s["raw_ptr"], 16), s["raw_size"]) for s in self.ident["sections"]]
        first_raw = min(int(s["raw_ptr"], 16) for s in self.ident["sections"])
        self.secs.insert(0, (self.base, first_raw, 0, first_raw))  # PE headers map at the base
        self.short_reads = []

    def read(self, va, n):
        out = bytearray(n)
        for sva, vsize, rptr, rsize in self.secs:
            span = max(vsize, rsize)  # the loader maps the raw bytes even past vsize, up to the page
            lo = max(va, sva)
            hi = min(va + n, sva + span)
            if lo < hi:
                for a in range(lo, hi):
                    off = a - sva
                    out[a - va] = self.raw[rptr + off] if off < rsize else 0
        return bytes(out)


def ranges_from_diff(live, ref, va, gap=8):
    """Coalesced differing ranges: [(va_lo, va_hi_excl, n_diff_bytes)]. Method: numpy != then
    flatnonzero; runs separated by <= gap identical bytes are merged."""
    import numpy as np
    n = min(len(live), len(ref))
    if n == 0:
        return []
    a = np.frombuffer(live[:n], dtype=np.uint8)
    b = np.frombuffer(ref[:n], dtype=np.uint8)
    idx = np.flatnonzero(a != b)
    out = []
    if len(idx) == 0:
        return out
    start = prev = int(idx[0])
    count = 1
    for i in idx[1:]:
        i = int(i)
        if i - prev > gap + 1:
            out.append((va + start, va + prev + 1, count))
            start = i
            count = 0
        prev = i
        count += 1
    out.append((va + start, va + prev + 1, count))
    return out


def load_allowlist(spec):
    if spec is None or spec.lower() == "none":
        return []
    with open(spec, "r", encoding="utf-8") as f:
        d = json.load(f)
    entries = d.get("entries", d) if isinstance(d, dict) else d
    out = []
    for e in entries:
        out.append({"va": int(e["va"], 16) if isinstance(e["va"], str) else e["va"], "len": int(e["len"]),
                    "md5": e.get("md5") or e.get("new_md5"), "why": e.get("why", "")})
    return out


def diff_regions(img, ref_raw, allow):
    """Diff every REGION of img against the pristine file bytes. Returns per-region dicts."""
    results = []
    for name, lo, hi, delta, kind in REGIONS:
        n = hi - lo
        ref = ref_raw[lo - delta: lo - delta + n]
        live = img.read(lo, n)
        r = {"region": name, "va_lo": hex(lo), "va_hi": hex(hi), "bytes": n, "kind": kind,
             "read": len(live), "ref_md5": md5b(ref), "live_md5": md5b(live)}
        if len(live) != n:
            r["verdict"] = "SHORT-READ"
            r["ranges"] = []
            results.append(r)
            continue
        rngs = ranges_from_diff(live, ref, lo)
        rows = []
        n_allow = 0
        n_bytes = 0
        for a, b, cnt in rngs:
            row = {"va_lo": hex(a), "va_hi": hex(b), "len": b - a, "diff_bytes": cnt,
                   "live_md5": md5b(live[a - lo:b - lo]), "ref_md5": md5b(ref[a - lo:b - lo]),
                   "live_hex": live[a - lo:b - lo][:16].hex(), "ref_hex": ref[a - lo:b - lo][:16].hex()}
            n_bytes += cnt
            for e in allow:
                if e["va"] <= a and b <= e["va"] + e["len"]:
                    span = live[e["va"] - lo: e["va"] - lo + e["len"]]
                    if e["md5"] is None or md5b(span) == e["md5"]:
                        row["allowlisted"] = e["why"] or hex(e["va"])
                        n_allow += 1
                    else:
                        row["allowlist_hash_mismatch"] = {"expected": e["md5"], "got": md5b(span)}
                    break
            rows.append(row)
        r["ranges"] = rows
        r["diff_bytes"] = n_bytes
        if kind == "iat":
            live_thunks = [int.from_bytes(live[i:i + 4], "little") for i in range(0, n, 4)]
            r["thunks_nonzero"] = sum(1 for t in live_thunks if t)
            r["thunks_resolved_outside_image"] = sum(1 for t in live_thunks if t and not (IMAGE_BASE <= t < IMAGE_BASE + 0x26b000))
            r["verdict"] = "identical" if not rows else ("resolved-by-loader" if r["thunks_resolved_outside_image"] else "DIFFERS")
        elif kind == "data":
            r["verdict"] = "identical" if not rows else "runtime-writes (data, not tampering)"
        else:
            if not rows:
                r["verdict"] = "identical"
            elif all("allowlisted" in x for x in rows):
                r["verdict"] = "allowlisted"
            else:
                r["verdict"] = "DIFFERS"
        results.append(r)
    return results


def parse_live_imports(img, base):
    """Import descriptor DLL names as the live image holds them (patched builds carry u32x/WINMM)."""
    hdr = img.read(base, 0x1000)
    if len(hdr) < 0x400 or hdr[:2] != b"MZ":
        return {"error": "no MZ header at %s" % hex(base)}
    e_lfanew = int.from_bytes(hdr[0x3c:0x40], "little")
    if hdr[e_lfanew:e_lfanew + 4] != b"PE\0\0":
        return {"error": "no PE signature"}
    opt = e_lfanew + 24
    magic = int.from_bytes(hdr[opt:opt + 2], "little")
    dd = opt + (96 if magic == 0x10b else 112)
    imp_rva = int.from_bytes(hdr[dd + 8: dd + 12], "little")
    imp_size = int.from_bytes(hdr[dd + 12: dd + 16], "little")
    ts = int.from_bytes(hdr[e_lfanew + 8: e_lfanew + 12], "little")
    names = []
    if imp_rva:
        desc = img.read(base + imp_rva, max(imp_size, 20 * 32))
        for i in range(0, len(desc) - 19, 20):
            name_rva = int.from_bytes(desc[i + 12: i + 16], "little")
            if name_rva == 0:
                break
            s = img.read(base + name_rva, 64)
            names.append(s.split(b"\0")[0].decode("latin-1", "replace"))
    return {"import_dir_va": hex(base + imp_rva), "dll_names": names, "pe_timestamp": ts, "pe_timestamp_utc": pe_ident.utc(ts) if ts else None}


def wmi_process(pid):
    try:
        import win32com.client
        svc = win32com.client.GetObject(r"winmgmts:\\.\root\cimv2")
        for p in svc.ExecQuery("SELECT CommandLine, SessionId, ExecutablePath, CreationDate, ParentProcessId FROM Win32_Process WHERE ProcessId = %d" % pid):
            return {"command_line": p.CommandLine, "session_id": p.SessionId, "executable_path": p.ExecutablePath,
                    "creation_date": p.CreationDate, "parent_pid": p.ParentProcessId, "method": "WMI Win32_Process (win32com)"}
        return {"error": "pid %d not found in Win32_Process" % pid, "method": "WMI Win32_Process (win32com)"}
    except Exception as e:  # fall back to PowerShell CIM
        try:
            ps = ("Get-CimInstance Win32_Process -Filter 'ProcessId=%d' | Select-Object CommandLine,SessionId,ExecutablePath,ParentProcessId | ConvertTo-Json -Compress" % pid)
            out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=60).stdout.strip()
            d = json.loads(out) if out else {}
            return {"command_line": d.get("CommandLine"), "session_id": d.get("SessionId"), "executable_path": d.get("ExecutablePath"),
                    "parent_pid": d.get("ParentProcessId"), "method": "WMI Win32_Process (Get-CimInstance); win32com failed: %s" % e}
        except Exception as e2:
            return {"error": "WMI unavailable: %s / %s" % (e, e2)}


def query_session():
    """Parse `query session` (exit code is meaningless: 255/1 on success). Returns rows + verdict."""
    try:
        out = subprocess.run(["query", "session"], capture_output=True, text=True, timeout=30).stdout
    except Exception as e:
        return {"error": str(e), "rows": []}
    rows = []
    for line in out.splitlines()[1:]:
        if not line.strip():
            continue
        current = line.startswith(">")
        parts = line[1:].split()
        if not parts:
            continue
        # columns: SESSIONNAME [USERNAME] ID STATE [TYPE DEVICE]; USERNAME may be absent
        try:
            id_idx = next(i for i, p in enumerate(parts) if p.isdigit())
        except StopIteration:
            continue
        rows.append({"session": parts[0], "user": parts[1] if id_idx == 2 else "", "id": int(parts[id_idx]),
                     "state": parts[id_idx + 1] if id_idx + 1 < len(parts) else "", "current": current})
    console = [r for r in rows if r["session"].lower() == "console"]
    cur = [r for r in rows if r["current"]]
    return {"rows": rows, "raw": out,
            "console_active": bool(console and console[0]["state"].lower() == "active"),
            "console_id": console[0]["id"] if console else None,
            "current_session": cur[0]["session"] if cur else None,
            "current_is_console": bool(cur and cur[0]["session"].lower() == "console"),
            "rdp_active": any(r["session"].lower().startswith("rdp-tcp#") and r["state"].lower() == "active" for r in rows)}


def parse_conf_sections(text):
    """[(section, key, value, line_no)] for every `key = value` line; section None before the first header."""
    sec = None
    rows = []
    for i, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if not s or s.startswith(";") or s.startswith("#"):
            continue
        m = re.match(r"^\[(.+?)\]", s)
        if m:
            sec = m.group(1)
            continue
        m = re.match(r"^([A-Za-z0-9_]+)\s*=\s*(.*?)\s*$", s)
        if m:
            rows.append((sec, m.group(1), m.group(2), i))
    return rows


def conf_owner_table(template=CONF_TEMPLATE):
    """{key: [owning sections]} = built-in rows + every key of the dgVoodooCpl-written template."""
    owners = {k: list(v) for k, v in CONF_KEY_OWNERS.items()}
    src = {"builtin_keys": sorted(CONF_KEY_OWNERS), "template": None}
    if template and os.path.exists(template):
        try:
            with open(template, "rb") as f:
                rows = parse_conf_sections(f.read().decode("utf-8", "replace"))
            n = 0
            for sec, key, _v, _ln in rows:
                if sec is None:
                    continue
                lst = owners.setdefault(key, [])
                if sec not in lst:
                    lst.append(sec)
                    n += 1
            src["template"] = {"path": template, "keys_added": n, "md5": pe_ident.hashes(template)[0]}
        except OSError as e:
            src["template"] = {"path": template, "error": str(e)}
    return owners, src


def dgvoodoo_conf(game_dir, template=CONF_TEMPLATE):
    """G-CONF: section-aware parse. `effective[section][key]` = last value inside that section (what
    dgVoodoo reads); `misplaced` = a key found in a section that does not own it (a manifest warning);
    `report` = the four gate keys per owning section, 'absent' when the section does not set them."""
    p = os.path.join(game_dir, "dgVoodoo.conf")
    if not os.path.exists(p):
        return {"present": False, "path": p}
    with open(p, "rb") as f:
        raw = f.read()
    rows = parse_conf_sections(raw.decode("utf-8", "replace"))
    owners, owner_src = conf_owner_table(template)
    effective = {}
    misplaced = []
    duplicates = []
    for sec, key, val, ln in rows:
        secname = sec if sec is not None else "(preamble)"
        d = effective.setdefault(secname, {})
        if key in d:
            duplicates.append({"section": secname, "key": key, "line": ln, "previous": d[key], "value": val})
        d[key] = val
        own = owners.get(key)
        if sec is not None and own and sec not in own:
            misplaced.append({"section": secname, "key": key, "value": val, "line": ln, "owners": own,
                              "warning": "key outside its owning section: dgVoodoo ignores it here (G-CONF)"})
    report = {}
    for key in CONF_REPORT_KEYS:
        for sec in owners.get(key, []):
            report["%s.%s" % (sec, key)] = effective.get(sec, {}).get(key, "absent")
    # legacy flat view kept for older readers of the manifest
    keys = {"%s.%s" % (sec, k): v for sec, kv in effective.items() for k, v in kv.items()
            if k in ("Resolution", "FPSLimit", "Windowed", "FullScreenMode", "Antialiasing", "EnableInactiveAppState", "ScalingMode")}
    return {"present": True, "path": p, "sha256": hashlib.sha256(raw).hexdigest(), "md5": md5b(raw),
            "mtime_utc": pe_ident.utc(os.stat(p).st_mtime), "keys": keys,
            "sections": sorted(effective), "effective": report, "effective_all": effective,
            "misplaced": misplaced, "duplicates_in_section": duplicates,
            "owner_table_source": owner_src, "method": "parse_conf_sections: last `key = value` per [section] wins; ownership from CONF_KEY_OWNERS + the Cpl template"}


def read_hooks_json(path):
    """G-ATTEST: fired-counter fields written by a Frida driver (tools\\snapshot.py --pump writes
    captures\\<id>\\hooks.json as {"tool", "time_utc", "counters": {name: fired}, ...}). A counter of 0
    voids the capture; absence is reported as unmeasured, never as pass."""
    if not path:
        return {"present": False, "attest": "unmeasured (no hooks json)"}
    if not os.path.exists(path):
        return {"present": False, "path": path, "attest": "unmeasured (hooks json absent)"}
    try:
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError) as e:
        return {"present": True, "path": path, "error": str(e), "attest": "unmeasured (unparseable)"}
    counters = d.get("counters", {}) if isinstance(d, dict) else {}
    zero = sorted(k for k, v in counters.items() if not v)
    return {"present": True, "path": path, "tool": d.get("tool") if isinstance(d, dict) else None,
            "time_utc": d.get("time_utc") if isinstance(d, dict) else None, "counters": counters,
            "zero_counters": zero,
            "attest": ("void (counter 0: %s)" % ", ".join(zero)) if zero else ("pass (%d counters > 0)" % len(counters) if counters else "unmeasured (no counters)")}


def load_iat_slots(path=IMPORTS_TSV):
    """{slot_va: (dll, name)} from symbols\\imports.tsv (class iat)."""
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 3 or not parts[0].startswith("0x"):
                continue
            try:
                out[int(parts[0], 16)] = (parts[1], parts[2])
            except ValueError:
                pass
    return out


def iat_by_name(img, modules, slots=None):
    """Compare the IAT by import NAMES (console-smoke follow-up): for every slot in imports.tsv the
    live thunk is resolved to the loaded module that contains it and compared with the descriptor's
    DLL name. A USER32 slot resolving into u32x.dll is 'redirected', not tampering; a thunk inside no
    module is 'unresolved' (file image / fake target)."""
    slots = slots if slots is not None else load_iat_slots()
    if not slots:
        return {"method": "imports.tsv absent", "slots": 0}
    mods = sorted(((m["base"], m["base"] + m["size"], os.path.basename(m["path"]).lower()) for m in modules if m["base"]), key=lambda t: t[0])
    lo = min(slots)
    hi = max(slots) + 4
    raw = img.read(lo, hi - lo)
    per_dll = {}
    redirected = []
    unresolved = 0
    for va, (dll, name) in sorted(slots.items()):
        off = va - lo
        if off + 4 > len(raw):
            unresolved += 1
            continue
        thunk = int.from_bytes(raw[off:off + 4], "little")
        owner = None
        for b, e, n in mods:
            if b <= thunk < e:
                owner = n
                break
        d = per_dll.setdefault(dll.lower(), {"slots": 0, "same_module": 0, "other_module": 0, "unresolved": 0})
        d["slots"] += 1
        if owner is None:
            d["unresolved"] += 1
            unresolved += 1
        elif owner == dll.lower():
            d["same_module"] += 1
        else:
            d["other_module"] += 1
            redirected.append({"slot": hex(va), "import": "%s!%s" % (dll, name), "resolved_into": owner, "thunk": hex(thunk)})
    verdict = "unresolved (file image or fake target)" if unresolved == len(slots) else ("all slots resolve into their own DLL" if not redirected else "%d slots redirected" % len(redirected))
    return {"method": "live thunk -> containing loaded module (EnumProcessModulesEx) vs imports.tsv descriptor DLL", "slots": len(slots),
            "per_dll": per_dll, "redirected": redirected[:64], "unresolved": unresolved, "verdict": verdict}


# ---------------------------------------------------------------- per-build diff signatures
def clusters_from_ranges(rngs, gap=CLUSTER_GAP):
    """Merge coalesced differing runs [(lo, hi_excl, n_diff)] into clusters when the gap between a run's
    end and the next run's start is <= gap bytes. Returns [(lo, hi_excl, n_runs, n_diff, [runs])]."""
    out = []
    for lo, hi, cnt in sorted(rngs):
        if out and lo - out[-1][1] <= gap:
            c = out[-1]
            c[1] = hi
            c[2] += 1
            c[3] += cnt
            c[4].append((lo, hi, cnt))
        else:
            out.append([lo, hi, 1, cnt, [(lo, hi, cnt)]])
    return [tuple(c) for c in out]


def diff_tsv_path(md5):
    return os.path.join(BINARIES_DIR, "diff-%s-vs-%s.tsv" % (PRISTINE_MD5[:8], md5[:8]))


def gen_diff_tsv(build_path, ref_path, ref_raw, tag="", out_dir=BINARIES_DIR):
    """Write binaries\\diff-9a232dcc-vs-<md5>.tsv: one row per 64-B cluster per section (run list inside),
    plus header rows for the PE-level differences (size, SizeOfImage, section table). Returns (path, summary)."""
    img = FileImage(build_path)
    md5 = img.ident["md5"]
    regs = diff_regions(img, ref_raw, [])
    ref_ident = pe_ident.identity(ref_path)
    rows = []
    summary = {"md5": md5, "tag": tag, "path": build_path, "sections": {}}
    deltas = {name: delta for name, _lo, _hi, delta, _kind in REGIONS}
    for r in regs:
        rngs = [(int(x["va_lo"], 16), int(x["va_hi"], 16), x["diff_bytes"]) for x in r["ranges"]]
        cls = clusters_from_ranges(rngs)
        summary["sections"][r["region"]] = {"runs": len(rngs), "clusters": len(cls), "diff_bytes": r.get("diff_bytes", 0),
                                            "verdict": r["verdict"]}
        delta = deltas[r["region"]]
        for lo, hi, nruns, ndiff, runs in cls:
            rows.append([r["region"], r["kind"], hex(lo), hex(hi), str(hi - lo), str(nruns), str(ndiff),
                         ";".join("%s-%s:%d" % (hex(a), hex(b), c) for a, b, c in runs),
                         md5b(img.read(lo, hi - lo)), md5b(ref_raw[lo - delta: lo - delta + hi - lo]),
                         "build-shifted"])
    # file / header level
    hdr = []
    hdr.append(("file_size", str(ref_ident["size"]), str(img.ident["size"])))
    for k in ("size_of_image", "pe_timestamp", "entry_point"):
        if k in ref_ident and k in img.ident:
            hdr.append((k, str(ref_ident[k]), str(img.ident[k])))
    ref_secs = {s["name"]: s for s in ref_ident["sections"]}
    for s in img.ident["sections"]:
        rs = ref_secs.get(s["name"])
        if rs is None:
            hdr.append(("section_added", "-", "%s va %s vsize %d raw %d" % (s["name"], s["va"], s["vsize"], s["raw_size"])))
        elif (rs["va"], rs["vsize"], rs["raw_ptr"], rs["raw_size"]) != (s["va"], s["vsize"], s["raw_ptr"], s["raw_size"]):
            hdr.append(("section_changed:" + s["name"], "va %s vsize %d raw %s+%d" % (rs["va"], rs["vsize"], rs["raw_ptr"], rs["raw_size"]),
                        "va %s vsize %d raw %s+%d" % (s["va"], s["vsize"], s["raw_ptr"], s["raw_size"])))
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "diff-%s-vs-%s.tsv" % (PRISTINE_MD5[:8], md5[:8]))
    lines = ["# diff-%s-vs-%s.tsv - per-section differing byte clusters of %s (md5 %s, tag %s) against the pristine %s (md5 %s)" % (
                 PRISTINE_MD5[:8], md5[:8], build_path, md5, tag or "-", ref_path, PRISTINE_MD5),
             "# method: tools\\which_build.py %s gen_diff_tsv; per REGION byte compare (FileImage, file bytes at the section delta); runs = differing bytes coalesced across <= 8 identical bytes (ranges_from_diff); clusters = runs merged when the gap <= %d B (clusters_from_ranges); every VA is class init (image bytes; .rdata-iat = iat); tag build-shifted = instruction addresses inside the cluster do not transfer 1:1 (FOLDIN-REPORT section 3, gate P)" % (VERSION, CLUSTER_GAP),
             "# generated %s" % utc_now(),
             "# header\t" + "\t".join("%s=%s->%s" % h for h in hdr),
             "# summary\t" + "\t".join("%s:runs=%d,clusters=%d,diff_bytes=%d,%s" % (n, v["runs"], v["clusters"], v["diff_bytes"], v["verdict"]) for n, v in summary["sections"].items()),
             "section\tkind\tcluster_lo\tcluster_hi\tcluster_len\truns\tdiff_bytes\trun_list(lo-hi:diff)\tbuild_md5\tref_md5\ttag"]
    lines += ["\t".join(r) for r in rows]
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    os.replace(tmp, path)
    back = load_diff_tsv(path)
    assert len(back["clusters"]) == len(rows), "diff tsv read-back: %d rows written, %d read" % (len(rows), len(back["clusters"]))
    summary["path"] = path
    summary["clusters_total"] = len(rows)
    summary["header"] = hdr
    return path, summary


def load_diff_tsv(path):
    """{'build_md5', 'clusters': [(section, lo, hi, n_runs, n_diff)], 'summary': str}"""
    d = {"path": path, "build_md5": None, "clusters": [], "summary": ""}
    m = re.search(r"diff-[0-9a-f]{8}-vs-([0-9a-f]{8})\.tsv$", os.path.basename(path))
    if m:
        d["build_md5"] = m.group(1)
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("# summary"):
                d["summary"] = line.strip()
            if line.startswith("#") or line.startswith("section\t") or not line.strip():
                continue
            p = line.rstrip("\n").split("\t")
            d["clusters"].append((p[0], int(p[2], 16), int(p[3], 16), int(p[5]), int(p[6])))
    return d


def load_all_diffs(out_dir=BINARIES_DIR):
    out = {}
    for p in sorted(glob.glob(os.path.join(out_dir, "diff-%s-vs-*.tsv" % PRISTINE_MD5[:8]))):
        d = load_diff_tsv(p)
        out[d["build_md5"]] = d
    return out


def classify_va(va, diffs):
    """For every generated build: is `va` inside a differing cluster? Returns {md5_8: {inside, cluster, tag}}.
    Inside -> 'build-shifted' (instruction-level addresses do not transfer); outside -> 'transfers'."""
    out = {}
    for md5_8, d in diffs.items():
        hit = None
        for sec, lo, hi, nruns, ndiff in d["clusters"]:
            if lo <= va < hi:
                hit = {"section": sec, "lo": hex(lo), "hi": hex(hi), "runs": nruns, "diff_bytes": ndiff}
                break
        out[md5_8] = {"inside": hit is not None, "cluster": hit, "tag": "build-shifted" if hit else "transfers"}
    return out


def diff_signature(stamp, diffs):
    """Identify a live/offline image by its per-section diff clusters rather than md5 alone: the live
    clusters (H0 regions + .text-tail) are matched against each generated build's cluster list."""
    live = []
    for r in stamp["regions"]:
        if r["region"] in (".text", ".text-tail", ".rdata", ".rdata-tail"):
            rngs = [(int(x["va_lo"], 16), int(x["va_hi"], 16), x["diff_bytes"]) for x in r.get("ranges", [])]
            live += [(r["region"], lo, hi) for lo, hi, _n, _d, _r in clusters_from_ranges(rngs)]
    res = {"live_clusters": len(live), "builds": {}}
    best = None
    for md5_8, d in diffs.items():
        known = [(s, lo, hi) for s, lo, hi, _a, _b in d["clusters"] if s in (".text", ".text-tail", ".rdata", ".rdata-tail")]
        matched = sum(1 for s, lo, hi in live if any(ks == s and klo <= lo and hi <= khi for ks, klo, khi in known))
        unexplained = len(live) - matched
        missing = sum(1 for ks, klo, khi in known if not any(s == ks and klo <= lo and hi <= khi for s, lo, hi in live))
        res["builds"][md5_8] = {"known_clusters": len(known), "live_matched": matched, "live_unexplained": unexplained, "known_missing_live": missing}
        if unexplained == 0 and missing == 0 and (best is None or len(known) > best[1]):
            best = (md5_8, len(known))
    res["match"] = best[0] if best else None
    res["verdict"] = ("signature = %s" % best[0]) if best else ("pristine (no clusters)" if not live else "no generated build explains every live cluster")
    return res


def folder_hashes(game_dir):
    out = {}
    for p in sorted(glob.glob(os.path.join(game_dir, "Z*.DLL")) + glob.glob(os.path.join(game_dir, "z*.dll"))):
        out[os.path.basename(p)] = pe_ident.hashes(p)[0]
    for w in WRAPPERS:
        p = os.path.join(game_dir, w)
        if os.path.exists(p):
            out[w] = pe_ident.hashes(p)[0]
    return out


def shell_info(game_dir, modules):
    live = [m for m in modules if os.path.basename(m["path"]).lower() == "i76shell.dll"]
    p = live[0]["path"] if live else os.path.join(game_dir, "i76shell.dll")
    if not os.path.exists(p):
        return {"present": False, "path": p}
    d = pe_ident.identity(p)
    return {"present": True, "path": p, "loaded": bool(live), "base": hex(live[0]["base"]) if live else None,
            "md5": d["md5"], "size": d["size"], "pe_timestamp_utc": d["pe_timestamp_utc"], "mtime_utc": d["mtime_utc"],
            "linker": d["linker"], "imports": d["imports"],
            "ground_truth": d["md5"] == "8960fa16c1581da85ad5d6085517f292"}


def find_pid_by_name(name):
    arr = (wt.DWORD * 4096)()
    got = wt.DWORD(0)
    psapi.EnumProcesses(arr, ctypes.sizeof(arr), ctypes.byref(got))
    hits = []
    for i in range(got.value // 4):
        pid = arr[i]
        h = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
        if not h:
            continue
        buf = ctypes.create_unicode_buffer(1024)
        if psapi.GetProcessImageFileNameW(h, buf, 1024) and os.path.basename(buf.value).lower() == name.lower():
            hits.append(pid)
        k32.CloseHandle(h)
    return hits


def build_stamp(img, ref_path, ref_raw, game_dir, allow, base, pid=None, mode="live"):
    stamp = {"tool": "which_build.py", "tool_version": VERSION, "time_utc": utc_now(), "mode": mode,
             "pristine_md5": PRISTINE_MD5, "ref_file": ref_path, "ref_md5": md5b(ref_raw), "base": hex(base)}
    if stamp["ref_md5"] != PRISTINE_MD5:
        stamp["warning"] = "reference file is not the pristine exe"
    if base != IMAGE_BASE:
        stamp["warning_base"] = "image base %s != 0x400000; region VAs are pristine-layout VAs and will not match" % hex(base)
    regs = diff_regions(img, ref_raw, allow)
    stamp["regions"] = regs
    h0 = [r for r in regs if r["region"] in H0_REGIONS]
    stamp["h0_pass"] = all(r["verdict"] in ("identical", "allowlisted") for r in h0)
    stamp["h0_summary"] = {r["region"]: r["verdict"] for r in regs}
    if isinstance(img, LiveImage):
        stamp["short_reads"] = img.short_reads
    stamp["live_imports"] = parse_live_imports(img, base)
    names = [n.lower() for n in stamp["live_imports"].get("dll_names", [])]
    stamp["import_flags"] = {"u32x": "u32x.dll" in names, "user32": "user32.dll" in names,
                             "winmm": "winmm.dll" in names, "win32": "win32.dll" in names}
    diffs = load_all_diffs()
    stamp["diff_signature"] = diff_signature(stamp, diffs) if diffs else {"verdict": "no binaries\\diff-*.tsv generated (run --gen-diffs)"}
    return stamp


def live_extras(stamp, img, pid, game_dir):
    mods = img.modules()
    stamp["pid"] = pid
    stamp["wow64"] = img.is_wow64()
    stamp["iat_by_name"] = iat_by_name(img, mods)
    stamp["main_module"] = mods[0] if mods else None
    if mods:
        stamp["main_module"]["base"] = hex(mods[0]["base"])
        p = mods[0]["path"]
        if os.path.exists(p):
            stamp["exe_md5"] = pe_ident.hashes(p)[0]
            stamp["exe_path"] = p
            stamp["build_class"] = KNOWN_MD5.get(stamp["exe_md5"], "unknown-md5")
    stamp["modules_loaded"] = sorted({os.path.basename(m["path"]).lower() for m in mods})
    stamp["module_bases"] = {os.path.basename(m["path"]).lower(): hex(m["base"]) for m in mods
                             if os.path.basename(m["path"]).lower() in ("i76shell.dll", "u32x.dll", "user32.dll", "winmm.dll", "win32.dll",
                                                                        "zglide.dll", "glide2x.dll", "ddraw.dll", "strlkup.dll", "anetdll.dll", "i7_sfrce.dll")}
    stamp["loaded_flags"] = {k: (k + ".dll") in stamp["modules_loaded"] for k in ("u32x", "user32", "winmm", "win32", "i76patch")}
    stamp["shell"] = shell_info(game_dir, mods)
    stamp["process"] = wmi_process(pid)
    sid = img.session_id()
    qs = query_session()
    stamp["session"] = {"process_session_id": sid, "console_session_id": k32.WTSGetActiveConsoleSessionId(),
                        "same_as_console": sid == k32.WTSGetActiveConsoleSessionId(),
                        "query_session": {k: v for k, v in qs.items() if k != "raw"}}
    return stamp


def add_folder(stamp, game_dir, hooks_json=None):
    stamp["game_dir"] = game_dir
    stamp["dgvoodoo_conf"] = dgvoodoo_conf(game_dir)
    stamp["module_md5"] = folder_hashes(game_dir)
    stamp["hooks"] = read_hooks_json(hooks_json)
    return stamp


def print_report(stamp):
    print("which_build.py %s  mode=%s  ref=%s (md5 %s)" % (VERSION, stamp["mode"], stamp["ref_file"], stamp["ref_md5"]))
    if "exe_path" in stamp:
        print("exe: %s md5 %s -> %s" % (stamp["exe_path"], stamp["exe_md5"], stamp.get("build_class")))
    for r in stamp["regions"]:
        extra = ""
        if r["kind"] == "iat" and "thunks_nonzero" in r:
            extra = "  thunks nonzero %d, resolved outside image %d" % (r["thunks_nonzero"], r["thunks_resolved_outside_image"])
        print("  %-11s %s-%s %7d B  %-40s diff_bytes=%s%s" % (r["region"], r["va_lo"], r["va_hi"], r["bytes"], r["verdict"], r.get("diff_bytes", "?"), extra))
        for x in r["ranges"][:12]:
            tag = " ALLOWLISTED: " + x["allowlisted"] if "allowlisted" in x else ""
            print("      %s-%s len %d diff %d live %s ref %s live[:16]=%s ref[:16]=%s%s" % (
                x["va_lo"], x["va_hi"], x["len"], x["diff_bytes"], x["live_md5"][:12], x["ref_md5"][:12], x["live_hex"], x["ref_hex"], tag))
        if len(r["ranges"]) > 12:
            print("      ... %d more ranges" % (len(r["ranges"]) - 12))
    print("H0: %s" % ("PASS" if stamp["h0_pass"] else "FAIL (.text/.text-tail/.rdata differ beyond the allowlist)"))
    li = stamp.get("live_imports", {})
    print("import descriptors in image: %s" % ", ".join(li.get("dll_names", [])) if "dll_names" in li else "import descriptors: %s" % li)
    if "modules_loaded" in stamp:
        print("loaded flags: %s ; bases: %s" % (stamp["loaded_flags"], stamp["module_bases"]))
        sh = stamp["shell"]
        print("i76shell.dll: %s md5 %s pe %s mtime %s loaded=%s ground_truth=%s" % (
            sh.get("path"), sh.get("md5"), sh.get("pe_timestamp_utc"), sh.get("mtime_utc"), sh.get("loaded"), sh.get("ground_truth")))
        print("cmdline: %s" % stamp["process"].get("command_line", stamp["process"]))
        s = stamp["session"]
        print("session: process %s console %s same=%s ; query session current=%s console_active=%s rdp_active=%s" % (
            s["process_session_id"], s["console_session_id"], s["same_as_console"], s["query_session"].get("current_session"),
            s["query_session"].get("console_active"), s["query_session"].get("rdp_active")))
    if "iat_by_name" in stamp:
        ib = stamp["iat_by_name"]
        print("IAT by name: %s (%s slots; unresolved %s)" % (ib.get("verdict"), ib.get("slots"), ib.get("unresolved")))
        for x in ib.get("redirected", [])[:8]:
            print("      %s %s -> %s" % (x["slot"], x["import"], x["resolved_into"]))
    if "diff_signature" in stamp:
        print("diff signature: %s" % stamp["diff_signature"].get("verdict"))
    if "dgvoodoo_conf" in stamp:
        d = stamp["dgvoodoo_conf"]
        print("dgVoodoo.conf: sha256 %s effective %s" % (d.get("sha256"), d.get("effective")))
        for m in d.get("misplaced", []):
            print("      WARNING G-CONF: [%s] %s = %s (line %d) belongs in %s" % (m["section"], m["key"], m["value"], m["line"], "/".join(m["owners"])))
        print("folder md5: %s" % ", ".join("%s=%s" % (k, v[:8]) for k, v in stamp["module_md5"].items()))
    if "hooks" in stamp:
        print("hooks (G-ATTEST): %s" % stamp["hooks"].get("attest"))


def write_manifest(path, stamp, stamp_class):
    stamp = dict(stamp)
    if stamp_class:
        stamp["build_class"] = stamp_class
    man = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try:
                man = json.load(f)
            except json.JSONDecodeError:
                man = {"_unparsable_previous": open(path, encoding="utf-8", errors="replace").read()}
    man["build"] = stamp
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(man, f, indent=1, default=str)
    with open(path, "r", encoding="utf-8") as f:  # read back
        back = json.load(f)
    assert back["build"]["time_utc"] == stamp["time_utc"], "manifest read-back mismatch"
    return path


def selftest(ref_path, game_dir, allow):
    """Offline unit test of the diff logic: pristine vs pristine (0 diffs), pristine vs pristine_fix
    (only the allowlisted 5 bytes), pristine vs patched i76.exe (.text-tail +132 and .rdata)."""
    with open(ref_path, "rb") as f:
        ref_raw = f.read()
    ok = True
    cases = [("i76.exe.2017galaxy", "identical everywhere"),
             ("i76_pristine_fix.exe", "one allowlisted 5-byte range at 0x499b25; nothing else"),
             ("i76.exe", ".text DIFFERS inside 0x401000-0x4bbe55 (the lab's own patches; measured, see status file); "
                         ".text-tail +132 B at 0x4bbe55; .rdata DIFFERS (u32x/WINMM names); .rdata-tail DIFFERS (I76PATCH.DLL); H0 FAIL")]
    for name, expect in cases:
        p = os.path.join(game_dir, name)
        if not os.path.exists(p):
            print("selftest: skip %s (absent)" % name)
            continue
        img = FileImage(p)
        st = build_stamp(img, ref_path, ref_raw, game_dir, allow, img.base, mode="file")
        st["exe_path"] = p
        st["exe_md5"] = img.ident["md5"]
        st["build_class"] = KNOWN_MD5.get(st["exe_md5"], "unknown-md5")
        print("\n=== selftest %s (expect: %s)" % (name, expect))
        print_report(st)
        v = st["h0_summary"]
        if name == "i76.exe.2017galaxy":
            good = all(x == "identical" for x in v.values())
        elif name == "i76_pristine_fix.exe":
            text = [r for r in st["regions"] if r["region"] == ".text"][0]
            good = (v[".text"] == "allowlisted" and len(text["ranges"]) == 1 and text["ranges"][0]["va_lo"] == "0x499b25"
                    and text["ranges"][0]["len"] == 5 and all(v[k] == "identical" for k in v if k != ".text"))
        else:
            tail = [r for r in st["regions"] if r["region"] == ".text-tail"][0]
            text = [r for r in st["regions"] if r["region"] == ".text"][0]
            good = (v[".text"] == "DIFFERS" and v[".text-tail"] == "DIFFERS" and v[".rdata"] == "DIFFERS"
                    and v[".rdata-tail"] == "DIFFERS" and not st["h0_pass"]
                    and len(tail["ranges"]) == 1 and tail["ranges"][0]["va_lo"] == "0x4bbe55" and tail["ranges"][0]["len"] == 132
                    and text["diff_bytes"] > 0
                    and "u32x.dll" in st["live_imports"].get("dll_names", []))
            print("selftest i76.exe measured: .text %d differing bytes in %d ranges; .text-tail %d; .rdata %d in %d ranges; .rdata-tail %d; imports %s" % (
                text["diff_bytes"], len(text["ranges"]), tail["diff_bytes"],
                [r for r in st["regions"] if r["region"] == ".rdata"][0]["diff_bytes"],
                len([r for r in st["regions"] if r["region"] == ".rdata"][0]["ranges"]),
                [r for r in st["regions"] if r["region"] == ".rdata-tail"][0]["diff_bytes"],
                st["live_imports"].get("dll_names")))
        print("selftest %s: %s" % (name, "OK" if good else "UNEXPECTED"))
        ok = ok and good
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--pid", type=int)
    g.add_argument("--name")
    g.add_argument("--file")
    g.add_argument("--selftest", action="store_true")
    ap.add_argument("--ref", default=DEFAULT_REF)
    ap.add_argument("--game-dir", default=DEFAULT_GAME)
    ap.add_argument("--allowlist", default=DEFAULT_ALLOWLIST if os.path.exists(DEFAULT_ALLOWLIST) else "none")
    ap.add_argument("--base", default=None, help="override the image base (fake targets); default: main module base")
    ap.add_argument("--out", help="manifest.json to write/merge the 'build' block into")
    ap.add_argument("--stamp", help="build class to stamp (pristine | pristine+i76fix-p1 | patched-build-only)")
    ap.add_argument("--json", action="store_true", help="print the JSON stamp")
    ap.add_argument("--hooks-json", help="G-ATTEST: fired-counter JSON written by the Frida driver (default: hooks.json beside --out)")
    g.add_argument("--gen-diffs", action="store_true", help="generate binaries\\diff-9a232dcc-vs-<md5>.tsv for the known patched builds (DIFF_BUILDS)")
    g.add_argument("--diff-file", help="generate the diff TSV for one exe")
    g.add_argument("--classify", help="comma-separated VAs: inside/outside a differing cluster per generated build (build-shifted tag)")
    ap.add_argument("--conf-template", default=CONF_TEMPLATE, help="dgVoodooCpl-written conf that supplies the key ownership table")
    a = ap.parse_args()

    if not os.path.exists(a.ref):
        print("reference file missing: %s" % a.ref)
        return 2
    allow = load_allowlist(a.allowlist)
    if a.selftest:
        return 0 if selftest(a.ref, a.game_dir, allow) else 1
    with open(a.ref, "rb") as f:
        ref_raw = f.read()
    if md5b(ref_raw) != PRISTINE_MD5:
        print("WARNING reference %s md5 %s is not the pristine %s" % (a.ref, md5b(ref_raw), PRISTINE_MD5))

    if a.gen_diffs or a.diff_file:
        builds = [("file", a.diff_file)] if a.diff_file else DIFF_BUILDS
        rc = 0
        for tag, path in builds:
            if not os.path.exists(path):
                print("skip %s: %s absent" % (tag, path))
                continue
            p, s = gen_diff_tsv(path, a.ref, ref_raw, tag=tag)
            print("%s md5 %s -> %s: %d clusters; %s" % (tag, s["md5"], os.path.relpath(p, MAP_ROOT), s["clusters_total"],
                                                    "; ".join("%s runs=%d clusters=%d diff=%d" % (n, v["runs"], v["clusters"], v["diff_bytes"]) for n, v in s["sections"].items() if v["runs"])))
            if s["header"]:
                print("   header: %s" % "; ".join("%s %s->%s" % h for h in s["header"]))
        return rc

    if a.classify:
        diffs = load_all_diffs()
        if not diffs:
            print("no binaries\\diff-*.tsv (run --gen-diffs first)")
            return 2
        for tok in a.classify.split(","):
            va = int(tok.strip(), 16)
            c = classify_va(va, diffs)
            print("%s: %s" % (hex(va), "; ".join("%s %s%s" % (k, v["tag"], (" (%s %s-%s)" % (v["cluster"]["section"], v["cluster"]["lo"], v["cluster"]["hi"])) if v["cluster"] else "") for k, v in sorted(c.items()))))
        return 0

    hooks_json = a.hooks_json or (os.path.join(os.path.dirname(os.path.abspath(a.out)), "hooks.json") if a.out else None)
    if a.file:
        img = FileImage(a.file)
        stamp = build_stamp(img, a.ref, ref_raw, a.game_dir, allow, img.base, mode="file")
        stamp["exe_path"] = os.path.abspath(a.file)
        stamp["exe_md5"] = img.ident["md5"]
        stamp["build_class"] = KNOWN_MD5.get(stamp["exe_md5"], "unknown-md5")
        stamp = add_folder(stamp, a.game_dir, hooks_json)
    else:
        pid = a.pid
        if a.name:
            hits = find_pid_by_name(a.name)
            if len(hits) != 1:
                print("process %s: %d matches %s" % (a.name, len(hits), hits))
                return 2
            pid = hits[0]
        if pid is None:
            ap.print_help()
            return 2
        img = LiveImage(pid)
        try:
            mods = img.modules()
            base = int(a.base, 16) if a.base else (mods[0]["base"] if mods else IMAGE_BASE)
            stamp = build_stamp(img, a.ref, ref_raw, a.game_dir, allow, base, pid=pid, mode="live")
            stamp = live_extras(stamp, img, pid, a.game_dir)
            stamp = add_folder(stamp, a.game_dir, hooks_json)
        finally:
            img.close()
    print_report(stamp)
    if a.out:
        p = write_manifest(a.out, stamp, a.stamp)
        print("manifest build block written and read back: %s" % p)
    if a.json:
        print(json.dumps(stamp, indent=1, default=str))
    return 0 if stamp["h0_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
