# ApplyNamesTsv.py - Jython post-script: apply an addr/kind/name TSV (tools/demech2_names.py output) to the
# current program. FUNCTION / STUB / LIBRARY rows rename (creating the function if Ghidra has none there);
# GLOBAL rows become labels. Used on the MW2.DLL reference import only, never on i76_ref.exe.
#@category i76map
from ghidra.program.model.symbol import SourceType
import java.lang
args = getScriptArgs()
path = args[0]
fm = currentProgram.getFunctionManager()
n = {"renamed": 0, "created": 0, "labels": 0, "failed": 0}
for line in open(path):
    if line.startswith("#") or line.startswith("addr\t"):
        continue
    f = line.rstrip("\n").split("\t")
    if len(f) < 3:
        continue
    a = toAddr(int(f[0], 16)); kind, name = f[1], f[2]
    try:
        if kind == "GLOBAL":
            createLabel(a, name, True, SourceType.IMPORTED); n["labels"] += 1
            continue
        fn = fm.getFunctionAt(a)
        if fn is None:
            fn = createFunction(a, name)
            if fn is not None:
                n["created"] += 1
        if fn is not None:
            fn.setName(name, SourceType.IMPORTED); n["renamed"] += 1
        else:
            n["failed"] += 1
    except (Exception, java.lang.Throwable) as ex:
        n["failed"] += 1
print("ApplyNamesTsv: %s" % n)
