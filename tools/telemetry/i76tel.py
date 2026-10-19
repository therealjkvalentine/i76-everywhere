#!/usr/bin/env python3
"""i76tel.py - listener for the Interstate '76 telemetry export (music-fix/strlkproxy.c, I76_TELEMETRY=<port>).

The proxy publishes one i76tel_frame_t per rendered frame over UDP (127.0.0.1:7676 by default), each datagram
followed by the events recorded since the previous one, and mirrors the same struct plus the 64-entry event ring
into the shared memory Local\\I76Telemetry. The layout comes from i76tel.h beside this script: it is parsed at
start-up, so this listener (and the --layout table in README.md) cannot drift from what the proxy compiles.

Usage:
  python i76tel.py                     # UDP on 127.0.0.1:7676, a status line 5x a second, every event as it arrives
  python i76tel.py --port 7700         # match I76_TELEMETRY=7700
  python i76tel.py --shm               # read the shared memory instead of UDP (same output)
  python i76tel.py --csv run.csv       # also log every field of every frame (events go to run.events.csv)
  python i76tel.py --check             # validate magic / version / size, the frame counter and the event sequence
  python i76tel.py --layout            # print the struct layout table (offsets from the header)
  python i76tel.py --layout --readme README.md   # rewrite the table between the layout markers in README.md

Versions: the live layout is i76tel.h (v3, 2026-10-10); a v2 proxy (any Strlkup.dll built before v3) is still
decoded through the frozen i76tel_v2.h, chosen per datagram / per shared-memory copy by the frame's version field.
Decoded frames and events always carry the v3 keys (v3-only fields 0 for v2 input), so CSV columns do not change.
v2 verified live 2026-10-01; the v3 fields and events are static-verified only (tests/test_i76tel_v3.py offline).
"""
import argparse, mmap, os, re, socket, struct, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
HEADER = os.path.join(HERE, "i76tel.h")
HEADER_V2 = os.path.join(HERE, "i76tel_v2.h")    # frozen: what every pre-v3 proxy writes

SCALARS = {"uint8_t": "B", "int8_t": "b", "char": "c", "uint16_t": "H", "int16_t": "h",
           "uint32_t": "I", "int32_t": "i", "uint64_t": "Q", "int64_t": "q", "float": "f", "double": "d"}


class Field:
    __slots__ = ("type", "name", "count", "comment", "offset", "size")

    def __init__(self, type_, name, count, comment):
        self.type, self.name, self.count, self.comment = type_, name, count, comment
        self.offset = self.size = 0


class Header:
    """i76tel.h: #define constants and the typedef'd structs, in file order, with offsets computed as '<' packing."""

    def __init__(self, path=HEADER):
        self.consts, self.structs, self.order = {}, {}, []
        text = open(path, encoding="utf-8").read()
        for m in re.finditer(r'^#define\s+(\w+)\s+("[^"]*"|0x[0-9a-fA-F]+u?|\d+)', text, re.M):
            v = m.group(2)
            self.consts[m.group(1)] = v.strip('"').replace("\\\\", "\\") if v.startswith('"') else int(v.rstrip("u"), 0)
        for m in re.finditer(r"typedef struct (\w+) \{(.*?)\} \1;", text, re.S):
            name, body, fields = m.group(1), m.group(2), []
            for line in body.splitlines():
                f = re.match(r"\s*(\w+)\s+(\w+)(?:\[(\w+)\])?\s*;\s*(?:/\*\s*(.*?)\s*\*/)?", line)
                if not f:
                    continue
                count = f.group(3)
                count = 1 if count is None else (int(count) if count.isdigit() else self.consts[count])
                fields.append(Field(f.group(1), f.group(2), count, f.group(4) or ""))
            off = 0
            for fl in fields:
                fl.offset = off
                fl.size = self.sizeof(fl.type) * fl.count
                off += fl.size
            self.structs[name] = (fields, off)
            self.order.append(name)
        self.frame_fmt, self.frame_names = self.flat_format("i76tel_frame_t")
        self.event_fmt, self.event_names = self.flat_format("i76tel_event_t")
        self.frame_size = struct.calcsize(self.frame_fmt)
        self.event_size = struct.calcsize(self.event_fmt)

    def offset(self, sname, field):
        return next(f.offset for f in self.structs[sname][0] if f.name == field)

    def sizeof(self, type_):
        if type_ in SCALARS:
            return struct.calcsize("<" + SCALARS[type_])
        return self.structs[type_][1]

    def flat_format(self, sname, prefix=""):
        """struct format string ('<' + codes) and the flattened field names; char arrays become one 's' field."""
        fmt, names = "", []
        for f in self.structs[sname][0]:
            if f.type in SCALARS:
                if f.type == "char" and f.count > 1:
                    fmt += "%ds" % f.count
                    names.append(prefix + f.name)
                elif f.count == 1:
                    fmt += SCALARS[f.type]
                    names.append(prefix + f.name)
                else:
                    fmt += SCALARS[f.type] * f.count
                    names += ["%s%s_%d" % (prefix, f.name, k) for k in range(f.count)]
            else:
                for k in range(f.count):
                    sub, subn = self.flat_format(f.type, "%s%s%d_" % (prefix, f.name, k) if f.count > 1 else prefix + f.name + "_")
                    fmt += sub.lstrip("<")
                    names += subn
        return "<" + fmt, names

    def layout_markdown(self):
        out = []
        for sname in self.order:
            fields, size = self.structs[sname]
            out.append("### `%s` (%d bytes)\n" % (sname, size))
            out.append("| offset | size | type | field | source / meaning |")
            out.append("|---:|---:|---|---|---|")
            for f in fields:
                t = f.type if f.count == 1 else "%s[%d]" % (f.type, f.count)
                out.append("| %d | %d | `%s` | `%s` | %s |" % (f.offset, f.size, t, f.name, f.comment.replace("|", "\\|")))
            out.append("")
        return "\n".join(out)


_LAYOUTS = {}


def layout(h, version):
    """The Header that describes data written with this version: h itself for its own version, the frozen v2 header
    for 2 (cached), else None."""
    if version == h.consts["I76TEL_VERSION"]:
        return h
    if version == 2:
        if 2 not in _LAYOUTS:
            _LAYOUTS[2] = Header(HEADER_V2)
        return _LAYOUTS[2]
    return None


def frame_version(data, offset=0):
    """the frame's version field (uint16 after the magic), 0 when the buffer is too short"""
    return struct.unpack_from("<H", data, offset + 4)[0] if len(data) >= offset + 6 else 0


def _widen(h, lay, names, values, fmt_names):
    d = dict(zip(names, values))
    if lay is h:
        return d
    return {n: d.get(n, 0) for n in fmt_names}          # h's keys, in h's order; fields the old layout lacks are 0


def decode_frame(h, data):
    """One frame as a dict with h's field names. The layout follows the frame's own version field (a v2 frame decodes
    through i76tel_v2.h, its v3-only fields 0); an unknown version is decoded with h as it stands."""
    lay = layout(h, frame_version(data)) or h
    return _widen(h, lay, lay.frame_names, struct.unpack_from(lay.frame_fmt, data, 0), h.frame_names)


def decode_event(h, data, offset, lay=None):
    lay = lay or h
    return _widen(h, lay, lay.event_names, struct.unpack_from(lay.event_fmt, data, offset), h.event_names)


def decode_events(h, data, offset, count, version=None):
    """count events from offset. version = the frame's version (the event size changed in v3); default h's."""
    lay = (layout(h, version) if version is not None else None) or h
    evs = []
    for k in range(count):
        if offset + (k + 1) * lay.event_size > len(data):
            break
        evs.append(decode_event(h, data, offset + k * lay.event_size, lay))
    return evs


def decode_datagram(h, data):
    """(frame, events) from one UDP datagram of any known version, or (None, []) when it is shorter than its frame."""
    lay = layout(h, frame_version(data)) or h
    if len(data) < lay.frame_size:
        return None, []
    fr = decode_frame(h, data)
    return fr, decode_events(h, data, lay.frame_size, fr["event_count"], lay.consts["I76TEL_VERSION"])


def open_shm(h, suffix=None):
    """Map Local\\I76Telemetry<suffix>: h's size first; if a v2 proxy (or a v2 reader) created the section smaller,
    Windows refuses the larger view, so fall back to the v2 size. Returns (mmap, size)."""
    if suffix is None:
        suffix = os.environ.get("I76_SHM_SUFFIX", "")   # lab runs: the proxy started with the same key names its blocks ...<suffix>
    name = h.consts["I76TEL_SHM_NAME"] + suffix
    size = h.structs["i76tel_shm_t"][1]
    try:
        return mmap.mmap(-1, size, tagname=name), size
    except OSError:
        size2 = layout(h, 2).structs["i76tel_shm_t"][1]
        return mmap.mmap(-1, size2, tagname=name), size2


def shm_layout(h, buf):
    """The Header that describes a copied i76tel_shm_t block (by its frame's version; h when unknown)"""
    return layout(h, frame_version(buf, h.offset("i76tel_shm_t", "frame"))) or h


SND_MODE = {0: "one-shot", 1: "loop", 2: "sustained"}
STOP_REASON = {1: "released", 2: "ended", 0x20: "stop 0x20", 0x40: "parked", 0x80: "stop 0x80", 0x100: "stop 0x100"}
SIDES = {0: "front", 1: "left", 2: "right", 3: "back", 4: "top", -1: "?"}
WEAPON_UI = {0: "cycle", 1: "link", 2: "unlink"}


def ev_name(ev):
    """the 8-byte name packed into i_0 / i_1 (EXPLOSION template, SOUND_* sample name)"""
    return struct.pack("<ii", ev["i_0"], ev["i_1"]).split(b"\0")[0].decode("ascii", "replace")


def sound_fields(h, ev):
    """SOUND_START / SOUND_STOP i_2 unpacked: a dict of mode / is_player / has_pos / detached / voice_level / prio
    (start) or reason / is_player (stop)."""
    b = ev["i_2"] & 0xffffffff
    c = h.consts
    if ev["type"] == c.get("I76TEL_EV_SOUND_STOP"):
        return {"reason": b & 0xffff, "is_player": int(bool(b & c["I76TEL_STOP_PLAYER"]))}
    return {"mode": b & c["I76TEL_SND_MODE"], "is_player": int(bool(b & c["I76TEL_SND_PLAYER"])),
            "has_pos": int(bool(b & c["I76TEL_SND_HAS_POS"])), "detached": int(bool(b & c["I76TEL_SND_DETACHED"])),
            "voice_level": int(bool(b & c["I76TEL_SND_VOICE_LVL"])), "prio": b >> c["I76TEL_SND_PRIO_SHIFT"]}


FLAG_LETTERS = ((0x1, "E"), (0x2, "S"), (0x4, "A"), (0x8, "s"), (0x20, "D"), (0x400, "O"), (0x800, "N"), (0x2000, "G"), (0x4000, "K"), (0x8000, "W"))
GEARS = {0: "R", 1: "N", 2: "1", 3: "2", 4: "3"}


def flags_str(fl):
    s = "".join(ch for bit, ch in FLAG_LETTERS if fl & bit)
    return s or "-"


def status_line(fr):
    if not fr["player_present"]:
        return "t=%7.2f frame %-7d  (no player: menu or loading)  ffb_present=%d" % (fr["sim_time"], fr["frame"], fr["ffb_present"])
    v = fr["speed"]
    name = fr["weapon_name"].split(b"\0")[0].decode("ascii", "replace")
    return ("t=%7.2f frame %-7d dt %5.1fms steps %2d | v %5.1f m/s (%3.0f km/h) gear %s rpm %4.0f thr %+5.2f str %+5.2f | "
            "flags %-5s surf %d | arm %3d/%3d/%3d/%3d chs %3d/%3d/%3d/%3d eng %d susp %d brk %d | %s ammo %d | ev %d" % (
                fr["sim_time"], fr["frame"], fr["dt"] * 1000.0, fr["step_count"], v, v * 3.6, GEARS.get(fr["gear"], str(fr["gear"])),
                fr["rpm"], fr["throttle"], fr["steer"], flags_str(fr["flags"]), fr["surface"],
                fr["armour_0"], fr["armour_1"], fr["armour_2"], fr["armour_3"],
                fr["chassis_0"], fr["chassis_1"], fr["chassis_2"], fr["chassis_3"],
                fr["engine_hp"], fr["susp_hp"], fr["brake_hp"], name or "-", fr["weapon_ammo"], fr["event_seq"]))


def event_line(h, ev):
    t = ev["type"]
    f = [ev["f_%d" % k] for k in range(4)]
    i = [ev["i_0"], ev["i_1"]]
    head = "  ev #%-6d frame %-7d " % (ev["seq"], ev["frame"])
    if t == h.consts.get("I76TEL_EV_SHOT"):
        return head + "SHOT      row %d weapdef %d x%d  ammo left %d  dmg/hit %d  dt_left %.3f" % (int(f[0]), i[0], i[1], int(f[1]), int(f[2]), f[3])
    if t == h.consts.get("I76TEL_EV_EXPLOSION"):
        name = struct.pack("<ii", i[0], i[1]).split(b"\0")[0].decode("ascii", "replace")
        return head + "EXPLOSION %-8s at (%.1f, %.1f, %.1f)  %s" % (name, f[0], f[1], f[2], ("%.1f m from the player" % f[3]) if f[3] >= 0 else "no player")
    if t == h.consts.get("I76TEL_EV_IMPACT"):
        mag = (f[0] ** 2 + f[1] ** 2 + f[2] ** 2) ** 0.5
        return head + "IMPACT    %s source class %d  impact (%.1f, %.1f, %.1f) |%.1f|  lost %d hp" % (
            "PLAYER" if i[0] else "other ", i[1], f[0], f[1], f[2], mag, int(f[3]))
    fx = [ev.get("f_%d" % k, 0.0) for k in range(6)]
    ix = [ev.get("i_%d" % k, 0) for k in range(5)]
    if t == h.consts.get("I76TEL_EV_SOUND_START"):
        s = sound_fields(h, ev)
        where = "at (%.1f, %.1f, %.1f)" % (fx[2], fx[3], fx[4]) if s["has_pos"] else "2D"
        return head + "SOUND+    %-8s %s %-9s %5.0f Hz vol %3.0f%% pan %+.0f prio %d %s%s%s obj 0x%08x voice 0x%08x" % (
            ev_name(ev), "PLAYER" if s["is_player"] else "other ", SND_MODE.get(s["mode"], str(s["mode"])), fx[0], fx[1], fx[5],
            s["prio"], where, " detached" if s["detached"] else "", " voice-level" if s["voice_level"] else "",
            ix[3] & 0xffffffff, ix[4] & 0xffffffff)
    if t == h.consts.get("I76TEL_EV_SOUND_STOP"):
        s = sound_fields(h, ev)
        return head + "SOUND-    %-8s %s %-10s after %.2f s  obj 0x%08x voice 0x%08x" % (
            ev_name(ev), "PLAYER" if s["is_player"] else "other ", STOP_REASON.get(s["reason"], hex(s["reason"])), fx[0],
            ix[3] & 0xffffffff, ix[4] & 0xffffffff)
    if t == h.consts.get("I76TEL_EV_DAMAGE_SIDE"):
        c = h.consts
        return head + "DAMAGE    %s side %-5s zone %d  in %.0f lost %.0f hp  hit (%.2f, %.2f, %.2f)  type 0x%x flags 0x%x  by class %d%s%s" % (
            "PLAYER" if ix[2] & c["I76TEL_DMG_PLAYER"] else "other ", SIDES.get(ix[0], str(ix[0])), ix[1], fx[0], fx[1],
            fx[2], fx[3], fx[4], ix[3] & 0xffff, (ix[3] >> 16) & 0xffff, ix[4],
            " (player's)" if ix[2] & c["I76TEL_DMG_BY_PLAYER"] else "", " KILLED" if ix[2] & c["I76TEL_DMG_KILLED"] else "")
    if t == h.consts.get("I76TEL_EV_WEAPON_UI"):
        return head + "WEAPON-UI %s" % WEAPON_UI.get(ix[0], str(ix[0]))
    return head + "type %d f=%s i=%s" % (t, fx, ix)


class Checker:
    """--check: header validity, the frame counter and the sequences."""

    def __init__(self, h):
        self.h, self.n, self.bad, self.last, self.n_old = h, 0, 0, None, 0
        self.seq_gaps = self.frame_still = self.frame_back = self.frame_skip = self.ev_gaps = 0
        self.last_ev = None
        self.t0 = time.time()

    def frame(self, fr, size):
        self.n += 1
        err = []
        if fr["magic"] != self.h.consts["I76TEL_MAGIC"]:
            err.append("magic 0x%08x" % fr["magic"])
        lay = layout(self.h, fr["version"])
        if lay is None:
            err.append("version %d" % fr["version"])
        else:
            if lay is not self.h and not self.n_old:
                print("note: a version %d proxy (this header is v%d) - decoding through %s" % (
                    fr["version"], self.h.consts["I76TEL_VERSION"], os.path.basename(HEADER_V2)))
            self.n_old += lay is not self.h
            if fr["size"] != lay.frame_size or size < lay.frame_size:
                err.append("size %d (header says %d, datagram %d)" % (fr["size"], lay.frame_size, size))
        if self.last is not None:
            if fr["seq"] != self.last["seq"] + 1:
                self.seq_gaps += 1
            d = fr["frame"] - self.last["frame"]
            if d == 0:
                self.frame_still += 1
            elif d < 0:
                self.frame_back += 1
            elif d > 1:
                self.frame_skip += 1
        self.last = fr
        if err:
            self.bad += 1
            print("BAD frame %d: %s" % (self.n, ", ".join(err)))

    def event(self, ev):
        if self.last_ev is not None and ev["seq"] != self.last_ev + 1:
            self.ev_gaps += 1
        self.last_ev = ev["seq"]

    def summary(self):
        dt = time.time() - self.t0
        print("check: %d frames in %.1f s (%.1f/s), %d bad headers, %d seq gaps, frame counter: %d unchanged, %d backwards, %d skipped; %d event-seq gaps" % (
            self.n, dt, self.n / dt if dt else 0.0, self.bad, self.seq_gaps, self.frame_still, self.frame_back, self.frame_skip, self.ev_gaps))


class Csv:
    def __init__(self, h, path):
        self.f = open(path, "w", encoding="utf-8")
        self.f.write(",".join(h.frame_names) + "\n")
        root, ext = os.path.splitext(path)
        self.e = open(root + ".events" + (ext or ".csv"), "w", encoding="utf-8")
        self.e.write(",".join(h.event_names) + "\n")

    @staticmethod
    def cell(v):
        if isinstance(v, bytes):
            return v.split(b"\0")[0].decode("ascii", "replace")
        if isinstance(v, float):
            return "%.6g" % v
        return str(v)

    def frame(self, fr):
        self.f.write(",".join(self.cell(v) for v in fr.values()) + "\n")

    def event(self, ev):
        self.e.write(",".join(self.cell(v) for v in ev.values()) + "\n")

    def close(self):
        self.f.close(); self.e.close()


def source_udp(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", port))
    s.settimeout(2.0)
    print("listening on 127.0.0.1:%d - set I76_TELEMETRY=%d (or =1 for 7676), start the game, enter a mission" % (port, port))
    while True:
        try:
            data, _ = s.recvfrom(65535)
        except socket.timeout:
            yield None
            continue
        yield data


def source_shm(h):
    """Poll Local\\I76Telemetry. A copy is accepted when seq is even and unchanged across the read; only new frames yield."""
    name = h.consts["I76TEL_SHM_NAME"] + os.environ.get("I76_SHM_SUFFIX", "")
    m, size = open_shm(h)
    print("reading shared memory %s (%d bytes) - a frame appears once the game publishes" % (name, size))
    last_seq, last_ev, idle = None, 0, 0.0
    while True:
        seq0 = struct.unpack_from("<I", m, 0)[0]
        if seq0 == 0 or seq0 & 1 or seq0 == last_seq:  # never written yet (whoever mapped first zeroed it) / being written / seen
            time.sleep(0.001)
            idle += 0.001
            if idle >= 2.0:
                idle = 0.0
                yield None
            continue
        buf = m[:size]
        seq1 = struct.unpack_from("<I", m, 0)[0]
        if seq1 != seq0:
            continue                                    # torn: the writer was inside during the copy
        last_seq, idle = seq0, 0.0
        lay = shm_layout(h, buf)                        # the writer's version decides every offset below
        if lay.structs["i76tel_shm_t"][1] > size:
            continue                                    # a v3 proxy behind a v2-sized view cannot be read whole
        frame_off, ring_off = lay.offset("i76tel_shm_t", "frame"), lay.offset("i76tel_shm_t", "ring")
        ev_seq_off, ev_count_off = lay.offset("i76tel_frame_t", "event_seq"), lay.offset("i76tel_frame_t", "event_count")
        frame = bytearray(buf[frame_off:frame_off + lay.frame_size])
        # splice the new ring entries in after the frame, as a datagram would carry them
        ev_seq = struct.unpack_from("<I", frame, ev_seq_off)[0]
        n = min(ev_seq - last_ev, h.consts["I76TEL_RING"]) if ev_seq >= last_ev else 0
        evs = b""
        for s in range(ev_seq - n + 1, ev_seq + 1):
            o = ring_off + (s % h.consts["I76TEL_RING"]) * lay.event_size
            evs += buf[o:o + lay.event_size]
        last_ev = ev_seq
        struct.pack_into("<I", frame, ev_count_off, n)
        yield bytes(frame) + evs


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=None, help="UDP port (default I76TEL_PORT from the header)")
    ap.add_argument("--shm", action="store_true", help="read Local\\I76Telemetry instead of UDP")
    ap.add_argument("--csv", default="", help="log every frame's fields to this CSV (events to <name>.events.csv)")
    ap.add_argument("--check", action="store_true", help="validate headers and counters; summary on Ctrl-C")
    ap.add_argument("--quiet", action="store_true", help="no status lines (events and check output only)")
    ap.add_argument("--layout", action="store_true", help="print the struct layout table from i76tel.h and exit")
    ap.add_argument("--readme", default="", help="with --layout: rewrite the table between the layout markers in this file")
    args = ap.parse_args()
    h = Header()

    if args.layout:
        table = h.layout_markdown()
        if args.readme:
            text = open(args.readme, encoding="utf-8").read()
            begin, end = "<!-- layout:begin -->", "<!-- layout:end -->"
            a, b = text.index(begin) + len(begin), text.index(end)
            text = text[:a] + "\n<!-- generated by `python i76tel.py --layout --readme README.md` from i76tel.h; do not edit by hand -->\n\n" + table + "\n" + text[b:]
            open(args.readme, "w", encoding="utf-8").write(text)
            print("updated", args.readme)
        else:
            print(table)
        return

    print("i76tel.h: frame %d B, event %d B, ring %d, version %d" % (h.frame_size, h.event_size, h.consts["I76TEL_RING"], h.consts["I76TEL_VERSION"]))
    src = source_shm(h) if args.shm else source_udp(args.port or h.consts["I76TEL_PORT"])
    chk = Checker(h) if args.check else None
    csv = Csv(h, args.csv) if args.csv else None
    frames, next_print, last_frame = 0, 0.0, None
    try:
        for data in src:
            if data is None:
                if frames == 0:
                    print("...nothing yet (is I76_TELEMETRY set for the game, and is it in a mission?)")
                continue
            fr, evs = decode_datagram(h, data)
            if fr is None:
                print("short datagram: %d bytes (version %d)" % (len(data), frame_version(data)))
                continue
            frames += 1
            if chk:
                chk.frame(fr, len(data))
            if csv:
                csv.frame(fr)
            for ev in evs:
                if chk:
                    chk.event(ev)
                if csv:
                    csv.event(ev)
                print(event_line(h, ev))
            now = time.time()
            if not args.quiet and now >= next_print:
                next_print = now + 0.2
                print(status_line(fr))
            last_frame = fr
    except KeyboardInterrupt:
        pass
    finally:
        if csv:
            csv.close()
        if chk:
            chk.summary()
        elif last_frame is not None:
            print("%d frames received; last: %s" % (frames, status_line(last_frame)))


if __name__ == "__main__":
    main()
