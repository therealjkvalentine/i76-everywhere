r"""ghidra_round.py - the merge worker's Ghidra round in one command (README section 3; PILOT-1 "every K merges").

    python tools\ghidra_round.py --label pilot1-remerge --since 2026-09-05T11:00:00

Steps (each logged, each verified before the next):
  1. copy ghidra\export -> <scratch>\<label>\export-before (robocopy /E /XD logs)   the G3 "before"
  2. headless ApplyMap.py            (map names/types into the project; G6 revert pass inside)
  3. headless ExportBaseline + DumpAll (re-export the corpus; ~90 s)
  4. tools\g3_check.py --addrs <merged addresses since --since, from status\merge-log.jsonl> --out status\tasks\<label>-g3.json
  5. tools\gates\gateG3_consistency.py --g3 <that report>
  6. tools\gen_tables.py --verify ; tools\completeness.py
Exit 0 only when every step passed; the G3 report path is printed for the sitting notes.
Never run while drafter/reviewer agents are reading ghidra\export (they read the files this rewrites).
"""
import argparse, json, os, subprocess, sys, time, shutil

M = r"C:\Users\james\i76-map"
HEADLESS = r"C:\Users\james\Downloads\ghidra_11.4.1_PUBLIC_20250731\ghidra_11.4.1_PUBLIC\support\analyzeHeadless.bat"


def run(cmd, log, cwd=M, check=True):
    t0 = time.time()
    with open(log, "w", encoding="utf-8") as fh:
        r = subprocess.run(cmd, cwd=cwd, stdout=fh, stderr=subprocess.STDOUT, shell=isinstance(cmd, str))
    dt = time.time() - t0
    print("  %-70s rc=%d %.1f s -> %s" % ((cmd if isinstance(cmd, str) else " ".join(cmd))[:70], r.returncode, dt, os.path.relpath(log, M)))
    if check and r.returncode != 0:
        print(open(log, encoding="utf-8", errors="replace").read()[-2000:])
        sys.exit("step failed: %s" % cmd)
    return r.returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--since", required=True, help="ISO time; merge-log entries at or after it form the touched set")
    ap.add_argument("--scratch", default=os.path.join(os.environ.get("TEMP", r"C:\Temp"), "i76-ghidra-round"))
    ap.add_argument("--skip-apply", action="store_true")
    a = ap.parse_args()
    logs = os.path.join(M, "ghidra", "export", "logs"); os.makedirs(logs, exist_ok=True)
    before = os.path.join(a.scratch, a.label, "export-before")
    # touched set
    addrs = []
    for line in open(os.path.join(M, "status", "merge-log.jsonl"), encoding="utf-8"):
        try:
            j = json.loads(line)
        except ValueError:
            continue
        if j.get("time", "") >= a.since:
            addrs.append("0x%x" % int(j["key"], 16))
    if not addrs:
        sys.exit("no merge-log entries since %s" % a.since)
    addr_file = os.path.join(M, "status", "tasks", "%s-touched.txt" % a.label)
    open(addr_file, "w", encoding="utf-8").write("\n".join(addrs) + "\n")
    print("touched set: %d address(es) since %s -> %s" % (len(addrs), a.since, os.path.relpath(addr_file, M)))
    # 1 before copy
    if os.path.exists(before):
        shutil.rmtree(before)
    os.makedirs(before)
    rc = run(["robocopy", os.path.join(M, "ghidra", "export"), before, "/E", "/XD", "logs", "/NFL", "/NDL", "/NJH"], os.path.join(logs, "%s-robocopy.log" % a.label), check=False)
    if rc >= 8:
        sys.exit("robocopy failed rc=%d" % rc)
    n_before = sum(len(f) for _, _, f in os.walk(before)); print("  before copy: %d files" % n_before)
    base = [HEADLESS, os.path.join(M, "ghidra", "proj"), "i76map", "-process", "i76_ref.exe", "-noanalysis", "-scriptPath", os.path.join(M, "ghidra", "scripts")]
    # 2 ApplyMap
    if not a.skip_apply:
        run(base + ["-postScript", "ApplyMap.py", M], os.path.join(logs, "%s-run1-applymap.log" % a.label))
        am = json.load(open(os.path.join(M, "status", "applymap-last.json"), encoding="utf-8"))
        print("  applymap: " + ", ".join("%s=%s" % (k, am.get(k)) for k in ("rows_read", "applied_rows", "renamed", "created", "reverted", "g6_reverted_names", "errors")))
        if am.get("errors"):
            sys.exit("ApplyMap reported errors")
    # 3 export
    exp = os.path.join(M, "ghidra", "export")
    run(base + ["-postScript", "ExportBaseline.java", exp, "-postScript", "DumpAll.py", exp], os.path.join(logs, "%s-run2-export.log" % a.label))
    summ = json.load(open(os.path.join(exp, "summary.json"), encoding="utf-8"))
    print("  export: functions=%s decomp_failed=%s symbols=%s" % (summ.get("functions"), summ.get("decomp_failed"), summ.get("symbols")))
    # 4 G3
    g3 = os.path.join(M, "status", "tasks", "%s-g3.json" % a.label)
    run([sys.executable, os.path.join(M, "tools", "g3_check.py"), "--before", before, "--addrs", addr_file, "--out", g3], os.path.join(logs, "%s-g3.log" % a.label))
    rep = json.load(open(g3, encoding="utf-8"))
    keys = [k for k in ("touched", "neighbourhood", "created", "unchanged", "improved", "regressions", "decompile_failures_before", "decompile_failures_after") if k in rep]
    print("  G3: " + ", ".join("%s=%s" % (k, rep[k] if not isinstance(rep[k], list) else len(rep[k])) for k in keys))
    # 5 gate G3
    run([sys.executable, os.path.join(M, "tools", "gates", "gateG3_consistency.py"), "--g3", g3], os.path.join(logs, "%s-gateG3.log" % a.label))
    # 6 tables + metrics
    run([sys.executable, os.path.join(M, "tools", "gen_tables.py"), "--verify"], os.path.join(logs, "%s-gen_tables.log" % a.label))
    run([sys.executable, os.path.join(M, "tools", "completeness.py")], os.path.join(logs, "%s-completeness.log" % a.label))
    print("ROUND OK %s: G3 report %s" % (a.label, os.path.relpath(g3, M)))


if __name__ == "__main__":
    main()
