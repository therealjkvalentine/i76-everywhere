r"""i76debug.py - I76 Debug: a local web dashboard of everything the I'76 tooling knows while the game runs.

    python tools\debug\i76debug.py                  serve http://127.0.0.1:17690/ and open it in the browser
    DEBUG.bat                                        the same (tools\debug\DEBUG.bat); TRAINER.bat opens it on the Trainer tab

Panels: Overview, Telemetry, Events, Force feedback, Rumble, LFE / transducers, Motion, Collision, Terrain / render,
Trainer, Log (README.md in this folder says what each shows and where it comes from).

Inputs, all optional - a panel without its source says so:
  --tel-port 7676        the proxy's telemetry (I76_TELEMETRY). Bound exclusively; when the port is taken (the haptics
                         host owns it) the tool falls back to Local\I76Telemetry opened EXISTING-only. 0 = shm only.
  --tee 17676[,..]       forward every telemetry datagram to these loopback ports, so the haptics host can listen too
                         (haptics.ps1 live --source udp --port 17676 --debug-udp)
  --haptics-port 17680   the haptics host's --debug-udp datagrams (bus, effect contributions, wheel/pad/LFE/motion)
  --log PATH             mciproxy.log to follow (default: beside the attached / running game, else the lab copy)
  --game-dir DIR         where the log and STRLKUP.DLL are (instead of guessing)
Trainer: --any (allow a non-sandbox game, as TRAINER.bat --any), --no-attach (never open the game process: read-only
panels only), --no-trainer.
Server: --http-port 17690, --no-browser, --tab trainer (the tab to open), --seconds N (exit after N s; tests).

Nothing here creates a named shared-memory section, opens a device, plays audio, or sends anywhere but 127.0.0.1.
"""
import argparse, json, os, sys, threading, time, webbrowser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "trainer"))
import debug_core
from debug_core import Hub, TelemetrySource, HapticsSource, LAB_GAME, file_md5

STATIC = os.path.join(HERE, "static")
CTYPES = {".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
          ".svg": "image/svg+xml", ".png": "image/png", ".json": "application/json"}


def running_game_path():
    """path of a running i76*.exe, for READING its log / DLL only (no handle beyond the image-name query is kept)"""
    try:
        import i76trainer
        import ctypes, ctypes.wintypes as wt
        arr = (wt.DWORD * 4096)(); got = wt.DWORD()
        i76trainer.psapi.EnumProcesses(arr, ctypes.sizeof(arr), ctypes.byref(got))
        for pid in arr[:got.value // 4]:
            h = i76trainer.k32.OpenProcess(0x1000, False, pid)
            if not h:
                continue
            buf = ctypes.create_unicode_buffer(1024); n = wt.DWORD(1024)
            ok = i76trainer.k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n))
            i76trainer.k32.CloseHandle(h)
            b = os.path.basename(buf.value).lower()
            if ok and b.startswith("i76") and b.endswith(".exe") and "wheel" not in b and "haptics" not in b:
                return buf.value
    except Exception:
        pass
    return None


class Server:
    def __init__(self, args):
        self.args = args
        self.hub = Hub()
        self.stop_ev = threading.Event()
        self.tlock = threading.RLock()
        tee = [int(p) for p in (args.tee or "").split(",") if p.strip()]
        self.tel = TelemetrySource(self.hub, port=args.tel_port, tee=tee) if args.tel_port is not None and args.tel_port >= 0 else None
        self.hap = HapticsSource(self.hub, port=args.haptics_port) if args.haptics_port else None
        self.hub.tel_source, self.hub.hap_source = self.tel, self.hap
        self.trainer = None
        if not args.no_trainer:
            from debug_trainer import TrainerCore
            self.trainer = TrainerCore(self.hub, allow_any=args.any, attach=not args.no_attach)
            self.hub.trainer = LockedTrainer(self.trainer, self.tlock)
        self.game_dir, self.game_dir_from, self.dll_md5, self.dll_path = None, None, None, None
        self.next_game_check = 0.0

    # ---- game dir, log path, DLL md5 (read-only)
    def resolve_game_dir(self):
        a = self.args
        if a.log:
            return os.path.dirname(os.path.abspath(a.log)), "--log"
        if a.game_dir:
            return a.game_dir, "--game-dir"
        if self.trainer and self.trainer.path:
            return os.path.dirname(self.trainer.path), "attached game"
        p = running_game_path()
        if p:
            return os.path.dirname(p), "running game (read-only)"
        return LAB_GAME, "default (lab copy)"

    def refresh_game(self):
        d, frm = self.resolve_game_dir()
        if d != self.game_dir:
            self.game_dir, self.game_dir_from = d, frm
            dll = next((os.path.join(d, n) for n in ("STRLKUP.DLL", "Strlkup.dll", "strlkup.dll") if os.path.exists(os.path.join(d, n))), None)
            self.dll_path, self.dll_md5 = dll, file_md5(dll) if dll else None
            with self.hub.lock:
                self.hub.log.set_path(self.args.log or os.path.join(d, "mciproxy.log"))
        with self.hub.lock:
            self.hub.game_info = {"dir": self.game_dir, "from": self.game_dir_from, "dll": self.dll_path, "dll_md5": self.dll_md5,
                                  "log": self.hub.log.path, "log_exists": bool(self.hub.log.path and os.path.exists(self.hub.log.path)),
                                  "sandbox": debug_core.LAB_GAME}

    # ---- threads
    def log_loop(self):
        while not self.stop_ev.is_set():
            if time.time() >= self.next_game_check:
                self.next_game_check = time.time() + 2.0
                try:
                    self.refresh_game()
                except Exception as e:
                    print("game check:", e)
            with self.hub.lock:
                self.hub.log.poll()
            self.stop_ev.wait(0.25)

    def trainer_loop(self):
        k = 0
        while not self.stop_ev.is_set():
            with self.tlock:
                try:
                    self.trainer.tick()
                    if k % 2 == 0:
                        self.trainer.direct_tick()
                except Exception as e:
                    self.trainer.log("tick error: %r" % e)
            k += 1
            self.stop_ev.wait(0.1)

    def start(self):
        if self.tel:
            self.tel.start()
        if self.hap:
            self.hap.start()
        threading.Thread(target=self.log_loop, daemon=True, name="log").start()
        if self.trainer:
            threading.Thread(target=self.trainer_loop, daemon=True, name="trainer").start()

    def stop(self):
        self.stop_ev.set()
        for s in (self.tel, self.hap):
            if s:
                s.stop_ev.set()
        if self.trainer:
            with self.tlock:
                self.trainer.close()


class LockedTrainer:
    """the hub's view of the trainer: status() under the trainer lock"""

    def __init__(self, t, lock):
        self.t, self.lock = t, lock

    def status(self):
        with self.lock:
            return self.t.status()


def make_handler(srv):
    hub = srv.hub

    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *a):            # quiet
            pass

        def send_json(self, obj, code=200):
            body = json.dumps(obj, separators=(",", ":"), default=str).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            u = urlparse(self.path)
            q = parse_qs(u.query)
            if u.path in ("/", "/index.html"):
                return self.static("index.html")
            if u.path.startswith("/static/"):
                return self.static(u.path[len("/static/"):])
            if u.path == "/api/state":
                return self.send_json(hub.snapshot(int(q.get("history", ["600"])[0])))
            if u.path == "/api/log":
                with hub.lock:
                    return self.send_json({"lines": hub.log.tail(int(q.get("n", ["500"])[0]), q.get("q", [None])[0]), "path": hub.log.path})
            if u.path == "/api/health":
                return self.send_json({"ok": True, "tel": srv.tel.mode if srv.tel else "off", "hap": srv.hap.mode if srv.hap else "off",
                                       "trainer": bool(srv.trainer)})
            if u.path == "/api/stream":
                return self.stream(float(q.get("hz", ["20"])[0]))
            self.send_error(404)

        def do_POST(self):
            u = urlparse(self.path)
            n = int(self.headers.get("Content-Length") or 0)
            try:
                req = json.loads(self.rfile.read(n) or b"{}")
            except ValueError:
                return self.send_json({"ok": False, "error": "bad json"}, 400)
            if u.path == "/api/trainer":
                if not srv.trainer:
                    return self.send_json({"ok": False, "error": "trainer disabled (--no-trainer)"}, 409)
                with srv.tlock:
                    ok = srv.trainer.action(req)
                    st = srv.trainer.status()
                return self.send_json({"ok": ok, "trainer": st})
            self.send_error(404)

        def static(self, rel):
            p = os.path.normpath(os.path.join(STATIC, rel))
            if not p.startswith(STATIC) or not os.path.isfile(p):
                return self.send_error(404)
            with open(p, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", CTYPES.get(os.path.splitext(p)[1], "application/octet-stream"))
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def stream(self, hz):
            """Server-sent events: one 'data:' JSON message per tick with what this client has not seen (Hub.delta)."""
            hz = max(1.0, min(30.0, hz))
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            self.close_connection = True
            cur = {}
            try:
                first = hub.snapshot(600)
                cur.update(s=hub.sample_id, e=hub.event_id, h=hub.hsample_id, he=hub.hap_event_id,
                           l=first["log_tail"][-1]["id"] if first["log_tail"] else 0, hc=hub.hap_count)
                self.wfile.write(b"event: snapshot\ndata: " + json.dumps(first, separators=(",", ":"), default=str).encode() + b"\n\n")
                self.wfile.flush()
                while not srv.stop_ev.is_set():
                    time.sleep(1.0 / hz)
                    d = hub.delta(cur)
                    self.wfile.write(b"data: " + json.dumps(d, separators=(",", ":"), default=str).encode() + b"\n\n")
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
                pass

    return H


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--http-port", type=int, default=17690)
    ap.add_argument("--tel-port", type=int, default=7676, help="proxy telemetry UDP port (0 = shm only, -1 = off)")
    ap.add_argument("--tee", default="", help="forward telemetry datagrams to these loopback ports (comma list)")
    ap.add_argument("--haptics-port", type=int, default=17680, help="haptics host --debug-udp port (0 = off)")
    ap.add_argument("--log", default="", help="mciproxy.log to follow")
    ap.add_argument("--game-dir", default="", help="game folder (log + STRLKUP.DLL)")
    ap.add_argument("--any", action="store_true", help="trainer: allow a game that is not the sandbox copy")
    ap.add_argument("--no-attach", action="store_true", help="trainer: never open the game process")
    ap.add_argument("--no-trainer", action="store_true")
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--tab", default="", help="tab to open (overview, telemetry, ..., trainer, log)")
    ap.add_argument("--seconds", type=float, default=0, help="exit after N seconds (tests)")
    args = ap.parse_args(argv)

    srv = Server(args)
    httpd = ThreadingHTTPServer(("127.0.0.1", args.http_port), make_handler(srv))
    httpd.daemon_threads = True
    port = httpd.server_address[1]
    srv.start()
    url = "http://127.0.0.1:%d/%s" % (port, ("#" + args.tab) if args.tab else "")
    print("I76 Debug: %s" % url, flush=True)
    print("  telemetry: %s%s" % ("udp 127.0.0.1:%d" % args.tel_port if args.tel_port and args.tel_port > 0 else ("shm only" if args.tel_port == 0 else "off"),
                                 (" (tee -> %s)" % args.tee) if args.tee else ""), flush=True)
    print("  haptics debug: %s" % ("udp 127.0.0.1:%d" % args.haptics_port if args.haptics_port else "off"), flush=True)
    print("  trainer: %s" % ("off" if args.no_trainer else ("no attach" if args.no_attach else ("any game" if args.any else "sandbox only"))), flush=True)
    print("  Ctrl+C stops.", flush=True)
    if not args.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    if args.seconds:
        threading.Timer(args.seconds, httpd.shutdown).start()
    try:
        httpd.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        srv.stop()
        httpd.server_close()
        if srv.tel:
            print("  telemetry: %d datagrams%s" % (srv.tel.received, (", %d forwarded" % srv.tel.forwarded) if srv.tel.tee else ""))
        if srv.hap:
            print("  haptics debug: %d datagrams" % srv.hap.received)
    return 0


if __name__ == "__main__":
    sys.exit(main())
