# DumpAll.py - Jython post-script (Ghidra 11.4.1 headless): full structural export of the program.
# Ported 2026-09-04 (Task 2) from recon-2026-09-04/recon/agent-harness/scripts/DumpAll.py and extended:
#   functions/<addr>.c and <addr>.pcode for EVERY function (thunks included; a thunk gets a header comment
#   and whatever the decompiler returns), functions.json (structural inventory incl. prototype), callgraph.json
#   (callers/callees/call sites), flows.csv (every flow reference whose destination is in .text; used by
#   tools/hookability.py for the "no branch target in the first 5 bytes" test), summary.json.
# Usage: -postScript DumpAll.py <outDir>      (default C:\Users\james\i76-map\ghidra\export)
# @category Recon
import os, time, json
from ghidra.app.decompiler import DecompInterface, DecompileOptions
from ghidra.util.task import ConsoleTaskMonitor

args = getScriptArgs()
outdir = args[0] if len(args) > 0 else "C:\\Users\\james\\i76-map\\ghidra\\export"
if not os.path.isdir(outdir): os.makedirs(outdir)
fdir = os.path.join(outdir, "functions")
if not os.path.isdir(fdir): os.makedirs(fdir)

prog = currentProgram
fm = prog.getFunctionManager()
refMgr = prog.getReferenceManager()
listing = prog.getListing()
mem = prog.getMemory()
textBlk = mem.getBlock(".text")
funcs = list(fm.getFunctions(True))
t0 = time.time()
ifc = DecompInterface()
opts = DecompileOptions()
ifc.setOptions(opts)
ifc.openProgram(prog)
mon = ConsoleTaskMonitor()

def hx(a):
    return "%08x" % a.getOffset()

inv = []
cg = {}
nfail = 0
nthunk = 0
for f in funcs:
    ea = f.getEntryPoint()
    body = f.getBody()
    callers = sorted(set(hx(c.getEntryPoint()) for c in f.getCallingFunctions(mon)))
    callees = sorted(set(hx(c.getEntryPoint()) for c in f.getCalledFunctions(mon)))
    thunked = f.getThunkedFunction(True) if f.isThunk() else None
    rec = {"addr": hx(ea), "name": f.getName(), "size": body.getNumAddresses(),
           "start": hx(body.getMinAddress()), "end": hx(body.getMaxAddress()),
           "ranges": body.getNumAddressRanges(),
           "thunk": f.isThunk(), "thunk_target": (thunked.getName() if thunked is not None else None),
           "external": f.isExternal(),
           "cc": f.getCallingConventionName(), "params": f.getParameterCount(),
           "prototype": f.getPrototypeString(True, True),
           "custom_storage": f.hasCustomVariableStorage(),
           "stack_purge": f.getStackPurgeSize(),
           "name_source": str(f.getSymbol().getSource()),
           "n_callers": len(callers), "n_callees": len(callees),
           "refs_to_entry": refMgr.getReferenceCountTo(ea)}
    inv.append(rec)
    # call sites: instructions inside the body whose flow refs hit a function entry
    sites = []
    it = listing.getInstructions(body, True)
    while it.hasNext():
        ins = it.next()
        if not ins.getFlowType().isCall(): continue
        for r in ins.getReferencesFrom():
            if not r.getReferenceType().isCall(): continue
            t = r.getToAddress()
            tf = fm.getFunctionAt(t)
            sites.append([hx(ins.getAddress()), hx(t) if not t.isExternalAddress() else str(t),
                          (tf.getName() if tf is not None else None)])
    cg[hx(ea)] = {"name": f.getName(), "callers": callers, "callees": callees, "call_sites": sites}
    if f.isThunk(): nthunk += 1
    base = os.path.join(fdir, hx(ea))
    hdr = "// %s %s size=%d thunk=%s%s\n" % (hx(ea), f.getName(), body.getNumAddresses(), f.isThunk(),
          (" -> " + thunked.getName()) if thunked is not None else "")
    res = None
    try:
        res = ifc.decompileFunction(f, 60, mon)
    except Exception, e:
        res = None
        rec["decomp_error"] = "exception: %s" % e
    if res is None or not res.decompileCompleted():
        nfail += 1
        if "decomp_error" not in rec:
            rec["decomp_error"] = res.getErrorMessage() if res else "none"
        rec["decomp_ok"] = False
        fh = open(base + ".c", "w"); fh.write(hdr + "// DECOMPILE FAILED: %s\n" % rec["decomp_error"]); fh.close()
        fh = open(base + ".pcode", "w"); fh.write(""); fh.close()
        continue
    rec["decomp_ok"] = True
    hf = res.getHighFunction()
    c = res.getDecompiledFunction().getC() if res.getDecompiledFunction() is not None else ""
    fh = open(base + ".c", "w"); fh.write(hdr + c); fh.close()
    lines = []
    if hf is not None:
        pit = hf.getPcodeOps()
        while pit.hasNext():
            op = pit.next()
            lines.append(str(op))
    fh = open(base + ".pcode", "w"); fh.write("\n".join(lines)); fh.close()
    rec["c_lines"] = c.count("\n")
    rec["pcode_ops"] = len(lines)
dt = time.time() - t0
fh = open(os.path.join(outdir, "functions.json"), "w"); json.dump(inv, fh, indent=1, sort_keys=True); fh.close()
fh = open(os.path.join(outdir, "callgraph.json"), "w"); json.dump(cg, fh, indent=1, sort_keys=True); fh.close()

# flows.csv: every flow reference whose destination lies in .text
nflow = 0
fh = open(os.path.join(outdir, "flows.csv"), "w")
fh.write("from,to,type,is_call,is_jump,is_computed,is_conditional,from_func,to_func\n")
rit = refMgr.getReferenceIterator(prog.getMinAddress())
while rit.hasNext():
    r = rit.next()
    rt = r.getReferenceType()
    if not rt.isFlow(): continue
    t = r.getToAddress()
    if t.isExternalAddress() or textBlk is None or not textBlk.contains(t): continue
    ff = fm.getFunctionContaining(r.getFromAddress())
    tf = fm.getFunctionContaining(t)
    fh.write("%s,%s,%s,%d,%d,%d,%d,%s,%s\n" % (hx(r.getFromAddress()), hx(t), str(rt), 1 if rt.isCall() else 0,
             1 if rt.isJump() else 0, 1 if rt.isComputed() else 0, 1 if rt.isConditional() else 0,
             hx(ff.getEntryPoint()) if ff is not None else "", hx(tf.getEntryPoint()) if tf is not None else ""))
    nflow += 1
fh.close()

st = prog.getSymbolTable()
nsym = st.getNumSymbols()
summary = {"functions": len(funcs), "thunks": nthunk, "decomp_failed": nfail, "decomp_seconds": dt, "symbols": nsym,
           "flow_refs_into_text": nflow,
           "image_base": "%08x" % prog.getImageBase().getOffset(),
           "language": str(prog.getLanguageID()), "compiler": str(prog.getCompilerSpec().getCompilerSpecID()),
           "program": prog.getName(), "exe_md5": prog.getExecutableMD5(), "ghidra": "11.4.1"}
fh = open(os.path.join(outdir, "summary.json"), "w"); json.dump(summary, fh, indent=1, sort_keys=True); fh.close()
print("SUMMARY " + json.dumps(summary, sort_keys=True))
