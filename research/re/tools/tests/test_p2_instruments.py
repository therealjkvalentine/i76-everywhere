#!/usr/bin/env python3
r"""test_p2_instruments.py - offline / throwaway-process tests for tools\i76poke.py, tools\snapshot.py,
tools\which_build.py 0.2 and tools\launch.ps1 0.2 (p2-poke-snapshot-h0). The game is never launched (H10).

    python tools\tests\test_p2_instruments.py [--keep] [--skip-launch]

Targets: tools\tests\fake_sim.py (pristine image mapped at 0x400000 inside a 64-bit python.exe with the
i76fix patch in memory, a ticking 0x5a7e1c, a per-tick clobber at 0x5367cc, a 25-tick event at 0x5367d4,
and a PeekMessageA call per tick) and C:\Windows\SysWOW64\notepad.exe (the 32-bit live read path and the
frida 64->32 pump hook). Everything is written under a scratch --map-root, not under captures\.
Every check prints its measured value; exit 0 only if all pass.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.abspath(os.path.join(HERE, ".."))
MAP = os.path.abspath(os.path.join(TOOLS, ".."))
sys.path.insert(0, TOOLS)
import which_build as wb  # noqa: E402

PY = sys.executable
PRISTINE = os.path.join(wb.DEFAULT_GAME, "i76.exe.2017galaxy")
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print("%s %s %s" % ("PASS" if cond else "FAIL", name, detail))


def run(args, timeout=300):
    cp = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    return cp.returncode, (cp.stdout + cp.stderr)


def start_fake(extra):
    cmd = [PY, os.path.join(HERE, "fake_sim.py"), "--image", PRISTINE, "--patch", "0x499b25:b8c8000000", "--seconds", "300"] + extra
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True)
    line = proc.stdout.readline().strip()
    print("  fake_sim:", line)
    if not line.startswith("READY"):
        proc.kill()
        raise RuntimeError(line)
    return proc


def last_record(map_root, cap):
    p = os.path.join(map_root, "captures", cap, "pokes.jsonl")
    with open(p, "r", encoding="utf-8") as f:
        lines = [l for l in f.read().splitlines() if l.strip()]
    return json.loads(lines[-1]), len(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--skip-launch", action="store_true")
    ap.add_argument("--map-root", default=None)
    a = ap.parse_args()
    map_root = a.map_root or tempfile.mkdtemp(prefix="i76map-p2-")
    os.makedirs(os.path.join(map_root, "captures"), exist_ok=True)
    print("scratch map root:", map_root)
    poke = [PY, os.path.join(TOOLS, "i76poke.py"), "--map-root", map_root]
    snap = [PY, os.path.join(TOOLS, "snapshot.py"), "--map-root", map_root]

    # ---------------------------------------------------------------- 1. i76poke against fake_sim
    t = start_fake(["--tick-ms", "20", "--clobber", "0x5367cc:00000000", "--event", "0x5367d4:00000000:25", "--pump"])
    pid = str(t.pid)
    try:
        time.sleep(0.5)
        rc, out = run(poke + ["--capture", "test-poke", "--pid", pid, "--va", "0x5aab28", "--type", "int32", "--value", "1234"])
        check("poke: H0 refuses the fake host (python.exe md5) without --allow-patched -> rc 3", rc == 3 and "REFUSED" in out, out.strip().splitlines()[-1][:160])
        rec, n = last_record(map_root, "test-poke")
        check("poke: refusal logged", rec.get("result") == "refused" and n == 1, str(rec.get("h0"))[:120])

        rc, out = run(poke + ["--capture", "test-poke", "--pid", pid, "--allow-patched", "--va", "0x5aab28", "--type", "int32", "--value", "1234", "--note", "G-POS ammo slot 0"])
        rec, n = last_record(map_root, "test-poke")
        check("poke: untouched bss dword -> sticks (rc 0)", rc == 0 and rec.get("classification") == "sticks", "%s | %s" % (rec.get("classification"), out.strip().splitlines()[-1][:160]))
        check("poke: three horizons recorded with frame advances", rec.get("h1_plus_1_frame", {}).get("frame_advanced") and rec.get("h2_plus_N_frames", {}).get("frame_advanced")
              and rec["h2_plus_N_frames"]["frames_advanced"] >= 5, json.dumps({k: rec.get(k) for k in ("h0_immediate", "h1_plus_1_frame", "h2_plus_N_frames")}))
        check("poke: record tagged patched-build-only and h0 fields present", rec.get("tag") == "patched-build-only" and "h0" in rec and rec.get("target", {}).get("class") == "bss", str(rec.get("target")))

        rc, out = run(poke + ["--capture", "test-poke", "--pid", pid, "--allow-patched", "--va", "0x5367cc", "--type", "int32", "--value", "7"])
        rec, n = last_record(map_root, "test-poke")
        check("poke: per-tick clobber at 0x5367cc -> clobbered-per-frame", rc == 0 and rec.get("classification") == "clobbered-per-frame", "%s imm=%s +1f=%s" % (rec.get("classification"), rec.get("h0_immediate", {}).get("value"), rec.get("h1_plus_1_frame", {}).get("value")))

        rc, out = run(poke + ["--capture", "test-poke", "--pid", pid, "--allow-patched", "--va", "0x5367d4", "--type", "int32", "--value", "9", "--frames", "40"])
        rec, n = last_record(map_root, "test-poke")
        check("poke: 25-tick event at 0x5367d4 with N=40 -> clobbered-on-event", rc == 0 and rec.get("classification") == "clobbered-on-event", "%s +1f=%s +40f=%s" % (rec.get("classification"), rec.get("h1_plus_1_frame", {}).get("value"), rec.get("h2_plus_N_frames", {}).get("value")))

        # root 0x4f2860 (init) = input-action table row 0: its first dword is the name pointer -> 0x4f45d4 (init string)
        rc, out = run(poke + ["--capture", "test-poke", "--pid", pid, "--allow-patched", "--chain", "0x4f2860,0x0", "--type", "byte", "--value", "0x41", "--restore"])
        rec, n = last_record(map_root, "test-poke")
        hops = rec.get("target", {}).get("hops", [])
        check("poke: chain 0x4f2860,0x0 resolves through one hop to 0x4f45d4 (init), byte sticks, restored", rc == 0 and len(hops) == 1 and rec.get("target", {}).get("resolved") == "0x4f45d4" and rec.get("classification") == "sticks" and rec.get("restore", {}).get("restored"),
              "%s -> %s restore=%s" % (rec.get("target", {}).get("chain"), rec.get("target", {}).get("resolved"), rec.get("restore")))

        rc, out = run(poke + ["--capture", "test-poke", "--pid", pid, "--allow-patched", "--va", "0x10", "--type", "byte", "--value", "1"])
        rec, n = last_record(map_root, "test-poke")
        check("poke: unmapped VA 0x10 -> did-not-land (rc 1) with the write error recorded", rc == 1 and rec.get("classification") == "did-not-land" and rec.get("write", {}).get("win32_error"), str(rec.get("write")))

        rc, out = run(poke + ["--capture", "test-poke", "--pid", pid, "--allow-patched", "--chain", "0x5aab00,0x4", "--type", "int32", "--value", "1"])
        rec, n = last_record(map_root, "test-poke")
        check("poke: chain through a null pointer -> chain-unresolvable (rc 2)", rc == 2 and rec.get("result") == "chain-unresolvable", str(rec.get("target", {}).get("hops"))[:160])
        check("poke: pokes.jsonl holds every record (7 pokes incl. the refusal)", n == 7, "n=%d" % n)
        check("poke: manifest.json build block written by the H0 gate", os.path.exists(os.path.join(map_root, "captures", "test-poke", "manifest.json")))

        # ------------------------------------------------------------ 2. snapshot against fake_sim
        rc, out = run(snap + ["--capture", "test-snap-pair", "--pid", pid, "--gap", "0.5", "--heaps", "--pos-control", "0x5a7e1c:uint32:changes", "--pos-control", "0x4c2000:uint32:constant"])
        man = json.load(open(os.path.join(map_root, "captures", "test-snap-pair", "manifest.json"), encoding="utf-8"))
        s = man["snapshot"]
        check("snapshot pair: driving state (0x5a7e1c advanced)", rc == 0 and s["state"].startswith("driving"), s["state"])
        check("snapshot pair: both files 1,736,440 B and read back", all(v["bytes"] == 0x669EF8 - 0x4C2000 and v["readback_equal"] for k, v in s["files"].items() if k.startswith("snapshot")), str({k: v["bytes"] for k, v in s["files"].items()}))
        check("snapshot pair: G-POS rows pass (frame counter changes, 0x4c2000 constant)", all(p["pass"] for p in s["pos_control"]) and len(s["pos_control"]) == 2, str(s["pos_control"]))
        check("snapshot pair: heaps enumerated, heap handle globals read as zero in the file image", s["heaps"]["enumerated"] and s["heaps"]["regions"] > 0 and all(not o["value"] for o in s["heaps"]["owners"]), "regions=%d owners set=%d" % (s["heaps"]["regions"], sum(1 for o in s["heaps"]["owners"] if o["value"])))
        check("snapshot pair: frames tagged torn-possible while the sim advances (G-TORN)", all(f["torn"].startswith("torn-possible") for f in s["frames"]), str([f["torn"] for f in s["frames"]]))

        rc, out = run(snap + ["--capture", "test-snap-series", "--pid", pid, "--series", "--hz", "5", "--window", "3", "--windows", "2", "--pump", "--pos-control", "0x5a7e1c:uint32:changes"])
        man = json.load(open(os.path.join(map_root, "captures", "test-snap-series", "manifest.json"), encoding="utf-8"))
        s = man["snapshot"]
        r = s.get("series", {})
        check("snapshot series: 2 windows x ~15 frames, stats present", rc == 0 and r.get("windows") == 2 and r.get("frames_total", 0) >= 20 and "AA_0v1_p" in r, "frames=%s win0_p=%s AA_0v1_p=%s churn_runs=%s" % (r.get("frames_total"), r.get("win0_p"), r.get("AA_0v1_p"), r.get("churn_runs")))
        check("snapshot series: churn = the fake's two moving dwords (0x5a7e1c, 0x5a7e74; the clobber/event writers rewrite 0 over 0)", r.get("churn_runs") == 2 and r.get("win0_changed_dwords") == 2, str(r.get("churn_top_runs")))
        check("snapshot series: one full frame + xz deltas for the rest, deltas < 1 % of the raw equivalent", s["compression"]["frames_stored_as_delta"] == r["frames_total"] - 1 and s["compression"]["delta_bytes_total"] * 100 < s["compression"]["raw_equivalent_bytes"], str(s["compression"]))
        check("snapshot series: every frame torn-possible while driving", s["torn_possible_frames"] == r["frames_total"], "torn=%s of %s" % (s["torn_possible_frames"], r["frames_total"]))
        check("snapshot series: pump hook via fallback export counted the fake pump (frida attach 64->64)", s["pump"].get("measured") and s["pump_counts"]["after"]["other"] > s["pump_counts"]["before"]["other"], str(s.get("pump_counts")))
        hj = os.path.join(map_root, "captures", "test-snap-series", "hooks.json")
        check("snapshot series: hooks.json written for G-ATTEST", os.path.exists(hj) and json.load(open(hj))["counters"]["pump_other"] > 0, hj)
        check("snapshot series: state driving", s["state"].startswith("driving"), s["state"])
    finally:
        t.kill()

    # ---------------------------------------------------------------- 3. paused / menu canaries on fake_sim
    t = start_fake(["--tick-ms", "20", "--start-after", "1.5", "--pause-after", "4", "--pause-for", "6", "--pump"])
    pid = str(t.pid)
    try:
        time.sleep(0.2)
        rc, out = run(snap + ["--capture", "test-snap-menu", "--pid", pid, "--gap", "0.5"])
        s = json.load(open(os.path.join(map_root, "captures", "test-snap-menu", "manifest.json"), encoding="utf-8"))["snapshot"]
        check("snapshot: menu state when 0x5a7e1c == 0", s["state"].startswith("menu"), s["state"])
        time.sleep(4.5)
        rc, out = run(snap + ["--capture", "test-snap-paused", "--pid", pid, "--gap", "1", "--pump"])
        s = json.load(open(os.path.join(map_root, "captures", "test-snap-paused", "manifest.json"), encoding="utf-8"))["snapshot"]
        check("snapshot: paused state = 0x5a7e1c frozen AND > 0 AND pump advanced (fallback-export metric text+other on the fake host)",
              s["state"].startswith("paused") and s["pump"].get("metric", "").startswith("text+other"), s["state"] + " pump=" + str(s.get("pump_counts")))
        check("snapshot: paused frames coherent (not torn)", all(f["torn"].startswith("coherent") for f in s["frames"]), str([f["torn"] for f in s["frames"]]))
        rc, out = run(snap + ["--capture", "test-snap-frozen-nopump", "--pid", pid, "--gap", "0.5"])
        s = json.load(open(os.path.join(map_root, "captures", "test-snap-frozen-nopump", "manifest.json"), encoding="utf-8"))["snapshot"]
        check("snapshot: frozen without --pump reports the pump as unmeasured (paused not proven)", s["state"].startswith("frozen") and "unmeasured" in s["state"], s["state"])
    finally:
        t.kill()

    # ---------------------------------------------------------------- 4. notepad (32-bit): live read null + frida 64->32 pump
    np_path = r"C:\Windows\SysWOW64\notepad.exe"
    if os.path.exists(np_path):
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0
        n = subprocess.Popen([np_path], startupinfo=si)
        try:
            time.sleep(1.5)
            rc, out = run(snap + ["--capture", "test-notepad", "--pid", str(n.pid), "--gap", "0.2", "--heaps"])
            check("snapshot notepad: region not mapped -> short read null, exit 1", rc == 1 and "short read" in out, out.strip().splitlines()[-1][:160])
            reg = [l for l in out.splitlines() if l.startswith("regions:")]
            check("snapshot notepad: VirtualQueryEx enumerates the 32-bit process's private RW regions (> 0)", reg and int(reg[0].split()[1]) > 0, reg[0][:160] if reg else out[:160])
            rc, out = run(poke + ["--capture", "test-notepad", "--pid", str(n.pid), "--va", "0x5aab28", "--type", "int32", "--value", "1"])
            check("poke notepad: refused (H0 fail on a 32-bit non-i76 image), exit 3", rc == 3, out.strip().splitlines()[-1][:160])
            rc, out = run(snap + ["--capture", "test-notepad-pump", "--pid", str(n.pid), "--gap", "0.2", "--pump", "--pump-export", "PeekMessageW"])
            lines = out.strip().splitlines()
            inst = [l for l in lines if l.startswith("pump hook installed")]
            check("snapshot notepad: frida attached 64->32 and the pump hook installed on the fallback export (arch ia32)", inst and "fallback export" in inst[0] and "arch ia32" in inst[0] and rc == 1, inst[0][:200] if inst else out[:200])
        finally:
            n.kill()
    else:
        check("notepad present", False)

    # ---------------------------------------------------------------- 5. which_build 0.2 offline
    rc, out = run([PY, os.path.join(TOOLS, "which_build.py"), "--selftest"])
    check("which_build --selftest exit 0 (IAT excluded from the H0 compare: .rdata region starts at 0x4bc404)", rc == 0, "rc=%d" % rc)
    diffs = wb.load_all_diffs()
    check("which_build: four diff TSVs generated", set(diffs) >= {"58d9dec0", "60abf7bc", "4fabc303", "6319abf7"}, str(sorted(diffs)))
    c = wb.classify_va(0x49c920, diffs)
    check("classify 0x49c920: build-shifted on aio/sandbox/portable, transfers on 58d9dec0",
          c["60abf7bc"]["inside"] and c["4fabc303"]["inside"] and c["6319abf7"]["inside"] and not c["58d9dec0"]["inside"], str({k: v["tag"] for k, v in c.items()}))
    c = wb.classify_va(0x4059de, diffs)
    check("classify 0x4059de (far-clip reader patch): sandbox only", c["4fabc303"]["inside"] and not c["60abf7bc"]["inside"] and not c["6319abf7"]["inside"], str({k: v["tag"] for k, v in c.items()}))
    c = wb.classify_va(0x438630, diffs)
    check("classify 0x438630 (integrator): transfers everywhere", not any(v["inside"] for v in c.values()), str({k: v["tag"] for k, v in c.items()}))
    st = wb.dgvoodoo_conf(wb.DEFAULT_GAME)
    check("G-CONF: sandbox dgVoodoo.conf parsed section-aware with effective keys", st["present"] and st["effective"].get("GeneralExt.FPSLimit") == "21" and st["effective"].get("Glide.Resolution") == "3360x2100"
          and st["effective"].get("General.ScalingMode") == "stretched_ar", str(st["effective"]))
    check("G-CONF: EnableInactiveAppState under [General] flagged as misplaced", any(m["key"] == "EnableInactiveAppState" and m["section"] == "General" for m in st["misplaced"]), str([(m["section"], m["key"]) for m in st["misplaced"]]))
    hj = os.path.join(map_root, "captures", "test-snap-series", "hooks.json")
    hk = wb.read_hooks_json(hj)
    check("G-ATTEST: hooks.json read into the stamp; pump_text 0 on the fake host voids (counter 0)", hk["present"] and "pump_text" in hk["zero_counters"] and hk["attest"].startswith("void"), hk["attest"])
    with open(os.path.join(map_root, "zero.json"), "w") as f:
        json.dump({"counters": {"a": 3, "b": 1}}, f)
    check("G-ATTEST: all counters > 0 -> pass", wb.read_hooks_json(os.path.join(map_root, "zero.json"))["attest"].startswith("pass"))
    check("G-ATTEST: absent file -> unmeasured (never pass)", "unmeasured" in wb.read_hooks_json(os.path.join(map_root, "nope.json"))["attest"])
    rc, out = run([PY, os.path.join(TOOLS, "which_build.py"), "--file", os.path.join(wb.DEFAULT_GAME, "i76.exe.camorig"), "--json"])
    i = out.find("\n{")
    stamp = json.loads(out[i + 1:]) if i >= 0 else {}
    check("which_build --file camorig: diff signature identifies 60abf7bc, class patched-build-only", stamp.get("diff_signature", {}).get("match") == "60abf7bc" and stamp.get("build_class") == "patched-build-only", str(stamp.get("diff_signature", {}).get("verdict")))
    # live IAT-by-name on a fake target: thunks unresolved (file image)
    t = start_fake([])
    try:
        rc, out = run([PY, os.path.join(TOOLS, "which_build.py"), "--pid", str(t.pid), "--base", "0x400000", "--json"])
        i = out.find("\n{")
        stamp = json.loads(out[i + 1:]) if i >= 0 else {}
        ib = stamp.get("iat_by_name", {})
        check("which_build live (fake): IAT by name = 244 slots, all unresolved (file image thunks)", ib.get("slots") == 244 and ib.get("unresolved") == 244, str(ib.get("verdict")))
        check("which_build live (fake): H0 PASS with the allowlisted 5 B, signature 58d9dec0", stamp.get("h0_pass") and stamp.get("diff_signature", {}).get("match") == "58d9dec0", str(stamp.get("h0_summary")))
    finally:
        t.kill()

    # ---------------------------------------------------------------- 6. launch.ps1 0.2 empty -GameArgs (notepad as the exe)
    if not a.skip_launch and os.path.exists(np_path):
        cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", os.path.join(TOOLS, "launch.ps1"), "-GameDir", r"C:\Windows\SysWOW64", "-Exe", "notepad.exe",
               "-GameArgs", "@()", "-AllowPatched", "-CaptureId", "test-launch-noargs", "-MapRoot", map_root, "-SettleSeconds", "3"]
        rc, out = run(cmd, timeout=120)
        log = os.path.join(map_root, "captures", "test-launch-noargs", "launch.log")
        logtxt = open(log, encoding="utf-8-sig").read() if os.path.exists(log) else ""
        if rc == 4:
            check("launch.ps1 -GameArgs @(): the session gate refused this RDP/agent shell (exit 4, gate working); the in-situ branch stays for the console", True, logtxt.splitlines()[0][:200] if logtxt else out[:200])
        else:
            check("launch.ps1 -GameArgs @(): Start-Process branch taken, notepad launched, which_build ran (exit 1 = H0 FAIL on notepad as expected)", rc == 1 and "no game arguments" in logtxt and "pid=" in logtxt, "rc=%d %s" % (rc, [l for l in logtxt.splitlines() if "pid=" in l or "no game" in l or "exit=" in l][:3]))
            m = [l for l in logtxt.splitlines() if l.startswith("pid=")]
            if m:
                try:
                    subprocess.run(["taskkill", "/PID", m[0].split("=")[1].split()[0], "/F"], capture_output=True)
                except Exception:
                    pass
        # the exact two Start-Process forms of launch.ps1, in isolation: the @() form must fail (the bug), the no -ArgumentList form must start
        ps = ("$ErrorActionPreference='Stop'; $bug='no'; try { Start-Process -FilePath '%s' -ArgumentList @() -WorkingDirectory 'C:\Windows\SysWOW64' -PassThru | Out-Null } catch { $bug='yes: ' + $_.Exception.Message }; "
              "$p = Start-Process -FilePath '%s' -WorkingDirectory 'C:\Windows\SysWOW64' -PassThru; Start-Sleep 1; $p.Refresh(); \"bug=$bug pid=$($p.Id) exited=$($p.HasExited)\"; Stop-Process -Id $p.Id -Force" % (np_path, np_path))
        rc, out = run(["powershell", "-NoProfile", "-Command", ps], timeout=60)
        check("launch.ps1 branch in isolation: -ArgumentList @() is rejected by PowerShell 5.1 and the no -ArgumentList form starts the process", "bug=yes" in out and "exited=False" in out, out.strip()[:200])
        rc, out = run(["powershell", "-NoProfile", "-Command", "$e=$null; [void][System.Management.Automation.PSParser]::Tokenize((Get-Content -Raw '%s'), [ref]$e); 'parse_errors=' + @($e).Count" % os.path.join(TOOLS, "launch.ps1")], timeout=60)
        check("launch.ps1 0.2 parses with 0 errors (PSParser)", "parse_errors=0" in out, out.strip()[:120])
        rc, out = run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", os.path.join(TOOLS, "launch.ps1"), "-DryRun", "-GameArgs", "@()", "-CaptureId", "test-launch-dry", "-MapRoot", map_root], timeout=60)
        check("launch.ps1 -DryRun -GameArgs @() with the default -Exe i76_pristine_fix.exe passes the md5 gate (exit 6 dry run or 4 session)", rc in (6, 4) and "i76_pristine_fix.exe" in out, "rc=%d %s" % (rc, out.strip().splitlines()[0][:160] if out.strip() else ""))

    failed = [n for n, ok in results if not ok]
    print("\n%d checks, %d failed%s" % (len(results), len(failed), (": " + ", ".join(failed)) if failed else ""))
    if not a.keep and not a.map_root:
        shutil.rmtree(map_root, ignore_errors=True)
    else:
        print("kept", map_root)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
