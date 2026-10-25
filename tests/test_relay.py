"""Offline checks of the internet relay (issue #113, docs/records/RELAY-DESKTOP-2026-10-25.md).

    python -m pytest tests/test_relay.py -q

1. tools/relay/pyrelay.py on loopback: registration, unicast echo, broadcast to the others but not the sender, allowlist refusal,
   unregistered senders dropped.
2. PLAY-i76.ps1 -Relay / -CheckRelay / -RelayRestore on a scratch game folder (no game: a stand-in i76.exe that exits at once):
   address checks, the sha256 pins, the LAN files parked and put back, the settings-file line, --relay off.
The IPXWrapper DLLs are not in the repo; part 2 builds stand-ins whose sha256 cannot match, so it checks the refusal path, and the
swap path only when I76_RELAY_DLL_DIR names a folder with the real pinned build (the lab's builds\\ipxwrapper-master-20261025\\out).
"""
import os, shutil, socket, struct, subprocess, sys, time

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RELAY = os.path.join(REPO, "tools", "relay", "pyrelay.py")
LAUNCHER = os.path.join(REPO, "PLAY-i76.ps1")
POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")
DLL_DIR = os.environ.get("I76_RELAY_DLL_DIR", os.path.join(os.path.expanduser("~"), "i76-uncap-lab", "builds", "ipxwrapper-master-20261025", "out"))
HAVE_DLLS = all(os.path.exists(os.path.join(DLL_DIR, n)) for n in ("ipxwrapper.dll", "wsock32.dll", "mswsock.dll"))


def pkt(dnode, dsock, snode=b"\0" * 6, ssock=0x4000, data=b""):
    return struct.pack(">HHBB4s6sH4s6sH", 0xFFFF, 30 + len(data), 0, 0, b"\0" * 4, dnode, dsock, b"\0" * 4, snode, ssock) + data


def free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


@pytest.fixture
def relay(tmp_path):
    procs = []

    def start(*extra):
        port = free_port()
        p = subprocess.Popen([sys.executable, "-I", RELAY, "--config", str(tmp_path / "none.ini"), "--bind", "127.0.0.1", "--port", str(port),
                              "--log", str(tmp_path / ("relay-%d.log" % port)), "--stats", "1"] + list(extra),
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        procs.append(p); time.sleep(0.8)
        return port, tmp_path / ("relay-%d.log" % port)
    yield start
    for p in procs:
        p.terminate(); p.wait(5)


def client(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(1.5)
    s.sendto(pkt(b"\0" * 6, 2, ssock=2), ("127.0.0.1", port))
    r, _ = s.recvfrom(2048)
    return s, r[10:16]   # the node the relay assigned = our IP:port


def test_relay_forwards(relay):
    port, logf = relay()
    a, na = client(port); b, nb = client(port); c, nc = client(port)
    assert na == socket.inet_aton("127.0.0.1") + struct.pack(">H", a.getsockname()[1])
    a.sendto(pkt(nb, 0x4000, na, data=b"hi b"), ("127.0.0.1", port))          # unicast a -> b
    assert b.recvfrom(2048)[0].endswith(b"hi b")
    a.sendto(pkt(b"\xff" * 6, 0x4000, na, data=b"all"), ("127.0.0.1", port))  # broadcast: b and c, not a
    assert b.recvfrom(2048)[0].endswith(b"all") and c.recvfrom(2048)[0].endswith(b"all")
    a.settimeout(0.5)
    with pytest.raises(socket.timeout):
        a.recvfrom(2048)
    x = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)                      # never registered: dropped
    x.sendto(pkt(nb, 0x4000, data=b"spoof"), ("127.0.0.1", port))
    b.settimeout(0.5)
    with pytest.raises(socket.timeout):
        b.recvfrom(2048)
    time.sleep(1.3)
    log = logf.read_text()
    assert log.count("player joined the relay") == 3 and "unregistered" in log


def test_relay_allowlist(relay):
    port, logf = relay("--allow", "10.0.0.0/8")
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(1.0)
    s.sendto(pkt(b"\0" * 6, 2, ssock=2), ("127.0.0.1", port))
    with pytest.raises(socket.timeout):
        s.recvfrom(2048)
    time.sleep(0.3)
    assert "refused 127.0.0.1" in logf.read_text()


def test_relay_ini(tmp_path):
    ini = tmp_path / "relay.ini"
    ini.write_text("[relay]\nport = 19977\nallow = 10.1.2.0/24, 203.0.113.7\nlog level = quiet\nlog file =\n", encoding="utf-8")
    sys.path.insert(0, os.path.dirname(RELAY))
    import pyrelay
    cfg = pyrelay.parse_args(["--config", str(ini)])
    assert cfg["port"] == 19977 and cfg["level"] == "quiet" and cfg["log"] == "" and len(cfg["allow_nets"]) == 2
    assert pyrelay.parse_args(["--config", str(ini), "--port", "19900"])["port"] == 19900


# ---- PLAY-i76.ps1 -Relay ------------------------------------------------------------------------------------------------------
pytestmark_ps = pytest.mark.skipif(not POWERSHELL, reason="needs Windows PowerShell")


@pytest.fixture
def game(tmp_path):
    g = tmp_path / "game folder"
    (g / "_ipx" / "relay").mkdir(parents=True)
    (g / "ipxwrapper.dll").write_bytes(b"LAN ipxwrapper")
    (g / "ipxwrapper.ini").write_text("logging = debug\n")
    shutil.copy(os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "waitfor.exe"), g / "i76.exe")   # exits at once on -glide
    return g


def ps(g, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("I76_")}
    return subprocess.run([POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", LAUNCHER, "-GameDir", str(g), "-Preset", "stock",
                           "-NoFfb", "-NoHeadTrack", "-NoMusic", "-LosslessScaling", "none"] + list(args), capture_output=True, text=True, env=env, timeout=120)


@pytestmark_ps
@pytest.mark.parametrize("target,ok", [("off", True), ("203.0.113.7:70000", False), ("bad host:1", False), ("a:b:c", False)])
def test_check_relay_address(game, target, ok):
    r = ps(game, "-Relay", target, "-CheckRelay")
    assert (r.returncode == 0) == ok, r.stdout


@pytestmark_ps
def test_check_relay_refuses_unpinned(game):
    for n in ("ipxwrapper.dll", "wsock32.dll", "mswsock.dll"):
        (game / "_ipx" / "relay" / n).write_bytes(b"not the pinned build")
    r = ps(game, "-Relay", "203.0.113.7", "-CheckRelay")
    assert r.returncode == 7 and "not the pinned IPXWrapper build" in r.stdout
    r = ps(game, "-Relay", "203.0.113.7")   # a real start refuses too, and leaves the folder alone
    assert r.returncode == 7
    assert (game / "ipxwrapper.dll").read_bytes() == b"LAN ipxwrapper" and not (game / "_ipx" / "relay-active.txt").exists()


@pytestmark_ps
@pytest.mark.skipif(not HAVE_DLLS, reason="needs the pinned IPXWrapper build (I76_RELAY_DLL_DIR)")
def test_relay_swap_and_restore(game):
    for n in ("ipxwrapper.dll", "wsock32.dll", "mswsock.dll"):
        shutil.copy(os.path.join(DLL_DIR, n), game / "_ipx" / "relay" / n)
    assert ps(game, "-Relay", "203.0.113.7:19900", "-CheckRelay").returncode == 0
    r = ps(game, "-Relay", "203.0.113.7:19900")
    log = (game / "play-i76.log").read_text(encoding="utf-8-sig")
    assert "relay: 203.0.113.7:19900 - IPXWrapper master dbe9a81" in log and "LAN) IPX files back (the game exited)" in log, log
    assert (game / "ipxwrapper.dll").read_bytes() == b"LAN ipxwrapper" and (game / "ipxwrapper.ini").read_text() == "logging = debug\n"
    assert not (game / "mswsock.dll").exists() and not (game / "_ipx" / "relay-active.txt").exists()
    # an unfinished relay launch (marker + parked files) is undone by the next plain start, and by -RelayRestore
    for undo in (["-RelayRestore"], []):
        (game / "_ipx" / "lan-saved").mkdir(exist_ok=True)
        shutil.move(str(game / "ipxwrapper.dll"), str(game / "_ipx" / "lan-saved" / "ipxwrapper.dll"))
        shutil.copy(os.path.join(DLL_DIR, "ipxwrapper.dll"), game / "ipxwrapper.dll")
        (game / "_ipx" / "relay-active.txt").write_text("stale")
        assert ps(game, *undo).returncode == 0
        assert (game / "ipxwrapper.dll").read_bytes() == b"LAN ipxwrapper" and not (game / "_ipx" / "relay-active.txt").exists()
    # the settings file's line, and --relay off over it
    (game / "i76-settings.txt").write_text("[Multiplayer]\nrelay = 198.51.100.4\n", encoding="utf-8")
    assert "relay: 198.51.100.4:19900" in ps(game, "-CheckRelay").stdout
    assert "relay: off" in ps(game, "-Relay", "off", "-CheckRelay").stdout
