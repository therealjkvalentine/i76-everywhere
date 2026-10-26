r"""run_phase1.py - phase 1 of VERIFICATION-PROGRAM.md: the call census over every batch, unattended, on the sandbox.

    python verify\run_phase1.py [--pass entity|early] [--batches 001,002] [--scenarios drive,fire-each,melee] [--secs 120] [--dry]

Pass `entity` (the default, the first census pass): for every batches\batch-NNN.json, `drive` and `fire-each` (t01
direct boot on i76.exe), plus `melee` (Instant Melee on i76_pristine_fix.exe, --nomission, one AI car) when at least
half of the batch's functions belong to the renderer / sound / shell / AI families (MELEE_PREFIXES). Every run hooks
after the player entity exists (--attach-after-entity).

Pass `early` (the second pass: loader, startup, shell-menu and init code): Frida hooks the batch before WinMain's first
instruction (run_scenario.py --attach-at-spawn). `mission-idle` (t01 direct boot, 60 s) for every batch, plus
`menu-idle` (plain boot, the shell main menu sits, 75 s from launch) for MENU_BATCHES (shell / renderer / sound / menu
code). --scenarios overrides the list.

Every run is classified (census.py classify) and gets one line in runs\PROGRESS.md (pass `early` lines carry a pass
column); on restart, batch x scenario x pass triples already marked ok are skipped. A run that fails is retried once.
After every run (and after a killed one) the sandbox is checked: no i76 process, no lock, STRLKUP.DLL back to the
original (the .pretest backup is restored if the runner died before its finally). coverage.py runs at the end.
"""
import argparse
import datetime
import glob
import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import BATCHES, G, LOCK, RUNS, VERIFY, log, md5_file  # noqa: E402

PROGRESS = os.path.join(RUNS, "PROGRESS.md")
ORIG_DLL_MD5 = "54f2de9da2beacb1b66a697eaf0d9ea1"
MELEE_PREFIXES = {"ai", "renderer", "image", "light", "camera", "sound", "shell", "font", "input", "match", "salvage",
                  "startup", "profiler", "simclock", "player", "ffb", "FFB", "mouse", "smk", "pcx"}
MELEE_SHARE = 0.5
MENU_BATCHES = {"004", "005", "006", "007", "008", "009", "010", "014"}     # pass early: the batches with shell / renderer / sound / menu code
EARLY_SCENARIOS = {"mission-idle": 60, "menu-idle": 75}                     # scenario -> --secs for pass early
RUN_TIMEOUT = 420          # s per run_scenario.py call (35 s boot + melee nav ~60 s + secs + quit)
CLASSES = ("per_frame", "per_substep", "per_event", "init_only", "never", "irregular", "menu_only")
EARLY_HEADER = ("| batch | scenario | pass | run id | status | per_frame | per_substep | per_event | init_only | menu_only | never | irregular | not_hooked | live frames | fired | attach s | anomalies |\n"
                "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n")


def progress_done():
    """(batch, scenario, pass) -> run id for lines marked ok in PROGRESS.md (pass `entity` lines have no pass column)."""
    done = {}
    if not os.path.exists(PROGRESS):
        return done
    for line in open(PROGRESS, encoding="utf-8"):
        m = re.match(r"\|\s*(batch-\d+)\s*\|\s*([\w-]+)\s*\|\s*([\d-]+)\s*\|\s*(\w+)\s*\|", line)
        if m and m.group(4) == "ok":
            done[(m.group(1), m.group(2), "entity")] = m.group(3)
            continue
        m = re.match(r"\|\s*(batch-\d+)\s*\|\s*([\w-]+)\s*\|\s*(\w+)\s*\|\s*([\d-]+)\s*\|\s*(\w+)\s*\|", line)
        if m and m.group(5) == "ok":
            done[(m.group(1), m.group(2), m.group(3))] = m.group(4)
    return done


def progress_line(batch, scenario, run_id, status, hist, anomalies, pass_="entity"):
    new = not os.path.exists(PROGRESS)
    with open(PROGRESS, "a", encoding="utf-8") as f:
        if new:
            f.write("# Phase 1 census progress (run_phase1.py; one line per batch x scenario; `ok` lines are skipped on restart)\n\n")
            f.write("| batch | scenario | run id | status | per_frame | per_substep | per_event | init_only | never | irregular | not_hooked | live frames | fired | anomalies |\n")
            f.write("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n")
        if pass_ == "entity":
            f.write("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |\n" % (
                batch, scenario, run_id, status, hist.get("per_frame", ""), hist.get("per_substep", ""), hist.get("per_event", ""),
                hist.get("init_only", ""), hist.get("never", ""), hist.get("irregular", ""), hist.get("not_hooked", ""),
                hist.get("_live", ""), hist.get("_fired", ""), anomalies.replace("|", "/")))
        else:
            if EARLY_HEADER.splitlines()[0] not in open(PROGRESS, encoding="utf-8").read():
                f.write("\n## Pass `%s` (run_phase1.py --pass %s: Frida hooks before WinMain's first instruction; mission-idle = t01 direct boot, menu-idle = shell main menu)\n\n" % (pass_, pass_))
                f.write(EARLY_HEADER)
            f.write("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |\n" % (
                batch, scenario, pass_, run_id, status, hist.get("per_frame", ""), hist.get("per_substep", ""), hist.get("per_event", ""),
                hist.get("init_only", ""), hist.get("menu_only", ""), hist.get("never", ""), hist.get("irregular", ""), hist.get("not_hooked", ""),
                hist.get("_live", ""), hist.get("_fired", ""), hist.get("_attach", ""), anomalies.replace("|", "/")))


def sandbox_state():
    import psutil
    procs = [q.pid for q in psutil.process_iter(["name"]) if (q.info["name"] or "").lower().startswith("i76")]
    dll = os.path.join(G, "STRLKUP.DLL")
    return {"i76_pids": procs, "lock": os.path.exists(LOCK), "dll_md5": md5_file(dll) if os.path.exists(dll) else None,
            "pretest": os.path.exists(dll + ".pretest")}


def sandbox_restore(reason):
    """Leave the sandbox as found: kill i76*, restore STRLKUP.DLL from .pretest, remove the lock. Returns what it did."""
    import psutil
    import shutil
    did = []
    for q in psutil.process_iter(["name"]):
        if (q.info["name"] or "").lower().startswith("i76"):
            try:
                q.kill(); q.wait(10); did.append("killed pid %d" % q.pid)
            except Exception as e:  # noqa: BLE001
                did.append("kill %d failed: %r" % (q.pid, e))
    time.sleep(1.0)
    dll, bak = os.path.join(G, "STRLKUP.DLL"), os.path.join(G, "STRLKUP.DLL.pretest")
    if os.path.exists(bak):
        shutil.copy2(bak, dll); os.remove(bak); did.append("restored STRLKUP.DLL from .pretest")
    if os.path.exists(LOCK):
        os.remove(LOCK); did.append("removed lock")
    st = sandbox_state()
    if st["dll_md5"] != ORIG_DLL_MD5:
        did.append("WARNING: STRLKUP.DLL md5 %s != original" % st["dll_md5"])
    if did:
        log("sandbox restore (%s): %s" % (reason, "; ".join(did)))
    return did, st


def latest_run_dir(scenario, after_ts):
    dirs = sorted(d for d in glob.glob(os.path.join(RUNS, scenario, "*")) if os.path.isdir(d) and os.path.basename(d) >= after_ts)
    return dirs[-1] if dirs else None


def run_one(batch_path, scenario, secs, dry, pass_="entity"):
    """One run_scenario.py call + classify. Returns (run_id, status, hist, anomalies)."""
    cmd = [sys.executable, os.path.join(VERIFY, "run_scenario.py"), scenario, "--census", batch_path, "--secs", str(secs)]
    cmd += ["--attach-at-spawn"] if pass_ == "early" else ["--attach-after-entity"]
    if scenario == "melee":
        cmd += ["--exe", "i76_pristine_fix.exe", "--nomission", "--ai", "1"]
    log("RUN %s" % " ".join(cmd[1:]))
    if dry:
        return "dry", "dry", {}, ""
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    logf = os.path.join(RUNS, "phase1-%s-%s.log" % (scenario, ts))
    anomalies = []
    try:
        with open(logf, "w", encoding="utf-8") as lf:
            r = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT, timeout=RUN_TIMEOUT, cwd=VERIFY)
        rc = r.returncode
    except subprocess.TimeoutExpired:
        rc = "timeout"
        anomalies.append("run_scenario timed out after %d s (killed)" % RUN_TIMEOUT)
    did, st = sandbox_restore("after run rc=%s" % rc)
    if did:
        anomalies.append("sandbox restore: " + "; ".join(did))
    run = latest_run_dir(scenario, ts[:8] + "-" + ts[9:])
    if run is None:
        return "-", "failed", {}, "; ".join(anomalies + ["no run directory; rc %s; log %s" % (rc, os.path.basename(logf))])
    run_id = os.path.basename(run)
    man = {}
    mp = os.path.join(run, "manifest.json")
    if os.path.exists(mp):
        man = json.load(open(mp, encoding="utf-8"))
    for e in man.get("errors", []):
        anomalies.append("error: " + str(e)[:160])
    for w in man.get("warnings", []):
        if "duration reached" not in w:
            anomalies.append("warn: " + str(w)[:120])
    for c in man.get("checks", []):
        if not c.get("ok"):
            anomalies.append("check FAIL %s %s" % (c.get("check"), c.get("detail")))
    cen = man.get("census") or {}
    att = cen.get("attest") or {}
    menu = man.get("boot") == "menu"
    if cen.get("attach_entity_present") is False and pass_ == "entity":
        anomalies.append("attach before entity")
    if pass_ == "early":
        if cen.get("attach_entity_present") or (man.get("resumed") or {}).get("frame"):
            anomalies.append("NOT early: entity present / frame moved before the hooks went in")
        if not (man.get("launch") or {}).get("method", "").startswith("frida.spawn"):
            anomalies.append("not spawned by frida (launch %s)" % (man.get("launch") or {}).get("method"))
    if menu and not man.get("menu_up"):
        anomalies.append("menu never up (game state %s)" % ((man.get("start_state") or {}).get("game_state")))
    if att.get("attach_errors"):
        anomalies.append("%d attach errors" % len(att["attach_errors"]))
    if att.get("runtime_errors"):
        anomalies.append("%d frida runtime errors" % len(att["runtime_errors"]))
    if att.get("void"):
        anomalies.append("VOID census (no hook fired)")
    if "quit" in man and "killed" in man["quit"]:
        anomalies.append(man["quit"])
    hist = {}
    status = "failed"
    if os.path.exists(os.path.join(run, "census.series.json")) and os.path.exists(os.path.join(run, "census.jsonl")) and man.get("start_frame") is not None:
        try:
            cr = subprocess.run([sys.executable, os.path.join(VERIFY, "census.py"), "classify", run], capture_output=True, text=True, timeout=600)
            cl = json.load(open(os.path.join(run, "census.classified.json"), encoding="utf-8"))
            hist = dict(cl["classes"])
            hist["not_hooked"] = sum(1 for f in cl["functions"] if f["class"] == "not_hooked")
            hist["_live"] = cl["frames_live"]
            hist["_fired"] = (att.get("stop") or {}).get("fired_total")
            hist["_attach"] = "%s/%s" % (cen.get("attach_t_after_launch"), cen.get("hooks_done_t_after_launch")) if pass_ == "early" else cen.get("attach_t_after_launch")
            if cl["frames_live"] < 200 and not menu:
                anomalies.append("only %d live frames" % cl["frames_live"])
            if cl.get("first_wreck_frame"):
                anomalies.append("player wrecked at frame %s (%d frames excluded)" % (cl["first_wreck_frame"], cl["frames_wrecked_excluded"]))
            usable = (cl["frames_live"] >= 200) or (menu and man.get("menu_up") and (cl["menu"] or {}).get("sit_s", 0) >= 20)
            status = "ok" if man.get("ok") and rc == 0 else ("ok-with-errors" if usable else "failed")
            if cr.returncode != 0:
                anomalies.append("classify rc %d: %s" % (cr.returncode, (cr.stderr or "").strip()[-200:]))
        except Exception as e:  # noqa: BLE001
            anomalies.append("classify failed: %r" % (e,))
    else:
        anomalies.append("no census outputs (rc %s)" % rc)
    return run_id, status, hist, "; ".join(anomalies)


def melee_wanted(batch):
    fs = batch["functions"]
    n = sum(1 for f in fs if (f["name"].split("_")[0] if "_" in f["name"] else f["name"]) in MELEE_PREFIXES)
    return n / float(len(fs)) >= MELEE_SHARE, n


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pass", dest="pass_", default="entity", choices=("entity", "early"), help="entity: hook after the player entity (default); early: hook at spawn, mission-idle + menu-idle")
    ap.add_argument("--batches", default="", help="comma list of batch numbers (001,002); default all")
    ap.add_argument("--scenarios", default=None, help="default drive,fire-each,melee (pass entity) or mission-idle,menu-idle (pass early)")
    ap.add_argument("--secs", type=float, default=None, help="recording seconds (default 120; pass early: 60 mission-idle / 75 menu-idle)")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--no-coverage", action="store_true")
    a = ap.parse_args()
    want = set(a.batches.split(",")) if a.batches else None
    scns = (a.scenarios or ("mission-idle,menu-idle" if a.pass_ == "early" else "drive,fire-each,melee")).split(",")
    st = sandbox_state()
    log("sandbox at start: %s" % st)
    if st["i76_pids"] or st["lock"] or st["dll_md5"] != ORIG_DLL_MD5:
        raise SystemExit("ABORT: sandbox not clean at start: %s" % st)
    done = progress_done()
    for bp in sorted(glob.glob(os.path.join(BATCHES, "batch-*.json"))):
        b = json.load(open(bp, encoding="utf-8"))
        bid = b["batch"]
        if want and bid.split("-")[1] not in want:
            continue
        melee, nm = melee_wanted(b)
        for scn in scns:
            if scn == "melee" and not melee:
                continue
            if scn == "menu-idle" and a.pass_ == "early" and bid.split("-")[1] not in MENU_BATCHES:
                continue
            secs = a.secs if a.secs is not None else (EARLY_SCENARIOS.get(scn, 60) if a.pass_ == "early" else 120)
            if (bid, scn, a.pass_) in done:
                log("skip %s %s %s (done: %s)" % (bid, scn, a.pass_, done[(bid, scn, a.pass_)]))
                continue
            if a.dry:
                run_one(bp, scn, secs, True, a.pass_)
                continue
            for attempt in (1, 2):
                run_id, status, hist, anomalies = run_one(bp, scn, secs, False, a.pass_)
                if attempt == 2:
                    anomalies = ("retry %d; " % attempt) + anomalies
                progress_line(bid, scn, run_id, status, hist, anomalies, a.pass_)
                log("%s %s %s -> %s %s %s | %s" % (bid, scn, a.pass_, run_id, status, {k: v for k, v in hist.items()}, anomalies[:200]))
                if status.startswith("ok"):
                    break
                time.sleep(5)
            time.sleep(5)
    if not a.no_coverage and not a.dry:
        r = subprocess.run([sys.executable, os.path.join(VERIFY, "coverage.py"), "--all"], capture_output=True, text=True)
        open(os.path.join(RUNS, "coverage-stdout.txt"), "w", encoding="utf-8").write(r.stdout + r.stderr)
        log((r.stdout or "").splitlines()[0] if r.stdout else "coverage.py produced no output")
    did, st = sandbox_restore("end")
    log("sandbox at end: %s" % st)
    if a.dry:
        return 0
    with open(PROGRESS, "a", encoding="utf-8") as f:
        f.write("\n<!-- run_phase1.py --pass %s finished %s; sandbox %s -->\n" % (a.pass_, datetime.datetime.now().isoformat(timespec="seconds"), json.dumps(st)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
