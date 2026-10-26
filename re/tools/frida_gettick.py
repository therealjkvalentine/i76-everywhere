#!/usr/bin/env python3
r"""frida_gettick.py - Task 1 smoke: attach (never spawn, H10) to the running game and hook only GetTickCount.

    python tools\frida_gettick.py --name i76_pristine_fix [--pid N] [--seconds 10] [--out captures\000-live-check\frida-gettick.json]
    python tools\frida_gettick.py --pid <notepad pid> --seconds 3          # environment check (as Task 6 did)

Hooks kernel32!GetTickCount (the function the IAT slot 0x4bc100 resolves to; class iat) and counts the calls
whose return address lies in the exe's .text 0x401000-0x4bbe55 (the sites gate C counts: 9 call + 1 load in
7 functions) separately from calls made by other modules. Method: Interceptor.attach on the export; per call
the return address is bucketed into text / other. Writes the counts (+ the per-site histogram for .text) as
JSON; nothing else is touched in the process. Records the H0 identity of the target's main module file.
"""
import argparse
import hashlib
import json
import os
import sys
import time

SCRIPT = r"""
var lo = ptr('0x401000'), hi = ptr('0x4bbe55');
var text = 0, other = 0, sites = {};
var addr = Process.getModuleByName('kernel32.dll').getExportByName('GetTickCount');
send({gettickcount: addr.toString(), arch: Process.arch});
Interceptor.attach(addr, {
  onEnter: function (args) {
    var ra = this.returnAddress;
    if (ra.compare(lo) >= 0 && ra.compare(hi) < 0) { text++; var k = ra.toString(); sites[k] = (sites[k] || 0) + 1; }
    else other++;
  }
});
rpc.exports = { counts: function () { return {text: text, other: other, sites: sites}; } };
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int)
    ap.add_argument("--name", default="i76_pristine_fix")
    ap.add_argument("--seconds", type=float, default=10.0)
    ap.add_argument("--out")
    a = ap.parse_args()
    import frida
    import psutil
    pid = a.pid
    if pid is None:
        pids = [p.pid for p in psutil.process_iter(["name"]) if (p.info["name"] or "").lower().startswith(a.name.lower())]
        if len(pids) != 1:
            print(f"process {a.name}: {len(pids)} matches {pids} (need exactly one; use --pid)")
            return 2
        pid = pids[0]
    exe = psutil.Process(pid).exe()
    exe_md5 = hashlib.md5(open(exe, "rb").read()).hexdigest() if os.path.exists(exe) else None
    print(f"attach pid {pid} exe {exe} md5 {exe_md5} tools/frida_gettick.py 0.1 (frida {frida.__version__})")
    session = frida.attach(pid)
    msgs = []
    script = session.create_script(SCRIPT)
    script.on("message", lambda m, d: msgs.append(m.get("payload", m)))
    script.load()
    if not msgs or not isinstance(msgs[0], dict) or "gettickcount" not in msgs[0]:
        print(f"hook did not install: {msgs}")
        session.detach()
        return 1
    t0 = time.time()
    time.sleep(a.seconds)
    counts = script.exports_sync.counts()
    elapsed = time.time() - t0
    script.unload()
    session.detach()
    rec = {"tool": "tools/frida_gettick.py 0.1", "frida": frida.__version__, "pid": pid, "exe": exe, "exe_md5": exe_md5,
           "hook": msgs[0] if msgs else None, "seconds": round(elapsed, 2),
           "calls_from_text": counts["text"], "calls_from_other_modules": counts["other"],
           "sites_in_text": counts["sites"],
           "method": "Interceptor.attach on kernel32!GetTickCount; return address bucketed into .text 0x401000-0x4bbe55 vs other; sites keyed by return address (the instruction after the call [0x4bc100] site)"}
    print(json.dumps(rec))
    if a.out:
        os.makedirs(os.path.dirname(a.out), exist_ok=True)
        tmp = a.out + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(rec, f, indent=1)
        os.replace(tmp, a.out)
        back = json.load(open(a.out, encoding="utf-8"))
        assert back["calls_from_text"] == counts["text"]
        print(f"wrote {a.out} (read back OK)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
