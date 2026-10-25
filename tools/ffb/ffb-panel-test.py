#!/usr/bin/env python3
"""ffb-panel-test.py - the FFB web panel server against a fake interposer (no game, no wheel, ~3 s).

Starts ffb-panel.py on free ports, plays the interposer's side of the protocol (meta + state datagrams in,
commands out) and checks: the page is served, state / events arrive and are de-duplicated, NaN never reaches
the browser, a slider write lands in the tune file (only values that differ from the defaults), reset /
reset-all remove them, clamping, the LFE rule refuses music / voice keys, gate / arm commands reach the
interposer's port, a checklist verdict is appended to the session notes file, and "applied" is confirmed
only once the interposer's meta says so.
"""
import json, os, socket, subprocess, sys, tempfile, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
fails = 0


def ok(cond, what):
    global fails
    print(("PASS  " if cond else "FAIL  ") + what)
    if not cond:
        fails += 1


def free_udp():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def free_tcp():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def get(url):
    with urllib.request.urlopen(url, timeout=3) as r:
        return r.status, r.read()


def post(url, obj):
    req = urllib.request.Request(url, data=json.dumps(obj).encode(), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=3) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def main():
    http, udp, ctl = free_tcp(), free_udp(), free_udp()
    tmp = tempfile.mkdtemp(prefix="ffbpanel-")
    tune_file = os.path.join(tmp, "ffb-tune-owner.json")
    with open(tune_file, "w") as f:
        f.write('{\n    "PavementScale":  0.4\n}\n')
    proc = subprocess.Popen([sys.executable, os.path.join(HERE, "ffb-panel.py"), "--no-browser", "--http-port", str(http),
                             "--udp-port", str(udp), "--ctl-port", str(ctl), "--seconds", "30"],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    fake_ctl = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); fake_ctl.bind(("127.0.0.1", ctl)); fake_ctl.settimeout(2)
    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    base = "http://127.0.0.1:%d" % http
    try:
        for _ in range(50):
            try:
                get(base + "/api/health"); break
            except OSError:
                time.sleep(0.1)
        st, body = get(base + "/")
        ok(st == 200 and b"I76 FFB panel" in body and b"://" not in body and b"<script src" not in body, "page served, no external script")

        st, j = post(base + "/api/tune", {"key": "WeaponGain", "value": 2800})
        ok(st == 409, "no interposer yet: tune write refused (409)")

        defaults = {"Master": 1.0, "WeaponGain": 3400, "PavementScale": 0.5, "HitSideSign": 1, "LfeEngineAmp": 0.45, "SatGain": 5200}
        tune = dict(defaults, PavementScale=0.4)

        def meta():
            m = {"k": "meta", "v": 1, "pid": 4242, "t": 1.0, "tune_file": tune_file, "tune": tune, "defaults": defaults, "channels": ["center"]}
            tx.sendto(json.dumps(m).encode(), ("127.0.0.1", udp))

        def state(seq, evs, extra=None):
            m = {"k": "ffb", "v": 1, "seq": seq, "t": 1.0 + seq * 0.05, "pid": 4242, "mode": "DRY RUN", "dry": True, "armed": True,
                 "master": 1.0, "rate": 60, "ctl": True, "ch": {"center": 120, "weapon": 3300}, "force": 3420, "act": {"center": True},
                 "ev_last": evs[-1][0] if evs else 0, "ev": evs}
            if extra:
                m.update(extra)
            tx.sendto(json.dumps(m).encode(), ("127.0.0.1", udp))
        # NaN as PowerShell would print it (json.loads accepts it) must not reach the page
        tx.sendto(b'{"k":"ffb","v":1,"seq":1,"t":1.0,"pid":4242,"mode":"DRY RUN","tel":{"slide":NaN},"ev":[[1,1.0,"IGNITION"]]}', ("127.0.0.1", udp))
        meta()
        state(2, [[1, 1.0, "IGNITION"], [2, 1.1, "FIRE gun/cannon (dmg 15)"]])
        state(3, [[2, 1.1, "FIRE gun/cannon (dmg 15)"], [3, 1.2, "HIT left"]])
        time.sleep(0.3)
        st, body = get(base + "/api/state")
        ok(b"NaN" not in body, "NaN is not forwarded to the browser")
        d = json.loads(body)
        ok(d["status"] == "live", "status live after datagrams")
        ok([e[2] for e in d["events"]] == ["IGNITION", "FIRE gun/cannon (dmg 15)", "HIT left"], "events in order, de-duplicated across datagrams")
        ok(d["server"]["tune_file"] == tune_file, "tune file taken from the interposer's meta")

        st, j = post(base + "/api/tune", {"key": "WeaponGain", "value": 2800})
        cur = json.load(open(tune_file))
        ok(st == 200 and cur == {"PavementScale": 0.4, "WeaponGain": 2800.0}, "slider write lands in the file (only non-defaults): %s" % cur)
        st, d = 0, json.loads(get(base + "/api/state")[1])
        ok(d["tune_log"][-1]["key"] == "WeaponGain" and d["tune_log"][-1]["applied"] is None, "not 'applied' before the interposer confirms")
        tune["WeaponGain"] = 2800.0; meta(); time.sleep(0.2)
        d = json.loads(get(base + "/api/state")[1])
        ok(d["tune_log"][-1]["applied"] is not None, "'applied' once the interposer's meta carries the value")

        st, j = post(base + "/api/tune", {"key": "WeaponGain", "value": 99999})
        ok(st == 200 and json.load(open(tune_file))["WeaponGain"] == 10000 or json.load(open(tune_file))["WeaponGain"] == 3 * 3400, "clamped to 3 x default / 10000")
        st, j = post(base + "/api/tune", {"key": "WeaponGain", "value": 3400})
        ok("WeaponGain" not in json.load(open(tune_file)), "a value equal to the default is removed from the file")
        st, j = post(base + "/api/tune", {"key": "HitSideSign", "value": -0.3})
        ok(json.load(open(tune_file)).get("HitSideSign") == -1.0, "HitSideSign snaps to -1")
        st, j = post(base + "/api/tune", {"key": "HitSideSign", "reset": True})
        ok("HitSideSign" not in json.load(open(tune_file)), "reset removes the key")
        for bad in ("LfeMusicGain", "VoiceBoost", "MusicDuck", "LfeLoopbackAmp"):
            defaults[bad] = 0.5
        meta(); time.sleep(0.2)
        for bad in ("LfeMusicGain", "VoiceBoost", "MusicDuck", "LfeLoopbackAmp"):
            st, j = post(base + "/api/tune", {"key": bad, "value": 0.9})
            ok(st == 403 and "game events only" in j.get("error", ""), "LFE rule: %s refused (403)" % bad)
        st, j = post(base + "/api/tune", {"key": "NoSuchKey", "value": 1})
        ok(st == 400, "unknown key refused")
        st, j = post(base + "/api/tune", {"key": "SatGain", "value": "nan"})
        ok(st == 400, "NaN value refused")
        st, j = post(base + "/api/tune", {"reset_all": True})
        ok(st == 200 and json.load(open(tune_file)) == {}, "reset all empties the file")

        post(base + "/api/gate", {"ch": "weapon", "mode": "solo"})
        m, _ = fake_ctl.recvfrom(4096)
        ok(json.loads(m) == {"op": "gate", "ch": "weapon", "mode": "solo"}, "gate command reaches the interposer port")
        post(base + "/api/arm", {"on": False})
        m, _ = fake_ctl.recvfrom(4096)
        ok(json.loads(m) == {"op": "arm", "on": False}, "arm command reaches the interposer port")
        st, j = post(base + "/api/gate", {"ch": "weapon", "mode": "boost"})
        ok(st == 400, "unknown gate mode refused")

        st, j = post(base + "/api/note", {"item": "Gun / cannon", "verdict": "strong", "text": "kicks a lot", "keys": ["WeaponGain"], "last_event": "FIRE gun"})
        ok(st == 200 and os.path.isfile(j["file"]) and os.path.dirname(j["file"]) == os.path.join(tmp, "notes"), "verdict saved in notes\\ beside the tune file")
        txt = open(j["file"], encoding="utf-8").read()
        ok("Gun / cannon,strong,kicks a lot" in txt and "WeaponGain" in txt, "notes row carries item, verdict, comment and the gain")
        st, j = post(base + "/api/note", {"item": "x", "verdict": "maybe"})
        ok(st == 400, "unknown verdict refused")

        tx.sendto(b'{"k":"bye","pid":4242}', ("127.0.0.1", udp)); time.sleep(0.2)
        d = json.loads(get(base + "/api/state")[1])
        ok(d["status"] == "stopped", "bye -> status stopped")

        # the event stream sends JSON lines
        with urllib.request.urlopen(base + "/api/stream?hz=10", timeout=3) as r:
            line = r.readline()
        ok(line.startswith(b"data: {"), "event stream answers")
    finally:
        proc.terminate()
        try:
            proc.wait(5)
        except subprocess.TimeoutExpired:
            proc.kill()
    print("%d failed" % fails)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
