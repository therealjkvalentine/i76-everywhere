#!/usr/bin/env python3
r"""pyrelay.py - an internet relay for Interstate '76 / Nitro network games (DOSBox IPX protocol), Python 3 standard library only.

Every player's game (with the IPXWrapper build in the Patch Kit's _ipx\relay\ folder, PLAY.bat --relay <host>:<port>) sends its IPX
packets to this relay over UDP; the relay forwards them to the other players. To the games it looks like one LAN. Players need no
port forwarding (every packet they get is a reply on the flow they opened); the machine that runs the relay needs one UDP port
reachable from the internet (RELAY-FIREWALL.bat for Windows Firewall, a port forward in the router). tools/relay/README.md.

Wire behaviour = DOSBox / dosbox-x `ipxnet startserver` (src/hardware/ipxserver.cpp) and ipxbox:
  - registration: a packet to socket 2 whose destination host is 0. The player's node = its public IP:port as the relay sees it
    (6 bytes, as DOSBox), answered with an IPX header {dest net 0, node = that address, socket 2; src net 1}.
  - broadcast (destination node ff:ff:ff:ff:ff:ff): to every registered player except the sender.
  - unicast: to the player whose node is the destination node.
Differences, all on the side of safety:
  - the sender is identified by its UDP source address, not by the header's source field (DOSBox trusts the header, so a player
    could pose as another); packets from addresses that did not register are dropped.
  - allow = CIDR[, CIDR ...]: registrations from other addresses are refused (DOSBox / ipxbox have no allowlist).
  - idle timeout: players silent that long are dropped (ipxbox: --client_timeout 10 min; DOSBox: never).
  - a stats line every "stats every" seconds: per player packets / bytes in and out, the relay's forwarding time, drops.
NOT hidden: under this protocol every player's node IS his public address, and every packet carries it - every player in a
session can read every other player's IP address. Invite people you would give your address to.

    python pyrelay.py [--config relay.ini] [--port 19900] [--bind 0.0.0.0] [--allow 10.1.2.0/24,203.0.113.7]
                      [--timeout 600] [--stats 10] [--log relay.log] [--log-level quiet|info|debug]
Settings come from relay.ini beside this file (or --config), then the command line. Ctrl+C stops it.
"""
import argparse, configparser, ipaddress, os, socket, struct, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
LEVELS = {"quiet": 0, "info": 1, "debug": 2}
BCAST = b"\xff" * 6


def read_config(path):
    """relay.ini [relay] -> dict of strings (missing file = {})"""
    if not path or not os.path.exists(path):
        return {}
    cp = configparser.ConfigParser(inline_comment_prefixes=("#", ";"))
    cp.read(path, encoding="utf-8")
    return {k.strip().lower(): v.strip() for k, v in cp.items("relay")} if cp.has_section("relay") else {}


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="DOSBox-protocol IPX relay for Interstate '76 / Nitro network games")
    ap.add_argument("--config", default=os.path.join(HERE, "relay.ini"))
    ap.add_argument("--port", type=int); ap.add_argument("--bind"); ap.add_argument("--allow")
    ap.add_argument("--timeout", type=float); ap.add_argument("--stats", type=float)
    ap.add_argument("--log"); ap.add_argument("--log-level", choices=sorted(LEVELS))
    a = ap.parse_args(argv)
    c = read_config(a.config)
    pick = lambda cli, key, default: cli if cli is not None else (c.get(key) if c.get(key, "") != "" else default)
    cfg = {
        "port": int(pick(a.port, "port", 19900)),
        "bind": pick(a.bind, "bind", "0.0.0.0"),
        "allow": pick(a.allow, "allow", ""),
        "timeout": float(pick(a.timeout, "idle timeout", 600)),
        "stats": float(pick(a.stats, "stats every", 10)),
        "log": a.log if a.log is not None else c.get("log file", "relay.log"),   # "log file =" (empty) = no log file
        "level": pick(a.log_level, "log level", "info").lower(),
        "config": a.config if os.path.exists(a.config) else "(none)",
    }
    if cfg["level"] not in LEVELS:
        sys.exit("log level must be quiet, info or debug (got %r)" % cfg["level"])
    if not 1 <= cfg["port"] <= 65535:
        sys.exit("port must be 1 to 65535 (got %d)" % cfg["port"])
    try:
        cfg["allow_nets"] = [ipaddress.ip_network(x.strip(), strict=False) for x in cfg["allow"].split(",") if x.strip()]
    except ValueError as e:
        sys.exit("allow: %s (use addresses or CIDR ranges, comma separated, e.g. 10.1.2.0/24, 203.0.113.7)" % e)
    if cfg["log"] and not os.path.isabs(cfg["log"]):
        cfg["log"] = os.path.join(HERE, cfg["log"])
    return cfg


class Relay:
    def __init__(self, cfg):
        self.cfg = cfg
        self.level = LEVELS[cfg["level"]]
        self.logf = open(cfg["log"], "a", buffering=1, encoding="utf-8") if cfg["log"] else None
        self.clients = {}   # node (6 bytes) -> {"addr", "last", "since", "pin", "bin", "pout", "bout"}
        self.by_addr = {}   # (ip, port) -> node
        self.fwd = [0, 0]   # forwarding time (ns), packets forwarded
        self.dropped = {"unregistered": 0, "not allowed": 0, "short": 0, "no such node": 0}
        self.s = None

    def log(self, msg, level=1):
        if level > self.level and level != 0:
            return
        line = "%s %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
        print(line, flush=True)
        if self.logf:
            self.logf.write(line + "\n")

    def open(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1 << 20)
        s.bind((self.cfg["bind"], self.cfg["port"]))
        s.settimeout(1.0)
        if sys.platform == "win32":   # a player that vanishes makes recvfrom raise WSAECONNRESET on Windows; switch that off
            try:
                s.ioctl(socket.SIO_UDP_CONNRESET, False)
            except (AttributeError, OSError):
                pass
        self.s = s
        self.log("relay listening on UDP %s:%d - allow %s, idle timeout %.0f s, log %s (level %s), config %s, python %s" % (
            self.cfg["bind"], self.cfg["port"], ", ".join(map(str, self.cfg["allow_nets"])) or "anyone with the address",
            self.cfg["timeout"], self.cfg["log"] or "(none)", self.cfg["level"], self.cfg["config"], sys.version.split()[0]), 0)

    def allowed(self, ip):
        nets = self.cfg["allow_nets"]
        return not nets or any(ipaddress.ip_address(ip) in n for n in nets)

    def handle(self, data, addr, now):
        if len(data) < 30:
            self.dropped["short"] += 1
            return
        dsock = struct.unpack_from(">H", data, 16)[0]
        dnode = data[10:16]
        if dsock == 2 and data[10:14] == b"\0\0\0\0":   # registration (DOSBox: dest socket 2, dest host 0)
            if not self.allowed(addr[0]):
                self.dropped["not allowed"] += 1
                if self.dropped["not allowed"] <= 20:
                    self.log("refused %s:%d (not in allow)" % addr, 0)
                return
            nd = socket.inet_aton(addr[0]) + struct.pack(">H", addr[1])
            if nd not in self.clients:
                self.clients[nd] = {"addr": addr, "last": now, "since": now, "pin": 0, "bin": 0, "pout": 0, "bout": 0}
                self.by_addr[addr] = nd
                self.log("player joined the relay: %s:%d (%d connected)" % (addr[0], addr[1], len(self.clients)), 0)
            else:
                self.clients[nd]["last"] = now
                self.log("registration again from %s:%d" % addr, 2)
            ack = struct.pack(">HHBB4s6sH4s6sH", 0xFFFF, 30, 0, 0, b"\0\0\0\0", nd, 2, b"\0\0\0\1",
                              b"\0\0\0\0" + struct.pack(">H", self.cfg["port"]), 2)
            self.s.sendto(ack, addr)
            return
        src = self.by_addr.get(addr)
        if src is None:
            self.dropped["unregistered"] += 1
            if self.dropped["unregistered"] <= 5:
                self.log("dropped a packet from %s:%d (it never registered)" % addr, 2)
            return
        t0 = time.perf_counter_ns()
        c = self.clients[src]
        c["last"] = now; c["pin"] += 1; c["bin"] += len(data)
        if dnode == BCAST:
            targets = [v for k, v in self.clients.items() if k != src]
        else:
            v = self.clients.get(dnode)
            targets = [v] if v else []
            if not v:
                self.dropped["no such node"] += 1
        for v in targets:
            self.s.sendto(data, v["addr"]); v["pout"] += 1; v["bout"] += len(data)
        self.fwd[0] += time.perf_counter_ns() - t0; self.fwd[1] += 1

    def tick(self, now):
        for k in [k for k, v in self.clients.items() if now - v["last"] > self.cfg["timeout"]]:
            v = self.clients.pop(k)
            self.by_addr.pop(v["addr"], None)
            self.log("player left (silent %.0f s): %s:%d (%d connected)" % (self.cfg["timeout"], v["addr"][0], v["addr"][1], len(self.clients)), 0)
        if self.clients:
            parts = ["%s:%d in %d pkt / %d B, out %d pkt / %d B" % (v["addr"][0], v["addr"][1], v["pin"], v["bin"], v["pout"], v["bout"])
                     for v in self.clients.values()]
            self.log("stats %d connected | %s | %.1f us/pkt | dropped %s" % (
                len(self.clients), " ; ".join(parts), (self.fwd[0] / self.fwd[1] / 1000) if self.fwd[1] else 0,
                {k: v for k, v in self.dropped.items() if v} or "none"), 1)

    def run(self):
        self.open()
        t_stats = time.time() + self.cfg["stats"]
        try:
            while True:
                try:
                    data, addr = self.s.recvfrom(2048)
                except socket.timeout:
                    data = None
                except ConnectionResetError:
                    continue
                now = time.time()
                if data is not None:
                    self.handle(data, addr, now)
                if now >= t_stats:
                    t_stats = now + self.cfg["stats"]
                    self.tick(now)
        except KeyboardInterrupt:
            self.log("relay stopped (Ctrl+C)", 0)
        finally:
            self.s.close()


def main(argv=None):
    cfg = parse_args(argv)
    try:
        Relay(cfg).run()
    except OSError as e:
        sys.exit("could not open UDP %s:%d: %s (another relay already running on that port?)" % (cfg["bind"], cfg["port"], e))


if __name__ == "__main__":
    main()
