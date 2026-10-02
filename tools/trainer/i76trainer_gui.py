r"""i76trainer_gui.py - player-facing trainer window for the running Interstate '76 (GOG builds), SANDBOX by default.

    python i76trainer_gui.py              the window (or double-click TRAINER.bat)
    python i76trainer_gui.py --selftest   parse i76trn.h + ..\telemetry\i76tel.h, print the layouts, round-trip a
                                          request through a private shared-memory block, exit 0; no game needed
    python i76trainer_gui.py --any        start with 'allow non-sandbox' ticked (the daily driver is otherwise refused)

Two ways of applying a cheat, chosen automatically (README-GUI.md):

  proxy   The Strlkup proxy (music-fix/strlkproxy.c) creates the shared block Local\I76Trainer (layout: i76trn.h,
          parsed here at run time so it cannot drift) and, at the top of every frame on the game's own thread, holds
          the flags and runs the one-shot commands. Used whenever the block carries the magic.
  direct  No proxy: the pokes from i76trainer.py (WriteProcessMemory, each read back) re-asserted on a 5 Hz timer.
          A poke that lands inside the render window is undone once by the proxy's I76_RENDER_INTERP restore
          (cheats.md section 2), and a hit can register in the same frame as a repair; the hold timer papers over
          both, which is why this is the fallback and not the default.

Every address comes from i76-map\subsystems\cheats.md. Nothing here sets the "cheats used" marker 0x535f78; the
Play Options menus do (a cheated mission success then becomes outcome 0xb). Status comes from Local\I76Telemetry
(i76tel.h) when the game publishes it, from direct reads otherwise.
"""
import sys, os, io, mmap, struct, time, json, contextlib, ctypes, collections

HERE = os.path.dirname(os.path.abspath(__file__))
TEL_DIR = os.path.join(os.path.dirname(HERE), "telemetry")
sys.path.insert(0, HERE)
sys.path.insert(0, TEL_DIR)
import i76trainer                                           # find_game, Game, cmd_repair / cmd_ammo / cmd_teleport
from i76trainer import k32, PLAY_FLAGS, UNLIMITED, COMP_HEALTH, SANDBOX
import i76tel                                               # Header (the .h parser), decode_frame
from i76tel import Header, SCALARS

TRN_H = os.path.join(HERE, "i76trn.h")
TEL_H = os.path.join(TEL_DIR, "i76tel.h")
WAYPOINTS = os.path.join(HERE, "waypoints.json")

CHEAT_MARKER = 0x535f78                                     # cheats.md section 1: set by the menus, read at mission end
WEAP_TABLE, WEAP_STRIDE, WEAP_COUNT = 0x5aab08, 0x4c, 0x5da750   # cheats.md section 3: live weapon instances
WEAP_AMMO, WEAP_NAMEOBJ, WEAP_MAX_SLOTS = 0x20, 0x08, 16
PLAY_BITS = (("arcade", 0x01), ("no-salvage", 0x02), ("ammo", 0x04), ("armour", 0x08), ("chassis", 0x10))
COMPONENT_SLOT = {"engine": 0x3c4, "susp": 0x3c8, "brake": 0x3cc}     # entity+slot -> component object, +0x70 -> data (i76tel.h)
WHEEL_NAMES = ("FL", "FR", "ML", "MR", "RL", "RR")
CMD_RESULT = {0: "ok", 1: "no player", 2: "unknown cmd", 3: "bad slot"}
ACK_TIMEOUT = 1.0
STALE_AFTER = 0.5                                           # a mapping survives the game while anyone holds it (the selftest, this window,
                                                            # a test); it keeps the last magic and frames. Only an advancing counter is live.
SHM_SUFFIX = os.environ.get("I76TRAINER_SHM_SUFFIX", "")   # tests set this so their fake blocks never share the game's mappings


# ---------------------------------------------------------------- headers and shared memory

class CtlHeader(Header):
    """i76trn.h through the telemetry parser. Header.__init__ also builds the telemetry frame / event formats by name;
    those structs are not in this file, so they come out empty instead of raising."""

    def flat_format(self, sname, prefix=""):
        if sname not in self.structs:
            return "<", []
        return super().flat_format(sname, prefix)


class Block:
    """A struct from a parsed header mapped over a named shared-memory block. mmap(-1, size, tagname=) opens the
    existing mapping when the proxy made it first, or creates a zeroed one (magic 0 = no proxy)."""

    def __init__(self, hdr, sname, tagname):
        self.fields = {f.name: f for f in hdr.structs[sname][0]}
        self.size = hdr.structs[sname][1]
        self.tagname = tagname + SHM_SUFFIX
        self.m = mmap.mmap(-1, self.size, tagname=self.tagname)

    def get(self, name):
        f = self.fields[name]
        if f.type == "char":
            return bytes(self.m[f.offset:f.offset + f.size]).split(b"\0")[0].decode("latin1", "replace")
        v = struct.unpack_from("<" + SCALARS[f.type] * f.count, self.m, f.offset)
        return v[0] if f.count == 1 else v

    def set(self, name, value):
        f = self.fields[name]
        if f.type == "char":
            data = value.encode("latin1", "replace")[:f.size - 1]
            self.m[f.offset:f.offset + f.size] = data + b"\0" * (f.size - len(data))
            return
        vals = (value,) if f.count == 1 else tuple(value)
        struct.pack_into("<" + SCALARS[f.type] * f.count, self.m, f.offset, *vals)

    def close(self):
        self.m.close()


class Telemetry:
    """Local\\I76Telemetry, read once per GUI tick without blocking: the seq-even / unchanged rule of i76tel.source_shm."""

    def __init__(self, h):
        self.h = h
        self.size = h.structs["i76tel_shm_t"][1]
        self.tagname = h.consts["I76TEL_SHM_NAME"] + SHM_SUFFIX
        self.m = mmap.mmap(-1, self.size, tagname=self.tagname)
        self.frame_off = h.offset("i76tel_shm_t", "frame")
        self.last_seq, self.frame, self.changed_at = 0, None, 0.0

    def live(self):
        """seq advanced within STALE_AFTER: a surviving mapping keeps its last frame, so a frame alone proves nothing"""
        return self.frame is not None and time.time() - self.changed_at < STALE_AFTER

    def poll(self):
        """the newest consistent frame as a dict, or None while seq is 0 (nothing published since the mapping was made)"""
        for _ in range(4):
            seq0 = struct.unpack_from("<I", self.m, 0)[0]
            if seq0 == 0:
                return None
            if seq0 & 1:
                continue                                    # the writer is inside
            buf = self.m[:self.size]
            if struct.unpack_from("<I", self.m, 0)[0] != seq0:
                continue                                    # torn
            if seq0 != self.last_seq:
                if self.last_seq:
                    self.changed_at = time.time()           # the first sight of a value is not an advance
                self.last_seq = seq0
                fr = i76tel.decode_frame(self.h, buf[self.frame_off:self.frame_off + self.h.frame_size])
                self.frame = fr if fr["magic"] == self.h.consts["I76TEL_MAGIC"] else None
            return self.frame
        return self.frame

    def close(self):
        self.m.close()


# ---------------------------------------------------------------- game access helpers (reads; the writes are i76trainer's)

def capture(fn, *args):
    """run one of i76trainer's printing commands, returning (result, what it printed)"""
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            r = fn(*args)
    except SystemExit as e:                                 # i76trainer reports 'no player vehicle' with sys.exit
        return None, buf.getvalue() + ("%s\n" % e)
    return r, buf.getvalue()


def player_or_none(g):
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            return g.player()
    except SystemExit:
        return None


def weapon_slots(g):
    """[(slot, name, ammo)] for the live weapon instances: table 0x5aab08, stride 0x4c, count 0x5da750 (cheats.md s.3)"""
    n = g.u32(WEAP_COUNT)
    out = []
    if n is None:
        return out
    for s in range(min(n, WEAP_MAX_SLOTS)):
        inst = WEAP_TABLE + s * WEAP_STRIDE
        if not g.u32(inst + 4):
            continue
        nobj = g.u32(inst + WEAP_NAMEOBJ)
        nm = ((g.rd(nobj, 8) if nobj else b"") or b"").split(b"\0")[0].decode("latin1", "replace")
        out.append((s, nm or "?", g.i32(inst + WEAP_AMMO)))
    return out


def read_status_direct(g):
    """the status panel's fields by ReadProcessMemory, the same shape the telemetry frame gives"""
    st = {"present": False}
    p = player_or_none(g)
    if not p:
        return st
    obj, ent = p
    raw = g.rd(obj + 0x40, 24)
    if raw is None:
        return st
    st["present"] = True
    st["pos"] = struct.unpack("<3d", raw)
    st["speed"] = g.f32(ent + 0xac) or 0.0
    st["vel"] = struct.unpack("<3f", g.rd(ent + 0xbc, 12) or b"\0" * 12)
    for key, cur, mx, hud in (("armour", 0x138, 0x158, 0x178), ("chassis", 0x148, 0x168, 0x18c)):
        st[key] = [g.i32(ent + cur + 4 * s) for s in range(4)]
        st[key + "_max"] = [g.i32(ent + mx + 4 * s) for s in range(4)]
        st[key + "_hud"] = [g.i32(ent + hud + 4 * s) for s in range(5)]
    for key, (ho, mo) in (("engine", (0, 4)), ("susp", (0, 4)), ("brake", (4, 8))):
        comp = g.u32(ent + COMPONENT_SLOT[key])
        data = g.u32(comp + 0x70) if comp else None
        st[key] = (g.i32(data + ho), g.i32(data + mo)) if data else (None, None)
    wheels = []
    for i in range(6):
        c = g.u32(ent + 0x3a8 + 4 * i)
        ce = g.u32(c + 0x70) if c else None
        if ce and g.u32(c + 0x6c) == 30:
            wheels.append((True, g.u32(ce + 0x44), g.i32(ce + 4), g.i32(ce + 8)))
        else:
            wheels.append((False, 0, 0, 0))
    st["wheels"] = wheels
    st["weapon_name"], st["weapon_ammo"] = None, None          # the selected row needs the telemetry frame
    return st


def status_from_frame(fr):
    st = {"present": bool(fr["player_present"])}
    if not st["present"]:
        return st
    st["pos"] = (fr["pos_0"], fr["pos_1"], fr["pos_2"])
    st["speed"] = fr["speed"]
    st["vel"] = (fr["velocity_0"], fr["velocity_1"], fr["velocity_2"])
    for key in ("armour", "chassis"):
        st[key] = [fr["%s_%d" % (key, s)] for s in range(4)]
        st[key + "_max"] = [fr["%s_max_%d" % (key, s)] for s in range(4)]
        st[key + "_hud"] = None
    for key in ("engine", "susp", "brake"):
        st[key] = (fr[key + "_hp"], fr[key + "_hp_max"])
    st["wheels"] = [(bool(fr["wheel%d_present" % k]), fr["wheel%d_flat" % k], fr["wheel%d_hp" % k], fr["wheel%d_hp_max" % k]) for k in range(6)]
    st["weapon_name"] = fr["weapon_name"].split(b"\0")[0].decode("ascii", "replace") if fr["weapon_row"] >= 0 else None
    st["weapon_ammo"] = fr["weapon_ammo"]
    return st


def fix_flats(g, ent):
    """the wheel branch of i76trainer.cmd_repair on its own: flat flag +0x44 cleared, radius +0x1c restored (/0.688)"""
    for i, c, t, ce in g.components(ent):
        if t == 30 and ce and g.u32(ce + 0x44):
            g.put(ce + 0x1c, "<f", g.f32(ce + 0x1c) / 0.688, "component %d wheel radius" % i)
            g.put(ce + 0x44, "<I", 0, "component %d flat flag" % i)


def fix_components(g, ent):
    """the component branch of i76trainer.cmd_repair on its own: every component's health to its max"""
    for i, c, t, ce in g.components(ent):
        if t in COMP_HEALTH and ce:
            ho, mo = COMP_HEALTH[t]
            mx = g.i32(ce + mo)
            if mx and mx > 0 and g.i32(ce + ho) != mx:
                g.put(ce + ho, "<i", mx, "component %d type %d health" % (i, t))


def set_slot_ammo(g, slot, value):
    inst = WEAP_TABLE + slot * WEAP_STRIDE
    if not g.u32(inst + 4):
        print("  weapon slot %d is empty" % slot)
        return False
    return g.put(inst + WEAP_AMMO, "<i", value, "weapon slot %d ammo" % slot)


def stop_car(g, ent):
    g.wr(ent + 0xbc, struct.pack("<3f", 0, 0, 0))
    for off, nm in ((0xbc, "velocity x"), (0xc0, "velocity y"), (0xc4, "velocity z"), (0xc8, "pitch rate"), (0xcc, "yaw rate"), (0xd0, "roll rate")):
        g.put(ent + off, "<f", 0.0, nm)


def process_alive(g):
    """GetExitCodeProcess works with the QUERY_INFORMATION right Game opens with (WaitForSingleObject would need SYNCHRONIZE)"""
    code = ctypes.c_ulong(0)
    return bool(k32.GetExitCodeProcess(g.h, ctypes.byref(code))) and code.value == 259     # STILL_ACTIVE


# ---------------------------------------------------------------- the window

def build_gui():
    import tkinter as tk
    from tkinter import ttk, scrolledtext

    class TrainerGui(tk.Tk):
        def __init__(self, allow_any):
            super().__init__()
            self.title("Interstate '76 trainer")
            self.ctl_h = CtlHeader(TRN_H)
            self.tel_h = Header(TEL_H)
            self.MAGIC, self.VERSION = self.ctl_h.consts["I76TRN_MAGIC"], self.ctl_h.consts["I76TRN_VERSION"]
            self.F = {k[len("I76TRN_F_"):]: v for k, v in self.ctl_h.consts.items() if k.startswith("I76TRN_F_")}
            self.CMD = {k[len("I76TRN_CMD_"):]: v for k, v in self.ctl_h.consts.items() if k.startswith("I76TRN_CMD_")}
            self.ctl = Block(self.ctl_h, "i76trn_ctl_t", self.ctl_h.consts["I76TRN_SHM_NAME"])
            self.tel = Telemetry(self.tel_h)
            self.game, self.pid, self.path = None, None, None
            self.attach_error, self.next_attach = "", 0.0
            self.mode = "none"                                 # none / proxy / direct
            self.hb = collections.deque(maxlen=40)             # (time, heartbeat) at each observed change
            self.hb_changed_at = None                          # when the heartbeat was last seen to move
            self.live_pid = None                               # the attached pid the block was last seen live for
            self.pending = None                                # (req_seq, sent_at, label)
            self.direct_saved = {}                             # play-flag bit -> value before the direct hold forced it
            self.freeze_armed = False
            self.slots = []
            self.waypoints = self.load_waypoints()
            self.build(allow_any)
            self.protocol("WM_DELETE_WINDOW", self.on_close)
            self.log("i76trn.h: %s %d bytes (proxy block), i76tel.h: frame %d bytes, shm %d bytes" % (
                "i76trn_ctl_t", self.ctl.size, self.tel_h.frame_size, self.tel.size))
            self.after(100, self.tick)
            self.after(200, self.direct_tick)

        # ------------------------------------------------ layout
        def build(self, allow_any):
            self.columnconfigure(0, weight=1)
            self.columnconfigure(1, weight=0)
            top = ttk.Frame(self, padding=6)
            top.grid(row=0, column=0, columnspan=2, sticky="ew")
            self.var_any = tk.BooleanVar(value=allow_any)
            ttk.Button(top, text="Attach", command=self.attach).pack(side="left")
            ttk.Checkbutton(top, text="allow non-sandbox game (the daily driver - read AGENTS.md first)", variable=self.var_any,
                            command=self.on_any_change).pack(side="left", padx=8)
            self.var_attach = tk.StringVar(value="not attached")
            ttk.Label(top, textvariable=self.var_attach).pack(side="left", padx=8)
            ttk.Label(self, text="sandbox: %s" % SANDBOX, padding=(6, 0)).grid(row=1, column=0, columnspan=2, sticky="w")

            status = ttk.LabelFrame(self, text="Status (10 Hz)", padding=6)
            status.grid(row=2, column=0, sticky="nsew", padx=6, pady=4)
            self.status_text = tk.Text(status, width=92, height=15, font=("Consolas", 9), state="disabled", wrap="none")
            self.status_text.pack(fill="both", expand=True)

            right = ttk.Frame(self)
            right.grid(row=2, column=1, rowspan=2, sticky="n", padx=6, pady=4)

            holds = ttk.LabelFrame(right, text="Holds (flags, held every frame)", padding=6)
            holds.pack(fill="x")
            self.var_flag = {}
            for name, text in (("GOD", "God mode (armour, chassis, components, flats; play bits 0x18)"),
                               ("AMMO", "Unlimited ammo (play bit 0x04 + every slot 0x0fffffff)"),
                               ("NOFLATS", "No flats (wheel flag +0x44 cleared, radius restored)"),
                               ("COMPONENTS", "Components invulnerable (engine / susp / brakes / wheels / weapons at max)"),
                               ("FREEZE_POS", "Freeze position (held at the teleport x y z, zero velocity)")):
                v = tk.BooleanVar(value=False)
                self.var_flag[name] = v
                ttk.Checkbutton(holds, text=text, variable=v, command=self.on_flags_change).pack(anchor="w")

            shots = ttk.LabelFrame(right, text="One-shots", padding=6)
            shots.pack(fill="x", pady=4)
            row = ttk.Frame(shots); row.pack(fill="x")
            ttk.Button(row, text="Repair now", command=self.do_repair).pack(side="left")
            ttk.Button(row, text="Stop car", command=self.do_stop).pack(side="left", padx=4)
            row = ttk.Frame(shots); row.pack(fill="x", pady=2)
            ttk.Button(row, text="Refill ammo (all slots)", command=self.do_ammo).pack(side="left")
            self.var_ammo = tk.StringVar(value="unlimited")
            ttk.Entry(row, textvariable=self.var_ammo, width=12).pack(side="left", padx=4)
            row = ttk.Frame(shots); row.pack(fill="x", pady=2)
            ttk.Label(row, text="slot").pack(side="left")
            self.var_slot = tk.StringVar()
            self.slot_box = ttk.Combobox(row, textvariable=self.var_slot, width=22, state="readonly", values=[])
            self.slot_box.pack(side="left", padx=4)
            self.var_slot_ammo = tk.StringVar(value="unlimited")
            ttk.Entry(row, textvariable=self.var_slot_ammo, width=10).pack(side="left")
            ttk.Button(row, text="Set slot ammo", command=self.do_slot_ammo).pack(side="left", padx=4)

            tele = ttk.LabelFrame(right, text="Teleport (x, y up, z - keep y above the ground)", padding=6)
            tele.pack(fill="x", pady=4)
            row = ttk.Frame(tele); row.pack(fill="x")
            self.var_xyz = [tk.StringVar(value="0") for _ in range(3)]
            for v in self.var_xyz:
                ttk.Entry(row, textvariable=v, width=10).pack(side="left", padx=2)
            ttk.Button(row, text="Use current", command=self.use_current).pack(side="left", padx=4)
            ttk.Button(row, text="Teleport", command=self.do_teleport).pack(side="left")
            self.var_wp = []
            for i in range(3):
                row = ttk.Frame(tele); row.pack(fill="x", pady=1)
                ttk.Label(row, text="waypoint %d" % (i + 1)).pack(side="left")
                v = tk.StringVar(value=self.wp_text(i))
                self.var_wp.append(v)
                ttk.Label(row, textvariable=v, width=34).pack(side="left", padx=4)
                ttk.Button(row, text="Save here", command=lambda i=i: self.wp_save(i)).pack(side="left")
                ttk.Button(row, text="Go", command=lambda i=i: self.wp_go(i)).pack(side="left", padx=2)

            play = ttk.LabelFrame(right, text="Play Options bits 0x654b98 (the game's own switches; offline only)", padding=6)
            play.pack(fill="x", pady=4)
            row = ttk.Frame(play); row.pack(fill="x")
            self.var_play = {}
            for name, bit in PLAY_BITS:
                v = tk.BooleanVar(value=False)
                self.var_play[bit] = v
                ttk.Checkbutton(row, text="%s 0x%02x" % (name, bit), variable=v).pack(side="left", padx=2)
            row = ttk.Frame(play); row.pack(fill="x", pady=2)
            ttk.Button(row, text="Set ticked bits", command=lambda: self.do_playflags(True)).pack(side="left")
            ttk.Button(row, text="Clear ticked bits", command=lambda: self.do_playflags(False)).pack(side="left", padx=4)
            ttk.Label(play, text="Poking these does not set the 'cheats used' marker 0x535f78; the menus do.", wraplength=380).pack(anchor="w")

            logf = ttk.LabelFrame(self, text="Log (every direct write is read back)", padding=6)
            logf.grid(row=3, column=0, sticky="nsew", padx=6, pady=4)
            self.rowconfigure(3, weight=1)
            self.log_text = scrolledtext.ScrolledText(logf, width=92, height=12, font=("Consolas", 9), state="disabled")
            self.log_text.pack(fill="both", expand=True)

        # ------------------------------------------------ logging
        def log(self, text):
            self.log_text.configure(state="normal")
            for line in text.rstrip("\n").splitlines():
                self.log_text.insert("end", time.strftime("%H:%M:%S ") + line + "\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")

        def set_status(self, text):
            self.status_text.configure(state="normal")
            self.status_text.delete("1.0", "end")
            self.status_text.insert("end", text)
            self.status_text.configure(state="disabled")

        # ------------------------------------------------ attach / mode
        def on_any_change(self):
            self.next_attach, self.attach_error = 0.0, ""
            if self.game:
                self.detach("re-checking the game path")

        def attach(self):
            if self.game:
                self.detach("re-attaching")
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    self.pid, self.path = i76trainer.find_game(self.var_any.get())
                    self.game = i76trainer.Game(self.pid)
            except SystemExit as e:
                self.game, self.attach_error = None, str(e)
                self.var_attach.set(self.attach_error)
                return False
            self.attach_error, self.live_pid, self.hb_changed_at = "", None, None
            self.hb.clear()
            self.var_attach.set("pid %d  %s" % (self.pid, self.path))
            self.log("attached to %s (pid %d)%s" % (self.path, self.pid,
                     "" if os.path.normcase(os.path.dirname(self.path)) == SANDBOX else "   NOT THE SANDBOX"))
            self.slots = []
            return True

        def detach(self, why):
            if self.game:
                self.release_direct()
                k32.CloseHandle(self.game.h)
                self.log("detached (%s)" % why)
            self.game = self.pid = self.path = None
            self.var_attach.set("not attached")

        def proxy_state(self):
            """('live' | 'paused' | 'pending' | 'stale' | 'mismatch' | 'absent', detail). Present = magic AND the heartbeat
            advanced within STALE_AFTER; 'paused' is a stall of a block seen live for the attached, still-running pid;
            'pending' is a block seen for less than STALE_AFTER (no verdict yet)."""
            if self.ctl.get("magic") != self.MAGIC:
                return "absent", "no proxy block (magic 0x%08x)" % self.ctl.get("magic")
            ver, size = self.ctl.get("version"), self.ctl.get("size")
            if ver != self.VERSION or size != self.ctl.size:
                return "mismatch", "proxy block version %d size %d, i76trn.h says %d / %d - not driving it" % (ver, size, self.VERSION, self.ctl.size)
            now, hb = time.time(), self.ctl.get("heartbeat")
            if not self.hb:
                self.hb.append((now, hb))                         # first sight of a value is not an advance
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
            # the proxy block is session-global: without a passed attach (the sandbox gate) it is not driven,
            # and a stale block (left over from a dead game) is never driven
            new = "none" if not self.game else ("proxy" if pstate in ("live", "paused") else ("none" if pstate == "pending" else "direct"))
            if new != self.mode:
                if self.mode == "proxy":
                    self.ctl.set("flags", 0)
                if self.mode == "direct":
                    self.release_direct()
                self.mode = new
                self.log("mode: %s" % {"proxy": "proxy (the game thread applies the flags and commands)",
                                       "direct": "DIRECT POKES - fallback: no proxy block; WriteProcessMemory re-asserted at 5 Hz, "
                                                 "a write inside the render window is undone once by I76_RENDER_INTERP",
                                       "none": "none (not attached)"}[new])
                for v in self.var_flag.values():
                    v.set(False)
                self.freeze_armed = False
                if new == "proxy":
                    self.ctl.set("flags", 0)

        # ------------------------------------------------ the 10 Hz tick
        def tick(self):
            try:
                self.tick_body()
            except Exception as e:                           # the window must outlive a torn read or a vanished process
                self.log("tick error: %r" % e)
            self.after(100, self.tick)

        def tick_body(self):
            now = time.time()
            if self.game and not process_alive(self.game):
                self.detach("the game exited")
            if not self.game and now >= self.next_attach and not self.attach_error.startswith("refusing"):
                self.attach()
                self.next_attach = now + 2.0
            pstate, pdetail = self.proxy_state()
            self.choose_mode(pstate)
            self.check_ack()
            fr = self.tel.poll()
            tel_live = self.tel.live()
            st = status_from_frame(fr) if tel_live else (read_status_direct(self.game) if self.game else {"present": False})
            if self.game and st["present"]:
                slots = weapon_slots(self.game)
                if slots != self.slots:
                    self.slots = slots
                    self.slot_box["values"] = ["%d: %s (%s)" % (s, n, "unlimited" if a == UNLIMITED else a) for s, n, a in slots]
                    if slots and (not self.var_slot.get() or not self.var_slot.get().split(":")[0].isdigit()):
                        self.slot_box.current(0)
            self.set_status(self.status_lines(st, pstate, pdetail, tel_live, fr))

        def status_lines(self, st, pstate, pdetail, tel_live, fr):
            L = []
            L.append("mode     %-8s %s%s" % (self.mode, pdetail, "   (not attached: the block is not driven)" if pstate != "absent" and not self.game else ""))
            if pstate in ("live", "paused"):
                L.append("proxy    applied 0x%04x  player_present %d  faults %d  last cmd %s  msg: %s" % (
                    self.ctl.get("applied"), self.ctl.get("player_present"), self.ctl.get("faults"),
                    CMD_RESULT.get(self.ctl.get("cmd_result"), str(self.ctl.get("cmd_result"))), self.ctl.get("msg") or "-"))
            L.append("source   %s" % ("telemetry %s (seq %d, frame %d, sim dt %.1f ms)" % (self.tel.tagname, self.tel.last_seq, fr["frame"], fr["sim_dt"] * 1000.0)
                                       if tel_live else ("direct reads (telemetry %s)" % ("stale: seq %d not advancing" % self.tel.last_seq if self.tel.last_seq else "off")
                                                         if self.game else "nothing attached")))
            g = self.game
            if g:
                pf = self.ctl.get("play_flags_now") if pstate == "live" else g.u32(PLAY_FLAGS)
                marker = g.u32(CHEAT_MARKER)
                names = ", ".join(n for n, b in PLAY_BITS if pf is not None and pf & b) or "none"
                L.append("play     0x%02x: %-36s cheats-used marker 0x535f78 = %s (menus set it; pokes do not)" % (
                    pf or 0, names, "?" if marker is None else marker))
            if not st["present"]:
                L.append("player   absent (menu, loading, or no mission)")
                return "\n".join(L)
            x, y, z = st["pos"]
            L.append("player   present   pos %9.1f %8.1f %9.1f   speed %5.1f m/s (%3.0f km/h)" % (x, y, z, st["speed"], st["speed"] * 3.6))
            for key in ("armour", "chassis"):
                sides = "  ".join("%s %d/%d" % (n, c if c is not None else -1, m if m is not None else -1) for n, c, m in zip(("F", "L", "R", "B"), st[key], st[key + "_max"]))
                hud = st.get(key + "_hud")
                L.append("%-8s %s%s" % (key, sides, "   hud %s side4 %s" % (" ".join(str(v) for v in hud[:4]), hud[4]) if hud else ""))
            L.append("engine   %s/%s   susp %s/%s   brake %s/%s" % (st["engine"] + st["susp"] + st["brake"]))
            L.append("wheels   " + "  ".join("%s %s" % (n, ("FLAT" if fl else "%d/%d" % (hp, mx)) if pr else "-") for n, (pr, fl, hp, mx) in zip(WHEEL_NAMES, st["wheels"])))
            if st["weapon_name"] is not None:
                a = st["weapon_ammo"]
                L.append("weapon   %-10s ammo %s" % (st["weapon_name"], "unlimited" if a == UNLIMITED else a))
            else:
                L.append("weapon   (selected weapon needs telemetry; the slot list below is live)")
            if self.slots:
                L.append("slots    " + "  ".join("%d:%s=%s" % (s, n, "inf" if a == UNLIMITED else a) for s, n, a in self.slots))
            return "\n".join(L)

        # ------------------------------------------------ holds
        def flags_word(self):
            return sum(self.F[n] for n, v in self.var_flag.items() if v.get())

        def on_flags_change(self):
            if self.var_flag["FREEZE_POS"].get() and not self.freeze_armed:
                p = self.current_pos()                           # freeze where the car IS, never at whatever the entries hold
                if not p:
                    self.var_flag["FREEZE_POS"].set(False)
                    self.log("freeze: no player position to hold")
                else:
                    for v, c in zip(self.var_xyz, p):
                        v.set("%.2f" % c)
                    self.log("freeze: holding (%.1f, %.1f, %.1f)" % tuple(p))
            self.freeze_armed = self.var_flag["FREEZE_POS"].get()
            word = self.flags_word()
            if self.mode == "proxy":
                if self.freeze_armed:
                    self.ctl.set("pos", self.xyz())
                self.ctl.set("flags", word)
                self.log("flags -> 0x%04x (%s)" % (word, ", ".join(n for n, v in self.var_flag.items() if v.get()) or "none"))
            elif self.mode == "direct":
                self.direct_apply_play_bits()
                self.log("direct hold flags -> 0x%04x (re-asserted at 5 Hz)" % word)
            else:
                for v in self.var_flag.values():
                    v.set(False)
                self.log("not attached: nothing to hold")

        def direct_apply_play_bits(self):
            """direct mode: force the play bits the proxy would force (0x18 for god, 0x04 for ammo), remembering what they were"""
            g = self.game
            cur = g.u32(PLAY_FLAGS)
            if cur is None:
                return
            want = cur
            for flag, bits in (("GOD", 0x18), ("AMMO", 0x04)):
                if self.var_flag[flag].get():
                    for b in (0x04, 0x08, 0x10):
                        if bits & b and b not in self.direct_saved:
                            self.direct_saved[b] = cur & b
                    want |= bits
                else:
                    for b in (0x04, 0x08, 0x10):
                        if bits & b and b in self.direct_saved and not any(self.var_flag[o].get() and ob & b for o, ob in (("GOD", 0x18), ("AMMO", 0x04))):
                            want = (want & ~b) | self.direct_saved.pop(b)
            if want != cur:
                self.log(capture(g.put, PLAY_FLAGS, "<I", want, "options_play_flags")[1])

        def release_direct(self):
            if self.game and self.direct_saved:
                cur = self.game.u32(PLAY_FLAGS)
                if cur is not None:
                    want = cur
                    for b, v in self.direct_saved.items():
                        want = (want & ~b) | v
                    if want != cur:
                        self.log(capture(self.game.put, PLAY_FLAGS, "<I", want, "options_play_flags (restored)")[1])
            self.direct_saved = {}

        def direct_tick(self):
            try:
                if self.mode == "direct" and self.game and self.flags_word():
                    self.direct_hold()
            except Exception as e:
                self.log("direct hold error: %r" % e)
            self.after(200, self.direct_tick)

        def direct_hold(self):
            g = self.game
            p = player_or_none(g)
            if not p:
                return                                          # never write without a player
            obj, ent = p
            out = []
            if self.var_flag["GOD"].get():
                out.append(capture(i76trainer.cmd_repair, g)[1])
            else:
                if self.var_flag["NOFLATS"].get():
                    out.append(capture(fix_flats, g, ent)[1])
                if self.var_flag["COMPONENTS"].get():
                    out.append(capture(fix_components, g, ent)[1])
            if self.var_flag["AMMO"].get():
                out.append(capture(i76trainer.cmd_ammo, g)[1])
            if self.var_flag["FREEZE_POS"].get():
                xyz = self.xyz()
                if xyz:
                    g.wr(obj + 0x40, struct.pack("<3d", *xyz))
                    g.wr(ent + 0xbc, struct.pack("<3f", 0, 0, 0))
                    back = struct.unpack("<3d", g.rd(obj + 0x40, 24) or b"\0" * 24)
                    if any(abs(a - b) > 0.01 for a, b in zip(back, xyz)):
                        out.append("  freeze: position read back (%.1f, %.1f, %.1f), wanted (%.1f, %.1f, %.1f)\n" % (back + tuple(xyz)))
            bad = [ln for o in out for ln in o.splitlines() if "FAILED" in ln or "freeze:" in ln or "no player" in ln]
            if bad:
                self.log("\n".join(bad))

        # ------------------------------------------------ one-shots
        def player_present(self):
            if self.mode == "proxy":
                return self.ctl.get("player_present") == 1 or (self.game and player_or_none(self.game) is not None)
            return bool(self.game and player_or_none(self.game) is not None)

        def guard(self, what):
            if self.mode == "none":
                self.log("%s: not attached" % what); return False
            if not self.player_present():
                self.log("%s: no player vehicle (not in a mission?) - nothing written" % what); return False
            if self.mode == "proxy" and self.pending:
                self.log("%s: a command is still waiting for its ack" % what); return False
            return True

        def send(self, cmd_name, label, **ops):
            """proxy one-shot: operands, cmd, then req_seq; the tick reports the ack"""
            for k, v in ops.items():
                self.ctl.set(k, v)
            self.ctl.set("cmd", self.CMD[cmd_name])
            req = (self.ctl.get("req_seq") + 1) & 0xffffffff or 1
            self.ctl.set("req_seq", req)
            self.pending = (req, time.time(), label)
            self.log("%s: request #%d sent (%s)" % (label, req, cmd_name))

        def check_ack(self):
            if not self.pending:
                return
            req, sent, label = self.pending
            if self.ctl.get("ack_seq") == req:
                self.pending = None
                r = self.ctl.get("cmd_result")
                self.log("%s: ack #%d after %.0f ms - %s%s" % (label, req, (time.time() - sent) * 1000.0,
                                                               CMD_RESULT.get(r, "result %d" % r), ("; " + self.ctl.get("msg")) if self.ctl.get("msg") else ""))
            elif time.time() - sent > ACK_TIMEOUT:
                self.pending = None
                self.log("%s: no ack for #%d within %.0f s (game paused, in a menu, or the proxy is gone); the request stays queued in the block"
                         % (label, req, ACK_TIMEOUT))

        def ammo_value(self, s):
            s = s.strip().lower()
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
                self.log(capture(i76trainer.cmd_repair, self.game)[1])

        def do_stop(self):
            if not self.guard("stop"):
                return
            if self.mode == "proxy":
                self.send("STOP", "stop")
            else:
                obj, ent = player_or_none(self.game)
                self.log(capture(stop_car, self.game, ent)[1])

        def do_ammo(self):
            try:
                v = self.ammo_value(self.var_ammo.get())
            except ValueError as e:
                self.log("ammo: %s" % e); return
            if not self.guard("ammo"):
                return
            if self.mode == "proxy":
                self.send("AMMO", "ammo", ammo_value=v)
            else:
                g = self.game
                if v == UNLIMITED:
                    self.log(capture(i76trainer.cmd_ammo, g)[1])
                else:
                    for s, n, a in weapon_slots(g):
                        self.log(capture(set_slot_ammo, g, s, v)[1])

        def do_slot_ammo(self):
            sel = self.var_slot.get()
            if not sel or not sel.split(":")[0].isdigit():
                self.log("slot ammo: pick a slot"); return
            slot = int(sel.split(":")[0])
            try:
                v = self.ammo_value(self.var_slot_ammo.get())
            except ValueError as e:
                self.log("slot ammo: %s" % e); return
            if not self.guard("slot ammo"):
                return
            if self.mode == "proxy":
                self.send("SLOT_AMMO", "slot %d ammo" % slot, slot_index=slot, ammo_value=v)
            else:
                self.log(capture(set_slot_ammo, self.game, slot, v)[1])

        def xyz(self):
            try:
                return [float(v.get()) for v in self.var_xyz]
            except ValueError:
                self.log("teleport: x y z must be numbers")
                return None

        def current_pos(self):
            fr = self.tel.frame if self.tel.live() else None
            if fr and fr["player_present"]:
                return (fr["pos_0"], fr["pos_1"], fr["pos_2"])
            if self.game:
                st = read_status_direct(self.game)
                if st["present"]:
                    return st["pos"]
            return None

        def use_current(self):
            p = self.current_pos()
            if not p:
                self.log("use current: no player position"); return
            for v, c in zip(self.var_xyz, p):
                v.set("%.2f" % c)

        def do_teleport(self, xyz=None):
            xyz = xyz or self.xyz()
            if not xyz or not self.guard("teleport"):
                return
            for v, c in zip(self.var_xyz, xyz):
                v.set("%.2f" % c)
            if self.mode == "proxy":
                self.send("TELEPORT", "teleport to (%.1f, %.1f, %.1f)" % tuple(xyz), pos=xyz, vel=(0.0, 0.0, 0.0))
            else:
                self.log(capture(i76trainer.cmd_teleport, self.game, [str(c) for c in xyz])[1])

        # ------------------------------------------------ waypoints
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

        def wp_text(self, i):
            w = self.waypoints[i]
            return "(%.1f, %.1f, %.1f)  %s" % (w["x"], w["y"], w["z"], w.get("saved", "")) if w else "- empty -"

        def wp_save(self, i):
            p = self.current_pos()
            if not p:
                self.log("waypoint %d: no player position to save" % (i + 1)); return
            self.waypoints[i] = {"x": p[0], "y": p[1], "z": p[2], "saved": time.strftime("%Y-%m-%d %H:%M")}
            self.save_waypoints()
            self.var_wp[i].set(self.wp_text(i))
            self.log("waypoint %d saved: (%.1f, %.1f, %.1f) -> %s" % (i + 1, p[0], p[1], p[2], WAYPOINTS))

        def wp_go(self, i):
            w = self.waypoints[i]
            if not w:
                self.log("waypoint %d is empty" % (i + 1)); return
            self.do_teleport([w["x"], w["y"], w["z"]])

        # ------------------------------------------------ play options
        def do_playflags(self, on):
            bits = sum(b for b, v in self.var_play.items() if v.get())
            if not bits:
                self.log("play options: tick at least one bit"); return
            if self.mode == "none":
                self.log("play options: not attached"); return
            if self.mode == "proxy":
                if self.pending:
                    self.log("play options: a command is still waiting for its ack"); return
                self.send("PLAYFLAGS", "play options %s 0x%02x" % ("set" if on else "clear", bits),
                          play_set=bits if on else 0, play_clear=0 if on else bits)
            else:
                g = self.game
                f = g.u32(PLAY_FLAGS)
                self.log(capture(g.put, PLAY_FLAGS, "<I", (f | bits) if on else (f & ~bits), "options_play_flags")[1])

        # ------------------------------------------------ shutdown
        def on_close(self):
            try:
                if self.mode == "proxy" and self.ctl.get("magic") == self.MAGIC:
                    self.ctl.set("flags", 0)
                self.release_direct()
                if self.game:
                    k32.CloseHandle(self.game.h)
                self.ctl.close(); self.tel.close()
            finally:
                self.destroy()

    return TrainerGui


# ---------------------------------------------------------------- self-test (no game, no window)

def selftest():
    ok = True
    ctl_h, tel_h = CtlHeader(TRN_H), Header(TEL_H)
    for h, sname in ((ctl_h, "i76trn_ctl_t"), (tel_h, "i76tel_frame_t"), (tel_h, "i76tel_shm_t")):
        fields, size = h.structs[sname]
        print("%s: %d bytes" % (sname, size))
        if sname == "i76trn_ctl_t":
            for f in fields:
                print("  %3d %3d  %-9s %s%s" % (f.offset, f.size, f.type, f.name, "[%d]" % f.count if f.count > 1 else ""))
    ctl_size = ctl_h.structs["i76trn_ctl_t"][1]
    print("constants:", ", ".join("%s=%s" % (k, hex(v) if isinstance(v, int) else v) for k, v in ctl_h.consts.items()))
    if ctl_size != 168:                                      # sizeof(i76trn_ctl_t) in the built proxy (its log line says 168 B)
        print("WARNING: i76trn_ctl_t parses as %d bytes, the proxy was built with 168; the GUI refuses a block whose "
              "'size' field differs from the parsed header, so re-check i76trn.h against strlkproxy.c" % ctl_size); ok = False
    if tel_h.frame_size != 628:
        print("WARNING: i76tel_frame_t is %d bytes, expected 628" % tel_h.frame_size); ok = False
    if ctl_h.consts["I76TRN_MAGIC"] != 0x43363749:
        print("WARNING: I76TRN_MAGIC parsed as 0x%x" % ctl_h.consts["I76TRN_MAGIC"]); ok = False

    # the real mappings: open (or create zeroed) and report, never write to them here - a live proxy may own them.
    # Holding them open keeps a dead game's block alive with its last magic, so 'present' needs the counters to move.
    ctl = Block(ctl_h, "i76trn_ctl_t", ctl_h.consts["I76TRN_SHM_NAME"])
    tel = Telemetry(tel_h)
    hb0, seq0 = ctl.get("heartbeat"), struct.unpack_from("<I", tel.m, 0)[0]
    tel.poll(); time.sleep(0.5); tel.poll()
    hb1, seq1 = ctl.get("heartbeat"), struct.unpack_from("<I", tel.m, 0)[0]
    magic_ok = ctl.get("magic") == ctl_h.consts["I76TRN_MAGIC"]
    print("%s: magic 0x%08x, version %d, size %d, heartbeat %d -> %d in 0.5 s: %s" % (
        ctl.tagname, ctl.get("magic"), ctl.get("version"), ctl.get("size"), hb0, hb1,
        "PROXY LIVE" if magic_ok and hb1 != hb0 else ("STALE (magic but no heartbeat: a surviving mapping)" if magic_ok else "no proxy")))
    print("%s: %d bytes mapped, seq %d -> %d: %s" % (tel.tagname, tel.size, seq0, seq1,
                                                       "telemetry live" if seq1 != seq0 and seq1 else ("STALE" if seq1 else "telemetry off")))

    # request round trip on a private block with the same layout (never the game's: a live proxy would run it)
    t = Block(ctl_h, "i76trn_ctl_t", "Local\\I76TrainerSelftest%d" % os.getpid())
    t.set("flags", 0x1f); t.set("cmd", ctl_h.consts["I76TRN_CMD_TELEPORT"]); t.set("slot_index", 3); t.set("ammo_value", UNLIMITED)
    t.set("pos", (1234.5, 67.0, -890.25)); t.set("vel", (0.0, 0.0, 0.0)); t.set("play_set", 0x1c); t.set("play_clear", 0x02)
    t.set("req_seq", t.get("req_seq") + 1); t.set("msg", "selftest")
    raw = bytes(t.m[:t.size])
    back = dict(flags=t.get("flags"), cmd=t.get("cmd"), slot_index=t.get("slot_index"), ammo_value=t.get("ammo_value"),
                pos=t.get("pos"), vel=t.get("vel"), play_set=t.get("play_set"), play_clear=t.get("play_clear"), req_seq=t.get("req_seq"), msg=t.get("msg"))
    print("round trip:", back)
    off = ctl_h.offset
    checks = [back["flags"] == 0x1f, back["cmd"] == 2, back["slot_index"] == 3, back["ammo_value"] == UNLIMITED,
              back["pos"] == (1234.5, 67.0, -890.25), back["play_set"] == 0x1c, back["play_clear"] == 2, back["req_seq"] == 1, back["msg"] == "selftest",
              struct.unpack_from("<3d", raw, off("i76trn_ctl_t", "pos")) == (1234.5, 67.0, -890.25),
              struct.unpack_from("<I", raw, off("i76trn_ctl_t", "req_seq"))[0] == 1,
              raw[off("i76trn_ctl_t", "msg"):off("i76trn_ctl_t", "msg") + 8] == b"selftest"]
    print("round trip %s (%d/%d checks)" % ("ok" if all(checks) else "FAILED", sum(checks), len(checks)))
    ok = ok and all(checks)
    t.close(); ctl.close(); tel.close()
    print("selftest", "ok" if ok else "FAILED")
    return 0 if ok else 1


def main():
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    Gui = build_gui()
    Gui("--any" in sys.argv).mainloop()


if __name__ == "__main__":
    main()
