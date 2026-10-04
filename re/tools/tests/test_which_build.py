#!/usr/bin/env python3
r"""test_which_build.py - offline + fake-target tests for tools\which_build.py (no game launch).

    python tools\tests\test_which_build.py

1. selftest: FileImage diff of pristine / pristine_fix / patched i76.exe against the pristine bytes.
2. fake target A: pristine image mapped at 0x400000 in a throwaway python.exe, i76fix patch1 applied
   in memory -> expect .text allowlisted (one 5-byte range at 0x499b25), everything else identical,
   H0 PASS, import descriptors read from live memory = the pristine 13 names (WIN32.dll, USER32.dll).
3. fake target B: the patched i76.exe image -> expect H0 FAIL, u32x.dll + WINMM.dll in the live
   import descriptors.
4. WOW64 read path: SysWOW64\notepad.exe started hidden; LiveImage.modules() finds the main module,
   IsWow64Process is true, the PE header read at the live base carries the file's TimeDateStamp.
Every assertion prints its measured value; exit 0 only if all pass.
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, "..")
sys.path.insert(0, TOOLS)
import pe_ident  # noqa: E402
import which_build as wb  # noqa: E402

GAME = wb.DEFAULT_GAME
PY = sys.executable
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print("%s %s %s" % ("PASS" if cond else "FAIL", name, detail))


def run_wb(args):
    cp = subprocess.run([PY, os.path.join(TOOLS, "which_build.py")] + args + ["--json"], capture_output=True, text=True, timeout=300)
    out = cp.stdout
    i = out.find("\n{")
    stamp = json.loads(out[i + 1:]) if i >= 0 else None
    return cp.returncode, out, stamp


def fake(image, patches=()):
    cmd = [PY, os.path.join(HERE, "fake_target.py"), "--image", image, "--seconds", "120"]
    for p in patches:
        cmd += ["--patch", p]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True)
    line = proc.stdout.readline().strip()
    print("  fake target:", line)
    if not line.startswith("READY"):
        proc.kill()
        raise RuntimeError(line)
    return proc


def main():
    # 1. offline selftest
    rc = subprocess.run([PY, os.path.join(TOOLS, "which_build.py"), "--selftest"], capture_output=True, text=True).returncode
    check("selftest exit 0", rc == 0, "rc=%d" % rc)

    # 2. fake target A: pristine + in-memory i76fix patch1
    t = fake(os.path.join(GAME, "i76.exe.2017galaxy"), ["0x499b25:b8c8000000"])
    try:
        rc, out, st = run_wb(["--pid", str(t.pid), "--base", "0x400000"])
        s = st["h0_summary"]
        text = [r for r in st["regions"] if r["region"] == ".text"][0]
        check("A: H0 pass (rc 0)", rc == 0 and st["h0_pass"], "rc=%d summary=%s" % (rc, s))
        check("A: .text allowlisted, one range at 0x499b25 len 5", s[".text"] == "allowlisted" and len(text["ranges"]) == 1
              and text["ranges"][0]["va_lo"] == "0x499b25" and text["ranges"][0]["len"] == 5, str(text["ranges"]))
        check("A: other regions identical", all(s[k] == "identical" for k in s if k != ".text"), str(s))
        names = st["live_imports"].get("dll_names", [])
        check("A: live import descriptors = pristine 13 incl WIN32.dll/USER32.dll", len(names) == 13 and "WIN32.dll" in names and "USER32.dll" in names, str(names))
        check("A: no short reads", not st.get("short_reads"), str(st.get("short_reads")))
        check("A: process/session block present", "session" in st and "process" in st and st["process"].get("command_line"), str(st.get("process")))
        check("A: main module is python (fake), base != 0x400000 noted", st["main_module"] and "python" in st["main_module"]["path"].lower(), str(st.get("main_module")))
    finally:
        t.kill()

    # 3. fake target B: the patched local i76.exe image
    t = fake(os.path.join(GAME, "i76.exe"))
    try:
        rc, out, st = run_wb(["--pid", str(t.pid), "--base", "0x400000"])
        s = st["h0_summary"]
        names = st["live_imports"].get("dll_names", [])
        tail = [r for r in st["regions"] if r["region"] == ".text-tail"][0]
        check("B: H0 fail (rc 1)", rc == 1 and not st["h0_pass"], "rc=%d summary=%s" % (rc, s))
        check("B: live import descriptors carry u32x.dll and WINMM.dll", "u32x.dll" in names and "WINMM.dll" in names, str(names))
        check("B: .text-tail +132 at 0x4bbe55", len(tail["ranges"]) == 1 and tail["ranges"][0]["va_lo"] == "0x4bbe55" and tail["ranges"][0]["len"] == 132, str(tail["ranges"]))
        check("B: import_flags u32x/winmm true, user32/win32 false", st["import_flags"] == {"u32x": True, "user32": False, "winmm": True, "win32": False}, str(st["import_flags"]))
    finally:
        t.kill()

    # 4. real 32-bit (WOW64) process read path
    np_path = r"C:\Windows\SysWOW64\notepad.exe"
    if os.path.exists(np_path):
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0  # SW_HIDE
        n = subprocess.Popen([np_path], startupinfo=si)
        try:
            time.sleep(1.5)
            img = wb.LiveImage(n.pid)
            mods = img.modules()
            main = mods[0] if mods else None
            check("notepad: WOW64 process", img.is_wow64())
            check("notepad: main module found", main and os.path.basename(main["path"]).lower() == "notepad.exe", str(main))
            if main:
                hdr = img.read(main["base"], 0x400)
                e_lfanew = int.from_bytes(hdr[0x3c:0x40], "little")
                live_ts = int.from_bytes(hdr[e_lfanew + 8:e_lfanew + 12], "little")
                file_ts = pe_ident.identity(np_path)["pe_timestamp"]
                check("notepad: live PE TimeDateStamp == file", live_ts == file_ts, "live %d file %d base %s" % (live_ts, file_ts, hex(main["base"])))
                li = wb.parse_live_imports(img, main["base"])
                check("notepad: import descriptors readable from live base", li.get("dll_names"), str(li.get("dll_names", li))[:200])
            check("notepad: session id readable", isinstance(img.session_id(), int), str(img.session_id()))
            img.close()
        finally:
            n.kill()
    else:
        check("notepad: SysWOW64\\notepad.exe present", False)

    failed = [n for n, ok in results if not ok]
    print("\n%d checks, %d failed%s" % (len(results), len(failed), (": " + ", ".join(failed)) if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
