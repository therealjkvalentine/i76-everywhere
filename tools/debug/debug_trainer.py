r"""debug_trainer.py - the trainer of I76 Debug: tools/trainer/i76trainer_gui.py's controls without tkinter.

Same memory writes, same rules, same code where it can be shared: the pokes are i76trainer.py's (cmd_repair, cmd_ammo,
cmd_teleport, cmd_uncheat, Game.put with read-back) and the GUI module's helpers (fix_flats, fix_components, set_slot_ammo,
stop_car, weapon_slots, read_status_direct, status_from_frame, proxy_guard_in_log), imported, not copied. The proxy control
block layout is i76trn.h parsed at run time through the GUI's CtlHeader.

Differences from the tkinter window, all deliberate:
* Local\I76Trainer is opened EXISTING-only (never created): with no proxy block the trainer runs in direct mode, and a
  proxy started later is picked up on the next attach. The window created a zeroed block for the proxy to adopt; that is
  harmless for this block (its size never changed) but this tool creates no named section at all.
* Telemetry comes from the debug hub (UDP or the existing shm section), never from a mapping made at a fixed size.
* Entering proxy mode does NOT write flags = 0: the holds already in the block (for example from the old trainer window,
  if it is still open) are shown as they are. Closing the server clears only the holds this tool set.
* The non-sandbox gate is the same (i76trainer.SANDBOX; --any or the checkbox overrides), but find_game's sys.exit is
  caught so the server keeps running.

Full car state (2026-10-20, owner: "the teleport capability ... should also teleport 6 axis position and speed when stored").
A proxy whose block carries i76trn_ext_t (i76trn.h, ext_magic at +168) captures and restores, on the game thread, the pose
(rotation rows + position), the motion (velocity, |v|, body rates, acceleration), the contact state, the wheels' suspension
history and the engine (I76TRN_CMD_STORE_STATE / SET_STATE). Waypoint Save stores all of it, Go puts all of it back, so a
jump run-up replays from the same state; "Go stopped" puts the pose back with zero motion. Ctrl+9 / Ctrl+0 in the game do
the same on the quick slot (the proxy watches the keys while this tool has them enabled). waypoints.json keeps x / y / z at
the top (old readers, the classic window) and adds "state"; a waypoint without "state" (saved before, or by an older proxy)
still loads and teleports the position only, as before. Direct mode (no proxy) stores / restores the pose and the motion
with WriteProcessMemory.
"""
import collections, contextlib, ctypes, io, json, math, os, struct, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(TOOLS, "trainer"))
sys.path.insert(0, os.path.join(TOOLS, "telemetry"))
import i76trainer                                               # find_game, Game, cmd_* (the writes)
from i76trainer import k32, PLAY_FLAGS, UNLIMITED, SANDBOX
import i76trainer_gui as gui                                    # CtlHeader, helpers (tkinter is imported only inside build_gui)
from debug_core import ShmView

TRN_H = os.path.join(TOOLS, "trainer", "i76trn.h")
WAYPOINTS = os.path.join(TOOLS, "trainer", "waypoints.json")     # shared with the tkinter window
STALE_AFTER, ACK_TIMEOUT = gui.STALE_AFTER, gui.ACK_TIMEOUT
PLAY_BITS, CHEAT_MARKER = gui.PLAY_BITS, gui.CHEAT_MARKER
CMD_RESULT = {**gui.CMD_RESULT, 4: "nothing stored"}
WHEEL_NAMES = gui.WHEEL_NAMES
SHM_SUFFIX = os.environ.get("I76TRAINER_SHM_SUFFIX", os.environ.get("I76_SHM_SUFFIX", ""))

# Presets: (label, x, y, z, note). T05 hill top = the crest at the head of the straight down to the barricades
# (lab docs/COLL-TIMING-2026-10-12.md section 4: I76_START_POS=7972,101.8,44035,-90; the ground there is 101.2-101.8 m).
# The trainer's TELEPORT moves the car but cannot turn it (i76trn.h has no yaw): it keeps the heading it had.
PRESETS = {
    "t05_hilltop": ("T05 hill top (crest above the barricades)", 7972.0, 102.3, 44035.0,
                    "T05 only. Lands 0.5-1 m above the road and keeps your heading: turn to face -x (west) down the hill."),
}


# direct-mode state (no proxy): the pose and the motion only, same offsets as the proxy's trn_capture
DIRECT_STATE = (("obj", 0x18, "rot", "<9f"), ("obj", 0x40, "pos", "<3d"), ("ent", 0xbc, "vel", "<3f"), ("ent", 0xac, "speed", "<f"),
                ("ent", 0xb0, "inv_speed", "<f"), ("ent", 0xc8, "rates", "<3f"), ("ent", 0xd4, "accel", "<3f"))


def struct_to_dict(h, sname, buf, off=0):
    """a parsed-header struct at buf[off:] as a dict: scalar -> number, array -> list, nested struct -> dict / list of dicts"""
    out = {}
    for f in h.structs[sname][0]:
        o = off + f.offset
        if f.type in gui.SCALARS:
            if f.type == "char":
                out[f.name] = bytes(buf[o:o + f.size]).split(b"\0")[0].decode("latin1", "replace")
                continue
            v = struct.unpack_from("<" + gui.SCALARS[f.type] * f.count, buf, o)
            out[f.name] = v[0] if f.count == 1 else list(v)
        else:
            sz = h.structs[f.type][1]
            subs = [struct_to_dict(h, f.type, buf, o + k * sz) for k in range(f.count)]
            out[f.name] = subs[0] if f.count == 1 else subs
    return out


def dict_to_struct(h, sname, d):
    """the inverse: bytes of struct sname from a dict (missing fields are 0, so an older or partial dict still packs)"""
    buf = bytearray(h.structs[sname][1])
    d = d or {}
    for f in h.structs[sname][0]:
        v = d.get(f.name)
        if f.type in gui.SCALARS:
            if f.type == "char":
                data = str(v or "").encode("latin1", "replace")[:f.size - 1]
                buf[f.offset:f.offset + len(data)] = data
                continue
            vals = [0] * f.count if v is None else ([v] if f.count == 1 else list(v)[:f.count] + [0] * max(0, f.count - len(v)))
            code = gui.SCALARS[f.type]
            vals = [float(x) if code in "fd" else int(x) for x in vals]
            struct.pack_into("<" + code * f.count, buf, f.offset, *vals)
        else:
            sz = h.structs[f.type][1]
            subs = [v] if f.count == 1 else list(v or [])
            for k in range(f.count):
                sub = subs[k] if k < len(subs) else None
                buf[f.offset + k * sz:f.offset + (k + 1) * sz] = dict_to_struct(h, f.type, sub)
    return bytes(buf)


def state_summary(st):
    """pos, km/h, heading / pitch / roll in degrees, airborne, parts - for the log, the page and waypoints.json"""
    if not st or not st.get("valid"):
        return None
    r = st.get("rot") or [1, 0, 0, 0, 1, 0, 0, 0, 1]
    cl = lambda x: max(-1.0, min(1.0, x))
    v = st.get("vel") or [0, 0, 0]
    return {"pos": [round(c, 2) for c in st["pos"]], "kmh": round(math.sqrt(sum(c * c for c in v)) * 3.6, 1),
            "vel": [round(c, 2) for c in v], "heading": round(math.degrees(math.atan2(r[6], r[8])), 1),
            "pitch": round(math.degrees(math.asin(cl(r[7]))), 1), "roll": round(math.degrees(math.asin(cl(r[1]))), 1),
            "airborne": bool(st.get("ent_flags", 0) & 4), "parts": st.get("parts", 0)}


def quiet(fn, *a):
    """i76trainer functions print and sys.exit; run one, returning (result, printed text)"""
    return gui.capture(fn, *a)


class TrainerBlock:
    """i76trn_ctl_t over the EXISTING Local\\I76Trainer (writable view). get/set like the GUI's Block."""

    def __init__(self, hdr, view):
        self.fields = {f.name: f for f in hdr.structs["i76trn_ctl_t"][0]}
        self.size = hdr.structs["i76trn_ctl_t"][1]
        self.v = view

    def get(self, name):
        f = self.fields[name]
        raw = self.v.read(f.offset, f.size)
        if f.type == "char":
            return raw.split(b"\0")[0].decode("latin1", "replace")
        vals = struct.unpack("<" + gui.SCALARS[f.type] * f.count, raw)
        return vals[0] if f.count == 1 else vals

    def set(self, name, value):
        f = self.fields[name]
        if f.type == "char":
            data = value.encode("latin1", "replace")[:f.size - 1]
            self.v.write(f.offset, data + b"\0" * (f.size - len(data)))
            return
        vals = (value,) if f.count == 1 else tuple(value)
        self.v.write(f.offset, struct.pack("<" + gui.SCALARS[f.type] * f.count, *vals))

    def close(self):
        self.v.close()


class TrainerCore:
    """The window's state machine, driven by tick() at 10 Hz and direct_tick() at 5 Hz from the server's trainer thread;
    every user action is a method that returns nothing and logs what it did (status()['log'])."""

    def __init__(self, hub, allow_any=False, attach=True):
        self.hub = hub
        self.ctl_h = gui.CtlHeader(TRN_H)
        c = self.ctl_h.consts
        self.MAGIC, self.VERSION, self.NAME = c["I76TRN_MAGIC"], c["I76TRN_VERSION"], c["I76TRN_SHM_NAME"] + SHM_SUFFIX
        self.F = {k[len("I76TRN_F_"):]: v for k, v in c.items() if k.startswith("I76TRN_F_")}
        self.CMD = {k[len("I76TRN_CMD_"):]: v for k, v in c.items() if k.startswith("I76TRN_CMD_")}
        self.size = self.ctl_h.structs["i76trn_ctl_t"][1]
        self.EXT_OFF = c.get("I76TRN_EXT_OFFSET", self.size)
        self.EXT_MAGIC = c.get("I76TRN_EXT_MAGIC")
        self.ST = {k[len("I76TRN_ST_"):]: v for k, v in c.items() if k.startswith("I76TRN_ST_")}
        self.ext_size = self.ctl_h.structs["i76trn_ext_t"][1] if "i76trn_ext_t" in self.ctl_h.structs else 0
        self.hotkeys_want = True                                # Ctrl+9 / Ctrl+0 enabled while this tool drives a proxy block
        self.hotkeys_set = False
        self.seen_store_seq = self.seen_restore_seq = None
        self.quick = None                                       # the last state the proxy captured (ext.stored), as a dict
        self.ctl = None
        self.allow_any, self.attach_enabled = allow_any, attach
        self.game = self.pid = self.path = None
        self.attach_error, self.next_attach, self.next_block = "", 0.0, 0.0
        self.mode = "none"
        self.hb = collections.deque(maxlen=40)
        self.hb_changed_at = self.live_pid = self.pending = self.guard_ok = None
        self.flag = {n: False for n in self.F}
        self.owned_flags = 0                                    # the bits this tool set (cleared at shutdown)
        self.freeze_armed = False
        self.xyz = [0.0, 0.0, 0.0]
        self.slots = []
        self.waypoints = self.load_waypoints()
        self.logq = collections.deque(maxlen=400)
        self.log_id = 0
        self.st, self.pstate, self.pdetail, self.tel_live = {"present": False}, "absent", "", False
        self.log("i76trn.h: i76trn_ctl_t %d bytes; %s opened existing-only (never created)" % (self.size, self.NAME))
        if not attach:
            self.log("attach disabled (--no-attach): no process is opened, nothing is written")

    # ---- log
    def log(self, text):
        for line in str(text).rstrip("\n").splitlines():
            if line.strip():
                self.log_id += 1
                self.logq.append({"id": self.log_id, "t": time.strftime("%H:%M:%S"), "text": line})

    # ---- block
    def open_block(self):
        if self.ctl is None and time.time() >= self.next_block:
            self.next_block = time.time() + 1.0
            v = ShmView.open(self.NAME, writable=True)
            if v is not None:
                if v.size < self.size:
                    v.close()
                    self.log("%s is %d bytes, smaller than i76trn.h's %d - not driving it" % (self.NAME, v.size, self.size))
                else:
                    self.ctl = TrainerBlock(self.ctl_h, v)
                    self.hb.clear(); self.hb_changed_at = None

    # ---- the full-state extension (i76trn_ext_t at +168)
    def ext_ok(self):
        if self.ctl is None or not self.ext_size or self.EXT_MAGIC is None or self.ctl.v.size < self.EXT_OFF + self.ext_size:
            return False
        return struct.unpack("<I", self.ctl.v.read(self.EXT_OFF, 4))[0] == self.EXT_MAGIC

    def ext_off(self, name):
        return self.EXT_OFF + self.ctl_h.offset("i76trn_ext_t", name)

    def ext_u32(self, name):
        return struct.unpack("<I", self.ctl.v.read(self.ext_off(name), 4))[0]

    def ext_set_u32(self, name, v):
        self.ctl.v.write(self.ext_off(name), struct.pack("<I", v & 0xffffffff))

    def ext_state(self, which="stored"):
        sz = self.ctl_h.structs["i76trn_state_t"][1]
        return struct_to_dict(self.ctl_h, "i76trn_state_t", self.ctl.v.read(self.ext_off(which), sz))

    def ext_set_target(self, st):
        self.ctl.v.write(self.ext_off("target"), dict_to_struct(self.ctl_h, "i76trn_state_t", st))

    def ext_tick(self):
        """follow the proxy's captures (also the Ctrl+9 ones) and keep the hotkey switch as wanted"""
        if self.mode != "proxy" or not self.ext_ok():
            return
        want = 1 if self.hotkeys_want else 0
        if (self.ext_u32("hotkeys") & 1) != want:
            self.ext_set_u32("hotkeys", (self.ext_u32("hotkeys") & ~1) | want)
            self.hotkeys_set = bool(want)
        ss, rs = self.ext_u32("store_seq"), self.ext_u32("restore_seq")
        if self.seen_store_seq is None:
            self.seen_store_seq, self.seen_restore_seq = ss, rs
            if ss:
                self.quick = self.ext_state("stored")
            return
        if ss != self.seen_store_seq:
            self.seen_store_seq = ss
            self.quick = self.ext_state("stored")
            if not self.pending:
                sm = state_summary(self.quick)
                self.log("Ctrl+9 in the game: state stored at (%.1f, %.1f, %.1f), %.0f km/h, heading %.0f, pitch %.1f%s"
                         % (tuple(sm["pos"]) + (sm["kmh"], sm["heading"], sm["pitch"], ", airborne" if sm["airborne"] else "")))
        if rs != self.seen_restore_seq:
            self.seen_restore_seq = rs
            if not self.pending:
                bad = self.ext_u32("readback_bad")
                self.log("Ctrl+0 in the game: state restored%s" % (" - READBACK MISMATCH %d" % bad if bad else " (read back exact)"))

    # ---- attach
    def set_allow_any(self, on):
        self.allow_any = bool(on)
        self.next_attach, self.attach_error = 0.0, ""
        if self.game:
            self.detach("re-checking the game path")

    def attach(self):
        if not self.attach_enabled:
            return False
        if self.game:
            self.detach("re-attaching")
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                self.pid, self.path = i76trainer.find_game(self.allow_any)
                self.game = i76trainer.Game(self.pid)
        except SystemExit as e:
            self.game, self.attach_error = None, str(e)
            return False
        self.attach_error, self.live_pid, self.hb_changed_at = "", None, None
        self.hb.clear()
        self.guard_ok = gui.proxy_guard_in_log(self.path)
        self.log("attached to %s (pid %d)%s" % (self.path, self.pid,
                 "" if os.path.normcase(os.path.dirname(self.path)) == SANDBOX else "   NOT THE SANDBOX"))
        self.slots = []
        return True

    def detach(self, why):
        if self.game:
            k32.CloseHandle(self.game.h)
            self.log("detached (%s)" % why)
        self.game = self.pid = self.path = None

    def proxy_state(self):
        if self.ctl is None:
            return "absent", "no proxy block (%s not present)" % self.NAME
        if self.ctl.get("magic") != self.MAGIC:
            return "absent", "no proxy block (magic 0x%08x)" % self.ctl.get("magic")
        ver, size = self.ctl.get("version"), self.ctl.get("size")
        if ver != self.VERSION or size != self.size:
            return "mismatch", "proxy block version %d size %d, i76trn.h says %d / %d - not driving it" % (ver, size, self.VERSION, self.size)
        now, hb = time.time(), self.ctl.get("heartbeat")
        if not self.hb:
            self.hb.append((now, hb))
        elif self.hb[-1][1] != hb:
            self.hb.append((now, hb))
            self.hb_changed_at = now
        if self.hb_changed_at is not None and now - self.hb_changed_at < STALE_AFTER:
            fps = 0.0
            if len(self.hb) >= 2:
                (t0, h0), (t1, h1) = self.hb[0], self.hb[-1]
                fps = (h1 - h0) / (t1 - t0) if t1 > t0 else 0.0
            if self.game:
                self.live_pid = self.pid
            return "live", "proxy live, heartbeat %d (%.0f fps)" % (hb, fps)
        if self.game and self.live_pid == self.pid:
            return "paused", "proxy paused: heartbeat %d still for %.0f s (game paused or in a menu)" % (hb, now - self.hb_changed_at)
        if now - self.hb[0][0] < STALE_AFTER:
            return "pending", "proxy block found, waiting %.1f s for its heartbeat" % (STALE_AFTER - (now - self.hb[0][0]))
        return "stale", "proxy: stale (magic but heartbeat %d not advancing - a mapping left over from an earlier game)" % hb

    def choose_mode(self, pstate):
        new = "none" if not self.game else ("proxy" if pstate in ("live", "paused") else ("none" if pstate == "pending" else "direct"))
        if new == self.mode:
            return
        if self.mode == "proxy" and self.owned_flags and self.ctl is not None:
            self.ctl.set("flags", self.ctl.get("flags") & ~self.owned_flags)
        if self.mode == "proxy" and self.hotkeys_set and self.ctl is not None and self.ext_ok():
            self.ext_set_u32("hotkeys", self.ext_u32("hotkeys") & ~1)
        self.hotkeys_set = False
        self.seen_store_seq = self.seen_restore_seq = None
        self.mode = new
        self.owned_flags = 0
        self.log("mode: %s" % {"proxy": "proxy (the game thread applies the flags and commands)",
                               "direct": "DIRECT POKES - fallback: no proxy block; WriteProcessMemory re-asserted at 5 Hz, "
                                         "a write inside the render window is undone once by I76_RENDER_INTERP",
                               "none": "none (not attached)"}[new])
        self.freeze_armed = False
        if new == "proxy":
            word = self.ctl.get("flags")
            self.flag = {n: bool(word & b) for n, b in self.F.items()}
            if word:
                self.log("proxy block already holds flags 0x%04x (another trainer window?) - shown as they are" % word)
        else:
            self.flag = {n: False for n in self.F}

    # ---- ticks (server thread)
    def tick(self):
        now = time.time()
        self.open_block()
        if self.game and not gui.process_alive(self.game):
            self.detach("the game exited")
        if self.attach_enabled and not self.game and now >= self.next_attach and not self.attach_error.startswith("refusing"):
            self.attach()
            self.next_attach = now + 2.0
        self.pstate, self.pdetail = self.proxy_state()
        self.choose_mode(self.pstate)
        if self.mode == "proxy":
            word = self.ctl.get("flags")                         # follow the block (another client may change it)
            self.flag = {n: bool(word & b) for n, b in self.F.items()}
        self.check_ack()
        self.ext_tick()
        fr = self.hub.frame if self.hub and self.hub.frame is not None and now - self.hub.frame_at < STALE_AFTER else None
        self.tel_live = fr is not None
        self.st = gui.status_from_frame(fr) if fr else (gui.read_status_direct(self.game) if self.game else {"present": False})
        if self.game and self.st.get("present"):
            self.slots = gui.weapon_slots(self.game)

    def direct_tick(self):
        if self.mode == "direct" and self.game and self.flags_word():
            self.direct_hold()

    def flags_word(self):
        return sum(self.F[n] for n, v in self.flag.items() if v)

    def direct_hold(self):
        g = self.game
        p = gui.player_or_none(g)
        if not p:
            return
        obj, ent = p
        out = []
        if self.flag.get("GOD"):
            out.append(quiet(i76trainer.cmd_repair, g)[1])
        else:
            if self.flag.get("NOFLATS"):
                out.append(quiet(gui.fix_flats, g, ent)[1])
            if self.flag.get("COMPONENTS"):
                out.append(quiet(gui.fix_components, g, ent)[1])
        if self.flag.get("AMMO"):
            out.append(quiet(i76trainer.cmd_ammo, g)[1])
        if self.flag.get("FREEZE_POS"):
            xyz = self.xyz
            g.wr(obj + 0x40, struct.pack("<3d", *xyz))
            g.wr(ent + 0xbc, struct.pack("<3f", 0, 0, 0))
            back = struct.unpack("<3d", g.rd(obj + 0x40, 24) or b"\0" * 24)
            if any(abs(a - b) > 0.01 for a, b in zip(back, xyz)):
                out.append("  freeze: position read back (%.1f, %.1f, %.1f), wanted (%.1f, %.1f, %.1f)\n" % (back + tuple(xyz)))
        bad = [ln for o in out for ln in o.splitlines() if "FAILED" in ln or "freeze:" in ln or "no player" in ln]
        if bad:
            self.log("\n".join(bad))

    # ---- holds
    def set_flags(self, wanted):
        """wanted: {name: bool} for any subset of GOD AMMO NOFLATS COMPONENTS FREEZE_POS"""
        for k, v in wanted.items():
            if k in self.flag:
                self.flag[k] = bool(v)
        if self.flag["FREEZE_POS"] and not self.freeze_armed:
            p = self.current_pos()
            if not p:
                self.flag["FREEZE_POS"] = False
                self.log("freeze: no player position to hold")
            else:
                self.xyz = list(p)
                self.log("freeze: holding (%.1f, %.1f, %.1f)" % tuple(p))
        self.freeze_armed = self.flag["FREEZE_POS"]
        word = self.flags_word()
        if self.mode == "proxy":
            if self.freeze_armed:
                self.ctl.set("pos", tuple(self.xyz))
            before = self.ctl.get("flags")
            self.ctl.set("flags", word)
            self.owned_flags = (self.owned_flags | (word & ~before)) & word
            self.log("flags -> 0x%04x (%s)" % (word, ", ".join(n for n, v in self.flag.items() if v) or "none"))
        elif self.mode == "direct":
            self.log("direct hold flags -> 0x%04x (re-asserted at 5 Hz; no Play Options bits)" % word)
        else:
            self.flag = {n: False for n in self.F}
            self.log("not attached: nothing to hold")

    # ---- one-shots
    def player_present(self):
        if self.mode == "proxy":
            return self.ctl.get("player_present") == 1 or (self.game and gui.player_or_none(self.game) is not None)
        return bool(self.game and gui.player_or_none(self.game) is not None)

    def guard(self, what):
        if self.mode == "none":
            self.log("%s: not attached" % what); return False
        if not self.player_present():
            self.log("%s: no player vehicle (not in a mission?) - nothing written" % what); return False
        if self.mode == "proxy" and self.pending:
            self.log("%s: a command is still waiting for its ack" % what); return False
        return True

    def send(self, cmd_name, label, on_ack=None, **ops):
        for k, v in ops.items():
            self.ctl.set(k, v)
        self.ctl.set("cmd", self.CMD[cmd_name])
        req = (self.ctl.get("req_seq") + 1) & 0xffffffff or 1
        self.ctl.set("req_seq", req)
        self.pending = (req, time.time(), label, on_ack)
        self.log("%s: request #%d sent (%s)" % (label, req, cmd_name))

    def check_ack(self):
        if not self.pending or self.ctl is None:
            return
        req, sent, label, on_ack = self.pending
        if self.ctl.get("ack_seq") == req:
            self.pending = None
            r = self.ctl.get("cmd_result")
            self.log("%s: ack #%d after %.0f ms - %s%s" % (label, req, (time.time() - sent) * 1000.0,
                                                           CMD_RESULT.get(r, "result %d" % r), ("; " + self.ctl.get("msg")) if self.ctl.get("msg") else ""))
            if on_ack and r == 0:
                on_ack()
        elif time.time() - sent > ACK_TIMEOUT:
            self.pending = None
            self.log("%s: no ack for #%d within %.0f s (game paused, in a menu, or the proxy is gone); the request stays queued in the block"
                     % (label, req, ACK_TIMEOUT))

    @staticmethod
    def ammo_value(s):
        s = str(s).strip().lower()
        if s in ("", "unlimited", "inf", "max"):
            return UNLIMITED
        v = int(s, 0)
        if not 0 <= v <= UNLIMITED:
            raise ValueError("ammo out of range")
        return v

    def do_repair(self):
        if not self.guard("repair"):
            return
        if self.mode == "proxy":
            self.send("REPAIR", "repair")
        else:
            self.log(quiet(i76trainer.cmd_repair, self.game)[1])

    def do_stop(self):
        if not self.guard("stop"):
            return
        if self.mode == "proxy":
            self.send("STOP", "stop")
        else:
            obj, ent = gui.player_or_none(self.game)
            self.log(quiet(gui.stop_car, self.game, ent)[1])

    def do_ammo(self, value="unlimited"):
        try:
            v = self.ammo_value(value)
        except ValueError as e:
            self.log("ammo: %s" % e); return
        if not self.guard("ammo"):
            return
        if self.mode == "proxy":
            self.send("AMMO", "ammo", ammo_value=v)
        else:
            if v == UNLIMITED:
                self.log(quiet(i76trainer.cmd_ammo, self.game)[1])
            else:
                for s, n, a in gui.weapon_slots(self.game):
                    self.log(quiet(gui.set_slot_ammo, self.game, s, v)[1])

    def do_slot_ammo(self, slot, value="unlimited"):
        try:
            slot = int(slot)
            v = self.ammo_value(value)
        except (TypeError, ValueError) as e:
            self.log("slot ammo: %s" % e); return
        if not self.guard("slot ammo"):
            return
        if self.mode == "proxy":
            self.send("SLOT_AMMO", "slot %d ammo" % slot, slot_index=slot, ammo_value=v)
        else:
            self.log(quiet(gui.set_slot_ammo, self.game, slot, v)[1])

    def current_pos(self):
        fr = self.hub.frame if self.hub and self.hub.frame is not None and time.time() - self.hub.frame_at < STALE_AFTER else None
        if fr and fr["player_present"]:
            return (fr["pos_0"], fr["pos_1"], fr["pos_2"])
        if self.game:
            st = gui.read_status_direct(self.game)
            if st["present"]:
                return st["pos"]
        return None

    def do_teleport(self, xyz):
        try:
            xyz = [float(c) for c in xyz][:3]
            if len(xyz) != 3:
                raise ValueError
        except (TypeError, ValueError):
            self.log("teleport: x y z must be numbers"); return
        if not self.guard("teleport"):
            return
        self.xyz = list(xyz)
        if self.mode == "proxy":
            self.send("TELEPORT", "teleport to (%.1f, %.1f, %.1f)" % tuple(xyz), pos=tuple(xyz), vel=(0.0, 0.0, 0.0))
        else:
            self.log(quiet(i76trainer.cmd_teleport, self.game, [str(c) for c in xyz])[1])

    def do_preset(self, key):
        p = PRESETS.get(key)
        if not p:
            self.log("preset %s: unknown" % key); return
        self.log("preset: %s - %s" % (p[0], p[4]))
        self.do_teleport(p[1:4])

    # ---- waypoints (the window's file, so both tools share the three slots)
    def load_waypoints(self):
        try:
            with open(WAYPOINTS, encoding="utf-8") as f:
                wp = json.load(f)
            return (list(wp) + [None] * 3)[:3]
        except (OSError, ValueError):
            return [None, None, None]

    def save_waypoints(self):
        with open(WAYPOINTS, "w", encoding="utf-8") as f:
            json.dump(self.waypoints, f, indent=1)

    @staticmethod
    def waypoint_from_state(st, how):
        sm = state_summary(st)
        return {"x": st["pos"][0], "y": st["pos"][1], "z": st["pos"][2], "saved": time.strftime("%Y-%m-%d %H:%M"), "how": how,
                "summary": sm, "state": st}

    def wp_save(self, i):
        """proxy with the extension: the full state, captured on the game thread; else the position (as before)"""
        if self.mode == "proxy" and self.ext_ok():
            if not self.guard("waypoint %d" % (i + 1)):
                return

            def done():
                st = self.ext_state("stored")
                self.quick = st
                self.seen_store_seq = self.ext_u32("store_seq")
                self.waypoints[i] = self.waypoint_from_state(st, "proxy full state")
                self.save_waypoints()
                sm = state_summary(st)
                self.log("waypoint %d saved (full state): (%.1f, %.1f, %.1f) %.0f km/h heading %.0f pitch %.1f%s -> %s"
                         % ((i + 1,) + tuple(sm["pos"]) + (sm["kmh"], sm["heading"], sm["pitch"], " airborne" if sm["airborne"] else "", WAYPOINTS)))
            self.send("STORE_STATE", "waypoint %d store" % (i + 1), on_ack=done)
            return
        if self.mode == "direct" and self.game:
            st = self.direct_capture()
            if st:
                self.waypoints[i] = self.waypoint_from_state(st, "direct pose + motion")
                self.save_waypoints()
                self.log("waypoint %d saved (direct: pose + motion): (%.1f, %.1f, %.1f)" % ((i + 1,) + tuple(st["pos"])))
                return
        p = self.current_pos()
        if not p:
            self.log("waypoint %d: no player position to save" % (i + 1)); return
        self.waypoints[i] = {"x": p[0], "y": p[1], "z": p[2], "saved": time.strftime("%Y-%m-%d %H:%M"), "how": "position only"}
        self.save_waypoints()
        self.log("waypoint %d saved: (%.1f, %.1f, %.1f) -> %s (position only: %s)" % (i + 1, p[0], p[1], p[2], WAYPOINTS,
                 "this proxy has no full-state store" if self.mode == "proxy" else "not attached to a proxy"))

    def wp_go(self, i, still=False):
        w = self.waypoints[i]
        if not w:
            self.log("waypoint %d is empty" % (i + 1)); return
        st = w.get("state")
        if st and st.get("valid"):
            self.restore_state(st, "waypoint %d" % (i + 1), still)
        else:
            if still is False and self.mode == "proxy" and self.ext_ok():
                self.log("waypoint %d holds a position only (saved before the full-state store): teleporting the position" % (i + 1))
            self.do_teleport([w["x"], w["y"], w["z"]])

    def restore_state(self, st, label, still=False):
        """put a stored state back: everything (still=False), or the pose with zero motion (still=True)"""
        if not self.guard(label):
            return
        st = dict(st)
        parts = 0
        if still:
            for k in ("vel", "rates", "accel"):
                st[k] = [0.0, 0.0, 0.0]
            st["speed"], st["inv_speed"] = 0.0, 0.0
            parts = self.ST["POSE"] | self.ST["MOTION"]
        if self.mode == "proxy" and self.ext_ok():
            self.ext_set_target(st)
            self.ext_set_u32("restore_parts", parts)

            def done():
                self.seen_restore_seq = self.ext_u32("restore_seq")
                bad = self.ext_u32("readback_bad")
                self.log("%s: restored%s%s" % (label, " (pose, stopped)" if still else " (full state)",
                                               " - READBACK MISMATCH %d" % bad if bad else ", read back exact"))
            self.send("SET_STATE", "%s restore" % label, on_ack=done)
        elif self.mode == "direct":
            self.log(self.direct_restore(st))
        else:
            self.log("%s: this proxy has no full-state restore - teleporting the position only" % label)
            self.do_teleport(st["pos"])

    def do_store(self):
        """the quick slot (= Ctrl+9 in the game)"""
        if self.mode == "proxy" and self.ext_ok():
            if not self.guard("store"):
                return

            def done():
                self.quick = self.ext_state("stored")
                self.seen_store_seq = self.ext_u32("store_seq")
                sm = state_summary(self.quick)
                self.log("quick slot: stored (%.1f, %.1f, %.1f) %.0f km/h heading %.0f pitch %.1f%s"
                         % (tuple(sm["pos"]) + (sm["kmh"], sm["heading"], sm["pitch"], " airborne" if sm["airborne"] else "")))
            self.send("STORE_STATE", "store", on_ack=done)
        elif self.mode == "direct" and self.game:
            self.quick = self.direct_capture()
            self.log("quick slot: stored (direct: pose + motion)" if self.quick else "store: no player")
        else:
            self.log("store: needs the proxy's full-state block (or direct mode)")

    def do_restore(self, still=False):
        if not self.quick or not self.quick.get("valid"):
            self.log("restore: the quick slot is empty (Store, or Ctrl+9 in the game)"); return
        self.restore_state(self.quick, "quick slot", still)

    def quick_to_waypoint(self, i):
        if not self.quick or not self.quick.get("valid"):
            self.log("quick slot is empty"); return
        self.waypoints[i] = self.waypoint_from_state(self.quick, "quick slot")
        self.save_waypoints()
        self.log("waypoint %d <- quick slot" % (i + 1))

    # ---- direct mode (no proxy): pose + motion through WriteProcessMemory
    def direct_capture(self):
        p = gui.player_or_none(self.game)
        if not p:
            return None
        base = {"obj": p[0], "ent": p[1]}
        st = {"valid": 1, "parts": self.ST["POSE"] | self.ST["MOTION"], "frame": 0}
        for which, off, name, fmt in DIRECT_STATE:
            raw = self.game.rd(base[which] + off, struct.calcsize(fmt))
            if raw is None:
                return None
            v = struct.unpack(fmt, raw)
            st[name] = v[0] if len(v) == 1 else list(v)
        return st

    def direct_restore(self, st):
        p = gui.player_or_none(self.game)
        if not p:
            return "restore: no player"
        base = {"obj": p[0], "ent": p[1]}
        bad = 0
        for _ in range(2):                                      # twice, as cmd_teleport: a write in the render window is undone once
            for which, off, name, fmt in DIRECT_STATE:
                v = st.get(name)
                if v is None:
                    continue
                data = struct.pack(fmt, *(v if isinstance(v, (list, tuple)) else [v]))
                self.game.wr(base[which] + off, data)
            k32.Sleep(40)
        for which, off, name, fmt in DIRECT_STATE:
            v = st.get(name)
            if v is None:
                continue
            if self.game.rd(base[which] + off, struct.calcsize(fmt)) != struct.pack(fmt, *(v if isinstance(v, (list, tuple)) else [v])):
                bad += 1
        return "direct restore (pose + motion): %s" % ("read back exact" if not bad else "%d fields moved on after the write (the game ran a step)" % bad)

    # ---- play options
    def do_playflags(self, bits, on, confirmed=False):
        bits = int(bits) & 0x1f
        if not bits:
            self.log("play options: tick at least one bit"); return
        if self.mode == "none":
            self.log("play options: not attached"); return
        if on and bits & 0x1c and not confirmed:
            self.log("play options: ammo / armour / chassis are the game's cheater options - not set without the confirmation"); return
        if self.mode == "proxy":
            if self.pending:
                self.log("play options: a command is still waiting for its ack"); return
            self.send("PLAYFLAGS", "play options %s 0x%02x" % ("set" if on else "clear", bits),
                      play_set=bits if on else 0, play_clear=0 if on else bits)
        else:
            g = self.game
            f = g.u32(PLAY_FLAGS)
            self.log(quiet(g.put, PLAY_FLAGS, "<I", (f | bits) if on else (f & ~bits), "options_play_flags")[1])

    def do_uncheat(self):
        if self.mode == "none" or not self.game:
            self.log("uncheat: not attached"); return
        if self.mode == "proxy":
            if self.pending:
                self.log("uncheat: a command is still waiting for its ack"); return
            self.flag["GOD"] = self.flag["AMMO"] = False
            self.ctl.set("flags", self.flags_word())
            self.send("PLAYFLAGS", "uncheat: play options clear 0x1c", play_set=0, play_clear=0x1c)
            self.log(quiet(self.game.put, CHEAT_MARKER, "<I", 0, "cheats-used marker")[1])
        else:
            self.log(quiet(i76trainer.cmd_uncheat, self.game)[1])
        self.log("uncheat: done - win the mission again (or replay it) and it will advance; God / Ammo holds were released")

    # ---- the request router (HTTP POST /api/trainer)
    def action(self, req):
        a = req.get("action")
        if a == "attach":
            self.next_attach, self.attach_error = 0.0, ""
            self.attach()
        elif a == "allow_any":
            self.set_allow_any(req.get("on"))
        elif a == "flags":
            self.set_flags(req.get("flags", {}))
        elif a == "repair":
            self.do_repair()
        elif a == "stop":
            self.do_stop()
        elif a == "ammo":
            self.do_ammo(req.get("value", "unlimited"))
        elif a == "slot_ammo":
            self.do_slot_ammo(req.get("slot"), req.get("value", "unlimited"))
        elif a == "teleport":
            self.do_teleport(req.get("xyz"))
        elif a == "use_current":
            p = self.current_pos()
            if p:
                self.xyz = list(p)
            else:
                self.log("use current: no player position")
        elif a == "preset":
            self.do_preset(req.get("key"))
        elif a == "wp_save":
            self.wp_save(int(req.get("i", 0)))
        elif a == "wp_go":
            self.wp_go(int(req.get("i", 0)), bool(req.get("still")))
        elif a == "wp_from_quick":
            self.quick_to_waypoint(int(req.get("i", 0)))
        elif a == "store":
            self.do_store()
        elif a == "restore":
            self.do_restore(bool(req.get("still")))
        elif a == "hotkeys":
            self.hotkeys_want = bool(req.get("on"))
            self.log("in-game keys Ctrl+9 store / Ctrl+0 restore: %s" % ("on" if self.hotkeys_want else "off"))
        elif a == "playflags":
            self.do_playflags(req.get("bits", 0), bool(req.get("on")), bool(req.get("confirmed")))
        elif a == "uncheat":
            self.do_uncheat()
        else:
            self.log("unknown action %r" % a)
            return False
        return True

    # ---- the view
    def campaign_note(self):
        if not self.game:
            return "campaign: not attached"
        if self.mode == "direct":
            return ("campaign: safe - direct mode holds God / Ammo by repair and ammo writes only, no play bits "
                    "(a big hit between two 5 Hz repairs can still kill). Play Options 'Set' is still cheating.")
        if self.mode == "proxy" and self.guard_ok:
            return ("campaign: safe - this proxy hides God / Ammo's play bits from the game's cheat check "
                    "(log: cheat-marker guard 4/4). Repair, refill, teleport, freeze, components, no-flats never touch it.")
        return ("campaign: UNTICK God and Unlimited ammo before the mission ends and before closing the Esc menu - "
                "this proxy %s, so the game would mark itself cheated and refuse to advance the campaign. "
                "Repair now / Refill ammo / teleport / freeze / components / no-flats are safe."
                % ("has no cheat-marker guard" if self.guard_ok is False else "log was not found, so the cheat-marker guard is unconfirmed"))

    def status(self):
        g, st = self.game, self.st
        out = {"mode": self.mode, "pstate": self.pstate, "pdetail": self.pdetail, "attached": bool(g), "pid": self.pid, "path": self.path,
               "sandbox": SANDBOX, "allow_any": self.allow_any, "attach_enabled": self.attach_enabled, "attach_error": self.attach_error,
               "not_sandbox": bool(g and os.path.normcase(os.path.dirname(self.path)) != SANDBOX),
               "flags": dict(self.flag), "xyz": [round(c, 2) for c in self.xyz], "pending": bool(self.pending), "tel_live": self.tel_live,
               "campaign": self.campaign_note(), "guard_ok": self.guard_ok,
               "waypoints": [None if not w else {"x": w["x"], "y": w["y"], "z": w["z"], "saved": w.get("saved"), "how": w.get("how", "position only"),
                                                 "full": bool(w.get("state")), "summary": w.get("summary") or state_summary(w.get("state"))} for w in self.waypoints],
               "quick": state_summary(self.quick), "hotkeys": self.hotkeys_want,
               "presets": [{"key": k, "label": v[0], "xyz": v[1:4], "note": v[4]} for k, v in PRESETS.items()],
               "play_bits": [{"name": n, "bit": b} for n, b in PLAY_BITS],
               "slots": [{"slot": s, "name": n, "ammo": "unlimited" if a == UNLIMITED else a} for s, n, a in self.slots],
               "log": list(self.logq)[-120:]}
        ext = self.ctl is not None and self.pstate in ("live", "paused") and self.ext_ok()
        out["full_state"] = ("proxy" if ext else "direct (pose + motion)" if self.mode == "direct" else
                             "no: this proxy predates it (position-only teleport)" if self.mode == "proxy" else "not attached")
        if ext:
            out["ext"] = {k: self.ext_u32(k) for k in ("hotkeys", "store_seq", "restore_seq", "readback_bad", "hotkey_stores", "hotkey_restores")}
        if self.ctl is not None and self.pstate in ("live", "paused"):
            out["proxy"] = {"applied": self.ctl.get("applied"), "player_present": self.ctl.get("player_present"), "faults": self.ctl.get("faults"),
                            "cmd_result": CMD_RESULT.get(self.ctl.get("cmd_result"), str(self.ctl.get("cmd_result"))), "msg": self.ctl.get("msg"),
                            "play_flags_now": self.ctl.get("play_flags_now")}
        if g:
            pf = self.ctl.get("play_flags_now") if (self.ctl is not None and self.pstate == "live") else g.u32(PLAY_FLAGS)
            out["play_flags"] = pf
            out["play_names"] = [n for n, b in PLAY_BITS if pf is not None and pf & b]
            out["cheat_marker"] = g.u32(CHEAT_MARKER)
        s = {"present": bool(st.get("present"))}
        if st.get("present"):
            s.update(pos=[round(c, 2) for c in st["pos"]], speed=round(st["speed"], 2),
                     armour=st["armour"], armour_max=st["armour_max"], chassis=st["chassis"], chassis_max=st["chassis_max"],
                     armour_hud=st.get("armour_hud"), chassis_hud=st.get("chassis_hud"),
                     engine=list(st["engine"]), susp=list(st["susp"]), brake=list(st["brake"]),
                     wheels=[{"name": n, "present": bool(pr), "flat": bool(fl), "hp": hp, "max": mx} for n, (pr, fl, hp, mx) in zip(WHEEL_NAMES, st["wheels"])],
                     weapon=st.get("weapon_name"), weapon_ammo=("unlimited" if st.get("weapon_ammo") == UNLIMITED else st.get("weapon_ammo")))
        out["status"] = s
        return out

    def close(self):
        try:
            if self.mode == "proxy" and self.ctl is not None and self.owned_flags and self.ctl.get("magic") == self.MAGIC:
                self.ctl.set("flags", self.ctl.get("flags") & ~self.owned_flags)
            if self.mode == "proxy" and self.ctl is not None and self.hotkeys_set and self.ext_ok():
                self.ext_set_u32("hotkeys", self.ext_u32("hotkeys") & ~1)
            if self.game:
                k32.CloseHandle(self.game.h)
        finally:
            if self.ctl is not None:
                self.ctl.close()
                self.ctl = None
