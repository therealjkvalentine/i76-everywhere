#!/usr/bin/env python3
r"""i76poke.py - write one value into the running game and read it back on three horizons (gates H0, H3).

    python tools\i76poke.py --capture 006-sentinel --va 0x5aab28 --type int32 --value 1234
    python tools\i76poke.py --capture 006-sentinel --chain 0x54a264,0,0x70,0xac --type float --value 12.5
    python tools\i76poke.py --capture test --pid <fake_sim pid> --allow-patched --va 0x5367cc --type int32 --value 7 --restore

Target: a VA (class init/bss, the address is the row) or a root chain `ROOT,OFF1,OFF2,...`: addr = ROOT;
for every OFF: addr = [addr] + OFF (so `[[[0x54a264]]+0x70]`'s field +0xac is `0x54a264,0,0x70,0xac`);
every hop is logged as (source, key, offset) per H6, the resolved absolute addresses are data of this
capture only. Types: int32 | uint32 | float | byte | uint16.

H0: before writing, tools\which_build.py's stamp is taken from the pid (build_stamp + live_extras); the
poke proceeds only when the main-module md5 is 58d9dec0 (pristine+i76fix-p1) or 9a232dcc (pristine) AND
h0_pass is true; anything else is refused with exit 3 unless --allow-patched (the record is then tagged
`patched-build-only`). The stamp is written to captures\<id>\manifest.json ('build' block) when absent.

H3 three horizons (ported from C:\Users\james\i76-uncap-lab\tools\instruments\verify-write.ps1, which read
immediate / +120 ms / +620 ms and printed "WRITE WORKS" / "ENGINE OVERWROTE it" / "PERSISTED" / "WRITE DID NOT
LAND"; here the delays are sim frames counted on 0x5a7e1c, class bss, so the horizons are tick-based per
G-UNITS, and the time-based fallback is used only when the counter does not advance):
    horizon 0  immediate read-back                 != wanted -> re-write with the process suspended (NtSuspendProcess):
               read == wanted while suspended -> `clobbered-per-loop` (the engine rewrites it every loop iteration;
               item 11 DS3D listener; added 2026-09-05, live test pending: the first attempt ran outside a mission), else `did-not-land` (silent write failure: finding, abort)
    horizon 1  after 0x5a7e1c advanced by 1        != wanted -> `clobbered-per-frame`
    horizon 2  after 0x5a7e1c advanced by N (--frames, default 5)   != wanted -> `clobbered-on-event`
    all equal wanted                                            -> `sticks`
If the frame counter never advances within --frame-timeout s (menu, PAUSE_GAME, fake target), the
horizons fall back to +120 ms / +620 ms and the class carries the suffix ` (time-based; sim clock not advancing)`.
Every read-back is a 4-byte ReadProcessMemory (G-TORN: single-dword reads are atomic on x86; chain hops
resolved while the sim runs are tagged torn-possible in the record).

Output: one JSON line appended to captures\<id>\pokes.jsonl (H8; read back after the append) and one
printed line. --restore writes the original value back at the end and reads it back too.
Exit: 0 sticks/clobbered (the write landed), 1 did-not-land, 2 error/unresolvable chain, 3 H0 refused.
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import datetime
import json
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import which_build as wb  # noqa: E402

VERSION = "0.1"
FRAME_COUNTER = 0x5A7E1C  # class bss; incremented inside 0x49c920 (sim clock), 0 in menus (console-smoke)
GAME_TIME = 0x5A7E74      # class bss
PROCESS_VM_READ = 0x10
PROCESS_VM_WRITE = 0x20
PROCESS_VM_OPERATION = 0x08
PROCESS_QUERY_INFORMATION = 0x400
TYPES = {"int32": ("<i", 4), "uint32": ("<I", 4), "float": ("<f", 4), "byte": ("<B", 1), "uint16": ("<H", 2)}

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype = wt.HANDLE
k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
k32.ReadProcessMemory.argtypes = [wt.HANDLE, wt.LPCVOID, wt.LPVOID, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.WriteProcessMemory.argtypes = [wt.HANDLE, wt.LPVOID, wt.LPCVOID, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.CloseHandle.argtypes = [wt.HANDLE]


def rd(h, addr, n):
    buf = ctypes.create_string_buffer(n)
    got = ctypes.c_size_t(0)
    ok = k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, n, ctypes.byref(got))
    return buf.raw[:got.value] if ok else b""


def wr(h, addr, data):
    got = ctypes.c_size_t(0)
    ok = k32.WriteProcessMemory(h, ctypes.c_void_p(addr), data, len(data), ctypes.byref(got))
    return bool(ok), got.value, (0 if ok else ctypes.get_last_error())


def rd_u32(h, addr):
    b = rd(h, addr, 4)
    return struct.unpack("<I", b)[0] if len(b) == 4 else None


def rd_val(h, addr, fmt, n):
    b = rd(h, addr, n)
    return struct.unpack(fmt, b)[0] if len(b) == n else None


def class_of(va):
    if 0x401000 <= va < 0x4bbe55:
        return "text"
    if 0x4bc000 <= va < 0x4bc404:
        return "iat"
    if 0x4bc404 <= va < 0x4c1788:
        return "rdata"
    if 0x4c2000 <= va < 0x501800:
        return "init"
    if 0x501800 <= va < 0x669ef8:
        return "bss"
    return "outside-image"


def resolve_chain(h, spec):
    """ROOT,OFF,... -> (final_addr, hops). hops = [{from, ptr, offset, to, class}]."""
    toks = [int(t.strip(), 0) for t in spec.split(",")]
    addr = toks[0]
    hops = []
    for off in toks[1:]:
        p = rd_u32(h, addr)
        if p is None:
            return None, hops + [{"read_failed_at": hex(addr)}]
        nxt = p + off
        hops.append({"at": hex(addr), "at_class": class_of(addr), "ptr": hex(p), "offset": hex(off), "to": hex(nxt),
                     "to_class": class_of(nxt) if class_of(nxt) != "outside-image" else "heap-off"})
        addr = nxt
        if p == 0:
            return None, hops
    return addr, hops


def wait_frames(h, n, timeout):
    """Block until 0x5a7e1c advanced by >= n; returns (advanced, frames_seen, seconds)."""
    f0 = rd_u32(h, FRAME_COUNTER)
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < timeout:
        f = rd_u32(h, FRAME_COUNTER)
        if f is not None and f0 is not None and f - f0 >= n:
            return True, f - f0, round(time.perf_counter() - t0, 4)
        time.sleep(0.002)
    f = rd_u32(h, FRAME_COUNTER)
    return False, (f - f0) if (f is not None and f0 is not None) else None, round(time.perf_counter() - t0, 4)


def h0_gate(pid, game_dir, allow_patched, capture_dir):
    """which_build stamp of the pid; returns (ok, reason, stamp)."""
    with open(wb.DEFAULT_REF, "rb") as f:
        ref_raw = f.read()
    allow = wb.load_allowlist(wb.DEFAULT_ALLOWLIST) if os.path.exists(wb.DEFAULT_ALLOWLIST) else []
    img = wb.LiveImage(pid)
    try:
        mods = img.modules()
        base = mods[0]["base"] if mods else wb.IMAGE_BASE
        if base != wb.IMAGE_BASE:
            base = wb.IMAGE_BASE  # fake targets map the image at 0x400000 inside a python.exe host
        stamp = wb.build_stamp(img, wb.DEFAULT_REF, ref_raw, game_dir, allow, base, pid=pid, mode="live")
        stamp = wb.live_extras(stamp, img, pid, game_dir)
    finally:
        img.close()
    md5 = stamp.get("exe_md5")
    cls = stamp.get("build_class", "unknown-md5")
    ok = bool(stamp.get("h0_pass")) and md5 in wb.H0_RUNNABLE
    reason = "H0 %s: exe md5 %s (%s), regions %s" % ("PASS" if ok else "FAIL", md5, cls, stamp.get("h0_summary"))
    if not ok and allow_patched:
        reason += "; proceeding under --allow-patched (record tagged patched-build-only)"
    man = os.path.join(capture_dir, "manifest.json")
    if not os.path.exists(man):
        os.makedirs(capture_dir, exist_ok=True)
        wb.write_manifest(man, stamp, None)
    return ok, reason, stamp


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--capture", required=True, help="captures\\<id> (pokes.jsonl and manifest.json live there)")
    ap.add_argument("--pid", type=int)
    ap.add_argument("--name", default="i76_pristine_fix.exe")
    t = ap.add_mutually_exclusive_group(required=True)
    t.add_argument("--va", help="absolute VA (class init/bss)")
    t.add_argument("--chain", help="ROOT,OFF1,OFF2,... root chain (H6)")
    ap.add_argument("--type", default="int32", choices=sorted(TYPES))
    ap.add_argument("--value", required=True, help="int (0x ok) or float")
    ap.add_argument("--frames", type=int, default=5, help="N for the third horizon")
    ap.add_argument("--frame-timeout", type=float, default=2.0, help="seconds to wait for a frame before the time-based fallback")
    ap.add_argument("--restore", action="store_true", help="write the original value back at the end (verify-write.ps1 behaviour)")
    ap.add_argument("--allow-patched", action="store_true")
    ap.add_argument("--game-dir", default=wb.DEFAULT_GAME)
    ap.add_argument("--map-root", default=wb.MAP_ROOT)
    ap.add_argument("--note", default="", help="free text stored in the record (predicted effect, G-POS row, ...)")
    a = ap.parse_args()

    fmt, width = TYPES[a.type]
    if a.type == "float":
        value = float(a.value)
    else:
        value = int(a.value, 0)
    cap_dir = os.path.join(a.map_root, "captures", a.capture)
    pid = a.pid
    if pid is None:
        hits = wb.find_pid_by_name(a.name)
        if len(hits) != 1:
            print("process %s: %d matches %s (use --pid)" % (a.name, len(hits), hits))
            return 2
        pid = hits[0]

    ok, reason, stamp = h0_gate(pid, a.game_dir, a.allow_patched, cap_dir)
    rec = {"tool": "tools/i76poke.py " + VERSION, "time": datetime.datetime.now().isoformat(timespec="seconds"), "pid": pid,
           "exe_md5": stamp.get("exe_md5"), "build_class": stamp.get("build_class"), "h0_pass": stamp.get("h0_pass"),
           "h0": reason, "tag": "patched-build-only" if not ok else stamp.get("build_class"),
           "note": a.note, "method": "WriteProcessMemory + ReadProcessMemory on three horizons (immediate / +1 frame of 0x5a7e1c / +N frames); ported from verify-write.ps1"}
    if not ok and not a.allow_patched:
        rec["result"] = "refused"
        append_record(cap_dir, rec)
        print("REFUSED (H0): %s [pass --allow-patched to poke a patched build; record tagged]" % reason)
        return 3

    h = k32.OpenProcess(PROCESS_VM_READ | PROCESS_VM_WRITE | PROCESS_VM_OPERATION | PROCESS_QUERY_INFORMATION, False, pid)
    if not h:
        print("OpenProcess(%d) failed: win32 error %d" % (pid, ctypes.get_last_error()))
        return 2
    try:
        fc_before = rd_u32(h, FRAME_COUNTER)
        if a.va:
            addr = int(a.va, 16)
            rec["target"] = {"va": hex(addr), "class": class_of(addr)}
        else:
            addr, hops = resolve_chain(h, a.chain)
            rec["target"] = {"chain": a.chain, "hops": hops, "resolved": hex(addr) if addr else None,
                             "class": ("heap-off" if addr and class_of(addr) == "outside-image" else (class_of(addr) if addr else None)),
                             "torn": "torn-possible (hops read while the sim may advance)" if (fc_before or 0) > 0 else "coherent (sim frozen or not started)"}
            if addr is None:
                rec["result"] = "chain-unresolvable"
                append_record(cap_dir, rec)
                print("chain %s unresolvable (null pointer or unreadable hop): %s" % (a.chain, hops))
                return 2
        orig = rd_val(h, addr, fmt, width)
        rec["type"] = a.type
        rec["original"] = orig
        rec["wanted"] = value
        data = struct.pack(fmt, value)
        w_ok, n_written, err = wr(h, addr, data)
        rec["write"] = {"ok": w_ok, "bytes": n_written, "win32_error": err}
        imm = rd_val(h, addr, fmt, width)
        fc_imm = rd_u32(h, FRAME_COUNTER)
        rec["h0_immediate"] = {"value": imm, "frame_counter": fc_imm}

        def same(v):
            if v is None:
                return False
            return abs(v - value) < 1e-6 if a.type == "float" else v == value

        if not same(imm):
            # H3 fourth class (item 11, 009-ds3d-listener): a write that lands and is overwritten by the engine faster
            # than the immediate read (the pause loop rewrites the DS3D listener ~140k times/s). Distinguish it from a
            # silent write failure by repeating the write with every thread of the process suspended: read == wanted
            # under suspension proves the write lands; the first read after resume shows the loop taking it back.
            susp = None
            try:
                nt = ctypes.windll.ntdll
                if nt.NtSuspendProcess(h) == 0:
                    try:
                        w2_ok, n2, err2 = wr(h, addr, data)
                        held = rd_val(h, addr, fmt, width)
                        fc_held = rd_u32(h, FRAME_COUNTER)
                    finally:
                        nt.NtResumeProcess(h)
                    time.sleep(0.02)
                    after = rd_val(h, addr, fmt, width)
                    susp = {"write_ok": w2_ok, "win32_error": err2, "read_while_suspended": held, "frame_counter_suspended": fc_held,
                            "read_20ms_after_resume": after}
                    rec["h0_suspended"] = susp
            except Exception as ex:
                rec["h0_suspended"] = {"error": str(ex)}
            if susp and same(susp.get("read_while_suspended")):
                rec["classification"] = "clobbered-per-loop" if not same(susp.get("read_20ms_after_resume")) else "sticks-after-resume"
                rec["finding"] = ("the write lands (read-back %r with the process suspended) and the engine overwrites it before an "
                                  "immediate read (unsuspended read-back %r): engine-owned, rewritten every loop iteration" % (susp["read_while_suspended"], imm))
                rec["result"] = rec["classification"]
                append_record(cap_dir, rec)
                print("poke %s %s %r (orig %r) -> immediate %r, suspended %r, after resume %r => %s [%s]" % (
                    target_str(rec), a.type, value, orig, imm, susp["read_while_suspended"], susp["read_20ms_after_resume"], rec["classification"], rel(cap_dir, a.map_root)))
                return 0
            rec["classification"] = "did-not-land"
            rec["finding"] = "silent write failure (H3): immediate read-back %r != wanted %r; win32 error %d; suspended re-write %s" % (imm, value, err, susp)
            rec["result"] = "did-not-land"
            append_record(cap_dir, rec)
            print("poke %s %s %r (orig %r) -> immediate %r => did-not-land (write ok=%s err=%d) [%s]" % (
                target_str(rec), a.type, value, orig, imm, w_ok, err, rel(cap_dir, a.map_root)))
            return 1
        adv1, seen1, s1 = wait_frames(h, 1, a.frame_timeout)
        if not adv1:
            time.sleep(0.12)
        v1 = rd_val(h, addr, fmt, width)
        rec["h1_plus_1_frame"] = {"value": v1, "frames_advanced": seen1, "seconds": s1, "frame_advanced": adv1,
                                  "fallback": None if adv1 else "+120 ms (sim clock not advancing)"}
        adv2, seen2, s2 = wait_frames(h, a.frames, a.frame_timeout * max(1, a.frames)) if adv1 else (False, 0, 0.0)
        if not adv2:
            time.sleep(0.5)
        v2 = rd_val(h, addr, fmt, width)
        rec["h2_plus_N_frames"] = {"N": a.frames, "value": v2, "frames_advanced": seen2, "seconds": s2, "frame_advanced": adv2,
                                   "fallback": None if adv2 else "+500 ms after horizon 1 (sim clock not advancing)"}
        if not same(v1):
            cls = "clobbered-per-frame"
        elif not same(v2):
            cls = "clobbered-on-event"
        else:
            cls = "sticks"
        if not adv1:
            cls += " (time-based; sim clock not advancing)"
        rec["classification"] = cls
        rec["frame_counter_before_after"] = [fc_before, rd_u32(h, FRAME_COUNTER)]
        if a.restore and orig is not None:
            r_ok, r_n, r_err = wr(h, addr, struct.pack(fmt, orig))
            back = rd_val(h, addr, fmt, width)
            rec["restore"] = {"ok": r_ok, "win32_error": r_err, "readback": back, "restored": back == orig}
        rec["result"] = "landed"
        append_record(cap_dir, rec)
        print("poke %s %s %r (orig %r) -> immediate %r  +1f %r  +%df %r => %s%s [%s]" % (
            target_str(rec), a.type, value, orig, imm, v1, a.frames, v2, cls,
            ("; restored=%s" % rec["restore"]["restored"]) if "restore" in rec else "", rel(cap_dir, a.map_root)))
        return 0
    finally:
        k32.CloseHandle(h)


def target_str(rec):
    t = rec["target"]
    return t.get("va") or ("%s->%s" % (t.get("chain"), t.get("resolved")))


def rel(p, root):
    try:
        return os.path.relpath(os.path.join(p, "pokes.jsonl"), root)
    except ValueError:
        return os.path.join(p, "pokes.jsonl")


def append_record(cap_dir, rec):
    os.makedirs(cap_dir, exist_ok=True)
    p = os.path.join(cap_dir, "pokes.jsonl")
    line = json.dumps(rec, default=str)
    with open(p, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    with open(p, "r", encoding="utf-8") as f:  # H3: read the append back
        last = f.read().rstrip("\n").split("\n")[-1]
    assert last == line, "pokes.jsonl read-back mismatch"


if __name__ == "__main__":
    sys.exit(main())
