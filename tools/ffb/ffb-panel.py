#!/usr/bin/env python3
"""ffb-panel.py - the FFB / LFE tuning page for the custom wheel force feedback (2026-10-25).

Serves http://127.0.0.1:17691/ (loopback only). What it shows comes from the interposer
(ffb-interposer.ps1), which publishes its state as JSON datagrams to 127.0.0.1:17682:

  * telemetry: speed, yaw rate against the steering law, slip, slide, surface, airborne, gear, rpm, ammo
  * every FFB channel's current output as a meter, with solo / mute (sent to the interposer's command
    port 127.0.0.1:17683 - the interposer owns the gates, this page only asks)
  * master and per-channel gains as sliders. A slider WRITES ffb-tune-owner.json (only the values that
    differ from the defaults, the same format as the console's [s]); the interposer re-reads the file
    when it changes and reports each changed value back, so the page shows "applied" only once the loop
    that drives the wheel says so
  * the event log (shots, hits, landing, ignition, gear, surface, tune changes) with times
  * the "things we want noticeable" checklist; each verdict is appended to a session notes file
    (notes\\ffb-notes-<start time>.csv beside the tune file)
  * the LFE bus (the bass-shaker sources), its gains, and the game's own music / SFX / voice levels,
    READ-ONLY.

THE LFE RULE (owner, 2026-10-24): the shakers are driven by game EVENTS and state only - impacts, road,
engine, weapons, landings. Never by the game's audio, and never by boosting voice or music. This server
refuses any tune key that names music, voice, the mix or a loopback, and only LFE event-source gains are
offered on the page. The music / voice levels are shown so it can be seen that nothing here touches them.

Stdlib only (the I76 Debug pattern: ThreadingHTTPServer, server-sent events, ?poll=1 fallback), no build
step, no CDN. Run: FFB-WEB-PANEL.bat, or  python ffb-panel.py [--no-browser] [--http-port N]
"""
import argparse, csv, json, math, os, re, socket, sys, threading, time, webbrowser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
PAGE = os.path.join(HERE, "ffb-panel.html")
VERSION = "2026-10-25"

# Keys the page may never write. The LFE rule: game events only, never the game's audio.
FORBIDDEN = re.compile(r"(music|voice|vocal|speech|mixbus|gamemix|loopback|capture|duckmusic)", re.I)
# Hard limits on top of "0 .. 3 x default": nothing the page sends can exceed these.
LIMITS = {"Master": (0.0, 1.5), "HitSideSign": (-1.0, 1.0), "PavementScale": (0.0, 2.0), "OffroadScale": (0.0, 2.0),
          "UndersteerDrop": (0.0, 1.0), "SurfaceFadeMs": (0.0, 3000.0)}
ABS_MAX = 10000.0


def clean(o):
    """NaN / inf -> None so the browser's JSON.parse accepts what we forward."""
    if isinstance(o, float):
        return o if math.isfinite(o) else None
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, list):
        return [clean(v) for v in o]
    return o


class Hub:
    def __init__(self, args):
        self.args = args
        self.lock = threading.Lock()
        self.state = None          # last "ffb" datagram
        self.state_wall = 0.0
        self.meta = None           # last "meta" datagram
        self.lfe = None            # last "lfe" datagram (ffb-lfe-live.ps1, when a shaker is running)
        self.lfe_wall = 0.0
        self.bye = None
        self.pid = None
        self.events = []           # [id, t, text, wall] for the current interposer pid
        self.ev_seen = 0
        self.packets = 0
        self.bad = 0
        self.notes = []            # this session's checklist verdicts
        self.notes_path = None
        self.tune_log = []         # what this page wrote, with the interposer's confirmation
        self.started = time.time()
        self.stop_ev = threading.Event()
        self.ctl = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # ---- the interposer's datagrams ------------------------------------------------------------------
    def udp_loop(self, port):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if os.name == "nt":
            try:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            except (AttributeError, OSError):
                pass
            try:
                s.ioctl(socket.SIO_UDP_CONNRESET, False)
            except (AttributeError, OSError, ValueError):
                pass
        s.bind(("127.0.0.1", port))
        s.settimeout(0.5)
        while not self.stop_ev.is_set():
            try:
                data, _ = s.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                continue
            try:
                m = json.loads(data.decode("utf-8", "replace"))
            except ValueError:
                self.bad += 1
                continue
            self.take(m)

    def take(self, m):
        k = m.get("k")
        now = time.time()
        with self.lock:
            self.packets += 1
            if k == "ffb":
                if m.get("pid") != self.pid:
                    self.pid = m.get("pid"); self.events = []; self.ev_seen = 0; self.meta = None
                self.state = m; self.state_wall = now; self.bye = None
                for e in m.get("ev") or []:
                    if isinstance(e, list) and len(e) >= 3 and e[0] > self.ev_seen:
                        self.events.append([e[0], e[1], e[2], now])
                        self.ev_seen = e[0]
                del self.events[:-500]
                self.confirm_tune()
            elif k == "meta":
                if m.get("pid") == self.pid or self.pid is None:
                    self.meta = m
                    self.confirm_tune()
            elif k == "lfe":
                self.lfe = m; self.lfe_wall = now
            elif k == "bye":
                self.bye = {"pid": m.get("pid"), "wall": now}

    def confirm_tune(self):
        if not self.meta:
            return
        tune = self.meta.get("tune") or {}
        for w in self.tune_log:
            if w.get("applied") is None and w["key"] in tune and abs(float(tune[w["key"]]) - w["value"]) < 1e-6:
                w["applied"] = time.time()

    # ---- what the page reads ------------------------------------------------------------------------
    def snapshot(self, since_ev=0):
        now = time.time()
        with self.lock:
            age = now - self.state_wall if self.state_wall else None
            status = "waiting"
            if self.bye:
                status = "stopped"                  # the interposer said goodbye (it clears on its next datagram)
            elif self.state and age is not None and age < 1.5:
                status = "live"
            elif self.state:
                status = "stale"
            return clean({
                "server": {"version": VERSION, "uptime": round(now - self.started, 1), "packets": self.packets, "bad": self.bad,
                           "udp_port": self.args.udp_port, "ctl_port": self.args.ctl_port, "notes_path": self.notes_path,
                           "tune_file": self.tune_file()},
                "status": status, "age": None if age is None else round(age, 2),
                "state": self.state, "meta": self.meta,
                "lfe_out": self.lfe if (self.lfe and now - self.lfe_wall < 2.0) else None,
                "events": [e for e in self.events if e[0] > since_ev][-200:],
                "notes": self.notes[-200:],
                "tune_log": self.tune_log[-40:],
            })

    def tune_file(self):
        if self.meta and self.meta.get("tune_file"):
            return self.meta["tune_file"]
        return os.path.join(HERE, "ffb-tune-owner.json")

    # ---- writes ---------------------------------------------------------------------------------------
    def set_tune(self, req):
        with self.lock:
            meta = self.meta
        if not meta:
            return 409, {"ok": False, "error": "the interposer is not running (no defaults known yet) - start the game with the wheel"}
        defaults = meta.get("defaults") or {}
        path = meta.get("tune_file") or self.tune_file()
        changes = {}
        if req.get("reset_all"):
            changes = {k: None for k in defaults}
        else:
            key = str(req.get("key", ""))
            if FORBIDDEN.search(key):
                return 403, {"ok": False, "error": "refused: %s - the LFE / FFB are driven by game events only, never by the game's music or voice" % key}
            if key not in defaults:
                return 400, {"ok": False, "error": "unknown tune key %r" % key}
            if req.get("reset"):
                changes[key] = None
            else:
                try:
                    v = float(req.get("value"))
                except (TypeError, ValueError):
                    return 400, {"ok": False, "error": "value must be a number"}
                if not math.isfinite(v):
                    return 400, {"ok": False, "error": "value must be finite"}
                d = float(defaults[key])
                lo, hi = LIMITS.get(key, (0.0, max(3.0 * abs(d), 1.0) if d >= 0 else 0.0))
                if d < 0 and key not in LIMITS:
                    lo, hi = 3.0 * d, 0.0
                hi = min(hi, ABS_MAX)
                if key == "HitSideSign":
                    v = 1.0 if v >= 0 else -1.0
                v = max(lo, min(hi, v))
                changes[key] = round(v, 4)
        cur = {}
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8-sig") as f:
                    txt = f.read().strip()
                cur = json.loads(txt) if txt else {}
            except (OSError, ValueError) as e:
                return 500, {"ok": False, "error": "could not read %s: %s" % (path, e)}
        for k, v in changes.items():
            if v is None or (k in defaults and abs(float(defaults[k]) - v) < 1e-9):
                cur.pop(k, None)
            else:
                cur[k] = v
        out = {k: cur[k] for k in sorted(cur)}
        body = json.dumps(out, indent=4) if out else "{}"
        tmp = path + ".panel-tmp"
        try:
            with open(tmp, "w", encoding="ascii", newline="\r\n") as f:
                f.write(body + "\n")
            os.replace(tmp, path)
            with open(path, "r", encoding="ascii") as f:
                back = json.loads(f.read())
        except (OSError, ValueError) as e:
            return 500, {"ok": False, "error": "could not write %s: %s" % (path, e)}
        if back != out:
            return 500, {"ok": False, "error": "read-back of %s differs from what was written" % path}
        now = time.time()
        with self.lock:
            cur_tune = meta.get("tune") or {}
            for k, v in changes.items():
                val = float(defaults[k]) if v is None else v
                if req.get("reset_all") and (k not in cur_tune or abs(float(cur_tune[k]) - val) < 1e-9):
                    continue                     # a reset of a key already at its default is not a change
                self.tune_log.append({"wall": now, "key": k, "value": val, "default": float(defaults.get(k, val)), "applied": None})
            del self.tune_log[:-200]
        return 200, {"ok": True, "file": path, "written": out}

    def send_ctl(self, obj):
        b = json.dumps(obj).encode("utf-8")
        self.ctl.sendto(b, ("127.0.0.1", self.args.ctl_port))

    def add_note(self, req):
        item = str(req.get("item", ""))[:80]
        verdict = str(req.get("verdict", ""))[:20]
        text = str(req.get("text", ""))[:500].replace("\r", " ").replace("\n", " ")
        if not item or verdict not in ("felt", "not", "strong", "weak", "note"):
            return 400, {"ok": False, "error": "item and verdict (felt | not | strong | weak | note) needed"}
        keys = [str(k) for k in (req.get("keys") or [])][:12]
        with self.lock:
            st, meta = self.state or {}, self.meta or {}
            tune = meta.get("tune") or {}
            snap = {k: tune.get(k) for k in keys if k in tune}
            last_ev = req.get("last_event") or ""
            row = {"wall": time.strftime("%Y-%m-%d %H:%M:%S"), "game_t": st.get("t"), "item": item, "verdict": verdict,
                   "text": text, "last_event": str(last_ev)[:120], "mode": st.get("mode", ""), "tune": json.dumps(snap, sort_keys=True)}
            if not self.notes_path:
                d = os.path.join(os.path.dirname(self.tune_file()), "notes")
                os.makedirs(d, exist_ok=True)
                self.notes_path = os.path.join(d, "ffb-notes-%s.csv" % time.strftime("%Y%m%d-%H%M%S", time.localtime(self.started)))
            new = not os.path.isfile(self.notes_path)
            with open(self.notes_path, "a", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(row.keys()))
                if new:
                    w.writeheader()
                w.writerow(row)
            self.notes.append(row)
        return 200, {"ok": True, "file": self.notes_path, "row": row}


def make_handler(hub):
    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *a):
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
                try:
                    with open(PAGE, "rb") as f:
                        body = f.read()
                except OSError:
                    return self.send_error(500, "ffb-panel.html missing")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                return self.wfile.write(body)
            if u.path == "/api/state":
                return self.send_json(hub.snapshot(int(q.get("since", ["0"])[0] or 0)))
            if u.path == "/api/health":
                return self.send_json({"ok": True, "version": VERSION})
            if u.path == "/api/stream":
                return self.stream(float(q.get("hz", ["15"])[0]))
            self.send_error(404)

        def do_POST(self):
            u = urlparse(self.path)
            n = int(self.headers.get("Content-Length") or 0)
            try:
                req = json.loads(self.rfile.read(n) or b"{}")
            except ValueError:
                return self.send_json({"ok": False, "error": "bad json"}, 400)
            if u.path == "/api/tune":
                code, r = hub.set_tune(req)
                return self.send_json(r, code)
            if u.path == "/api/gate":
                mode = req.get("mode")
                if mode not in ("solo", "mute", "on", "all"):
                    return self.send_json({"ok": False, "error": "mode: solo | mute | on | all"}, 400)
                hub.send_ctl({"op": "gate", "ch": str(req.get("ch", "")), "mode": mode})
                return self.send_json({"ok": True})
            if u.path == "/api/arm":
                hub.send_ctl({"op": "arm", "on": bool(req.get("on"))})
                return self.send_json({"ok": True})
            if u.path == "/api/note":
                code, r = hub.add_note(req)
                return self.send_json(r, code)
            self.send_error(404)

        def stream(self, hz):
            hz = max(1.0, min(30.0, hz))
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            self.close_connection = True
            seen = 0
            try:
                while not hub.stop_ev.is_set():
                    snap = hub.snapshot(seen)
                    if snap["events"]:
                        seen = snap["events"][-1][0]
                    self.wfile.write(b"data: " + json.dumps(snap, separators=(",", ":"), default=str).encode() + b"\n\n")
                    self.wfile.flush()
                    time.sleep(1.0 / hz)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
                pass
    return H


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--http-port", type=int, default=17691)
    ap.add_argument("--udp-port", type=int, default=17682, help="the interposer's state datagrams (its -PanelPort)")
    ap.add_argument("--ctl-port", type=int, default=17683, help="the interposer's command port (its -ControlPort)")
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--seconds", type=float, default=0, help="exit after N seconds (tests)")
    args = ap.parse_args(argv)
    hub = Hub(args)
    try:
        httpd = ThreadingHTTPServer(("127.0.0.1", args.http_port), make_handler(hub))
    except OSError as e:
        url = "http://127.0.0.1:%d/" % args.http_port
        print("port %d is taken: another FFB panel is probably running - opening %s (%s)" % (args.http_port, url, e), flush=True)
        if not args.no_browser:
            webbrowser.open(url)
        return 0
    httpd.daemon_threads = True
    try:
        t = threading.Thread(target=hub.udp_loop, args=(args.udp_port,), daemon=True)
        t.start()
    except OSError as e:
        print("cannot listen on udp %d: %s" % (args.udp_port, e), flush=True)
        return 2
    url = "http://127.0.0.1:%d/" % httpd.server_address[1]
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleTitleW("I76 FFB panel - %s" % url)
        except (OSError, AttributeError):
            pass
    print("I76 FFB / LFE panel: %s" % url, flush=True)
    print("  interposer feed: udp 127.0.0.1:%d   commands -> udp 127.0.0.1:%d" % (args.udp_port, args.ctl_port), flush=True)
    print("  Ctrl+C stops (the interposer keeps running; its console panel stays the fallback).", flush=True)
    if not args.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    if args.seconds:
        threading.Timer(args.seconds, httpd.shutdown).start()
    try:
        httpd.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        hub.stop_ev.set()
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
