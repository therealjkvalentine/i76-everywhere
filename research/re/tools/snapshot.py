#!/usr/bin/env python3
r"""snapshot.py - ReadProcessMemory snapshots of the game's .data (+ heaps/pools) with per-state canaries.
Task 10 items 002/003 (gate E input, M05 null spread); gates H0 H3 H4 H8, G-TORN, G-POS, G-ATTEST.

    python tools\snapshot.py --capture 002-paused --label paused --gap 2 [--pump]          two reads, --gap s apart
    python tools\snapshot.py --capture 003-cockpit-null --series --hz 5 --window 20 --windows 3 [--pump] [--heaps]
    python tools\snapshot.py --capture test --pid <fake_sim pid> --series --hz 5 --window 3 --windows 2 --map-root <dir>

Region: one bulk ReadProcessMemory of 0x4c2000-0x669ef8 (initialised .data, class init + BSS, class bss;
1,736,440 B) per frame; a short read is the null "region not fully mapped in this pid" and exits 1.
--heaps: VirtualQueryEx enumeration of every committed private RW region; the 10 heap-handle globals of
symbols\globals.tsv (class bss; the handle value is the NT heap's first-segment base) and the two pool
pointers [0x5dd320] / [0x5dd324] (class bss; pool_Reserve 0x498940 / the 0x402f98-0x402fd9 sizing) name
their containing region; with --read-heaps those regions are read every frame too (per-heap / per-pool p).

Canaries (H4), method = frame counter 0x5a7e1c (bss) read before and after every bulk read, game time
0x5a7e74 (bss), dt 0x4fe428 (init), and the PeekMessageA pump count from tools\pump_counter.js (--pump:
frida attach, hook on the function the IAT slot 0x4bc350 [imports.tsv] points to, callers with a return
address in .text counted as the exe's own pump):
    driving  0x5a7e1c advanced during the capture
    paused   0x5a7e1c frozen AND > 0 AND the pump count advanced (without --pump: "frozen, pump unmeasured")
    menu     0x5a7e1c == 0 throughout (the sim clock never runs outside a mission: console-smoke)
    dead     0x5a7e1c frozen AND pump measured AND pump did not advance (the process is hung: voids the capture)
G-TORN: every frame is tagged torn-possible while the state is driving (a tick during the read, or the sim
advancing anywhere in the capture); frames are coherent only when the sim is frozen for the whole capture.
G-POS: --pos-control ADDR:TYPE:EXPECT (repeatable; TYPE int32|uint32|float|byte; EXPECT a value, `changes`
or `constant`) is evaluated on every capture so an empty churn result is distinguishable from a dead
instrument. G-ATTEST: the pump counters are written to captures\<id>\hooks.json for which_build.py.

Series mode (--series): --windows windows of --window s at --hz; per window the fraction of dwords that
changed at least once (win<i>_p), A/A pairs between window ends (AA_<a>v<b>_p), churn runs, expected
false survivors N*p^k for k=5 (H1); the code is captures\002-idle-null\idle_null.py's, verbatim in method.
Storage (H8): raw\frame0.bin (full) + raw\w<i>-<j>.delta.xz per later frame (u32 count, u32 idx[], u32
val[] of the dwords differing from frame 0, xz preset 6); --budget-gb (default 20 per sitting) is checked
against the bytes already under captures\*\raw before and during the run. Every file is re-read and
hashed after the write (H3). The process is attached, never spawned (H10).
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import datetime as dt
import glob
import hashlib
import json
import lzma
import os
import struct
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
VERSION = "0.2"
BASE = 0x4C2000
END = 0x669EF8
FRAME_COUNTER = 0x5A7E1C
CANARIES = {"frame_counter_0x5a7e1c": (0x5A7E1C, "I", "bss"), "game_time_0x5a7e74": (0x5A7E74, "f", "bss"),
            "dt_0x4fe428": (0x4FE428, "f", "init")}
HEAP_HANDLE_GLOBALS = {  # symbols\globals.tsv rows of type HANDLE (anchored, class bss; creator function)
    0x531d04: "heap_531d04 (0x447f90)", 0x535f68: "heap_535f68 (0x44ae30)", 0x58dac8: "heap_58dac8 (0x474c10)",
    0x5a7cc0: "heap_5a7cc0 (0x499c90)", 0x5a7cc8: "heap_5a7cc8 (0x499c90)", 0x5a7d9c: "heap_5a7d9c (0x49b7e0)",
    0x5a7da0: "heap_5a7da0 (0x49c300)", 0x5a8104: "heap_5a8104 (0x49f1f0)", 0x5db990: "heap_5db990 (0x4b9dd0)",
    0x608be8: "heap_608be8 (0x43e950)"}
POOL_POINTER_GLOBALS = {0x5dd320: "pool_5dd320 (0x1a5e0 B, sized 0x402f98-0x402fd9)", 0x5dd324: "pool_5dd324 (512 KB render arena)"}
PEEKMESSAGE_SLOT_DEFAULT = 0x4bc350
PROCESS_VM_READ = 0x10
PROCESS_QUERY_INFORMATION = 0x400
MEM_COMMIT = 0x1000
MEM_PRIVATE = 0x20000
PAGE_READWRITE = 0x04
PAGE_EXECUTE_READWRITE = 0x40
TYPES = {"int32": "<i", "uint32": "<I", "float": "<f", "byte": "<B"}

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)
k32.OpenProcess.restype = wt.HANDLE
k32.ReadProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
psapi.GetModuleFileNameExW.argtypes = [wt.HANDLE, wt.HMODULE, wt.LPWSTR, wt.DWORD]


class MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p), ("AllocationProtect", wt.DWORD),
                ("PartitionId", wt.WORD), ("RegionSize", ctypes.c_size_t), ("State", wt.DWORD), ("Protect", wt.DWORD), ("Type", wt.DWORD)]


k32.VirtualQueryEx.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.POINTER(MBI), ctypes.c_size_t]
k32.VirtualQueryEx.restype = ctypes.c_size_t


def find_pid(name):
    import psutil
    name = name.lower()
    return [p.pid for p in psutil.process_iter(["name"]) if (p.info["name"] or "").lower().startswith(name)]


def module_path(h):
    buf = ctypes.create_unicode_buffer(1024)
    n = psapi.GetModuleFileNameExW(h, None, buf, 1024)
    return buf.value if n else None


def rd(h, addr, n):
    buf = ctypes.create_string_buffer(n)
    got = ctypes.c_size_t()
    ok = k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, n, ctypes.byref(got))
    return buf.raw[: got.value] if ok else b""


def rd_fmt(h, addr, fmt):
    n = struct.calcsize(fmt)
    b = rd(h, addr, n)
    return struct.unpack(fmt, b)[0] if len(b) == n else None


def md5b(b):
    return hashlib.md5(b).hexdigest()


def write_file(path, blob):
    """atomic write + read-back (H3); returns {bytes, md5, readback_equal}."""
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(blob)
    os.replace(tmp, path)
    with open(path, "rb") as f:
        back = f.read()
    return {"bytes": len(back), "md5": md5b(back), "readback_equal": back == blob}


def raw_bytes_used(map_root):
    """H8 budget: bytes already under captures\\*\\raw (all captures of the sitting share the 20 GB)."""
    n = 0
    for p in glob.glob(os.path.join(map_root, "captures", "*", "raw", "**", "*"), recursive=True):
        if os.path.isfile(p):
            n += os.path.getsize(p)
    return n


def enum_regions(h, limit=0x1_0000_0000):
    """Committed private RW regions of the target (method: VirtualQueryEx walk; needs PROCESS_QUERY_INFORMATION,
    with VM_READ alone it enumerates zero regions - AGENTS.md trap 2)."""
    out = []
    addr = 0
    mbi = MBI()
    while addr < limit:
        if not k32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            break
        base = mbi.BaseAddress or 0
        size = mbi.RegionSize
        if mbi.State == MEM_COMMIT and mbi.Type == MEM_PRIVATE and mbi.Protect in (PAGE_READWRITE, PAGE_EXECUTE_READWRITE):
            out.append({"base": base, "size": size, "protect": mbi.Protect, "alloc_base": mbi.AllocationBase or 0})
        addr = base + size
        if size == 0:
            break
    return out


def heaps_and_pools(h, regions):
    """Name the regions that hold the heap handles' bases and the two pools. Returns the annotated list."""
    owners = []
    for g, name in HEAP_HANDLE_GLOBALS.items():
        v = rd_fmt(h, g, "<I")
        owners.append({"global": hex(g), "class": "bss", "kind": "heap", "name": name, "value": hex(v) if v else v})
    for g, name in POOL_POINTER_GLOBALS.items():
        v = rd_fmt(h, g, "<I")
        owners.append({"global": hex(g), "class": "bss", "kind": "pool", "name": name, "value": hex(v) if v else v})
    for r in regions:
        r["owner"] = []
    for o in owners:
        v = int(o["value"], 16) if o["value"] else 0
        o["region"] = None
        if not v:
            continue
        for r in regions:
            if r["base"] <= v < r["base"] + r["size"]:
                r["owner"].append(o["name"])
                o["region"] = {"base": hex(r["base"]), "size": r["size"]}
                break
    return owners


class Pump:
    """Optional Frida pump counter (tools\\pump_counter.js). attach only, H10."""

    def __init__(self, pid, slot, module, export):
        import frida
        self.frida = frida
        self.session = frida.attach(pid)
        with open(os.path.join(ROOT, "tools", "pump_counter.js"), "r", encoding="utf-8") as f:
            self.script = self.session.create_script(f.read())
        self.script.load()
        self.info = self.script.exports_sync.start({"slot": hex(slot), "text_lo": "0x401000", "text_hi": "0x4bbe55",
                                                    "fallback_module": module, "fallback_export": export})

    def counts(self):
        return self.script.exports_sync.counts()

    def close(self):
        try:
            self.script.unload()
            self.session.detach()
        except Exception:
            pass


def classify_state(fc_first, fc_last, pump_before, pump_after):
    if fc_first is None or fc_last is None:
        return "unreadable (canary read failed)"
    if fc_first == 0 and fc_last == 0:
        return "menu (0x5a7e1c == 0: the sim clock never ran)"
    if fc_last != fc_first:
        return "driving (0x5a7e1c advanced %d)" % (fc_last - fc_first)
    if pump_before is None:
        return "frozen (0x5a7e1c > 0 and unchanged; pump unmeasured, so PAUSE_GAME is not proven: use --pump)"
    if pump_after > pump_before:
        return "paused (0x5a7e1c > 0 frozen, pump advanced %d)" % (pump_after - pump_before)
    return "dead (0x5a7e1c frozen and the pump did not advance: hung process, capture void)"


def pos_control_eval(specs, first, last, changed_mask):
    """G-POS rows: [(addr, type, expect)] -> verdicts against the first/last frames (+ change mask in series)."""
    out = []
    for addr, typ, expect in specs:
        off = addr - BASE
        fmt = TYPES[typ]
        n = struct.calcsize(fmt)
        v0 = struct.unpack_from(fmt, first, off)[0] if 0 <= off <= len(first) - n else None
        v1 = struct.unpack_from(fmt, last, off)[0] if 0 <= off <= len(last) - n else None
        changed = bool(changed_mask[off // 4]) if changed_mask is not None and 0 <= off // 4 < len(changed_mask) else (v0 != v1)
        if expect == "changes":
            ok = changed
        elif expect == "constant":
            ok = not changed
        else:
            want = float(expect) if typ == "float" else int(expect, 0)
            ok = (abs(v1 - want) < 1e-6) if (typ == "float" and v1 is not None) else (v1 == want)
        out.append({"addr": hex(addr), "class": "init" if addr < 0x501800 else "bss", "type": typ, "expect": expect,
                    "first": v0, "last": v1, "changed": changed, "pass": bool(ok)})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--capture", required=True)
    ap.add_argument("--pid", type=int)
    ap.add_argument("--name", default="i76_pristine_fix")
    ap.add_argument("--gap", type=float, default=1.0)
    ap.add_argument("--label", default="")
    ap.add_argument("--map-root", default=ROOT)
    ap.add_argument("--series", action="store_true")
    ap.add_argument("--hz", type=float, default=5.0)
    ap.add_argument("--window", type=float, default=20.0, help="seconds per window")
    ap.add_argument("--windows", type=int, default=3)
    ap.add_argument("--pump", action="store_true", help="frida pump counter (tools\\pump_counter.js)")
    ap.add_argument("--pump-slot", default=hex(PEEKMESSAGE_SLOT_DEFAULT), help="IAT slot of PeekMessageA (imports.tsv)")
    ap.add_argument("--pump-module", default="user32.dll")
    ap.add_argument("--pump-export", default="PeekMessageA")
    ap.add_argument("--heaps", action="store_true", help="enumerate private RW regions; name heaps/pools")
    ap.add_argument("--read-heaps", action="store_true", help="also read the named heap/pool regions each frame")
    ap.add_argument("--pos-control", action="append", default=[], help="ADDR:TYPE:EXPECT (G-POS)")
    ap.add_argument("--budget-gb", type=float, default=20.0)
    ap.add_argument("--xz-preset", type=int, default=6)
    a = ap.parse_args()
    pid = a.pid
    if pid is None:
        pids = find_pid(a.name)
        if len(pids) != 1:
            print(f"process {a.name}: {len(pids)} matches {pids} (need exactly one; use --pid)")
            sys.exit(2)
        pid = pids[0]
    h = k32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
    if not h:
        print(f"OpenProcess({pid}) failed: {ctypes.get_last_error()}")
        sys.exit(2)
    exe = module_path(h)
    exe_md5 = hashlib.md5(open(exe, "rb").read()).hexdigest() if exe and os.path.exists(exe) else None
    print(f"attached pid {pid} exe {exe} md5 {exe_md5} tools/snapshot.py {VERSION}")
    cap = os.path.join(a.map_root, "captures", a.capture)
    raw = os.path.join(cap, "raw")
    os.makedirs(raw, exist_ok=True)
    budget = int(a.budget_gb * (1 << 30))
    used0 = raw_bytes_used(a.map_root)
    if used0 >= budget:
        print(f"H8 budget exhausted: {used0} B under captures\\*\\raw >= {budget} B; nothing written")
        sys.exit(4)
    pos_specs = []
    for s in a.pos_control:
        addr_s, typ, expect = s.split(":", 2)
        pos_specs.append((int(addr_s, 16), typ, expect))

    def canaries():
        out = {}
        for k, (addr, fmt, cls) in CANARIES.items():
            out[k] = {"value": rd_fmt(h, addr, "<" + fmt), "class": cls}
        return out

    def fc():
        return rd_fmt(h, FRAME_COUNTER, "<I")

    pump = None
    pump_info = {"measured": False}
    if a.pump:
        try:
            pump = Pump(pid, int(a.pump_slot, 16), a.pump_module, a.pump_export)
            pump_info = {"measured": bool(pump.info.get("installed")), "info": pump.info,
                         "method": "frida Interceptor.attach on the function the PeekMessageA IAT slot points to (or the fallback export); callers with a return address in .text 0x401000-0x4bbe55 = the exe's pump"}
            if not pump.info.get("installed"):
                print(f"pump hook did not install: {pump.info}")
            else:
                print(f"pump hook installed: {pump.info.get('how')} target {pump.info.get('target')} arch {pump.info.get('arch')}")
        except Exception as e:  # frida missing or attach refused: the paused canary stays unmeasured
            pump_info = {"measured": False, "error": str(e)}
            print(f"pump hook unavailable: {e} (paused canary unmeasured)")
    regions = []
    owners = []
    named = []
    if a.heaps or a.read_heaps:
        regions = enum_regions(h)
        owners = heaps_and_pools(h, regions)
        named = [r for r in regions if r["owner"]]
        print(f"regions: {len(regions)} committed private RW ({sum(r['size'] for r in regions)} B); named heap/pool regions {len(named)}; "
              f"heap handles set {sum(1 for o in owners if o['kind'] == 'heap' and o['value'])}/{len(HEAP_HANDLE_GLOBALS)}, pools set {sum(1 for o in owners if o['kind'] == 'pool' and o['value'])}/2")

    def bulk():
        """one frame: (t, fc_before, blob, fc_after, heap_blobs)"""
        f0 = fc()
        t = time.time()
        b = rd(h, BASE, END - BASE)
        hb = {}
        if a.read_heaps:
            for r in named:
                hb[hex(r["base"])] = rd(h, r["base"], r["size"])
        f1 = fc()
        return t, f0, b, f1, hb

    # Pump metric: calls from .text when the hook sits on the exe's IAT-slot target (the game); on the fallback
    # export (a throwaway process without an i76 .text) every call counts, and the record says which.
    def pump_metric():
        c = pump.counts()
        return c["text"] if str(pump.info.get("how", "")).startswith("iat-slot") else c["text"] + c["other"]

    pump0 = pump_metric() if (pump and pump.info.get("installed")) else None
    pump0_all = pump.counts() if pump0 is not None else None
    if pump0 is not None:
        pump_info["metric"] = "text (callers in .text 0x401000-0x4bbe55)" if str(pump.info.get("how", "")).startswith("iat-slot") else "text+other (fallback export: no i76 .text in this process)"
    t_start = time.time()
    c0 = canaries()
    files = {}
    snap = {"tool": f"tools/snapshot.py {VERSION}", "time": dt.datetime.now().isoformat(timespec="seconds"), "label": a.label,
            "pid": pid, "exe": exe, "exe_md5": exe_md5,
            "region": {"base": f"0x{BASE:x}", "end": f"0x{END:x}", "bytes": END - BASE, "class": "init 0x4c2000-0x501800, bss 0x501800-0x669ef8"},
            "canaries_before": c0, "pump": pump_info, "budget": {"budget_bytes": budget, "raw_bytes_before": used0},
            "heaps": {"enumerated": bool(regions), "regions": len(regions), "regions_bytes": sum(r["size"] for r in regions),
                      "owners": owners, "named_regions": [{"base": hex(r["base"]), "size": r["size"], "owner": r["owner"]} for r in named],
                      "read_each_frame": a.read_heaps,
                      "method": "VirtualQueryEx walk (MEM_COMMIT, MEM_PRIVATE, RW); heap handle value = NT heap first-segment base; only the containing region is named (later segments are unowned)"}}
    import numpy as np
    if not a.series:
        t1, f0a, s1, f1a, hb1 = bulk()
        time.sleep(a.gap)
        t2, f0b, s2, f1b, hb2 = bulk()
        if len(s1) != END - BASE or len(s2) != END - BASE:
            print(f"short read: {len(s1)} / {len(s2)} of {END - BASE} (null: the region is not fully mapped in pid {pid})")
            sys.exit(1)
        c1 = canaries()
        a1 = np.frombuffer(s1, dtype=np.uint32)
        a2 = np.frombuffer(s2, dtype=np.uint32)
        diff = np.nonzero(a1 != a2)[0]
        runs = runs_of(diff)
        files["snapshot.bin"] = write_file(os.path.join(raw, "snapshot.bin"), s1)
        files["snapshot-2.bin"] = write_file(os.path.join(raw, "snapshot-2.bin"), s2)
        heap_diff = {}
        for k in hb1:
            if len(hb1[k]) == len(hb2[k]) and len(hb1[k]) >= 4:
                x = np.frombuffer(hb1[k][: len(hb1[k]) // 4 * 4], dtype=np.uint32)
                y = np.frombuffer(hb2[k][: len(hb2[k]) // 4 * 4], dtype=np.uint32)
                heap_diff[k] = {"dwords": int(len(x)), "differing": int((x != y).sum()), "p": float((x != y).mean()) if len(x) else None}
                files[f"heap-{k}.bin"] = write_file(os.path.join(raw, f"heap-{k}.bin"), hb1[k])
        pump1 = pump_metric() if pump0 is not None else None
        state = classify_state(f0a, f1b, pump0, pump1)
        snap.update({
            "read_seconds": [round(time.time() - t_start, 3)], "gap_seconds": a.gap, "canaries_after": c1,
            "frames": [{"t": t1, "fc_before": f0a, "fc_after": f1a, "torn": torn_tag(f0a, f1a, state)},
                       {"t": t2, "fc_before": f0b, "fc_after": f1b, "torn": torn_tag(f0b, f1b, state)}],
            "state": state, "canary_verdict": state,
            "canary_method": "0x5a7e1c before/after each bulk read; paused needs the pump count (tools\\pump_counter.js) to advance while 0x5a7e1c > 0 is frozen; menu = 0x5a7e1c == 0",
            "pump_counts": {"before": pump0_all, "after": pump.counts() if pump0 is not None else None},
            "differing_dwords_between_reads": int(len(diff)), "differing_runs": len(runs),
            "differing_top_runs": [[f"0x{r[0]:x}", f"0x{r[1]:x}", r[2]] for r in sorted(runs, key=lambda r: -r[2])[:10]],
            "heap_diff": heap_diff, "files": files,
            "pos_control": pos_control_eval(pos_specs, s1, s2, None)})
        summary = f"state {state}; {len(diff)} dwords differ between the two reads in {len(runs)} runs"
    else:
        hz, win, nwin = a.hz, a.window, a.windows
        est = int(nwin * win * hz * (END - BASE) * 0.05) + (END - BASE)  # xz deltas are small; 5 % is a generous bound
        if used0 + est > budget:
            print(f"H8 budget: {used0} + est {est} > {budget}; refusing")
            sys.exit(4)
        first = None
        series = []
        meta = []
        deltas_bytes = 0
        heap_series = {}
        stopped = None
        for wi in range(nwin):
            snaps = []
            t_end = time.time() + win
            j = 0
            while time.time() < t_end:
                t, f0, b, f1, hb = bulk()
                if len(b) != END - BASE:
                    print(f"short read {len(b)} of {END - BASE} (null: region not fully mapped)")
                    sys.exit(1)
                arr = np.frombuffer(b, dtype=np.uint32).copy()
                if first is None:
                    first = arr
                    files["frame0.bin"] = write_file(os.path.join(raw, "frame0.bin"), b)
                else:
                    d = np.nonzero(arr != first)[0].astype(np.uint32)
                    payload = struct.pack("<I", len(d)) + d.tobytes() + arr[d].tobytes()
                    xz = lzma.compress(payload, preset=a.xz_preset)
                    fn = f"w{wi}-{j}.delta.xz"
                    files[fn] = write_file(os.path.join(raw, fn), xz)
                    deltas_bytes += len(xz)
                    if used0 + deltas_bytes + len(b) > budget:
                        stopped = f"H8 budget reached after window {wi} frame {j}"
                        break
                for k, blob in hb.items():
                    heap_series.setdefault(k, []).append(np.frombuffer(blob[: len(blob) // 4 * 4], dtype=np.uint32).copy())
                snaps.append(arr)
                meta.append((wi, t, f0, f1, "torn-possible" if f0 != f1 else "coherent"))
                j += 1
                time.sleep(max(0, 1 / hz - (time.time() - t)))
            series.append(snaps)
            print(f"window {wi}: {len(snaps)} snapshots")
            if stopped:
                print(stopped)
                break
        # --- statistics: verbatim method of captures\002-idle-null\idle_null.py ---
        res = {}
        for wi, snaps in enumerate(series):
            if not snaps:
                continue
            st = np.stack(snaps)
            changed = (st != st[0]).any(axis=0)
            res[f"win{wi}_changed_dwords"] = int(changed.sum())
            res[f"win{wi}_p"] = float(changed.mean())
            res[f"win{wi}_n"] = len(snaps)
        pairs = [(x, y) for x in range(len(series)) for y in range(x + 1, len(series)) if series[x] and series[y]]
        for x, y in pairs:
            d = (series[x][-1] != series[y][-1])
            res[f"AA_{x}v{y}_diff_dwords"] = int(d.sum())
            res[f"AA_{x}v{y}_p"] = float(d.mean())
        allchanged = np.zeros((END - BASE) // 4, dtype=bool)
        for snaps in series:
            if snaps:
                allchanged |= (np.stack(snaps) != snaps[0]).any(axis=0)
        idx = np.nonzero(allchanged)[0]
        runs = runs_of(idx)
        res["churn_runs"] = len(runs)
        res["churn_top_runs"] = [[f"0x{r0:x}", f"0x{r1:x}", n] for r0, r1, n in sorted(runs, key=lambda r: -r[2])[:40]]
        p_all = float(allchanged.mean())
        res["p_union"] = p_all
        res["expected_false_survivors_k5"] = float(len(allchanged) * p_all ** 5)  # H1: N * p^k, k = 5 alternations
        res["hz"] = hz
        res["window_s"] = win
        res["windows"] = len(series)
        res["frames_total"] = sum(len(s) for s in series)
        heap_p = {}
        for k, arrs in heap_series.items():
            if len(arrs) >= 2 and all(len(x) == len(arrs[0]) for x in arrs):
                st = np.stack(arrs)
                ch = (st != st[0]).any(axis=0)
                heap_p[k] = {"dwords": int(len(ch)), "changed": int(ch.sum()), "p": float(ch.mean()), "frames": len(arrs),
                             "owner": next((r["owner"] for r in named if hex(r["base"]) == k), None)}
        fc_first = meta[0][2] if meta else None
        fc_last = meta[-1][3] if meta else None
        pump1 = pump_metric() if pump0 is not None else None
        state = classify_state(fc_first, fc_last, pump0, pump1)
        c1 = canaries()
        frames_meta = [{"window": m[0], "t": m[1], "fc_before": m[2], "fc_after": m[3], "torn": torn_tag(m[2], m[3], state)} for m in meta]
        snap.update({
            "series": res, "canaries_after": c1, "state": state, "canary_verdict": state,
            "frames_meta": frames_meta,
            "torn_possible_frames": sum(1 for m in frames_meta if m["torn"].startswith("torn-possible")),
            "pump_counts": {"before": pump0_all, "after": pump.counts() if pump0 is not None else None},
            "heap_p": heap_p, "files": files,
            "compression": {"xz_preset": a.xz_preset, "delta_bytes_total": deltas_bytes, "frames_stored_as_delta": max(0, res["frames_total"] - 1),
                            "raw_equivalent_bytes": res["frames_total"] * (END - BASE),
                            "ratio": (res["frames_total"] * (END - BASE)) / max(1, deltas_bytes + (END - BASE))},
            "stopped": stopped,
            "pos_control": pos_control_eval(pos_specs, first.tobytes() if first is not None else b"", series[-1][-1].tobytes() if series and series[-1] else b"", allchanged),
            "method": "captures\\002-idle-null\\idle_null.py statistics: per window fraction of dwords changed vs the window's first frame; A/A = last frames of two windows; runs merge dwords <= 8 B apart"})
        summary = f"state {state}; " + ", ".join(f"{k}={v:.3g}" if isinstance(v, float) else f"{k}={v}" for k, v in res.items() if k.endswith("_p") or k.endswith("_n") or k == "churn_runs")
    if pump:
        hooks = {"tool": f"tools/snapshot.py {VERSION} + tools/pump_counter.js", "time_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                 "counters": {"pump_text": (pump.counts()["text"] if pump.info.get("installed") else 0),
                              "pump_other": (pump.counts()["other"] if pump.info.get("installed") else 0)},
                 "hook": pump.info, "capture": a.capture}
        hp = os.path.join(cap, "hooks.json")
        with open(hp, "w", encoding="utf-8") as f:
            json.dump(hooks, f, indent=1)
        snap["hooks_json"] = hp
        pump.close()
    snap["budget"]["raw_bytes_after"] = raw_bytes_used(a.map_root)
    man_path = os.path.join(cap, "manifest.json")
    man = {}
    if os.path.exists(man_path):
        try:
            man = json.load(open(man_path, encoding="utf-8"))
        except ValueError:
            man = {"unparseable_previous": True}
    man["capture"] = a.capture
    man["snapshot"] = snap
    tmp = man_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(man, f, indent=1, default=str)
    os.replace(tmp, man_path)
    back = json.load(open(man_path, encoding="utf-8"))
    assert back["snapshot"]["files"] == files
    bad_pos = [p for p in snap.get("pos_control", []) if not p["pass"]]
    print(f"wrote {os.path.relpath(man_path, a.map_root)}: {len(files)} raw files; {summary}"
          + (f"; G-POS FAIL {bad_pos}" if bad_pos else (f"; G-POS pass {len(snap.get('pos_control', []))}" if pos_specs else "")))
    return 0


def torn_tag(fc_before, fc_after, state):
    """G-TORN. A read whose frame counter did not change is still torn-possible while the sim runs (the counter
    is bumped at the top of the tick in 0x49c920 and the sim writes follow, so a read that fits inside one
    tick can straddle those writes); coherence needs the sim frozen for the whole capture (paused / menu)."""
    if fc_before != fc_after:
        return "torn-possible (tick during the read)"
    if state.startswith("driving"):
        return "torn-possible (sim advancing during the capture)"
    return "coherent (sim frozen for the whole capture; single bulk read)"


def runs_of(idx):
    """cluster changed dword indices into [addr_lo, addr_hi, count] runs (<= 8 B apart, as idle_null.py)"""
    runs = []
    for i in idx:
        addr = BASE + int(i) * 4
        if runs and addr - runs[-1][1] <= 8:
            runs[-1][1] = addr
            runs[-1][2] += 1
        else:
            runs.append([addr, addr, 1])
    return runs


if __name__ == "__main__":
    sys.exit(main())
