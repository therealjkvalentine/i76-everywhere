#!/usr/bin/env python3
r"""frida_run.py - driver for runbook items 004 (census.js) and 005 (ledger.js). Attaches by pid, NEVER spawns (H10).

    python tools\frida_run.py --name i76_pristine_fix --capture 004-census --census --hooks 200 --seconds 60
    python tools\frida_run.py --name i76_pristine_fix --capture 004-census-all --census --hooks all --seconds 120
    python tools\frida_run.py --name i76_pristine_fix --capture 005-ledger --ledger --seconds 180
    python tools\frida_run.py --pid <notepad pid> --test-target --out-dir <dir> --census --ledger \
        --export-targets ntdll.dll:Rtl:120,kernel32.dll::80 --seconds 10          # mechanics test (no game)

H0 first: the driver runs `which_build.py --pid <pid> --out <capture>\manifest.json --stamp <class>` and refuses
to attach unless the stamp's h0_pass is true (build .text/.rdata identical to pristine except the allowlist).
`--test-target` is the only bypass: it records h0 as bypassed-test-target and REQUIRES --out-dir (never a
captures\<id> directory), so a notepad run can never masquerade as a game capture.

Census targets: symbols\functions.tsv rows with hookable=yes (1,984), first N by address for --hooks N, all
for --hooks all; --include addresses are always added (if absent from the table, or hookable=tbd, the driver
checks the prologue itself with capstone on ghidra\i76_ref.exe: >= 5 B of cleanly decoded, relocatable
instructions). The mandatory include list (0x406ab0, 0x4b6850, 0x445ba0, 0x438630, 0x49c920 and WinMain
0x402b30 = the function enclosing the 0x4039b8 call site) is always applied on a game target.

Outputs under <capture dir>:
  census\snapshots.csv   snap,t_ms,frame,gtime,final           (frame = u32 0x5a7e1c bss, gtime = f32 0x5a7e74 bss)
  census\counts.csv      snap,<addr>,<addr>,...                 cumulative counters per snapshot
  census\targets.csv     idx,addr,name,hookable_source,attached,error,fired
  ledger\records.csv     seq,drain,src,src_name,kind,key,size,extra,result,ra,frame,tid
  ledger\drains.csv      drain,t_ms,frame,gtime,r,w,n,dropped_now,<watch cells>
  ledger\sources.csv     id,name,kind,addr,key_addr,fired,fired_other
  manifest.json          merged: build (which_build), frida.{census,ledger} G-ATTEST blocks
Ctrl-C stops the run cleanly (stop rpc, counters read, manifest written, script unloaded, session detached).
"""
import argparse
import csv
import datetime
import hashlib
import json
import os
import signal
import struct
import subprocess
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
VERSION = "0.1"
TEXT_LO, TEXT_HI = 0x401000, 0x4bbe55
FRAME_ADDR, TIME_ADDR = 0x5a7e1c, 0x5a7e74          # class bss (frame counter u32, game time f32)
MANDATORY_INCLUDE = [0x406ab0, 0x4b6850, 0x445ba0, 0x438630, 0x49c920, 0x402b30]
# 0x402b30 = WinMain, the function enclosing the `call 0x49c920` at 0x4039b8 (functions.tsv: 0x402b30 size 7413)
POOL_WATCH = {"pool_a_base_0x5dd320": 0x5dd320, "pool_b_base_0x5dd324": 0x5dd324, "pool_a_plus54000_0x5dd2ec": 0x5dd2ec,
              "pool_a_vertex_count_0x6442ec": 0x6442ec, "pool_b_bump_ptr_0x654380": 0x654380}   # all class bss
LEDGER_EXPORTS = [  # (id, module, export, kind) - IAT slots in symbols\imports.tsv resolve to these exports
    (1, "kernel32.dll", "HeapCreate", "heap-create"),
    (2, "kernel32.dll", "HeapAlloc", "heap-alloc"),
    (3, "kernel32.dll", "HeapReAlloc", "heap-realloc"),
    (4, "kernel32.dll", "HeapFree", "heap-free"),
    (5, "kernel32.dll", "HeapDestroy", "heap-destroy"),
    (6, "msvcrt.dll", "malloc", "malloc"),
    (7, "msvcrt.dll", "free", "free"),
    (8, "msvcrt.dll", "realloc", "realloc"),
    (9, "msvcrt.dll", "??2@YAPAXI@Z", "new"),
    (10, "msvcrt.dll", "??3@YAXPAX@Z", "delete"),
]
LEDGER_EXE = [  # (id, addr, name, kind, key_addr) - class init (.text)
    (11, 0x498940, "pool_Reserve", "pool-reserve", None),
    (12, 0x498a00, "pool_Free", "pool-free", None),
]
STOP = threading.Event()


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(msg):
    print("[%s] %s" % (time.strftime("%H:%M:%S"), msg), flush=True)


# ------------------------------------------------------------------ targets
def load_functions_tsv(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            parts = line.rstrip("\n").split("\t")
            if parts[0] == "addr":
                continue
            rows.append({"addr": int(parts[0], 16), "size": int(parts[1]), "name": parts[2], "status": parts[3],
                         "hookable": parts[6] if len(parts) > 6 else ""})
    return rows


_pe_reader = None


def exe_reader(exe):
    global _pe_reader
    if _pe_reader is None:
        import pefile
        pe = pefile.PE(exe)
        data = open(exe, "rb").read()
        secs = [(0x400000 + s.VirtualAddress, 0x400000 + s.VirtualAddress + max(s.Misc_VirtualSize, s.SizeOfRawData),
                 s.PointerToRawData) for s in pe.sections]

        def rd(va, n):
            for lo, hi, raw in secs:
                if lo <= va < hi:
                    return data[raw + (va - lo): raw + (va - lo) + n]
            return b""
        _pe_reader = rd
    return _pe_reader


def prologue_hookable(va, exe):
    """Task 2 rule, first-5-bytes part: instructions covering [va, va+5) decode cleanly and carry no rel8/rel32
    branch and no ret (Frida relocates them into the trampoline). Branch targets into [va+1, va+4] are not
    checked here (that needs the whole-image flow set: hookability.py)."""
    from capstone import Cs, CS_ARCH_X86, CS_MODE_32, CS_GRP_JUMP, CS_GRP_CALL, CS_GRP_RET, CS_GRP_BRANCH_RELATIVE
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True
    b = exe_reader(exe)(va, 16)
    if len(b) < 16:
        return False, "no file bytes at %#x" % va
    covered = 0
    insns = []
    for i in md.disasm(b, va):
        insns.append("%s %s" % (i.mnemonic, i.op_str))
        groups = set(i.groups)
        if CS_GRP_BRANCH_RELATIVE in groups or CS_GRP_JUMP in groups or CS_GRP_CALL in groups or CS_GRP_RET in groups:
            return False, "branch/ret in first 5 B: %s" % "; ".join(insns)
        covered += i.size
        if covered >= 5:
            return True, "prologue %d B: %s" % (covered, "; ".join(insns))
    return False, "decode failed before 5 B: %s" % "; ".join(insns)


def build_census_targets(a):
    """Returns list of dicts {addr, name, source} in attach order."""
    rows = load_functions_tsv(os.path.join(ROOT, "symbols", "functions.tsv"))
    by_addr = {r["addr"]: r for r in rows}
    hookable = [r for r in rows if r["hookable"] == "yes"]
    hookable.sort(key=lambda r: r["addr"])
    includes = []
    if not a.test_target:
        includes += MANDATORY_INCLUDE
    for s in (a.include or "").split(","):
        s = s.strip()
        if s:
            includes.append(int(s, 16))
    if a.include_file:
        for line in open(a.include_file, encoding="utf-8"):
            line = line.split("#")[0].strip()
            if line:
                includes.append(int(line, 16))
    targets, seen = [], set()
    exe = os.path.join(ROOT, "ghidra", "i76_ref.exe")
    for va in includes:
        if va in seen:
            continue
        r = by_addr.get(va)
        if r and r["hookable"] == "yes":
            src = "functions.tsv hookable=yes"
        else:
            ok, why = prologue_hookable(va, exe)
            if not ok:
                log("include %#x REFUSED: %s" % (va, why))
                continue
            src = ("functions.tsv hookable=%s; " % (r["hookable"] if r else "absent")) + "capstone " + why
        targets.append({"addr": va, "name": r["name"] if r else "unlisted_%08x" % va, "source": src})
        seen.add(va)
    n = len(hookable) if a.hooks == "all" else int(a.hooks)
    for r in hookable:
        if len(targets) >= n + len(includes):
            break
        if r["addr"] in seen:
            continue
        targets.append({"addr": r["addr"], "name": r["name"], "source": "functions.tsv hookable=yes"})
        seen.add(r["addr"])
    return targets


def build_ledger_sources(a, script_resolve):
    """Returns (list of hook dicts for ledger.js, list of unresolved)."""
    hooks, unresolved = [], []
    for sid, mod, name, kind in LEDGER_EXPORTS:
        addr = script_resolve(mod, name)
        if addr is None:
            unresolved.append({"id": sid, "name": "%s!%s" % (mod, name), "error": "export not found (module not loaded?)"})
            continue
        hooks.append({"id": sid, "name": "%s!%s" % (mod, name), "addr": addr, "kind": kind, "key_addr": None})
    if not a.test_target:
        for sid, va, name, kind, key in LEDGER_EXE:
            hooks.append({"id": sid, "name": name, "addr": "0x%x" % va, "kind": kind, "key_addr": ("0x%x" % key) if key else None})
        # every heap_<handle>_alloc wrapper in functions.tsv: key = the heap handle global it names
        sid = 20
        for r in load_functions_tsv(os.path.join(ROOT, "symbols", "functions.tsv")):
            nm = r["name"]
            if nm.startswith("heap_") and nm.endswith("_alloc") and r["hookable"] == "yes":
                handle = nm[len("heap_"):-len("_alloc")]
                try:
                    key = int(handle, 16)
                except ValueError:
                    continue
                hooks.append({"id": sid, "name": nm, "addr": "0x%x" % r["addr"], "kind": "wrapper-alloc", "key_addr": "0x%x" % key})
                sid += 1
    return hooks, unresolved


# ------------------------------------------------------------------ H0
def run_which_build(pid, manifest_path, stamp):
    cmd = [sys.executable, os.path.join(TOOLS, "which_build.py"), "--pid", str(pid), "--out", manifest_path]
    if stamp:
        cmd += ["--stamp", stamp]
    log("H0: " + " ".join(cmd))
    p = subprocess.run(cmd, capture_output=True, text=True)
    h0 = {"command": cmd, "exit_code": p.returncode, "h0_pass": None, "build_class": None, "exe_md5": None}
    try:
        man = json.load(open(manifest_path, encoding="utf-8"))
        b = man.get("build", {})
        h0["h0_pass"] = b.get("h0_pass")
        h0["build_class"] = b.get("build_class")
        h0["exe_md5"] = b.get("exe_md5")
        h0["h0_summary"] = b.get("h0_summary")
    except Exception as e:  # noqa: BLE001
        h0["error"] = "manifest unreadable after which_build: %r" % (e,)
    tail = (p.stdout or "").strip().splitlines()
    h0["stdout_tail"] = tail[-6:]
    if p.stderr.strip():
        h0["stderr_tail"] = p.stderr.strip().splitlines()[-6:]
    return h0


def merge_manifest(path, key, block):
    man = {}
    if os.path.exists(path):
        try:
            man = json.load(open(path, encoding="utf-8"))
        except ValueError:
            man = {"unparseable_previous": True}
    man[key] = block
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(man, f, indent=1, default=str)
    os.replace(tmp, path)
    back = json.load(open(path, encoding="utf-8"))
    assert back[key] == json.loads(json.dumps(block, default=str)), "manifest read-back mismatch"


def md5_file(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()


# ------------------------------------------------------------------ census
class Census:
    def __init__(self, session, a, outdir):
        self.a, self.outdir = a, outdir
        os.makedirs(outdir, exist_ok=True)
        src = open(os.path.join(TOOLS, "census.js"), encoding="utf-8").read()
        self.script_md5 = hashlib.md5(src.encode()).hexdigest()
        self.script = session.create_script(src)
        self.script.on("message", self.on_message)
        self.script.load()
        self.rpc = self.script.exports_sync
        self.targets = []
        self.snapshots = 0
        self.errors = []
        self.batch_ms = []
        self.f_snap = open(os.path.join(outdir, "snapshots.csv"), "w", newline="", encoding="utf-8")
        self.w_snap = csv.writer(self.f_snap)
        self.w_snap.writerow(["snap", "t_ms", "frame", "gtime", "final"])
        self.f_counts = open(os.path.join(outdir, "counts.csv"), "w", newline="", encoding="utf-8")
        self.w_counts = csv.writer(self.f_counts)
        self.last_counts = None
        self.init_info = None

    def on_message(self, m, data):
        if m.get("type") == "error":
            log("census.js ERROR: %s" % m.get("description"))
            self.errors.append({"stage": "runtime", "error": m.get("description"), "stack": m.get("stack")})
            return
        p = m.get("payload", {})
        if p.get("type") == "snap":
            counts = struct.unpack("<%dI" % (len(data) // 4), data)
            self.w_snap.writerow([p["snap"], p["t_ms"], p["frame"], p["gtime"], int(p["final"])])
            self.w_counts.writerow([p["snap"]] + list(counts))
            self.last_counts = counts
            self.snapshots += 1
            if p["snap"] % 10 == 0 or p["final"]:
                self.f_snap.flush(); self.f_counts.flush()
                log("census snap %d frame=%s gtime=%s fired_total=%d" % (p["snap"], p["frame"], p["gtime"], sum(counts)))

    def setup(self, targets, frame_addr, time_addr):
        self.targets = targets
        self.init_info = self.rpc.init({"n": len(targets), "frame_addr": ("0x%x" % frame_addr) if frame_addr else None,
                                        "time_addr": ("0x%x" % time_addr) if time_addr else None,
                                        "snapshot_ms": self.a.snapshot_ms})
        self.w_counts.writerow(["snap"] + ["0x%x" % t["addr"] for t in targets])
        log("census.js init: %s" % json.dumps(self.init_info))

    def attach(self, batch_size):
        for t in self.targets:
            t["attached"] = False; t["error"] = ""
        for i in range(0, len(self.targets), batch_size):
            batch = [[j, "0x%x" % self.targets[j]["addr"]] for j in range(i, min(i + batch_size, len(self.targets)))]
            t0 = time.perf_counter()
            r = self.rpc.attach(batch)
            ms = (time.perf_counter() - t0) * 1000
            self.batch_ms.append({"from": i, "n": len(batch), "attached": r["attached"], "errors": len(r["errors"]),
                                  "js_ms": r["ms"], "rpc_ms": round(ms, 1)})
            for j in range(i, i + len(batch)):
                self.targets[j]["attached"] = True
            for e in r["errors"]:
                self.targets[e["idx"]]["attached"] = False
                self.targets[e["idx"]]["error"] = e["error"]
                self.errors.append({"stage": "attach", "addr": e["addr"], "error": e["error"]})
            log("census attach batch %d..%d: %d ok, %d errors, %.0f ms (js %d ms)" % (
                i, i + len(batch) - 1, r["attached"], len(r["errors"]), ms, r["ms"]))
            if STOP.is_set():
                break

    def start(self):
        return self.rpc.start()

    def stop(self):
        r = self.rpc.stop()
        counts = self.rpc.counters()
        for j, t in enumerate(self.targets):
            t["fired"] = counts[j]
        self.f_snap.close(); self.f_counts.close()
        with open(os.path.join(self.outdir, "targets.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["idx", "addr", "name", "hookable_source", "attached", "error", "fired"])
            for j, t in enumerate(self.targets):
                w.writerow([j, "0x%x" % t["addr"], t["name"], t["source"], int(t["attached"]), t["error"], t["fired"]])
        attached = sum(1 for t in self.targets if t["attached"])
        attest = {  # G-ATTEST
            "instrument": "tools/census.js", "script_md5": self.script_md5, "cmodule": self.init_info,
            "hooks_requested": len(self.targets), "hooks_attached": attached,
            "attach_errors": [e for e in self.errors if e["stage"] == "attach"],
            "runtime_errors": [e for e in self.errors if e["stage"] != "attach"],
            "attach_batches": self.batch_ms,
            "attach_ms_total": round(sum(b["rpc_ms"] for b in self.batch_ms), 1),
            "snapshot_ms": self.a.snapshot_ms, "snapshots": r["snapshots"], "seconds": round(r["seconds"], 2),
            "fired_total": r["fired_total"], "hooks_fired_nonzero": r["hooks_fired_nonzero"],
            "hooks_fired_zero": attached - r["hooks_fired_nonzero"],
            "void": r["fired_total"] == 0,
            "method": "CModule lock-incl counter per hook (Interceptor.attach, onEnter only); counters + 0x5a7e1c/0x5a7e74 read every snapshot_ms; a run with fired_total 0 is void (G-ATTEST)",
            "files": {"snapshots.csv": "snap,t_ms,frame,gtime,final", "counts.csv": "cumulative counters per snapshot, columns = target addr",
                      "targets.csv": "idx,addr,name,hookable_source,attached,error,fired"},
        }
        try:
            self.rpc.detach_all()
        except Exception as e:  # noqa: BLE001
            attest["detach_error"] = repr(e)
        return attest

    def unload(self):
        try:
            self.script.unload()
        except Exception:  # noqa: BLE001
            pass


# ------------------------------------------------------------------ ledger
REC_FMT = "<9I"
REC_SIZE = struct.calcsize(REC_FMT)


class Ledger:
    def __init__(self, session, a, outdir):
        self.a, self.outdir = a, outdir
        os.makedirs(outdir, exist_ok=True)
        src = open(os.path.join(TOOLS, "ledger.js"), encoding="utf-8").read()
        self.script_md5 = hashlib.md5(src.encode()).hexdigest()
        self.script = session.create_script(src)
        self.script.on("message", self.on_message)
        self.script.load()
        self.rpc = self.script.exports_sync
        self.errors = []
        self.sources = {}
        self.records = 0
        self.drains = 0
        self.watch_names = []
        self.f_rec = open(os.path.join(outdir, "records.csv"), "w", newline="", encoding="utf-8")
        self.w_rec = csv.writer(self.f_rec)
        self.w_rec.writerow(["seq", "drain", "src", "src_name", "kind", "key", "size", "extra", "result", "ra", "frame", "tid"])
        self.f_dr = open(os.path.join(outdir, "drains.csv"), "w", newline="", encoding="utf-8")
        self.w_dr = csv.writer(self.f_dr)
        self.init_info = None

    def on_message(self, m, data):
        if m.get("type") == "error":
            log("ledger.js ERROR: %s" % m.get("description"))
            self.errors.append({"stage": "runtime", "error": m.get("description"), "stack": m.get("stack")})
            return
        p = m.get("payload", {})
        if p.get("type") != "led":
            return
        self.w_dr.writerow([p["drain"], p["t_ms"], p["frame"], p["gtime"], p["r"], p["w"], p["n"], p["dropped_now"]] + list(p["watch"]))
        self.drains += 1
        if data:
            n = len(data) // REC_SIZE
            for i in range(n):
                seq, src, key, size, extra, result, ra, frame, tid = struct.unpack_from(REC_FMT, data, i * REC_SIZE)
                s = self.sources.get(src, {"name": "?", "kind": "?"})
                self.w_rec.writerow([seq, p["drain"], src, s["name"], s["kind"], "0x%x" % key, size, "0x%x" % extra,
                                     "0x%x" % result, "0x%x" % ra, frame, tid])
            self.records += n
        if p["drain"] % 20 == 0 or p["final"]:
            self.f_rec.flush(); self.f_dr.flush()
            log("ledger drain %d frame=%s records=%d dropped_now=%d watch=%s" % (p["drain"], p["frame"], self.records, p["dropped_now"], p["watch"]))

    def setup(self, frame_addr, time_addr, watch, only_text):
        self.watch_names = list(watch.keys())
        self.w_dr.writerow(["drain", "t_ms", "frame", "gtime", "r", "w", "n", "dropped_now"] + self.watch_names)
        self.init_info = self.rpc.init({"frame_addr": ("0x%x" % frame_addr) if frame_addr else None,
                                        "time_addr": ("0x%x" % time_addr) if time_addr else None,
                                        "ring_records": self.a.ring_records, "drain_ms": self.a.drain_ms,
                                        "only_text": bool(only_text), "text_lo": "0x%x" % TEXT_LO, "text_hi": "0x%x" % TEXT_HI,
                                        "watch": ["0x%x" % v for v in watch.values()]})
        log("ledger.js init: %s" % json.dumps(self.init_info))

    def hook(self, hooks, unresolved):
        for h in hooks:
            self.sources[h["id"]] = h
        self.unresolved = unresolved
        t0 = time.perf_counter()
        r = self.rpc.hook(hooks)
        self.hook_ms = round((time.perf_counter() - t0) * 1000, 1)
        for e in r["errors"]:
            self.errors.append({"stage": "attach", "id": e["id"], "addr": e["addr"], "error": e["error"]})
        for u in unresolved:
            self.errors.append({"stage": "resolve", "id": u["id"], "name": u["name"], "error": u["error"]})
        log("ledger hooks: %d attached, %d errors, %d unresolved, %.0f ms" % (r["attached"], len(r["errors"]), len(unresolved), self.hook_ms))
        return r

    def start(self):
        return self.rpc.start()

    def stop(self):
        r = self.rpc.stop()
        self.f_rec.close(); self.f_dr.close()
        with open(os.path.join(self.outdir, "sources.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["id", "name", "kind", "addr", "key_addr", "fired", "fired_other"])
            for s in r["fired"]:
                h = self.sources.get(s["id"], {})
                w.writerow([s["id"], s["name"], s["kind"], s["addr"], h.get("key_addr") or "", s["fired"], s["fired_other"]])
        fired_total = sum(s["fired"] for s in r["fired"])
        attest = {  # G-ATTEST
            "instrument": "tools/ledger.js", "script_md5": self.script_md5, "cmodule": self.init_info,
            "hooks_requested": len(self.sources) + len(self.unresolved), "hooks_attached": len(r["fired"]),
            "attach_errors": [e for e in self.errors if e["stage"] in ("attach", "resolve")],
            "runtime_errors": [e for e in self.errors if e["stage"] == "runtime"],
            "hook_ms": self.hook_ms, "drain_ms": self.a.drain_ms, "ring_records": self.a.ring_records,
            "drains": r["drains"], "records_written": r["written"], "records_dropped_ring_overflow": r["dropped"],
            "ring_w": r["ring_w"], "seconds": round(r["seconds"], 2),
            "fired": r["fired"], "fired_total": fired_total,
            "hooks_fired_nonzero": sum(1 for s in r["fired"] if s["fired"] > 0),
            "void": fired_total == 0,
            "watch_cells": self.watch_names,
            "method": "CModule on_enter/on_leave per hook; 36-B records {seq,src,key,size,extra,result,ra,frame,tid} in a lock-xadd ring drained every drain_ms; only_text drops records whose return address is outside .text 0x401000-0x4bbe55 (counted in fired_other); frame = *(u32*)0x5a7e1c at on_leave",
            "files": {"records.csv": "seq,drain,src,src_name,kind,key,size,extra,result,ra,frame,tid", "drains.csv": "drain,t_ms,frame,gtime,r,w,n,dropped_now,<watch>",
                      "sources.csv": "id,name,kind,addr,key_addr,fired,fired_other"},
        }
        try:
            self.rpc.detach_all()
        except Exception as e:  # noqa: BLE001
            attest["detach_error"] = repr(e)
        return attest

    def unload(self):
        try:
            self.script.unload()
        except Exception:  # noqa: BLE001
            pass


# ------------------------------------------------------------------ main
def find_pid(name):
    import psutil
    return [p.pid for p in psutil.process_iter(["name"]) if (p.info["name"] or "").lower().startswith(name.lower())]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--pid", type=int)
    g.add_argument("--name", help="process image name prefix (exactly one match required)")
    ap.add_argument("--capture", help="capture id -> captures\\<id>\\ (game runs)")
    ap.add_argument("--out-dir", help="explicit output directory (required with --test-target)")
    ap.add_argument("--census", action="store_true")
    ap.add_argument("--ledger", action="store_true")
    ap.add_argument("--hooks", default="200", help="200 | all | N (census)")
    ap.add_argument("--include", help="comma-separated hex addresses always hooked (census)")
    ap.add_argument("--include-file", help="file of hex addresses, one per line")
    ap.add_argument("--batch", type=int, default=200, help="hooks per Interceptor transaction (census)")
    ap.add_argument("--snapshot-ms", type=int, default=1000)
    ap.add_argument("--drain-ms", type=int, default=250)
    ap.add_argument("--ring-records", type=int, default=65536)
    ap.add_argument("--seconds", type=float, default=0, help="run time; 0 = until Ctrl-C")
    ap.add_argument("--stamp", default="pristine+i76fix-p1", help="build class passed to which_build.py --stamp")
    ap.add_argument("--frame-addr", default="0x%x" % FRAME_ADDR)
    ap.add_argument("--time-addr", default="0x%x" % TIME_ADDR)
    ap.add_argument("--no-only-text", action="store_true", help="ledger: keep records from every module")
    ap.add_argument("--test-target", action="store_true", help="throwaway 32-bit process (notepad): bypass H0, synthetic targets")
    ap.add_argument("--export-targets", default="ntdll.dll:Rtl:120,kernel32.dll::80", help="test: module:prefix:n,...")
    ap.add_argument("--test-tick-ms", type=int, default=50)
    ap.add_argument("--test-allocs", type=int, default=200)
    a = ap.parse_args()
    if not (a.census or a.ledger):
        ap.error("nothing to do: pass --census and/or --ledger")
    if a.test_target:
        if not a.out_dir or os.path.abspath(a.out_dir).lower().startswith(os.path.join(ROOT, "captures").lower()):
            ap.error("--test-target requires --out-dir outside captures\\")
        outdir = os.path.abspath(a.out_dir)
    else:
        if not a.capture:
            ap.error("--capture <id> is required for a game run")
        outdir = a.out_dir or os.path.join(ROOT, "captures", a.capture)
    os.makedirs(outdir, exist_ok=True)
    import frida
    import psutil
    pid = a.pid
    if pid is None:
        pids = find_pid(a.name)
        if len(pids) != 1:
            print("process %s: %d matches %s (need exactly one; use --pid)" % (a.name, len(pids), pids))
            return 2
        pid = pids[0]
    exe = psutil.Process(pid).exe()
    exe_md5 = md5_file(exe) if os.path.exists(exe) else None
    print("launched %s md5 %s tools/frida_run.py %s (frida %s; attach pid %d, never spawn)" % (exe, exe_md5, VERSION, frida.__version__, pid))
    manifest = os.path.join(outdir, "manifest.json")

    # H0 gate
    h0 = run_which_build(pid, manifest, a.stamp)
    if a.test_target:
        h0["bypassed"] = "test-target: throwaway process, H0 not applicable; outputs are NOT a game capture"
        log("H0 bypassed (test target): which_build h0_pass=%s build_class=%s" % (h0["h0_pass"], h0["build_class"]))
    elif h0["h0_pass"] is not True:
        log("H0 FAIL: refusing to attach (h0_pass=%s, build_class=%s, exit=%s). See %s" % (h0["h0_pass"], h0["build_class"], h0["exit_code"], manifest))
        merge_manifest(manifest, "frida", {"tool": "tools/frida_run.py " + VERSION, "refused": "H0 FAIL", "h0": h0, "time_utc": utc_now()})
        return 1
    else:
        log("H0 PASS: build_class=%s exe_md5=%s" % (h0["build_class"], h0["exe_md5"]))

    frame_addr = int(a.frame_addr, 16) if a.frame_addr not in ("", "none", "0") else None
    time_addr = int(a.time_addr, 16) if a.time_addr not in ("", "none", "0") else None
    frida_block = {"tool": "tools/frida_run.py " + VERSION, "frida": frida.__version__, "python": sys.version.split()[0],
                   "pid": pid, "exe": exe, "exe_md5": exe_md5, "time_start_utc": utc_now(), "h0": h0,
                   "args": vars(a), "test_target": a.test_target}
    signal.signal(signal.SIGINT, lambda *_: STOP.set())
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, lambda *_: STOP.set())   # Ctrl-Break / CTRL_BREAK_EVENT from a parent
    session = frida.attach(pid)
    frida_block["attach"] = "ok"
    census = ledger = None
    test_info = {}
    try:
        if a.census:
            census = Census(session, a, os.path.join(outdir, "census"))
            if a.test_target:
                specs = []
                for spec in a.export_targets.split(","):
                    mod, prefix, n = spec.split(":")
                    specs.append([mod, prefix, int(n)])
                picked = census.rpc.pick_exports(specs)
                targets = [{"addr": int(p["addr"], 16), "name": p["name"], "source": "test: exported function of " + p["module"]} for p in picked]
                # positive controls (G-POS): three functions driven by the synthetic tick at known rates
                k32 = "kernel32.dll"
                ctrl = {"per_tick": ("GetTickCount", k32), "per_frame_x3": ("GetCurrentProcessId", k32), "event": ("GetCurrentThreadId", k32)}
                ctrl_addr = {}
                for role, (name, mod) in ctrl.items():
                    addr = census.rpc.pick_exports([[mod, name, 1]])[0]
                    ctrl_addr[role] = addr["addr"]
                    if not any(t["addr"] == int(addr["addr"], 16) for t in targets):
                        targets.append({"addr": int(addr["addr"], 16), "name": addr["name"], "source": "test: positive control " + role})
                test_info["controls"] = {k: {"addr": v, "name": ctrl[k][0]} for k, v in ctrl_addr.items()}
                # overhead probe: bench before hooking
                b0 = census.rpc.bench(ctrl_addr["per_tick"], 200000)
                test_info["bench_unhooked"] = b0
            else:
                targets = build_census_targets(a)
            log("census targets: %d" % len(targets))
            census.setup(targets, frame_addr, time_addr)
            census.attach(a.batch)
            if a.test_target:
                b1 = census.rpc.bench(ctrl_addr["per_tick"], 200000)
                test_info["bench_hooked"] = b1
                test_info["hook_overhead_ns_per_call"] = round((b1["ms"] - b0["ms"]) * 1e6 / b1["n"], 1)
                test_info["bench_method"] = "NativeFunction loop of n calls to the per_tick control before and after hooking; difference / n; the NativeFunction call cost itself cancels"
                census.rpc.reset()
                ts = census.rpc.test_setup({"tick_ms": a.test_tick_ms, "per_tick": ctrl_addr["per_tick"],
                                            "per_frame_x3": ctrl_addr["per_frame_x3"], "event": ctrl_addr["event"], "event_every": 45})
                test_info["synthetic_tick"] = ts
                frame_addr, time_addr = int(ts["frame_addr"], 16), int(ts["time_addr"], 16)
                log("test: synthetic tick every %d ms; frame cell %s; overhead %s ns/call" % (a.test_tick_ms, ts["frame_addr"], test_info["hook_overhead_ns_per_call"]))
        if a.ledger:
            ledger = Ledger(session, a, os.path.join(outdir, "ledger"))
            watch = {} if a.test_target else dict(POOL_WATCH)
            ledger.setup(frame_addr, time_addr, watch, only_text=not (a.no_only_text or a.test_target))
            hooks, unresolved = build_ledger_sources(a, ledger.rpc.resolve_export)
            ledger.hook(hooks, unresolved)
        if census:
            census.start()
        if ledger:
            ledger.start()
            if a.test_target:
                test_info["test_alloc"] = ledger.rpc.test_alloc(a.test_allocs)
        t0 = time.time()
        log("running%s; Ctrl-C to stop" % (" for %.0f s" % a.seconds if a.seconds else ""))
        second_alloc_done = False
        while not STOP.is_set():
            if a.seconds and time.time() - t0 >= a.seconds:
                break
            time.sleep(0.2)
            if a.test_target and ledger and not second_alloc_done and time.time() - t0 >= 6:
                test_info["test_alloc_2_at_s"] = round(time.time() - t0, 1)   # after a ledger_mark.py marker at ~4 s
                test_info["test_alloc_2"] = ledger.rpc.test_alloc(a.test_allocs)
                second_alloc_done = True
            if session.is_detached:
                frida_block["target_detached"] = "session detached (process exited or crashed) after %.1f s" % (time.time() - t0)
                log(frida_block["target_detached"])
                break
    finally:
        if not session.is_detached:
            # stop both before unloading either: in test mode the ledger reads the census script's frame cell
            if census:
                try:
                    frida_block["census"] = census.stop()
                except Exception as e:  # noqa: BLE001
                    frida_block["census_stop_error"] = repr(e)
            if ledger:
                try:
                    frida_block["ledger"] = ledger.stop()
                except Exception as e:  # noqa: BLE001
                    frida_block["ledger_stop_error"] = repr(e)
            if census:
                census.unload()
            if ledger:
                ledger.unload()
            try:
                session.detach()
                frida_block["detach"] = "ok"
            except Exception as e:  # noqa: BLE001
                frida_block["detach"] = repr(e)
        else:
            for obj in (census, ledger):
                if obj:
                    for f in ("f_snap", "f_counts", "f_rec", "f_dr"):
                        if hasattr(obj, f):
                            getattr(obj, f).close()
        if test_info:
            frida_block["test"] = test_info
        frida_block["time_end_utc"] = utc_now()
        frida_block["stopped_by"] = "ctrl-c" if STOP.is_set() else "timer"
        merge_manifest(manifest, "frida", frida_block)
        log("manifest written (read back OK): %s" % manifest)
        for k in ("census", "ledger"):
            if k in frida_block:
                b = frida_block[k]
                log("%s: hooks %d/%d attached, fired_total %d, nonzero %d, void=%s" % (
                    k, b["hooks_attached"], b["hooks_requested"], b["fired_total"], b["hooks_fired_nonzero"], b["void"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
