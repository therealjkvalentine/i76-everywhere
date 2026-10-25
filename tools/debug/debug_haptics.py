r"""debug_haptics.py - I76 Debug's haptics-host starter (2026-10-20, owner: "not sure why no haptics host data in debug").

The Force feedback, Rumble, LFE and Motion tabs show what the haptics host (tools\haptics, i76haptics.exe) computes; the game
does not publish those numbers. Until now the tabs only said "No haptics host data" and the owner had to know the two command
lines. This module makes the state explain itself and starts the host in one click (Haptics tabs) or with DEBUG.bat --haptics:

* where the host is: --haptics-host / I76_HAPTICS_HOST, else tools\haptics beside this folder (the repo layout) or
  _tools\haptics (a shipped folder), else the owner's checkout tools\haptics. The built
  i76haptics.exe is preferred; haptics.ps1 (which builds it first, .NET 8 SDK) otherwise.
* what it could drive: winmm joysticks (what the game itself reads: joyGetNumDevs + joyGetPosEx) and XInput pads. With
  none, the start is refused with that message unless the caller forces a dry run.
* how it is started: `i76haptics live --source udp --port <tee> --debug-udp 127.0.0.1:<debug port>`, with the dashboard
  forwarding every telemetry datagram to <tee> (default 17676), so the dashboard keeps the game's port 7676. Without
  `--live` the host drives nothing (its outputs go to files, overwritten at every start, in %TEMP%\i76debug-haptics):
  that is the default, because a wheel's force must not be driven twice (the game's own force feedback, or a host the
  owner started himself). The Haptics tabs' "drive the devices" box (or DEBUG.bat --haptics-live) adds --live.
* only the process this module started is ever stopped (Stop button, or the dashboard exiting).
"""
import ctypes, ctypes.wintypes as wt, os, shutil, subprocess, sys, tempfile, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
OWNER_REPO_HAPTICS = (__import__("os").path.expanduser("~") + r"\i76-everywhere\tools\haptics")
EXE_REL = os.path.join("src", "Host", "bin", "Release", "net8.0", "i76haptics.exe")
TEE_PORT = 17676


class JOYINFOEX(ctypes.Structure):
    _fields_ = [(n, wt.DWORD) for n in ("dwSize", "dwFlags", "dwXpos", "dwYpos", "dwZpos", "dwRpos", "dwUpos", "dwVpos",
                                        "dwButtons", "dwButtonNumber", "dwPOV", "dwReserved1", "dwReserved2")]


class JOYCAPSW(ctypes.Structure):
    _fields_ = [("wMid", wt.WORD), ("wPid", wt.WORD), ("szPname", wt.WCHAR * 32)] + \
               [(n, wt.UINT) for n in ("wXmin", "wXmax", "wYmin", "wYmax", "wZmin", "wZmax", "wNumButtons", "wPeriodMin", "wPeriodMax",
                                       "wRmin", "wRmax", "wUmin", "wUmax", "wVmin", "wVmax", "wCaps", "wMaxAxes", "wNumAxes", "wMaxButtons")] + \
               [("szRegKey", wt.WCHAR * 32), ("szOEMVxD", wt.WCHAR * 260)]


def devices():
    """[(kind, name)] of the controllers the host could drive: winmm joysticks that answer joyGetPosEx, XInput pads.
    Enumeration only - nothing is opened or acquired."""
    out = []
    if os.name != "nt":
        return out
    try:
        winmm = ctypes.WinDLL("winmm")
        n = winmm.joyGetNumDevs()
        for i in range(min(n, 16)):
            ji = JOYINFOEX(); ji.dwSize = ctypes.sizeof(ji); ji.dwFlags = 0xff
            if winmm.joyGetPosEx(i, ctypes.byref(ji)) != 0:
                continue
            caps = JOYCAPSW()
            name = "joystick %d" % (i + 1)
            if winmm.joyGetDevCapsW(i, ctypes.byref(caps), ctypes.sizeof(caps)) == 0 and caps.szPname:
                name = "%s (joystick %d, %d axes, %d buttons)" % (caps.szPname, i + 1, caps.wNumAxes, caps.wNumButtons)
            out.append(("joystick", name))
    except OSError:
        pass
    for dll in ("xinput1_4", "xinput1_3", "xinput9_1_0"):
        try:
            xi = ctypes.WinDLL(dll)
        except OSError:
            continue
        buf = ctypes.create_string_buffer(16)
        for i in range(4):
            if xi.XInputGetState(i, buf) == 0:
                out.append(("xinput", "XInput pad %d" % (i + 1)))
        break
    return out


def kill_with_us(proc):
    """put proc in a job that closes with this process (JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE): closing the dashboard's window,
    which kills Python without running its cleanup, still ends the host it started. Returns the job handle (kept open)."""
    if os.name != "nt":
        return None
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateJobObjectW.restype = wt.HANDLE
    job = k32.CreateJobObjectW(None, None)
    if not job:
        return None
    info = (ctypes.c_byte * 144)()                             # JOBOBJECT_EXTENDED_LIMIT_INFORMATION (x64: 144 B, x86: 112 B)
    size = 144 if ctypes.sizeof(ctypes.c_void_p) == 8 else 112
    struct_off = 16                                            # BasicLimitInformation.LimitFlags after two LARGE_INTEGERs
    ctypes.c_uint32.from_buffer(info, struct_off).value = 0x2000
    k32.SetInformationJobObject(wt.HANDLE(job), 9, info, size)   # JobObjectExtendedLimitInformation
    k32.AssignProcessToJobObject(wt.HANDLE(job), wt.HANDLE(int(proc._handle)))
    return job


def find_host(hint=""):
    """{'dir', 'exe' or None, 'ps1' or None, 'how'} of the first haptics host found, else None"""
    cands = []
    for h in (hint, os.environ.get("I76_HAPTICS_HOST", "")):
        if h:
            cands.append((os.path.dirname(h) if os.path.isfile(h) and h.lower().endswith(".ps1") else h, "--haptics-host / I76_HAPTICS_HOST"))
    cands += [(os.path.join(TOOLS, "haptics"), "beside this tool"), (OWNER_REPO_HAPTICS, "the i76-everywhere checkout")]
    for d, how in cands:
        if os.path.isfile(d) and d.lower().endswith(".exe"):
            return {"dir": os.path.dirname(d), "exe": d, "ps1": None, "how": how}
        exe, ps1 = os.path.join(d, EXE_REL), os.path.join(d, "haptics.ps1")
        if os.path.isfile(exe) or os.path.isfile(ps1):
            return {"dir": d, "exe": exe if os.path.isfile(exe) else None, "ps1": ps1 if os.path.isfile(ps1) else None, "how": how}
    return None


class HapticsLauncher:
    """Starts / stops ONE haptics host process (its own) and explains the state for the Haptics tabs."""

    def __init__(self, hub, tel_source, debug_port, hint="", tee_port=TEE_PORT):
        self.hub, self.tel, self.debug_port, self.hint, self.tee_port = hub, tel_source, debug_port, hint, tee_port
        self.proc, self.cmd, self.live, self.started_at, self.msg = None, None, False, 0.0, ""
        self.log_path = os.path.join(tempfile.gettempdir(), "i76debug-haptics", "host.log")
        self.lock = threading.Lock()
        self._dev, self._dev_at, self._host = [], 0.0, None

    def devices(self):
        if time.time() - self._dev_at > 5.0:
            self._dev, self._dev_at = devices(), time.time()
            self._host = find_host(self.hint)
        return self._dev

    def running(self):
        return self.proc is not None and self.proc.poll() is None

    def log_tail(self, n=4):
        try:
            with open(self.log_path, encoding="utf-8", errors="replace") as f:
                return [ln.rstrip() for ln in f.readlines()[-n:]]
        except OSError:
            return []

    def start(self, live=False, force=False):
        """returns (ok, message)"""
        with self.lock:
            if self.running():
                return True, "the haptics host this dashboard started is already running (pid %d)" % self.proc.pid
            devs = self.devices()
            host = self._host
            if not host:
                self.msg = ("no haptics host found: it is not part of this folder (tools\\haptics in the i76-everywhere repo, "
                            ".NET 8). Set I76_HAPTICS_HOST to its folder, or start it by hand.")
                return False, self.msg
            if not devs and not force:
                self.msg = ("no wheel or gamepad found (winmm joysticks 0, XInput pads 0): there is nothing for the haptics host "
                            "to drive. 'Start anyway (dry run)' shows what it would send.")
                return False, self.msg
            if live and not devs:
                return False, "--live needs a wheel or a pad; none found"
            if not host["exe"] and not (host["ps1"] and shutil.which("dotnet")):
                self.msg = "the haptics host at %s is not built and no .NET SDK (dotnet) is on the PATH to build it" % host["dir"]
                return False, self.msg
            if self.tel is None:
                return False, "telemetry is off in this dashboard (--tel-port -1): the host would have no input"
            if not self.tel.mode.startswith("udp"):
                self.msg = ("this dashboard could not bind the telemetry port (%s): another program holds it - if that is a haptics "
                            "host, restart it with --debug-udp; else stop it and press Start again" % self.tel.mode)
                return False, self.msg
            self.tel.add_tee(self.tee_port)
            out = os.path.dirname(self.log_path)
            os.makedirs(out, exist_ok=True)
            args = ["live", "--source", "udp", "--port", str(self.tee_port), "--debug-udp", "127.0.0.1:%d" % self.debug_port,
                    "--out", out] + (["--live"] if live else [])
            if host["exe"]:
                cmd = [host["exe"]] + args
            else:
                cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", host["ps1"]] + args
            try:
                logf = open(self.log_path, "w", encoding="utf-8")
                self.proc = subprocess.Popen(cmd, cwd=host["dir"], stdout=logf, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                logf.close()                                    # the child has its own handle
            except OSError as e:
                self.msg = "could not start the haptics host: %s" % e
                return False, self.msg
            self.job = kill_with_us(self.proc)
            self.cmd, self.live, self.started_at = " ".join(cmd), live, time.time()
            self.msg = "haptics host started (pid %d, %s): %s" % (self.proc.pid, "devices LIVE" if live else "dry run, drives nothing", self.cmd)
            return True, self.msg

    def stop(self):
        with self.lock:
            if not self.running():
                self.proc = None
                return False, "no haptics host started by this dashboard is running"
            pid = self.proc.pid
            self.proc.terminate()
            try:
                self.proc.wait(5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
            self.proc = None
            self.msg = "haptics host (pid %d) stopped" % pid
            return True, self.msg

    def status(self):
        devs = self.devices()
        host = self._host
        st = {"running": self.running(), "pid": self.proc.pid if self.running() else None, "live": self.live, "cmd": self.cmd,
              "host": host and (host["exe"] or host["ps1"]), "host_how": host and host["how"], "built": bool(host and host["exe"]),
              "devices": [n for k, n in devs], "msg": self.msg, "tee": self.tee_port, "log": self.log_path,
              "tel_mode": self.tel.mode if self.tel else "off"}
        if self.proc is not None and not self.running():
            st["exited"] = self.proc.poll()
            st["log_tail"] = self.log_tail(6)
        elif self.running():
            st["log_tail"] = self.log_tail(3)
            st["uptime"] = round(time.time() - self.started_at, 1)
        return st
