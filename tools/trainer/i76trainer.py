r"""i76trainer.py - a small trainer for the running Interstate '76 (GOG builds), SANDBOX by default.

    python i76trainer.py status                   player armour / chassis / components, speed, position, flags, ammo
    python i76trainer.py flags ammo armour chassis  turn on the game's own Play Options switches (offline, player only)
    python i76trainer.py flags --off ammo         ...or off
    python i76trainer.py repair                   armour and chassis to max, every component to max, flat tyres fixed
    python i76trainer.py ammo                     every live weapon slot to unlimited (0x0FFFFFFF)
    python i76trainer.py teleport X Y Z           move the player's car (y is up; keep it above ground)
    python i76trainer.py uncheat                  clear the cheats-used marker 0x535f78 and Play Options bits 0x1c
    python i76trainer.py --any ...                allow a game that is not the sandbox copy

Every address comes from i76-map\subsystems\cheats.md (static reading of md5 9a232dcc, same link as the AiO builds
outside their patched clusters). Every write is read back and reported.

CAMPAIGN WARNING (corrected 2026-10-04): `flags ammo|armour|chassis` (bits 0x04 / 0x08 / 0x10) DOES end up marking the
game as cheated. The poke itself does not set the marker 0x535f78, but the game does as soon as it sees the bits:
closing the in-mission options menu (0x495170), the I76PLYR.DEF write at mission end (0x497290) and the DEF reload
after every return to the shell (0x4970f0). With the marker set, every mission won in that game process is refused
(outcome 0xb: no salvage, no next mission) until 'Turn off Cheater Options' or `uncheat` + a clean I76PLYR.DEF.
repair / ammo / teleport do not touch the Play Options and are safe for the campaign.
"""
import ctypes, ctypes.wintypes as wt, struct, sys, os

SANDBOX = os.path.normcase(r"C:\Users\james\i76-uncap-lab\game")
PLAY_FLAGS = 0x654b98
FLAG_BITS = {"ammo": 0x04, "armour": 0x08, "armor": 0x08, "chassis": 0x10}
AMMO_BASE, AMMO_STRIDE, AMMO_SLOTS, AMMO_OFF = 0x5AAB0C, 0x4C, 16, 0x1C
UNLIMITED = 0x0FFFFFFF
# component type -> (health offset, max offset) in the component entity (0x466ac0 / 0x466b70)
COMP_HEALTH = {20: (0, 4), 21: (0, 4), 23: (0, 4), 22: (4, 8), 24: (8, 0xC), 30: (4, 8)}

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi")


def find_game(allow_any):
    """(pid, path) of the running i76 process"""
    arr = (wt.DWORD * 4096)(); got = wt.DWORD()
    psapi.EnumProcesses(arr, ctypes.sizeof(arr), ctypes.byref(got))
    for pid in arr[:got.value // 4]:
        h = k32.OpenProcess(0x1000, False, pid)            # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            continue
        buf = ctypes.create_unicode_buffer(1024); n = wt.DWORD(1024)
        ok = k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n))
        k32.CloseHandle(h)
        if ok and os.path.basename(buf.value).lower().startswith("i76") and buf.value.lower().endswith(".exe") \
                and "wheel" not in buf.value.lower():
            if not allow_any and os.path.normcase(os.path.dirname(buf.value)) != SANDBOX:
                sys.exit("refusing: %s is not the sandbox copy (use --any to override)" % buf.value)
            return pid, buf.value
    sys.exit("no running i76 process")


class Game:
    def __init__(self, pid):
        self.h = k32.OpenProcess(0x0438, False, pid)       # VM_READ | VM_WRITE | VM_OPERATION | QUERY_INFORMATION
        if not self.h:
            sys.exit("OpenProcess failed (%d)" % ctypes.get_last_error())

    def rd(self, a, n):
        b = ctypes.create_string_buffer(n); got = ctypes.c_size_t()
        if not k32.ReadProcessMemory(self.h, ctypes.c_void_p(a), b, n, ctypes.byref(got)) or got.value != n:
            return None
        return b.raw

    def u32(self, a):
        b = self.rd(a, 4); return struct.unpack("<I", b)[0] if b else None

    def i32(self, a):
        b = self.rd(a, 4); return struct.unpack("<i", b)[0] if b else None

    def f32(self, a):
        b = self.rd(a, 4); return struct.unpack("<f", b)[0] if b else None

    def wr(self, a, data):
        return bool(k32.WriteProcessMemory(self.h, ctypes.c_void_p(a), data, len(data), None))

    def put(self, a, fmt, v, what):
        """write, read back, report"""
        ok = self.wr(a, struct.pack(fmt, v))
        back = struct.unpack(fmt, self.rd(a, struct.calcsize(fmt)))[0]
        good = ok and (back == v or (isinstance(v, float) and abs(back - v) < 1e-4 * max(1, abs(v))))
        print("  %-38s 0x%08x <- %-12s %s" % (what, a, v, "ok" if good else "FAILED (reads %r)" % back))
        return good

    def player(self):
        root = self.u32(0x54a264)
        obj = self.u32(root) if root else None
        ent = self.u32(obj + 0x70) if obj else None
        if not obj or not ent:
            sys.exit("no player vehicle (not in a mission?)")
        return obj, ent

    def components(self, ent):
        for i in range(24):
            c = self.u32(ent + 0x3a8 + 4 * i)
            if c:
                yield i, c, self.u32(c + 0x6c), self.u32(c + 0x70)


def cmd_status(g):
    obj, ent = g.player()
    x, y, z = struct.unpack("<3d", g.rd(obj + 0x40, 24))
    print("player object 0x%08x  entity 0x%08x  pos (%.1f, %.1f, %.1f)  speed %.1f m/s" % (obj, ent, x, y, z, g.f32(ent + 0xac)))
    for name, cur, hud, mx in (("armour", 0x138, 0x178, 0x158), ("chassis", 0x148, 0x18c, 0x168)):
        vals = ["%d/%d(%d)" % (g.i32(ent + cur + 4 * s), g.i32(ent + mx + 4 * s), g.i32(ent + hud + 4 * s)) for s in range(4)]
        print("  %-8s sides 0-3 cur/max(hud): %s   side 4: %d%%" % (name, "  ".join(vals), g.i32(ent + hud + 16)))
    for i, c, t, ce in g.components(ent):
        if t in COMP_HEALTH and ce:
            ho, mo = COMP_HEALTH[t]
            extra = "  flat" if t == 30 and g.u32(ce + 0x44) else ""
            print("  component %2d type %2d health %d/%d%s" % (i, t, g.i32(ce + ho), g.i32(ce + mo), extra))
    f = g.u32(PLAY_FLAGS)
    print("  play flags 0x%02x: %s   cheats-used marker 0x535f78 = %d" % (
        f, ", ".join(k for k, b in (("arcade", 1), ("no-salvage", 2), ("ammo", 4), ("armour", 8), ("chassis", 16)) if f & b) or "none",
        g.u32(0x535f78)))
    for s in range(AMMO_SLOTS):
        base = AMMO_BASE + s * AMMO_STRIDE
        if not g.u32(base):
            continue
        nobj = g.u32(base + 4)                                  # instance +0x08 -> object whose +0 is the .gdf name
        nm = ((g.rd(nobj, 12) if nobj else b"") or b"").split(b"\0")[0].decode("latin1", "replace")
        a = g.u32(base + AMMO_OFF)
        print("  weapon slot %2d %-10s ammo %s" % (s, nm, "unlimited" if a == UNLIMITED else a))


def cmd_flags(g, args):
    off = "--off" in args
    want = 0
    for a in args:
        if a in FLAG_BITS:
            want |= FLAG_BITS[a]
    if not want:
        sys.exit("which flags? ammo armour chassis")
    f = g.u32(PLAY_FLAGS)
    g.put(PLAY_FLAGS, "<I", (f & ~want) if off else (f | want), "options_play_flags")


def cmd_repair(g):
    obj, ent = g.player()
    for s in range(4):
        am, cm = g.i32(ent + 0x158 + 4 * s), g.i32(ent + 0x168 + 4 * s)
        g.put(ent + 0x138 + 4 * s, "<i", am, "armour side %d" % s)
        g.put(ent + 0x178 + 4 * s, "<i", am, "armour side %d (hud)" % s)
        g.put(ent + 0x148 + 4 * s, "<i", cm, "chassis side %d" % s)
        g.put(ent + 0x18c + 4 * s, "<i", cm, "chassis side %d (hud)" % s)
    for i, c, t, ce in g.components(ent):
        if t in COMP_HEALTH and ce:
            ho, mo = COMP_HEALTH[t]
            if t == 30 and g.u32(ce + 0x44):                    # flat tyre: undo 0x46ddd0 (radius x 0.688, flag 1)
                g.put(ce + 0x1c, "<f", g.f32(ce + 0x1c) / 0.688, "component %d wheel radius" % i)
                g.put(ce + 0x44, "<I", 0, "component %d flat flag" % i)
            mx = g.i32(ce + mo)
            if mx and mx > 0 and g.i32(ce + ho) != mx:
                g.put(ce + ho, "<i", mx, "component %d type %d health" % (i, t))


def cmd_ammo(g):
    for s in range(AMMO_SLOTS):
        base = AMMO_BASE + s * AMMO_STRIDE
        if g.u32(base):
            g.put(base + AMMO_OFF, "<I", UNLIMITED, "weapon slot %d ammo" % s)


def cmd_teleport(g, args):
    obj, ent = g.player()
    x, y, z = (float(v) for v in args[:3])
    for _ in range(2):                                          # twice: a write inside the render window of the
        g.wr(obj + 0x40, struct.pack("<3d", x, y, z))           # frame-rate proxy's interpolation is undone once
        g.wr(ent + 0xbc, struct.pack("<3f", 0, 0, 0))
        k32.Sleep(40)
    print("  position now (%.1f, %.1f, %.1f)" % struct.unpack("<3d", g.rd(obj + 0x40, 24)))


CHEAT_MARKER, CHEAT_BITS = 0x535f78, 0x1c


def cmd_uncheat(g):
    """the game's own 'Turn off Cheater Options' (0x4976a0) in memory: Play Options &= ~0x1c, marker 0x535f78 = 0.
    I76PLYR.DEF is rewritten clean by the game at the next options-menu close or mission end (or offline:
    i76-save-editor.py --clear-cheat-options with the game closed)."""
    f = g.u32(PLAY_FLAGS)
    if f is not None and f & CHEAT_BITS:
        g.put(PLAY_FLAGS, "<I", f & ~CHEAT_BITS, "options_play_flags (cheat bits off)")
    g.put(CHEAT_MARKER, "<I", 0, "cheats-used marker")


def main():
    args = [a for a in sys.argv[1:] if a != "--any"]
    if not args:
        print(__doc__); return
    pid, path = find_game("--any" in sys.argv)
    print("attached to %s (pid %d)" % (path, pid))
    g = Game(pid)
    cmd, rest = args[0], args[1:]
    {"status": lambda: cmd_status(g), "flags": lambda: cmd_flags(g, rest), "repair": lambda: cmd_repair(g),
     "ammo": lambda: cmd_ammo(g), "teleport": lambda: cmd_teleport(g, rest),
     "uncheat": lambda: cmd_uncheat(g)}.get(cmd, lambda: print(__doc__))()


if __name__ == "__main__":
    main()
