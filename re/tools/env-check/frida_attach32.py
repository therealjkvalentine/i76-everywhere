"""Task 6(b): 64-bit Python + Frida attaching to a throwaway 32-bit process.
Spawns SysWOW64\notepad.exe ourselves, attaches (never spawns via frida, per H10),
hooks kernel32!GetTickCount, calls it once from inside the target to prove the hook fires,
unloads, detaches, kills. Prints one JSON line."""
import ctypes, ctypes.wintypes, json, subprocess, sys, time
import frida

TARGET = r"C:\Windows\SysWOW64\notepad.exe"
p = subprocess.Popen([TARGET])
time.sleep(2.0)
h = ctypes.windll.kernel32.OpenProcess(0x1000, False, p.pid)  # PROCESS_QUERY_LIMITED_INFORMATION
wow = ctypes.wintypes.BOOL()
ctypes.windll.kernel32.IsWow64Process(h, ctypes.byref(wow))
ctypes.windll.kernel32.CloseHandle(h)
res = {"python": sys.version.split()[0], "python_bits": ctypes.sizeof(ctypes.c_void_p) * 8,
       "frida": frida.__version__, "target": TARGET, "pid": p.pid, "target_wow64": bool(wow.value)}
msgs = []
try:
    session = frida.attach(p.pid)
    script = session.create_script(r"""
        var k32 = Process.getModuleByName('kernel32.dll');
        var addr = k32.getExportByName('GetTickCount');
        var n = 0;
        Interceptor.attach(addr, {
            onEnter: function (args) { n++; },
            onLeave: function (retval) { if (n <= 2) send({hook_hit: n, tick: retval.toUInt32()}); }
        });
        send({arch: Process.arch, pointerSize: Process.pointerSize, gettickcount: addr.toString()});
        var f = new NativeFunction(addr, 'uint32', []);
        var v = f();
        send({self_call_ret: v});
        rpc.exports = { hits: function () { return n; } };
    """)
    script.on("message", lambda m, d: msgs.append(m.get("payload", m)))
    script.load()
    time.sleep(2.0)
    res["hook_hits_after_2s"] = script.exports_sync.hits()
    script.unload()
    session.detach()
    res["attach"] = "ok"
except Exception as e:
    res["attach"] = "FAIL: %r" % (e,)
finally:
    p.kill(); p.wait()
    res["target_exit"] = p.returncode
res["messages"] = msgs
print(json.dumps(res))
