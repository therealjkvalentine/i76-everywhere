r"""Task 6(c): PyGhidra smoke test. Opens a scratch project (NOT ghidra\proj), imports the pristine exe
without analysis, prints Ghidra's version and basic program facts. Prints one JSON line."""
import json, os, sys, time
os.environ.setdefault("GHIDRA_INSTALL_DIR",
    r"C:\Users\james\Downloads\ghidra_11.4.1_PUBLIC_20250731\ghidra_11.4.1_PUBLIC")
SCRATCH = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.environ["TEMP"], "pyghidra-smoke")
BIN = r"C:\Users\james\i76-uncap-lab\game\i76.exe.2017galaxy"
t0 = time.time()
import pyghidra
res = {"pyghidra": pyghidra.__version__, "ghidra_install_dir": os.environ["GHIDRA_INSTALL_DIR"]}
pyghidra.start()
from ghidra.framework import Application
import java.lang.System as JS
res["ghidra_version"] = str(Application.getApplicationVersion())
res["ghidra_release"] = str(Application.getApplicationReleaseName())
res["java_version"] = str(JS.getProperty("java.version"))
res["start_s"] = round(time.time() - t0, 1)
with pyghidra.open_program(BIN, project_location=SCRATCH, project_name="pyghidra-smoke", analyze=False) as flat:
    prog = flat.getCurrentProgram()
    res["program"] = prog.getName()
    res["image_base"] = str(prog.getImageBase())
    res["language"] = str(prog.getLanguageID())
    res["compiler_spec"] = str(prog.getCompilerSpec().getCompilerSpecID())
    res["blocks"] = [(str(b.getName()), str(b.getStart()), int(b.getSize())) for b in prog.getMemory().getBlocks()]
    res["functions_before_analysis"] = prog.getFunctionManager().getFunctionCount()
res["total_s"] = round(time.time() - t0, 1)
print(json.dumps(res))
