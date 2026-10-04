# ParamIdTargeted.py - Jython post-script (Ghidra 11.4.1 headless): Decompiler Parameter ID over a chosen set of
# functions only (a targeted analysis, not a re-analysis of the program).
# Targets = (a) symbols\functions.tsv rows whose hookable column is `tbd` (the rows ApplyMap created under
# -noanalysis, Task 4) and (b) every function in the program that has no functions.tsv row (created by
# CreateFuncsFromDataPtrs in the same round), plus (c) any addresses in an optional list file (one hex per line).
# Runs ghidra.app.cmd.function.DecompilerParameterIdCmd, the same command the "Decompiler Parameter ID" analyzer
# (DecompilerFunctionAnalyzer) runs, with that analyzer's option values read from the program's Analyzers options
# (Commit Data Types / Commit Void Return Values / Analysis Decompiler Timeout / Analysis Clear Level), so the result
# is what the pass-4 build would have produced for these entries. Everything it sets is `auto` under gate K.
# Step 0 (H5, found by the first run): a function created under -noanalysis has stack purge UNKNOWN (INT_MAX), and
# with an unknown purge the decompiler keeps the program's default model (__stdcall) for every target, while the
# pass-4 control rows (the 15 pre-existing shell_cb_* functions, plain `ret`, params > 0) are __cdecl. Pass 4 ran the
# "X86 Function Callee Purge" analyzer (FunctionPurgeAnalysisCmd: purge from `ret`/`ret N`) before Parameter ID, so
# this script runs that command over the same set first and logs purge before/after per function.
# Usage: -postScript ParamIdTargeted.py [<mapRoot>] [<extra-addrs.txt>]
# Summary JSON -> <map>\status\paramid-last.json (addresses, before/after cc, params, prototype). p4-ghidra-fixes.
# @category Recon
import os, json, time
from ghidra.app.cmd.function import DecompilerParameterIdCmd, FunctionPurgeAnalysisCmd
from ghidra.program.model.symbol import SourceType
from ghidra.program.model.address import AddressSet
from ghidra.util.task import ConsoleTaskMonitor

args = getScriptArgs()
M = args[0] if len(args) > 0 else "C:\\Users\\james\\i76-map"
extra = args[1] if len(args) > 1 else None
prog = currentProgram
fm = prog.getFunctionManager()
af = prog.getAddressFactory().getDefaultAddressSpace()
mon = ConsoleTaskMonitor()


def log(s):
    print("ParamIdTargeted: " + s)


def read_tsv(path):
    cols = None; rows = []
    fh = open(path, "r")
    for line in fh:
        if line.startswith("#"): continue
        line = line.rstrip("\r\n")
        if not line: continue
        p = line.split("\t")
        if cols is None: cols = p; continue
        while len(p) < len(cols): p.append("")
        rows.append(dict(zip(cols, p)))
    fh.close()
    return rows


rows = read_tsv(os.path.join(M, "symbols", "functions.tsv"))
tsv_addrs = set(int(r["addr"], 16) for r in rows)
targets = {}
for r in rows:
    if r.get("hookable", "") == "tbd":
        targets[int(r["addr"], 16)] = "tsv:hookable=tbd"
for f in fm.getFunctions(True):
    if f.isExternal(): continue
    a = f.getEntryPoint().getOffset()
    if a not in tsv_addrs:
        targets[a] = "program:no functions.tsv row"
if extra and os.path.exists(extra):
    for line in open(extra):
        line = line.strip()
        if line and not line.startswith("#"):
            targets[int(line, 16)] = "extra list"
log("targets: %d (tsv tbd %d, no-row %d, extra %d)" % (len(targets),
    sum(1 for v in targets.values() if v.startswith("tsv")), sum(1 for v in targets.values() if v.startswith("program")),
    sum(1 for v in targets.values() if v == "extra list")))

# analyzer options as stored in the program (fall back to the analyzer's defaults)
opts = prog.getOptions("Analyzers")
P = "Decompiler Parameter ID."
commitDT = opts.getBoolean(P + "Commit Data Types", True)
commitVoid = opts.getBoolean(P + "Commit Void Return Values", False)
timeout = opts.getInt(P + "Analysis Decompiler Timeout (sec)", 60)
try:
    clear = opts.getEnum(P + "Analysis Clear Level", SourceType.ANALYSIS)
except Exception, e:
    clear = SourceType.ANALYSIS
enabled = opts.getBoolean("Decompiler Parameter ID", False)
log("options: enabled=%s commitDataTypes=%s commitVoidReturn=%s timeout=%d clearLevel=%s" % (enabled, commitDT, commitVoid, timeout, clear))


def snap(a):
    f = fm.getFunctionAt(af.getAddress("0x%x" % a))
    if f is None:
        return None
    return {"name": f.getName(), "cc": f.getCallingConventionName(), "params": f.getParameterCount(),
            "prototype": f.getPrototypeString(True, True), "sig_source": str(f.getSignatureSource()),
            "size": f.getBody().getNumAddresses(), "stack_purge": f.getStackPurgeSize()}


before = dict((("0x%x" % a), snap(a)) for a in targets)
aset = AddressSet()
missing = []
for a in sorted(targets):
    if before["0x%x" % a] is None:
        missing.append("0x%x" % a); continue
    aset.add(af.getAddress("0x%x" % a))
if missing:
    log("no function at %s (not analysed)" % ",".join(missing))

# step 0: stack purge from the return instructions (the pass-4 order: purge analyzer, then Parameter ID)
purge_before = dict((k, (v["stack_purge"] if v else None)) for k, v in before.items())
tx = prog.startTransaction("ParamIdTargeted-purge")
try:
    pcmd = FunctionPurgeAnalysisCmd(aset)
    pok = pcmd.applyTo(prog, mon)
    log("FunctionPurgeAnalysisCmd.applyTo -> %s (%s)" % (pok, pcmd.getStatusMsg()))
finally:
    prog.endTransaction(tx, True)
purge_changed = 0
for a in sorted(targets):
    s2 = snap(a)
    if s2 is None: continue
    if s2["stack_purge"] != purge_before["0x%x" % a]:
        purge_changed += 1
        log("purge 0x%x %s: %s -> %d" % (a, s2["name"], purge_before["0x%x" % a], s2["stack_purge"]))
log("purge set on %d of %d targets (unknown = 2147483647)" % (purge_changed, len(targets)))

t0 = time.time()
tx = prog.startTransaction("ParamIdTargeted")
ok = False
try:
    cmd = DecompilerParameterIdCmd("ParamIdTargeted", aset, clear, commitDT, commitVoid, timeout)
    ok = cmd.applyTo(prog, mon)
    log("DecompilerParameterIdCmd.applyTo -> %s (%s) in %.1f s" % (ok, cmd.getStatusMsg(), time.time() - t0))
finally:
    prog.endTransaction(tx, True)

after = dict((("0x%x" % a), snap(a)) for a in targets)
changed = 0
for k in sorted(before):
    b, a2 = before[k], after[k]
    if b is None or a2 is None: continue
    if (b["cc"], b["params"], b["prototype"]) != (a2["cc"], a2["params"], a2["prototype"]):
        changed += 1
        log("%s %s: cc %s->%s params %d->%d : %s" % (k, a2["name"], b["cc"], a2["cc"], b["params"], a2["params"], a2["prototype"]))
summary = {"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "targets": len(targets), "missing": missing, "applied_ok": ok,
           "seconds": time.time() - t0, "changed": changed, "purge_changed": purge_changed, "purge_before": purge_before,
           "options": {"commitDataTypes": commitDT, "commitVoidReturn": commitVoid, "timeout": timeout, "clearLevel": str(clear)},
           "rows": dict((k, {"why": targets[int(k, 16)], "before": before[k], "after": after[k]}) for k in before)}
sp = os.path.join(M, "status")
fh = open(os.path.join(sp, "paramid-last.json"), "w"); json.dump(summary, fh, indent=1, sort_keys=True); fh.close()
log("SUMMARY targets=%d changed=%d ok=%s -> %s" % (len(targets), changed, ok, os.path.join(sp, "paramid-last.json")))
