#!/usr/bin/env python3
"""Serve the Interstate '76 save editor with your saves auto-loaded.

Runs a tiny local web server (127.0.0.1 only) that serves i76-save-editor.html
plus the save files from the game folder, so the page opens straight onto
Skeeter's order pad with your bookmarks listed - no drag-and-drop needed.
It also lets the page WRITE saves back into the game folder. Every write keeps
a timestamped <name>.bak-YYYYMMDD-HHMMSS copy (plus a one-time <name>.pre-edit
of the untouched original); DELETE renames rather than unlinks, so bookmarks
are always recoverable from the page's History / restore controls.

  i76-save-editor-server.py                 auto-find the Mac wrapper's game dir
  i76-save-editor-server.py --dir DIR       serve saves from DIR instead
  i76-save-editor-server.py --port N        default 7676
  i76-save-editor-server.py --no-open       don't auto-open the browser

Double-click launcher: i76-save-editor.command
"""
import argparse, datetime, glob, json, os, re, shutil, sys, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
SAFE = re.compile(r"^(save\d{3}\.cmp|savegame\.dir)$")
# backups are readable (for restore) but never writable/deletable
SAFE_READ = re.compile(r"^(save\d{3}\.cmp|savegame\.dir)(\.pre-edit|\.bak-\d{8}-\d{6})?$")

def stamp():
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

def find_game_dir():
    for base in (os.path.expanduser("~/Applications/Sikarugir"),
                 os.path.expanduser("~/Applications"), "/Applications"):
        if not os.path.isdir(base): continue
        for root, subdirs, files in os.walk(base):
            if root.count(os.sep) - base.count(os.sep) > 8:
                subdirs[:] = []; continue
            if root.endswith(os.path.join("drive_c", "GOG Games", "Interstate 76")):
                if glob.glob(os.path.join(root, "save*.cmp")):
                    return root
                subdirs[:] = []
    repo = os.path.join(HERE, "saves")
    if glob.glob(os.path.join(repo, "save*.cmp")):
        return repo
    return None

class Handler(BaseHTTPRequestHandler):
    savedir = None
    def _send(self, code, body, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            try:
                body = open(os.path.join(HERE, "i76-save-editor.html"), "rb").read()
            except OSError:
                return self._send(500, b"i76-save-editor.html not found next to the server script", "text/plain")
            return self._send(200, body, "text/html; charset=utf-8")
        if self.path == "/api/saves":
            names = sorted(os.path.basename(f)
                           for f in glob.glob(os.path.join(self.savedir, "save*.cmp"))
                           if SAFE.match(os.path.basename(f)))
            has_dir = os.path.isfile(os.path.join(self.savedir, "savegame.dir"))
            backups = {}
            for f in sorted(glob.glob(os.path.join(self.savedir, "*.pre-edit")) +
                            glob.glob(os.path.join(self.savedir, "*.bak-*"))):
                b = os.path.basename(f)
                base = re.sub(r"\.(pre-edit|bak-\d{8}-\d{6})$", "", b)
                backups.setdefault(base, []).append(b)
            return self._send(200, json.dumps(
                {"dir": self.savedir, "saves": names, "hasDir": has_dir,
                 "backups": backups}).encode())
        m = re.match(r"^/files/([^/]+)$", self.path)
        if m and SAFE_READ.match(m.group(1)):
            p = os.path.join(self.savedir, m.group(1))
            if not os.path.isfile(p): return self._send(404, b"not found", "text/plain")
            return self._send(200, open(p, "rb").read(), "application/octet-stream")
        self._send(404, b"not found", "text/plain")

    def do_PUT(self):
        m = re.match(r"^/files/([^/]+)$", self.path)
        if not (m and SAFE.match(m.group(1))):
            return self._send(403, b'{"error":"only save###.cmp / savegame.dir"}')
        n = int(self.headers.get("Content-Length", 0))
        if n <= 0 or n > 2_000_000:
            return self._send(400, b'{"error":"bad length"}')
        data = self.rfile.read(n)
        p = os.path.join(self.savedir, m.group(1))
        backed = None
        if os.path.isfile(p):
            if not os.path.isfile(p + ".pre-edit"):
                shutil.copy2(p, p + ".pre-edit")
            backed = os.path.basename(p) + ".bak-" + stamp()
            shutil.copy2(p, os.path.join(self.savedir, backed))
        open(p, "wb").write(data)
        self._send(200, json.dumps({"written": m.group(1), "bytes": n, "backup": backed}).encode())

    def do_DELETE(self):
        # delete = recoverable rename into the backup namespace (never unlinks)
        m = re.match(r"^/files/(save\d{3}\.cmp)$", self.path)
        if not m:
            return self._send(403, b'{"error":"only save###.cmp can be deleted"}')
        p = os.path.join(self.savedir, m.group(1))
        if not os.path.isfile(p):
            return self._send(404, b'{"error":"not found"}')
        bak = m.group(1) + ".bak-" + stamp()
        os.rename(p, os.path.join(self.savedir, bak))
        self._send(200, json.dumps({"deleted": m.group(1), "kept_as": bak}).encode())

    def log_message(self, fmt, *args):  # keep the terminal quiet
        pass

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dir", help="saves directory (default: auto-find the wrapper)")
    ap.add_argument("--port", type=int, default=7676)
    ap.add_argument("--no-open", action="store_true")
    a = ap.parse_args()
    savedir = os.path.abspath(a.dir) if a.dir else find_game_dir()
    if not savedir or not os.path.isdir(savedir):
        sys.exit("no saves directory found - pass one with --dir")
    Handler.savedir = savedir
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    url = f"http://127.0.0.1:{a.port}/"
    print(f"Salvage Ledger up at {url}")
    print(f"  saves: {savedir}")
    print("  Ctrl-C to stop. Every write keeps a timestamped backup; deletes are recoverable.")
    if not a.no_open:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")

if __name__ == "__main__":
    main()
