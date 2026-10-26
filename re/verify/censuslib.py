r"""censuslib.py - drive verify/census_frames.js against the running sandbox game and write the census outputs.

Built on tools/frida_run.py (its Census class is the model: attach by pid, CModule counters, snapshots to CSV,
G-ATTEST block). frida_run.main() cannot be used as-is because its H0 gate only admits the pristine / pristine+p1
md5s and the sandbox i76.exe is a patched build (md5 4fabc303, binaries\diff-9a232dcc-vs-4fabc303.tsv); this driver
instead checks every hook target's live prologue against the pristine image (ghidra\i76_ref.exe) and refuses the
hook when the bytes differ (a build patch or a proxy detour sits there: e.g. the telemetry export detours the
entries of weapon_FireShot 0x4a6e90 and physics_ApplyCollisionDamage 0x4a7c80).

Outputs under <run dir>:
  census.jsonl             one object per hooked function (section 2.2): addr, name, scenario, frames, calls,
                           frames_with_calls, calls_per_frame_hist, callers {ra: {n, name}}, first_frame, last_frame,
                           pre_window_calls, hook (attached / skipped reason)
  census.series.bin        u16 little-endian, n_functions x cap: calls per sim frame (frame = base_frame + column)
  census.series.json       {base_frame, cap, addrs[], window}
  census\snapshots.csv, counts.csv, targets.csv   tools/frida_run.py-compatible (tools/census_classify.py --dir <run>)
"""
import csv
import hashlib
import json
import os
import struct
import time

from common import FRAME_ADDR, TIME_ADDR, REF_EXE, TEXT_LO, TEXT_HI, VERIFY, log, tools_path

tools_path()
import frida_run  # noqa: E402  (tools/frida_run.py: load_functions_tsv, prologue_hookable, exe_reader)

JS = os.path.join(VERIFY, "census_frames.js")
PROLOGUE_BYTES = 16


class FrameCensus:
    def __init__(self, session, outdir, snapshot_ms=1000, cap=32768):
        self.outdir = outdir
        self.cdir = os.path.join(outdir, "census")
        os.makedirs(self.cdir, exist_ok=True)
        src = open(JS, encoding="utf-8").read()
        self.script_md5 = hashlib.md5(src.encode()).hexdigest()
        self.session = session
        self.script = session.create_script(src)
        self.script.on("message", self.on_message)
        self.script.load()
        self.rpc = self.script.exports_sync
        self.snapshot_ms, self.cap = snapshot_ms, cap
        self.targets = []
        self.errors = []
        self.batch_ms = []
        self.recs = {}
        self.series = {}
        self.snapshots = 0
        self.init_info = None
        self.f_snap = open(os.path.join(self.cdir, "snapshots.csv"), "w", newline="", encoding="utf-8")
        self.w_snap = csv.writer(self.f_snap)
        self.w_snap.writerow(["snap", "t_ms", "frame", "gtime", "final"])
        self.f_counts = open(os.path.join(self.cdir, "counts.csv"), "w", newline="", encoding="utf-8")
        self.w_counts = csv.writer(self.f_counts)

    # ---------------------------------------------------------------- messages
    def on_message(self, m, data):
        if m.get("type") == "error":
            log("census_frames.js ERROR: %s" % m.get("description"))
            self.errors.append({"stage": "runtime", "error": m.get("description"), "stack": m.get("stack")})
            return
        p = m.get("payload", {})
        if p.get("type") == "snap":
            counts = struct.unpack("<%dI" % (len(data) // 4), data)
            self.w_snap.writerow([p["snap"], p["t_ms"], p["frame"], p["gtime"], int(p["final"])])
            self.w_counts.writerow([p["snap"]] + list(counts))
            self.snapshots += 1
            if p["snap"] % 10 == 0 or p["final"]:
                self.f_snap.flush(); self.f_counts.flush()
                log("census snap %d frame=%s gtime=%s fired_total=%d" % (p["snap"], p["frame"], p["gtime"], sum(counts)))
        elif p.get("type") == "rec":
            self.recs[p["idx"]] = p
            self.series[p["idx"]] = bytes(data) if data else b""

    # ---------------------------------------------------------------- targets
    def check_prologues(self, targets, mem):
        """Compare the live first PROLOGUE_BYTES of every target with the pristine image. Sets t['hook'] = 'ok' or a
        skip reason; refused targets are kept in the table (counted, never attached)."""
        ref = frida_run.exe_reader(REF_EXE)
        for t in targets:
            va = t["addr"]
            if not (TEXT_LO <= va < TEXT_HI):
                t["hook"] = "outside .text"
                continue
            live = mem.rd(va, PROLOGUE_BYTES)
            want = ref(va, PROLOGUE_BYTES)
            if live is None:
                t["hook"] = "live read failed"
            elif live != want:
                t["hook"] = "prologue differs from pristine (build patch or proxy detour): live %s ref %s" % (live[:8].hex(), want[:8].hex())
            elif t.get("hookable") != "yes":
                ok, why = frida_run.prologue_hookable(va, REF_EXE)
                t["hook"] = "ok" if ok else "not hookable: " + why
            else:
                t["hook"] = "ok"
        return targets

    def setup(self, targets):
        self.targets = targets
        for t in targets:
            t.setdefault("hook", "ok")
            t["attached"] = False
            t["error"] = ""
        self.init_info = self.rpc.init({"n": len(targets), "frame_addr": "0x%x" % FRAME_ADDR, "time_addr": "0x%x" % TIME_ADDR,
                                        "cap": self.cap, "snapshot_ms": self.snapshot_ms})
        self.w_counts.writerow(["snap"] + ["0x%x" % t["addr"] for t in targets])
        log("census_frames.js init: %s" % json.dumps(self.init_info))
        return self.init_info

    def attach(self, batch_size=50):
        idx = [j for j, t in enumerate(self.targets) if t["hook"] == "ok"]
        for i in range(0, len(idx), batch_size):
            part = idx[i:i + batch_size]
            batch = [[j, "0x%x" % self.targets[j]["addr"]] for j in part]
            t0 = time.perf_counter()
            r = self.rpc.attach(batch)
            ms = (time.perf_counter() - t0) * 1000
            self.batch_ms.append({"from": i, "n": len(batch), "attached": r["attached"], "errors": len(r["errors"]),
                                  "js_ms": r["ms"], "rpc_ms": round(ms, 1)})
            for j in part:
                self.targets[j]["attached"] = True
            for e in r["errors"]:
                self.targets[e["idx"]]["attached"] = False
                self.targets[e["idx"]]["error"] = e["error"]
                self.errors.append({"stage": "attach", "addr": e["addr"], "error": e["error"]})
            log("census attach %d..%d: %d ok, %d errors, %.0f ms" % (i, i + len(batch) - 1, r["attached"], len(r["errors"]), ms))
        return sum(1 for t in self.targets if t["attached"])

    def start(self):
        return self.rpc.start()

    def stop(self):
        r = self.rpc.stop()
        self.f_snap.close(); self.f_counts.close()
        self.stop_info = r
        return r

    def dump(self):
        d = self.rpc.dump()
        for _ in range(100):           # the 'rec' messages arrive asynchronously after the rpc returns
            if len(self.recs) >= len(self.targets):
                break
            time.sleep(0.05)
        d["recs_received"] = len(self.recs)
        self.dump_info = d
        return d

    def detach(self):
        try:
            self.rpc.detach_all()
            return "ok"
        except Exception as e:  # noqa: BLE001
            return repr(e)

    def unload(self):
        try:
            self.script.unload()
        except Exception:  # noqa: BLE001
            pass

    # ---------------------------------------------------------------- outputs
    def write(self, scenario, window, functions, hist_max=64):
        """window = (first_frame, last_frame) of the scenario, inclusive, from the runner's state log. Writes
        census.jsonl, census.series.bin/json, census\\targets.csv; returns the G-ATTEST block."""
        base = self.init_info["base_frame"]
        cap = self.cap
        f0, f1 = window
        frames = (f1 - f0 + 1) if (f0 is not None and f1 is not None and f1 >= f0) else 0
        with open(os.path.join(self.cdir, "targets.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["idx", "addr", "name", "hookable_source", "attached", "error", "fired"])
            for j, t in enumerate(self.targets):
                fired = self.recs.get(j, {}).get("calls", 0)
                w.writerow([j, "0x%x" % t["addr"], t["name"], t.get("source", ""), int(t["attached"]), t["error"] or ("" if t["hook"] == "ok" else t["hook"]), fired])
        n = len(self.targets)
        with open(os.path.join(self.outdir, "census.series.bin"), "wb") as fb:
            for j in range(n):
                s = self.series.get(j, b"")
                fb.write(s if len(s) == 2 * cap else (s + b"\0" * (2 * cap - len(s)))[:2 * cap])
        json.dump({"base_frame": base, "cap": cap, "dtype": "<u2", "addrs": ["0x%x" % t["addr"] for t in self.targets],
                   "window": [f0, f1], "layout": "row j = function j (addrs[j]); column c = sim frame base_frame + c"},
                  open(os.path.join(self.outdir, "census.series.json"), "w", encoding="utf-8"), indent=1)
        nonzero = 0
        with open(os.path.join(self.outdir, "census.jsonl"), "w", encoding="utf-8") as fj:
            for j, t in enumerate(self.targets):
                r = self.recs.get(j, {})
                s = self.series.get(j, b"")
                hist, fwc, win_calls = {}, 0, 0
                if frames and s:
                    lo, hi = f0 - base, f1 - base
                    lo, hi = max(lo, 0), min(hi, cap - 1)
                    if hi >= lo:
                        counts = struct.unpack_from("<%dH" % (hi - lo + 1), s, 2 * lo)
                        for c in counts:
                            if c:
                                fwc += 1
                                win_calls += c
                                b = c if c < hist_max else hist_max
                                hist[str(b) if c < hist_max else "%d+" % hist_max] = hist.get(str(b) if c < hist_max else "%d+" % hist_max, 0) + 1
                    hist["0"] = frames - fwc
                callers = {}
                for ra, cnt in r.get("callers", []):
                    callers["0x%x" % ra] = {"n": cnt, "name": functions.name_for_ra(ra)}
                if r.get("caller_other"):
                    callers["other"] = {"n": r["caller_other"], "name": "(beyond the 8-entry table)"}
                calls = r.get("calls", 0)
                if calls:
                    nonzero += 1
                fj.write(json.dumps({
                    "addr": "0x%x" % t["addr"], "name": t["name"], "scenario": scenario, "frames": frames,
                    "calls": calls, "calls_in_window": win_calls, "frames_with_calls": fwc,
                    "calls_per_frame_hist": hist, "callers": callers,
                    "first_frame": r.get("first_frame") if r.get("have_first") else None,
                    "last_frame": r.get("last_frame") if r.get("have_first") else None,
                    "pre_base_calls": r.get("pre", 0), "overflow_calls": r.get("overflow", 0),
                    "hook": "attached" if t["attached"] else (t["error"] or t["hook"]),
                }) + "\n")
        attached = sum(1 for t in self.targets if t["attached"])
        return {
            "instrument": "verify/census_frames.js", "script_md5": self.script_md5, "cmodule": self.init_info,
            "hooks_requested": len(self.targets), "hooks_attached": attached,
            "hooks_skipped": [{"addr": "0x%x" % t["addr"], "name": t["name"], "reason": t["hook"]} for t in self.targets if t["hook"] != "ok"],
            "attach_errors": [e for e in self.errors if e["stage"] == "attach"],
            "runtime_errors": [e for e in self.errors if e["stage"] != "attach"],
            "attach_batches": self.batch_ms, "snapshot_ms": self.snapshot_ms, "snapshots": self.snapshots,
            "stop": getattr(self, "stop_info", None), "dump": getattr(self, "dump_info", None),
            "window": [f0, f1], "frames_in_window": frames, "hooks_fired_nonzero": nonzero,
            "void": nonzero == 0,
            "method": "CModule on_enter per hook: lock incl calls; u16 per-frame series indexed by *(u32*)0x5a7e1c - base; "
                      "8-entry return-address table; prologue of every target compared with ghidra/i76_ref.exe before hooking",
        }


def pick_pid(name_prefix="i76", require_path="i76-uncap-lab"):
    import psutil
    out = []
    for p in psutil.process_iter(["name", "exe"]):
        n = (p.info["name"] or "").lower()
        e = (p.info["exe"] or "").lower()
        if n.startswith(name_prefix) and require_path in e:
            out.append(p.pid)
    return out
