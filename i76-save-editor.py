#!/usr/bin/env python3
"""Interstate '76 save editor - list bookmarks, browse the garage inventory, swap any
part for any other allowed part, set condition / location / scene, and write saves the
game accepts. Doubles as the library behind i76-calibration-saves.py and tests/.

FORMAT (reconciled 2026-10-02; frame from the shell's own writer, i76shell.dll
Cmp_Write 0x10032980 / dir_WriteAndSave 0x10032f80 - see ../i76-map/shell/SAVE.md and
shell/work/cmp-layout.md - and checked byte-exact on every save*.cmp / .spc on this
machine: 27 files, 1676 records, 100 % formula matches, 100 % round-trips).

  saveNNN.cmp  (also reconfig.spc and trip4.spc: same writer, same layout)
    0x000  GarageRec, 0x8c4 bytes, written verbatim from the shell's slot record:
             +0x000 char[20] car name          ("Picard Piranha")
             +0x014 char[20] variant           ("Stock (Orange)" - LOAD-list text, display only)
             +0x028 char[16] id                ("doarmel")
             +0x03c u32      registry count    (Mr. Damage panel slots: 12..14 seen)
             +0x040 32-byte registry records   {u32 slot type, char[16] name, u32 x, u32 y, u32 0}
                                               (the damage panel: WHL FR (408,119) etc. - verified)
             +0x400 char[14][30] EQUIPPED names: engine, susp, brakes, tires FR/FL/RR/RL,
                    weapons x4 in hardpoint order (Piranha: dropper, top1, top2, rear),
                    specials x3.  An empty hardpoint is the literal string "Empty".
             +0x7fc u32[8]   ARMOR in tenths: armor F/R/L/Rear then chassis F/R/L/Rear
                    (verified against the in-game DEFENSE panel)
             +0x820 char[13] vdf ("vppirnha.vdf"), +0x82d char[13] vtf = the PAINT
                    ("piranha1.vtf"; 2/3/4 = the other factory schemes; swapping it repaints
                    the car - sandbox-verified 2026-10-02),
                    +0x83a/+0x847/+0x854 char[13] wheel wdf front/mid/rear
             +0x864 13 x u32 slot classes, +0x898 .. +0x8c4 misc (two floats, zeros; opaque)
    0x8c4  u32 nA
    0x8c8  nA x 116-byte records = SECTION A, the inventory ring. Each record is
           PartNode (0x20) followed by PartRec (0x54):
             +0x00 u32[3]   runtime pointers (rec*, next, prev) - garbage, rewritten on load
             +0x0c u32      CONDITION (hit points; full value is PartRec +0x4c below)
             +0x10 u32      STATE: 1 = mounted on the car (exactly one record per non-Empty
                            equipped name - 21/21 game-written saves), 2 = in the van (V),
                            3 = queued for repair (R), 4 = dropped = Field Salvage (S; trip4.spc
                            loading discards these). 2 and 4 sandbox-verified 2026-10-02.
                            Colour = floor(3*cond/full): 0 red, 1 yellow, 2 green, 3 unmarked
                            (sandbox-measured). The garage's car/van/bench WEAPONS list keeps only
                            the first 11 type-7/8 state-1/2/3 records in FILE order; later ones
                            become state 4 and a mounted one past the cap reads EMPTY on its
                            hardpoint (WEAPON_CAP / LIST_ALLOC below; loadout_warnings()).
             +0x14 12 bytes runtime leftovers (never read by the game; often the slot type)
             +0x20 char[30] display name           +0x3e u32 type (2 engine, 3 susp, 4 brakes,
                            5 wheel, 7 gun, 8 dropper, 13 special)
             +0x42 u32      0, or 11 on game-rewritten turret-class guns (opaque)
             +0x46 8 bytes  0                      +0x4e char[13] class id ("eng01","slg02"; "" specials)
             +0x5b char[13] def file ("gmmedium.gdf", "eng02", "spc05")
             +0x68 u32      0..3 (opaque)          +0x6c u32 FULL condition (= the def's maxHP)
             +0x70 f32      weight (= the def's weight)
    then   u32 nC
    then   nC x 116-byte records = SECTION C, the repair queue: byte copies of the
           section-A records whose state is 3 (the reader resolves each one back to a ring
           node by condition + state 3 + def file; order is the bench order, not A's)
    size == 0x8c4 + 8 + 116 * (nA + nC), exactly. No trailer, no padding, no truncation.

    What the 2026-07 model got wrong, and why: it framed records PartRec-first (name at +0),
    i.e. 32 bytes late, so every record's "cond/loc" (+96/+100) were really the NEXT record's
    node, the last record of each section looked "truncated" / "shifted by the count dword",
    and every cond/loc edit landed one record down. All July colour/location experiments
    edited the wrong record and must be re-run (docs/records/SAVE-EDITOR-STATUS-2026-10-02.md).

  savegame.dir
    u32 count, then count x 60-byte records at 4 + 60k:
      +0  u32 scene  (state 8 = saved in the garage: loads this scene as written;
                      state 1 = saved after a mission: plays scene+1 - sandbox-verified 2026-10-01)
      +4  char[32] display name (blank is legal: the LOAD board shows "SCENE N.")
      +36 char[16] file ("save006" - the reader opens "%s.cmp"; a record whose file does
                      not open is silently dropped from the board)
      +52 u32 state (the shell's entry state: 1 or 8)      +56 u32 flags (0)
    size == 4 + 60 * count, exactly. The old "0x28 header / 36 bytes short / truncated last
    entry" model read each record's scene from the record after it; the launchers' zero
    slack is harmless (the reader stops at count) and this module preserves any slack it
    finds, never shrinks a directory, and pads a short one.

Catalog sources: g*/t*.gdf (44 weapons), wauto_*.wdf (wheels: 4 designs x car-size family
digit), compnent.cdf (engines/susp/brakes), specials spc01..spc09 from the exe string table
(spc02 NitrousOxide, spc04 X-Aust, spc05 Structo, spc06 Curb Feelers, spc07 Mud Flaps,
spc08 Heated Seats, spc09 Cup Holders seen in saves; spc01 prints as "Radar Jammer" in the garage
(sandbox 2026-10-02); every pair is also code-verified: the exe builds the def as sprintf("spc%02d", type),
0x4b1502, i76-map engine.md). What each part does: PARTS_INFO below and docs/PARTS-REFERENCE.md.
Caps (sandbox 2026-10-02): the repair bench has none (15 queued jobs all listed, scrolling); the
van holds >= 5 suspensions; only the weapon list's 11 is a real cap. The inventory dialog's columns
are height-limited (ENGINES 4 rows, WEAPONS 11, WHEELS 12) - display, not storage.

Usage:
  i76-save-editor.py                      interactive (auto-finds the Mac wrapper saves)
  i76-save-editor.py --dir DIR            operate on saves in DIR (e.g. the repo saves/)
  i76-save-editor.py --dir DIR --list     list bookmarks (scene, state, name, car, counts)
  i76-save-editor.py --dir DIR --dump N   dump slot N (index in --list order, or "save006")
  i76-save-editor.py --dir DIR --check    validate every file against the writer's frame
  i76-save-editor.py --json FILE...       machine-readable dump (tests/ compare it to the HTML parser)
  i76-save-editor.py --parts              what every part does, with sources (docs/PARTS-REFERENCE.md)

Every modified file gets a one-time <name>.pre-edit backup plus a timestamped .bak-<ts>
copy next to it, and is read back after the write.
"""
import argparse, datetime, glob, json, os, re, shutil, struct, sys

# ---------------------------------------------------------------- frame constants
HDR_LEN  = 0x8c4          # GarageRec
REC_LEN  = 0x74           # PartNode 0x20 + PartRec 0x54
# PartNode
N_PTR, N_COND, N_STATE, N_LEFT = 0x00, 0x0c, 0x10, 0x14
# PartRec (offsets within the 116-byte record)
R_NAME, R_TYPE, R_U22, R_CLS, R_DFL, R_U48, R_FULL, R_WT = 0x20, 0x3e, 0x42, 0x4e, 0x5b, 0x68, 0x6c, 0x70
# GarageRec
G_CAR, G_VARIANT, G_ID, G_REGCOUNT, G_REG = 0, 20, 40, 60, 64
G_EQ, G_EQ_N, G_EQ_LEN = 0x400, 14, 30
G_ARMOR, G_VDF, G_VTF, G_WDF = 0x7fc, 0x820, 0x82d, (0x83a, 0x847, 0x854)
# savegame.dir
DIR_HDR, DIR_REC = 4, 60
D_SCENE, D_NAME, D_FILE, D_STATE, D_FLAGS = 0, 4, 36, 52, 56

STATE_BADGE = {1: "C", 2: "V", 3: "R", 4: "S"}
STATE_LABEL = {1: "(C) mounted on the car", 2: "(V) in the van",
               3: "(R) queued for repair", 4: "(S) field salvage"}
# condition colour, sandbox-measured 2026-10-02 (CAL COLOR): level = floor(3 * cond / full);
# 0 red, 1 yellow, 2 green, 3 (= 100 %) unmarked; specials (full 0) unmarked.
LEVEL_NAMES = {0: "red", 1: "yellow", 2: "green", 3: "none"}
# The garage's (C)+(V)+(R) WEAPONS list keeps at most 11 type-7/8 records with state != 4, in FILE
# order (Inventory_ClassifyParts 0x10019945: `cmp [list+4], 0xb`); the 12th and later are set to
# state 4 and show in Field Salvage - a mounted one past the cap reads EMPTY on its hardpoint
# (sandbox-verified 2026-10-02, CAL COLOR / CAL V VS S). The other lists have no count check:
# List_Insert (0x10027970) never tests capacity, so more records than Inventory_BuildLists
# allocated (List_New sizes below, 0x10019a82..0x10019b78) overflow the heap. Observed maxima in
# game-written saves: engines 3, suspensions 4, brakes 5, wheels 11, specials 9.
WEAPON_CAP = 11
LIST_ALLOC = {2: 4, 3: 6, 4: 6, 5: 32, 7: 32, 13: 10}   # per type; 8 (droppers) shares the weapon list
PLURAL = {2: "engines", 3: "suspensions", 4: "brakes", 5: "wheels", 7: "weapons", 13: "specials"}
TYPE_NAMES = {2: "engine", 3: "suspension", 4: "brakes", 5: "wheel", 7: "weapon", 8: "weapon", 13: "special"}
EQ_SLOTS = ["Engine", "Suspension", "Brakes", "Tire FR", "Tire FL", "Tire RR", "Tire RL",
            "Weapon 1", "Weapon 2", "Weapon 3", "Weapon 4", "Special 1", "Special 2", "Special 3"]
ARMOR_LABELS = ["front armor", "right armor", "left armor", "rear armor",
                "front chassis", "right chassis", "left chassis", "rear chassis"]
# field-solved 2026-07-14 (two builds): total = chassis + mounted parts + 1 lb per armor point
CHASSIS_LBS, ARMOR_LBS_PER_POINT = 2910.0, 1.0

class FormatError(ValueError):
    pass

# ---------------------------------------------------------------- catalog
# (name, class_id, def_file, type, maxdur, weight)  [weights f32]
ENGINES = [
    ("261ci  6 cyl", "eng01", "eng01", 2, 300, 200.0),
    ("305ci  V-8",   "eng02", "eng02", 2, 300, 230.0),
    ("432ci  SHO V8","eng03", "eng03", 2, 300, 275.0),
    ("595ci  V-10",  "eng04", "eng04", 2, 300, 340.0),
]
SUSPENSIONS = [
    ("Stock",        "sus01", "sus01", 3, 200, 35.0),
    ("Sway Bars",    "sus02", "sus02", 3, 200, 37.0),
    ("Coil Overs",   "sus03", "sus03", 3, 200, 41.0),
    ("EtherX Rally", "sus04", "sus04", 3, 200, 46.0),
]
BRAKES = [
    ("4-Wheel Drum", "bra01", "bra01", 4, 150, 12.0),
    ("Disc & Drum",  "bra02", "bra02", 4, 150, 15.0),
    ("4-Wheel Disc", "bra03", "bra03", 4, 150, 17.0),
    ("Aircraft Brk", "bra04", "bra04", 4, 150, 20.0),
]
# wheels: def = wauto_<family><design>.wdf ; the family digit is the CAR's tire size class -
# keep the save's own family digit when swapping, only change the design letter.
WHEEL_DESIGNS = [("a", "13in Stock"), ("b", "14in Rally"), ("c", "15in Kragers"), ("d", "16in Billets")]
WHEEL_DUR, WHEEL_WT = 100, 20.0
# weapons from g*/t*.gdf: (name, mount_class, def, maxdur, weight)
WEAPONS = [
    ("30cal MG",        "slg01", "gmlight.gdf",  200,  32.0),
    ("50cal MG",        "slg02", "gmmedium.gdf", 400,  47.0),
    ("7.62mm MG",       "slg03", "gmheavy.gdf",  600,  91.0),
    ("20mm Cannon",     "slg04", "gclight.gdf",  200,  69.0),
    ("25mm Cannon",     "slg05", "gcmedium.gdf", 400,  89.0),
    ("30mm Cannon",     "slg06", "gcheavy.gdf",  600, 150.0),
    ("Tank Cannon",     "slg06", "gtktank.gdf",  900, 170.0),
    ("Police Tank Cann","slg06", "gtptank.gdf",  900, 170.0),
    ("HADES Cannon",    "slg07", "gchades.gdf",  600, 150.0),
    ("FireRite Rkt",    "spp01", "gdumb.gdf",    200,  94.0),
    ("Aim-Nein Msl",    "spp02", "gsheat.gdf",   400, 169.0),
    ("DrRadar Msl",     "spp03", "gsradar.gdf",  600, 208.0),
    ("Cherub Msl",      "spp04", "gscherub.gdf", 650, 217.0),
    ("FlameThrower",    "flm01", "gflight.gdf",  200,  40.0),
    ("Gas Launcher",    "flm02", "gfmedium.gdf", 400,  64.0),
    ("Napalm Hose",     "flm03", "gfheavy.gdf",  600, 102.0),
    ("Pyro-Tomic",      "flm04", "gfpyro.gdf",   600, 120.0),
    ("HE Mortar",       "mor01", "ggrenade.gdf", 200,  70.0),
    ("WP Mortar",       "mor02", "gwhiteph.gdf", 400,  89.0),
    ("Cluster-Bomb",    "mor03", "gcluster.gdf", 600, 109.0),
    ("EZK Mortar",      "mor04", "gezkill.gdf",  650, 123.0),
    ("Oil Slick",       "drp01", "goilslck.gdf", 200,  46.0),
    ("Fire-Dropper",    "drp04", "gfirdrop.gdf", 200,  70.0),
    ("Landmines",       "drp05", "glandmin.gdf", 200,  60.0),
    ("Car-E-Racer",     "drp05", "gceracer.gdf",  20, 169.0),
    ("BloxDropper",     "drp06", "gblox.gdf",    200, 139.0),
    # turret variants
    ("30cal Turret",    "slg01", "tmlight.gdf",  200,  32.0),
    ("50cal Turret",    "slg02", "tmmedium.gdf", 400,  47.0),
    ("7.62 Turret",     "slg03", "tmheavy.gdf",  600,  91.0),
    ("20mm Turret",     "slg04", "tclight.gdf",  200,  69.0),
    ("25mm Turret",     "slg05", "tcmedium.gdf", 400,  89.0),
    ("30mm Turret",     "slg06", "tcheavy.gdf",  600, 150.0),
    ("Howitzer",        "slg06", "tthowitz.gdf", 900, 170.0),
    ("HADES Turret",    "slg07", "tchades.gdf",  600, 150.0),
    ("FireRite Trt",    "spp01", "tdumb.gdf",    200,  94.0),
    ("Aim-Nein Trt",    "spp02", "tsheat.gdf",   400, 169.0),
    ("DrRadar Trt",     "spp03", "tsradar.gdf",  600, 208.0),
    ("Cherub Trt",      "spp04", "tscherub.gdf", 650, 217.0),
    ("Flame Turret",    "flm01", "tflight.gdf",  200,  40.0),
    ("Gas Lnch Trt",    "flm02", "tfmedium.gdf", 400,  64.0),
    ("Napalm Trt",      "flm03", "tfheavy.gdf",  600, 102.0),
    ("Pyro-Turret",     "flm04", "tfpyro.gdf",   600, 120.0),
]
# specials: def "spcNN"; "seen" = the name/def pair occurs in a game-written save
SPECIALS = [
    ("Radar Jammer", "spc01", "verified (garage name; spc%02d code)"),
    ("NitrousOxide", "spc02", "seen"),
    ("Blower",       "spc03", "code-verified (spc%02d)"),
    ("X-Aust Brake", "spc04", "seen"),
    ("Structo Bmpr", "spc05", "seen"),
    ("Curb Feelers", "spc06", "seen"),
    ("Mud Flaps",    "spc07", "seen"),
    ("Heated Seats", "spc08", "seen"),
    ("Cup Holders",  "spc09", "seen"),
]
KNOWN_TYPES = set(TYPE_NAMES)
def weapon_type(mount): return 8 if mount.startswith("drp") else 7

def catalog_weight(name):
    for n, c, d, t, du, w in ENGINES + SUSPENSIONS + BRAKES:
        if n == name: return w
    for n, m, d, du, w in WEAPONS:
        if n == name: return w
    if any(n == name for _, n in WHEEL_DESIGNS): return WHEEL_WT
    return 0.0

# ---------------------------------------------------------------- what each part does in game
# Keyed by def code: eng01.., sus01.., bra01.., wauto_a..wauto_d (the design letter; the family
# digit is the car's size class and changes nothing below), the weapon .gdf, spc01..spc09.
# "short" is the one-line label the listings show; "what" carries the numbers and a source label
# on every claim:
#   [game data]  read from the stock I76.ZFS (md5 6dd57b16..., the lab and the pristine copy are
#                identical; the sandbox ADDON folder overrides none of these files) through
#                i76-map's parsers (data\mod\i76mod.py show zfs:compnent.cdf ENGN#0, ...)
#   [RE: ...]    i76-map's static reading of i76.exe (md5 9a232dcc), doc + address
#   [community]  published player measurements (Local Ditch, docs/WEAPON-STATS.md)
#   [unknown]    nothing found
# i76-save-editor.html embeds the same table as JSON (tests/test_save_editor.py keeps them equal).
# Full table with every source: docs/PARTS-REFERENCE.md.
PARTS_INFO = {}

def _info(key, name, short, what):
    PARTS_INFO[key] = {"name": name, "short": short, "what": what}

_ENG_TAIL = (" Gearing is the same for every engine (fixed exe constants): the rev limiter caps 1st / 2nd / 3rd"
             " at 104 / 182 / 261 km/h and full-throttle upshifts come at 62 / 106 km/h; power peaks at 3500 rpm"
             " [RE: i76-map subsystems/engine.md, ratios 0x4f8640, upshift 0x46a320]. Damage scales power by"
             " hp/max with a floor of 0.4 for the player [RE: engine.md, 0x469fb0]. Your car's component hp is"
             " x4 offline [RE: engine.md, 0x4be1c0]. Top speed per engine: [unknown] (not measured).")
for _k, _n, _p, _m, _raw, _pir in [
        ("eng01", "261ci  6 cyl", 104440, 200, "1.00", "1.00"),
        ("eng02", "305ci  V-8", 138010, 230, "1.32", "1.30"),
        ("eng03", "432ci  SHO V8", 193960, 275, "1.86", "1.79"),
        ("eng04", "595ci  V-10", 290940, 340, "2.79", "2.59")]:
    _info(_k, _n, f"power {_p:,} (" + ("baseline" if _raw == "1.00" else f"{_raw}x the 6 cyl") + ")",
          f"Drive power {_p:,}, 300 hp, {_m} lbs [game data: compnent.cdf ENGN]. Acceleration = power / (mass x speed)"
          f" x throttle, capped by rear-tyre traction [RE: engine.md, 0x43c55e / 0x43c578]: {_raw}x the 261ci's"
          f" power, about {_pir}x its acceleration on the Piranha once the engine's own weight is counted"
          f" (Jade's 1951-unit car) [derived from game data]." + _ENG_TAIL)

_SUS_TAIL = (" The coefficient sets the cornering force the car holds before it breaks into a slide: slide threshold"
             " = 2 x gravity x handling x surface grip x tyre grip x 0.25 (physics_ComputeSteerYawRate 0x43ce10,"
             " used at 0x43d00c for every car) [RE: engine.md; re-read from the exe in this pass]. Your steering"
             " limit itself (7.84 x tyre grip) does not use it [RE: physics.md 0x43cee0]. Damage decays it toward"
             " 0.5 [RE: engine.md]. The 'percent' field only feeds the suspension's own damage check [RE: engine.md]."
             " Spring rate, damping and ride height are not in the file: wheel travel is +-0.25 x wheel radius on"
             " every car [RE: physics.md 0x46d820].")
for _k, _n, _h, _pc, _m in [
        ("sus01", "Stock", "1.00", 0, 35), ("sus02", "Sway Bars", "1.25", 10, 37),
        ("sus03", "Coil Overs", "1.55", 20, 41), ("sus04", "EtherX Rally", "2.00", 45, 46)]:
    _info(_k, _n, "handling 1.00 (baseline)" if _h == "1.00" else f"handling {_h}x: slides later",
          f"Handling coefficient {_h}, percent {_pc}, 200 hp, {_m} lbs [game data: compnent.cdf SUSP]." + _SUS_TAIL)

_BRA_TAIL = (" Offline, this number is ignored: single-player cars get brake strength 2300 / mass whatever"
             " brake is fitted (physics_BrakeSetStrength 0x46a890 replaces it unless the game is networked or"
             " multi-melee, where it multiplies) [RE: engine.md; re-read from the exe in this pass]. Braking ="
             " strength x pedal x 8, capped by four-tyre grip; damage scales it by hp/max, floor 0.2"
             " [RE: engine.md, 0x43c49a / 0x46a7f0]. So in the campaign a better brake only adds weight (and"
             " 2300 / mass makes a heavier car brake slightly weaker); the X-Aust Brake special is the real upgrade.")
for _k, _n, _s, _m in [("bra01", "4-Wheel Drum", "1.0", 12), ("bra02", "Disc & Drum", "1.3", 15),
                       ("bra03", "4-Wheel Disc", "1.6", 17), ("bra04", "Aircraft Brk", "2.0", 20)]:
    _info(_k, _n, f"strength {_s} (ignored offline)",
          f"Brake strength {_s}, 150 hp, {_m} lbs [game data: compnent.cdf BRAK]." + _BRA_TAIL)

_WHL_TAIL = (" Tyre grip sets rear-wheel drive traction, the steering limit (7.84 m/s^2 per unit of grip) and the slide"
             " threshold [RE: physics.md, 0x43c543 / 0x43ce10]. The loader writes the size factor only into the"
             " tyre's current grip (wheel+0xc, 0x4ae8cf); the grip base (+0x10) is 1.0 for every tyre (0x46d795), so"
             " the first hit that damages a tyre resets its grip to hp/max (floor 0.5) and the size bonus is gone"
             " for that tyre until the car is rebuilt [RE: engine.md; re-read from the exe in this pass]. 100 hp,"
             " 10 lbs per wheel in the file [game data: wauto_*.wdf]; a blown tyre's radius drops to x0.688"
             " [RE: engine.md].")
for _l, _n, _g in [("a", "13in Stock", "1.0"), ("b", "14in Rally", "1.2"),
                   ("c", "15in Kragers", "1.4"), ("d", "16in Billets", "1.6")]:
    _info("wauto_" + _l, _n, f"grip {_g}x till the tyre is hit",
          f"Size factor {_g} [game data: WDFC +0x30; every *_N{_l}.wdf in the archive (wauto, wbtck, wctnk, ...) carries the same]." + _WHL_TAIL)

# weapons: what the shot does (numbers from the stock .gdf / ORDF / .xdf; flight models from i76-map
# subsystems/weapons.md, weapon_StepProjectileByType 0x4a0800)
_GUN = ("Straight-line bullets, {speed} m/s, {life} s flight (= {rng} m), bullet damage {dmg} per hit [game data: {gdf}];"
        " flight weapon_StepBullet 0x4abe60 [RE: weapons.md].")
def _gun(gdf, name, short, speed, life, dmg, extra=""):
    _info(gdf, name, short, _GUN.format(speed=speed, life=life, rng=round(speed * life), dmg=dmg, gdf=gdf) + extra)
for _g, _n, _s, _sp, _lf, _d in [
        ("gmlight.gdf", "30cal MG", "bullets, 10/s", 150, 3.33, 15), ("gmmedium.gdf", "50cal MG", "bullets, 10/s", 150, 3.33, 25),
        ("gmheavy.gdf", "7.62mm MG", "bullets, 20/s", 150, 3.33, 24), ("gclight.gdf", "20mm Cannon", "shells, 4/s", 200, 2.5, 45),
        ("gcmedium.gdf", "25mm Cannon", "shells, 3/s", 200, 2.5, 60), ("gcheavy.gdf", "30mm Cannon", "shells, 2/s", 200, 2.5, 150),
        ("gchades.gdf", "HADES Cannon", "shells, 2/s, 165 a hit", 200, 2.5, 165),
        ("tmmedium.gdf", "50cal Turret", "turret bullets, 10/s", 150, 3.33, 25), ("tmheavy.gdf", "7.62 Turret", "turret bullets, 20/s", 150, 3.33, 24),
        ("tclight.gdf", "20mm Turret", "turret shells, 4/s", 200, 2.5, 45), ("tcmedium.gdf", "25mm Turret", "turret shells, 3/s", 200, 2.5, 60),
        ("tcheavy.gdf", "30mm Turret", "turret shells, 2/s", 200, 2.5, 150), ("tchades.gdf", "HADES Turret", "turret shells, 2/s, 165 a hit", 200, 2.5, 165)]:
    _gun(_g, _n, _s, _sp, _lf, _d, " Turret variant: mounts on the turret location [RE: i76-map data/VEHICLES.md, GDFC sub >= 100]." if _g.startswith("t") else "")
_gun("tmlight.gdf", "30cal Turret", "turret bullets, 10/s, fast rounds", 700, 0.714, 15,
     " Unlike the 30cal MG its rounds fly at 700 m/s (same 500 m reach) [game data]. Turret variant [RE: VEHICLES.md].")
for _g, _n in [("gtktank.gdf", "Tank Cannon"), ("gtptank.gdf", "Police Tank Cann")]:
    _gun(_g, _n, "boss gun: 900 m/s shells", 900, 6.67, 260, " One shot a second plus a 2 s pause after each [game data].")
_info("tthowitz.gdf", "Howitzer", "boss mortar: 4 g arc",
      "Mortar shell, 100 m/s at 4 g (ballistic), 120 damage, 1 shot then a 5 s pause, 60 s flight [game data: tthowitz.gdf];"
      " flight weapon_StepMortarShell 0x4ac3d0 [RE: weapons.md].")
_MSL = " Shooter immunity: your own rockets and missiles cannot hit you for the first 70 m [RE: weapons.md]."
for _g, _n in [("gdumb.gdf", "FireRite Rkt"), ("tdumb.gdf", "FireRite Trt")]:
    _info(_g, _n, "unguided rockets, bursts of 3",
          "Unguided rockets: bursts of 3 at 4.5 a second, then a 1 s pause; 450 m/s, 1000 m flight, 120 explosive"
          f" damage a hit [game data: {_g}]; speed eases to 450 m/s (weapon_StepRocket 0x4aa5b0) [RE: weapons.md]." + _MSL)
for _g, _n in [("gsheat.gdf", "Aim-Nein Msl"), ("tsheat.gdf", "Aim-Nein Trt")]:
    _info(_g, _n, "heat seeker: snaps onto the target",
          f"Heat-seeking missile: 220 explosive damage, 450 m/s, 1000 m flight, one every 2 s [game data: {_g}]."
          " It re-acquires a heat target every step and snaps its nose straight at it: no turn limit"
          " (weapon_StepHeatMissile 0x4ab920) [RE: weapons.md]. A radar jammer does not affect it [RE: the jammer"
          " is read only by radar code and the radar missile, engine.md]." + _MSL)
for _g, _n, _sp, _lf in [("gsradar.gdf", "DrRadar Msl", 125, 8.0), ("tsradar.gdf", "DrRadar Trt", 450, 2.22)]:
    _info(_g, _n, "radar-guided, turn-limited; jammable",
          f"Radar-guided missile: 410 explosive damage, {_sp} m/s for {_lf} s (1000 m), one every 5 s [game data: {_g}]."
          " Turns at most 3 / 15 / 20 degrees a step (< 15 / 15-150 / > 150 m flown) and drops a jammed or dead"
          " target (weapon_StepRadarMissile 0x4aa9f0) [RE: weapons.md]." + _MSL)
for _g, _n in [("gscherub.gdf", "Cherub Msl"), ("tscherub.gdf", "Cherub Trt")]:
    _info(_g, _n, "radar-guided, 3200 a hit; jammable",
          f"The DrRadar's guidance (ordnance 8: turn-limited, drops a jammed target) with 3200 explosive damage a hit,"
          f" 450 m/s, 1000 m flight, 3 rounds [game data: {_g}; RE: weapons.md 0x4aa9f0]." + _MSL)
_FLM = (" Not a projectile: an emitter (weapon_FlameEmit 0x443c90) [RE: weapons.md]. Range is the community figure"
        " (time to destroy a bus) [community].")
for _g, _n, _d, _mode in [("gflight.gdf", "FlameThrower", 15, 0), ("tflight.gdf", "Flame Turret", 15, 0),
                          ("gfmedium.gdf", "Gas Launcher", 30, 1), ("tfmedium.gdf", "Gas Lnch Trt", 30, 1),
                          ("gfheavy.gdf", "Napalm Hose", 45, 2), ("tfheavy.gdf", "Napalm Trt", 45, 2),
                          ("gfpyro.gdf", "Pyro-Tomic", 60, 2), ("tfpyro.gdf", "Pyro-Turret", 60, 2)]:
    _info(_g, _n, "fire stream", f"Fire damage {_d} a tick, 20 ticks a second [game data: {_g}], emitter mode {_mode}." + _FLM)
_MORT = " Shooter immunity: 1 s [RE: weapons.md]."
_info("ggrenade.gdf", "HE Mortar", "lobbed shell, blast 95 in 25 m",
      "Lobbed shell: 100 m/s at 4 g, 3 a second, 45 explosive damage on a direct hit plus a blast of 95 within 25 m"
      " (xgren1.xdf) [game data]; weapon_StepMortarShell 0x4ac3d0 [RE: weapons.md]." + _MORT)
_info("gwhiteph.gdf", "WP Mortar", "lobbed shell, explosive + fire, blast 145",
      "Lobbed shell like the HE mortar; its 45 direct damage is split between explosive and fire (mask 6), and the"
      " blast is 145 within 25 m (xwhph1.xdf) [game data; RE: damage split over set bits, i76-map notes 0x4a774d]." + _MORT)
_info("gcluster.gdf", "Cluster-Bomb", "splits into 9-12 bomblets",
      "Mortar flight, then 9-12 bomblets spread +-10 m that go off over 1.8 s (weapon_StepClusterBomb 0x4ace20)"
      " [RE: weapons.md]; 45 damage and a blast of 45 within 20 m each (xclst1.xdf), 2 shells a second [game data]." + _MORT)
_info("gezkill.gdf", "EZK Mortar", "lobbed shell, tight spread",
      "Lobbed shell with twice the HE mortar's flight time (8 s) and a tighter spread (0.01), 25 direct damage plus the"
      " HE blast of 95 within 25 m (xgren1.xdf) [game data: gezkill.gdf]; weapon_StepMortarShell [RE: weapons.md]." + _MORT)
_DROP = " Shooter immunity: 2 s [RE: weapons.md]."
_info("goilslck.gdf", "Oil Slick", "spins out whoever drives over it",
      "Drops oil patches (60 a second, each lasts 20 s) that do no damage [game data: goilslck.gdf]. A car touching one"
      " loses traction for 2 s (weapon_StepOilSlick 0x4aa150, 0x466e80); the timer is shared with nitrous, so oil"
      " during a boost cuts the boost to 2 s [RE: weapons.md, engine.md; the nitrous interaction is a static inference]." + _DROP)
_info("gfirdrop.gdf", "Fire-Dropper", "fire patches on the road",
      "Drops burning patches (60 a second, each lasts 20 s) carrying 15 fire damage [game data: gfirdrop.gdf]; a patch"
      " is a stationary probe that fires an impact every frame a car touches it (weapon_StepFirePatch 0x4aa450)"
      " [RE: weapons.md]." + _DROP)
_info("glandmin.gdf", "Landmines", "mines: 240 + blast, kicks the car",
      "Mines that tumble, settle and wait (1000 s): 240 explosive damage plus a blast of 25 within 5 m (xmine1.xdf),"
      " and they kick the car that hits them (1, 2, 0.75) [game data: glandmin.gdf; RE: weapon_StepTumblingMine"
      " 0x4a92e0, weapons.md]." + _DROP)
_info("gceracer.gdf", "Car-E-Racer", "super-mine: 1200 a hit",
      "The landmine with 1200 explosive damage, 5 rounds, and only 20 hp of its own [game data: gceracer.gdf];"
      " same tumbling-mine flight and kick [RE: weapons.md]." + _DROP)
_info("gblox.gdf", "BloxDropper", "blocks: 95 blox damage, small kick",
      "Drops tumbling blocks that settle and wait: 95 damage of the 'blox' type (mask 8), a softer kick (0.5, 0.5, 0.5),"
      " one every 2 s, 10 rounds [game data: gblox.gdf; RE: weapons.md 0x4a92e0]." + _DROP)

_SPC = (" Specials are components with 10 hp (x4 for you offline); damage that destroys one ends its effect"
        " unless noted [RE: engine.md, entity_SpecialCreate 0x4676b0].")
_info("spc01", "Radar Jammer", "8 s invisible to radar, 5 uses (key)",
      "Press its special key: for 8 s your car is hidden from AI radar and the radar display, and radar-guided missiles"
      " (DrRadar, Cherub) drop you as a target; 5 uses, and every press costs one even while already active"
      " (entity_ActivateRadarJammer 0x461770, -8.0 at 0x4be17c) [RE: engine.md]. The heat seeker's code is not among its"
      " readers, so Aim-Nein missiles should ignore it [RE: inferred from the reader list]. Not yet live-tested." + _SPC)
_info("spc02", "NitrousOxide", "x5 drive for 15 s, 3 charges (key)",
      "Press its special key: drive acceleration x5.0 for 15 s, still capped by rear-tyre traction; 3 charges, a second"
      " press restarts the 15 s and costs a charge (physics_FireNitro 0x43d280, 15.0 at 0x43d2a6, x5.0 at 0x4bd1dc;"
      " re-read from the exe in this pass) [RE: engine.md]. The community figure '+50% acceleration, +20% top"
      " speed' [community: docs/I76-GAMEPLAY-REFERENCE.md] does not match the code." + _SPC)
_info("spc03", "Blower", "permanent x1.25 drive",
      "Passive: drive acceleration x1.25 from spawn (+0x128 = 1.25 at 0x438edb, read at 0x43c587; re-read in this pass)"
      " [RE: engine.md]. Set once at spawn, so it keeps working even after it is shot off [RE: engine.md].")
_info("spc04", "X-Aust Brake", "doubles braking (key, stays on)",
      "Press its special key once: brake input x2 for the rest of the car's life, no uses, no hp check (0x44f608 sets"
      " +0xf4; 0x43ab46 doubles a negative pedal; re-read in this pass) [RE: engine.md]. Still capped by four-tyre"
      " grip. This is the only brake upgrade that matters offline (see the brakes).")
_info("spc05", "Structo Bmpr", "front/rear chassis damage halved",
      "Passive: chassis absorb multiplier 2.0 on the front and back: a hit there is absorbed while it is <= chassis x 2"
      " and costs the chassis half as much (entity_ApplyDamage 0x46565b..0x4656ce) [RE: engine.md, damage.md]." + _SPC)
_info("spc06", "Curb Feelers", "armour takes ~9% less (x1.1)",
      "Passive: armour absorb multiplier 1.1 on every side: hits cost the armour damage / 1.1 (0x465772..0x4657d8)"
      " [RE: engine.md, damage.md]." + _SPC)
_info("spc07", "Mud Flaps", "chassis takes ~9% less (+0.1)",
      "Passive: chassis multiplier +0.1 on every side (2.1 front/back with the Structo Bumper): hits cost the chassis"
      " damage / 1.1 (0x4656ef..0x465759, -0.1 at 0x4be208; re-read in this pass) [RE: engine.md, damage.md]." + _SPC)
_info("spc08", "Heated Seats", "+10% ammo on every weapon",
      "Passive: every mounted weapon's ammo x1.1 at spawn (0x438ecb -> 0x4a4a40, 1.1 at 0x4beb20) [RE: engine.md]."
      " Applied once at spawn [RE: engine.md].")
_info("spc09", "Cup Holders", "10% chance a component hit does nothing",
      "Passive: a hit that reaches a component is absorbed whole 10% of the time (entity_DamageComponent, rand()%100 < 10"
      " at 0x465b7e) [RE: engine.md, damage.md]. docs/I76-GAMEPLAY-REFERENCE.md files cup holders among 'minor/flavor items (some"
      " are jokes)' [community]; the code gives them a real effect." + _SPC)

def info_key(typ, dfl, cls=""):
    """PARTS_INFO key for a record: engines/suspensions/brakes by def, wheels by design letter, weapons by .gdf"""
    if typ == 5:     # <family>_<size digit><design letter>.wdf: wauto_1b.wdf, wbtck_1d.wdf (same stats per letter)
        m = re.search(r"_\d([a-d])\.wdf$", dfl.lower())
        return "wauto_" + m.group(1) if m else None
    return dfl or cls or None

def part_info(typ, dfl, cls=""):
    return PARTS_INFO.get(info_key(typ, dfl, cls) or "")

def parts_json():
    """the exact text between the PARTS_INFO markers in i76-save-editor.html"""
    return "const PARTS_INFO=" + json.dumps(PARTS_INFO, ensure_ascii=False, indent=0) + ";"

def info_by_name(name):
    """the PARTS_INFO entry for a display name (equipped slots store only the name)"""
    return next((v for v in PARTS_INFO.values() if v["name"] == name), None)

def does(p):
    """one-line 'what it does' for a Part record ('' when unknown)"""
    i = part_info(p.type, p.dfl, p.cls)
    return i["short"] if i else ""

def print_parts_reference():
    for k, v in PARTS_INFO.items():
        print(f"{k:13} {v['name']:17} {v['short']}")
        print(f"{'':31}{v['what']}")

# ---------------------------------------------------------------- byte helpers
def cstr(b):
    return bytes(b).split(b"\0")[0].decode("latin-1", "replace")

def put_cstr(buf, off, n, s):
    buf[off:off+n] = s.encode("latin-1", "replace")[:n].ljust(n, b"\0")

def u32(buf, off): return struct.unpack_from("<I", buf, off)[0]
def set_u32(buf, off, v): struct.pack_into("<I", buf, off, int(v) & 0xffffffff)

# ---------------------------------------------------------------- inventory record
class Part:
    """A 116-byte inventory record (PartNode + PartRec), edited in place."""
    __slots__ = ("raw",)
    def __init__(self, raw):
        if len(raw) != REC_LEN: raise FormatError(f"record is {len(raw)} bytes, not {REC_LEN}")
        self.raw = raw if isinstance(raw, bytearray) else bytearray(raw)

    @classmethod
    def new(cls, name, typ, cls_id, dfl, full, wt, cond=None, state=2):
        p = cls(bytearray(REC_LEN))
        p.set_identity(name, typ, cls_id, dfl, full, wt)
        p.cond = full if cond is None else cond
        p.state = state
        return p

    def copy(self): return Part(bytearray(self.raw))

    # PartNode
    @property
    def ptrs(self): return struct.unpack_from("<3I", self.raw, N_PTR)
    @property
    def cond(self): return u32(self.raw, N_COND)
    @cond.setter
    def cond(self, v): set_u32(self.raw, N_COND, max(0, v))
    @property
    def state(self): return u32(self.raw, N_STATE)
    @state.setter
    def state(self, v):
        if v not in STATE_BADGE: raise ValueError("state must be 1..4")
        set_u32(self.raw, N_STATE, v)
    @property
    def leftovers(self): return bytes(self.raw[N_LEFT:N_LEFT+12])
    # PartRec
    @property
    def name(self): return cstr(self.raw[R_NAME:R_NAME+30])
    @name.setter
    def name(self, s): put_cstr(self.raw, R_NAME, 30, s)
    @property
    def type(self): return u32(self.raw, R_TYPE)
    @property
    def u22(self): return u32(self.raw, R_U22)
    @property
    def cls(self): return cstr(self.raw[R_CLS:R_CLS+13])
    @property
    def dfl(self): return cstr(self.raw[R_DFL:R_DFL+13])
    @property
    def u48(self): return u32(self.raw, R_U48)
    @property
    def full(self): return u32(self.raw, R_FULL)
    @full.setter
    def full(self, v): set_u32(self.raw, R_FULL, v)
    @property
    def wt(self): return struct.unpack_from("<f", self.raw, R_WT)[0]
    @wt.setter
    def wt(self, v): struct.pack_into("<f", self.raw, R_WT, float(v))

    @property
    def kind(self): return TYPE_NAMES.get(self.type, f"type{self.type}")
    @property
    def badge(self): return STATE_BADGE.get(self.state, "?")
    @property
    def is_weapon(self): return self.type in (7, 8)
    def level(self):
        """the game's highlight level: 0 red, 1 yellow, 2 green, 3 unmarked; None for specials"""
        if self.type == 13 or not self.full: return None
        return min(3, 3 * self.cond // self.full)
    @property
    def colour(self): return LEVEL_NAMES.get(self.level(), "none")

    def set_identity(self, name, typ, cls_id, dfl, full, wt):
        self.name = name
        set_u32(self.raw, R_TYPE, typ)
        put_cstr(self.raw, R_CLS, 13, cls_id)
        put_cstr(self.raw, R_DFL, 13, dfl)
        self.full = full
        self.wt = wt

    def key(self):
        """what Cmp_Read matches a section-C reference on (plus the name, for sanity)"""
        return (self.name, self.cond, self.dfl)

    def info(self):
        return dict(name=self.name, type=self.type, cls=self.cls, dfl=self.dfl, full=self.full,
                    wt=round(self.wt, 3), cond=self.cond, state=self.state, u22=self.u22, u48=self.u48,
                    level=self.level())

    def __repr__(self):
        return f"<Part {self.badge} {self.name!r} {self.kind} {self.dfl} {self.cond}/{self.full}>"

# ---------------------------------------------------------------- the .cmp / .spc file
class Cmp:
    """saveNNN.cmp / reconfig.spc / trip4.spc. to_bytes() reproduces the input byte for
    byte when nothing was changed (tested on every sample save in tests/)."""
    def __init__(self, data):
        data = bytes(data)
        if len(data) < HDR_LEN + 8:
            raise FormatError(f"{len(data)} bytes is shorter than a GarageRec + two counts ({HDR_LEN + 8})")
        nA = u32(data, HDR_LEN)
        oC = HDR_LEN + 4 + REC_LEN * nA
        if oC + 4 > len(data):
            raise FormatError(f"nA={nA} runs past the end of the file ({len(data)} bytes)")
        nC = u32(data, oC)
        want = HDR_LEN + 8 + REC_LEN * (nA + nC)
        if len(data) != want:
            raise FormatError(f"size {len(data)} != 0x8c4 + 8 + 116*({nA}+{nC}) = {want}")
        self.hdr = bytearray(data[:HDR_LEN])
        self.a = [Part(bytearray(data[HDR_LEN + 4 + REC_LEN * i:][:REC_LEN])) for i in range(nA)]
        self.c = [Part(bytearray(data[oC + 4 + REC_LEN * j:][:REC_LEN])) for j in range(nC)]

    @classmethod
    def load(cls, path):
        with open(path, "rb") as f: return cls(f.read())

    def to_bytes(self):
        out = bytearray(self.hdr)
        out += struct.pack("<I", len(self.a))
        for p in self.a: out += p.raw
        out += struct.pack("<I", len(self.c))
        for p in self.c: out += p.raw
        return bytes(out)

    # ---- GarageRec
    @property
    def car(self): return cstr(self.hdr[G_CAR:G_CAR+20])
    @property
    def variant(self): return cstr(self.hdr[G_VARIANT:G_VARIANT+20])
    @property
    def ident(self): return cstr(self.hdr[G_ID:G_ID+16])
    @property
    def equipped(self): return [cstr(self.hdr[G_EQ + k*G_EQ_LEN:][:G_EQ_LEN]) for k in range(G_EQ_N)]
    def set_equipped(self, slot, name): put_cstr(self.hdr, G_EQ + slot*G_EQ_LEN, G_EQ_LEN, name)
    @property
    def armor(self): return list(struct.unpack_from("<8I", self.hdr, G_ARMOR))
    def set_armor(self, i, tenths): set_u32(self.hdr, G_ARMOR + 4*i, max(0, tenths))
    @property
    def vdf(self): return cstr(self.hdr[G_VDF:G_VDF+13])
    @property
    def vtf(self): return cstr(self.hdr[G_VTF:G_VTF+13])
    @vtf.setter
    def vtf(self, s): put_cstr(self.hdr, G_VTF, 13, s)
    @property
    def wdf(self): return [cstr(self.hdr[o:o+13]) for o in G_WDF]
    def set_wdf(self, letter):
        for o in G_WDF[0], G_WDF[2]:
            cur = cstr(self.hdr[o:o+13])
            fam = cur[6] if cur.startswith("wauto_") and len(cur) > 6 else "1"
            put_cstr(self.hdr, o, 13, f"wauto_{fam}{letter}.wdf")
    @property
    def registry(self):
        n = u32(self.hdr, G_REGCOUNT)
        out = []
        for i in range(n):
            o = G_REG + 32*i
            if o + 32 > G_EQ: break
            out.append((u32(self.hdr, o), cstr(self.hdr[o+4:o+20])) + struct.unpack_from("<3I", self.hdr, o+20))
        return out
    def rename_registry(self, old, new):
        for i in range(u32(self.hdr, G_REGCOUNT)):
            o = G_REG + 32*i
            if cstr(self.hdr[o+4:o+20]) == old:
                put_cstr(self.hdr, o+4, 16, new); return True
        return False

    # ---- inventory views
    def weapons_in_cap(self):
        """the type-7/8 records with state != 4 the garage keeps, in file order (first WEAPON_CAP)"""
        return [p for p in self.a if p.is_weapon and p.state != 4][:WEAPON_CAP]
    def weapons_over_cap(self):
        return [p for p in self.a if p.is_weapon and p.state != 4][WEAPON_CAP:]

    def mounted(self):
        """one state-1 record per equipped label, matched by display name - what the garage
        resolves (MOUNT-VALIDATION.md): a weapon only counts when it is within the 11-record cap"""
        incap = set(id(p) for p in self.weapons_in_cap())
        pool = [p for p in self.a if p.state == 1 and (not p.is_weapon or id(p) in incap)]
        out = {}
        for slot, nm in enumerate(self.equipped):
            if not nm or nm == "Empty": continue
            for p in pool:
                if p.name == nm: out[slot] = p; pool.remove(p); break
        return out

    def loadout_warnings(self):
        """what the garage will do with this file that the bytes do not say: the same strings
        the browser editor's loadoutWarnings() produces (tests compare them)"""
        w = []
        over = self.weapons_over_cap()
        if over:
            w.append(f"{WEAPON_CAP + len(over)} car/van/bench weapons: the garage keeps the first {WEAPON_CAP} in file order, "
                     "the rest drop to Field Salvage: " + ", ".join(f"#{self.a.index(p)} ({p.badge}) {p.name}" for p in over))
        got = self.mounted()
        for slot, nm in enumerate(self.equipped):
            if nm and nm != "Empty" and slot not in got:
                w.append(f"{EQ_SLOTS[slot]} label '{nm}' has no mounted (state 1) record"
                         + (" within the weapon cap" if 7 <= slot <= 10 else "") + ": the hardpoint reads EMPTY")
        counts = {}
        for p in self.a:
            if p.state != 4:
                t = 7 if p.is_weapon else p.type
                counts[t] = counts.get(t, 0) + 1
        for t, n in sorted(counts.items()):
            if t in LIST_ALLOC and n > LIST_ALLOC[t]:
                w.append(f"{n} car/van/bench {PLURAL[t]}: the garage list is allocated for {LIST_ALLOC[t]} (heap overflow)")
        return w

    def prepare_for_write(self):
        """what write_cmp does beyond serialising: move mounted weapons to the front of section A
        when one of them sits past the 11-record cap (file order decides what the garage keeps),
        then rebuild the repair queue. Returns the list of actions taken; an untouched file gets none."""
        actions = []
        incap = set(id(p) for p in self.weapons_in_cap())
        if any(p.is_weapon and p.state == 1 and id(p) not in incap for p in self.a):
            first = [p for p in self.a if p.is_weapon and p.state == 1]
            self.a = first + [p for p in self.a if not (p.is_weapon and p.state == 1)]
            actions.append(f"moved {len(first)} mounted weapon records to the front of section A")
        if self.sync_repair_queue():
            actions.append(f"rebuilt the repair queue ({len(self.c)} references)")
        return actions

    def sync_repair_queue(self):
        """Section C must list the state-3 records of section A (the reader resolves each
        reference by condition + state 3 + def file). Leaves C untouched when it already
        matches as a multiset (preserves the game's bench order and bytes), otherwise
        rebuilds it from copies of the queued A records."""
        want = sorted(p.key() for p in self.a if p.state == 3)
        have = sorted(p.key() for p in self.c)
        if want == have: return False
        self.c = [p.copy() for p in self.a if p.state == 3]
        return True

    def mounted_weight(self):
        pool = [p for p in self.a if p.state == 1]
        t = 0.0
        for nm in self.equipped:
            if not nm or nm == "Empty": continue
            for p in pool:
                if p.name == nm: t += p.wt; pool.remove(p); break
            else:
                t += catalog_weight(nm)
        return t
    def total_weight(self):
        return CHASSIS_LBS + self.mounted_weight() + ARMOR_LBS_PER_POINT * sum(self.armor) / 10.0

    def check(self):
        """invariants seen in every game-written save; returns a list of warnings"""
        w = []
        neq = sum(1 for e in self.equipped if e and e != "Empty")
        n1 = sum(1 for p in self.a if p.state == 1)
        if neq != n1: w.append(f"{n1} mounted (state 1) records for {neq} equipped names")
        names1 = sorted(p.name for p in self.a if p.state == 1)
        namese = sorted(e for e in self.equipped if e and e != "Empty")
        if names1 != namese: w.append("state-1 names differ from the equipped block: "
                                      f"{sorted(set(names1) ^ set(namese))}")
        want = sorted(p.key() for p in self.a if p.state == 3)
        have = sorted(p.key() for p in self.c)
        if want != have: w.append(f"repair queue (section C, {len(self.c)}) != state-3 records ({len(want)})")
        for p in self.a + self.c:
            if p.state not in STATE_BADGE: w.append(f"{p.name}: state {p.state}")
            if p.type not in KNOWN_TYPES: w.append(f"{p.name}: type {p.type}")
        return w

    def info(self, file=None, size=None):
        return dict(file=file, size=size, car=self.car, variant=self.variant, id=self.ident,
                    nA=len(self.a), nC=len(self.c), armor=self.armor, equipped=self.equipped,
                    vdf=self.vdf, vtf=self.vtf, wdf=self.wdf, registry=[list(r) for r in self.registry],
                    a=[p.info() for p in self.a], c=[p.info() for p in self.c],
                    warnings=self.loadout_warnings())

# ---------------------------------------------------------------- savegame.dir
class DirRec:
    """one 60-byte savegame.dir record, edited in place. The raw bytes are kept because the
    shell writes its 32-byte name buffer verbatim - stale characters after the NUL
    ("\\0eppers" in the committed saves/savegame.dir) are part of the file."""
    __slots__ = ("raw",)
    def __init__(self, raw=None):
        self.raw = bytearray(raw) if raw is not None else bytearray(DIR_REC)
        if len(self.raw) != DIR_REC: raise FormatError(f"dir record is {len(self.raw)} bytes, not {DIR_REC}")
    @property
    def scene(self): return u32(self.raw, D_SCENE)
    @scene.setter
    def scene(self, v): set_u32(self.raw, D_SCENE, v)
    @property
    def name(self): return cstr(self.raw[D_NAME:D_NAME+32])
    @name.setter
    def name(self, s): put_cstr(self.raw, D_NAME, 32, s[:31])
    @property
    def file(self): return cstr(self.raw[D_FILE:D_FILE+16])
    @file.setter
    def file(self, s): put_cstr(self.raw, D_FILE, 16, s[:15])
    @property
    def state(self): return u32(self.raw, D_STATE)
    @state.setter
    def state(self, v): set_u32(self.raw, D_STATE, v)
    @property
    def flags(self): return u32(self.raw, D_FLAGS)
    @flags.setter
    def flags(self, v): set_u32(self.raw, D_FLAGS, v)
    def plays(self):
        """the scene the game starts when this record is loaded (sandbox-verified 2026-10-01)"""
        return self.scene if self.state == 8 else self.scene + 1
    def info(self):
        return dict(scene=self.scene, name=self.name, file=self.file, state=self.state, flags=self.flags, plays=self.plays())
    # dict-style access keeps the older callers working
    def __getitem__(self, k): return getattr(self, k)
    def __setitem__(self, k, v): setattr(self, k, v)
    def __repr__(self): return f"<DirRec {self.file} scene {self.scene} state {self.state} {self.name!r}>"

class SaveDir:
    """u32 count + 60-byte records. Keeps every record's raw bytes and any trailing slack
    verbatim, so an unmodified directory (including the launchers' padded ones) comes back
    byte for byte."""
    def __init__(self, data=b""):
        data = bytes(data)
        self.records = []
        if len(data) < DIR_HDR:
            self.slack = b""; self.short = False; return
        count = u32(data, 0)
        self.short = len(data) < DIR_HDR + DIR_REC * count
        for k in range(count):
            o = DIR_HDR + DIR_REC * k
            self.records.append(DirRec(data[o:o+DIR_REC].ljust(DIR_REC, b"\0")))   # a short file reads zero-filled
        self.slack = data[DIR_HDR + DIR_REC * count:]

    @classmethod
    def load(cls, path):
        with open(path, "rb") as f: return cls(f.read())

    def to_bytes(self, min_len=0):
        out = struct.pack("<I", len(self.records)) + b"".join(bytes(r.raw) for r in self.records) + self.slack
        if len(out) < min_len: out += b"\0" * (min_len - len(out))
        return out

    @property
    def exact_len(self): return DIR_HDR + DIR_REC * len(self.records)
    def get(self, file):
        for r in self.records:
            if r.file.lower() == file.lower(): return r
        return None
    def set_scene(self, file, scene):
        r = self.get(file)
        if not r: raise KeyError(file)
        r.scene = scene
    def set_name(self, file, name):
        r = self.get(file)
        if not r: raise KeyError(file)
        r.name = name
    def add(self, file, scene, name="", state=8, flags=0):
        if self.get(file): raise KeyError(f"{file} already listed")
        r = DirRec(); r.scene = scene; r.name = name; r.file = file; r.state = state; r.flags = flags
        self.records.append(r)
        return r
    def remove(self, file):
        self.records = [r for r in self.records if r.file.lower() != file.lower()]
    def free_slot(self):
        used = {r.file.lower() for r in self.records}
        for i in range(1000):
            s = f"save{i:03d}"
            if s not in used: return s
        raise RuntimeError("no free slot")
    def info(self, file=None, size=None):
        return dict(file=file, size=size, count=len(self.records), exact_len=self.exact_len,
                    slack=len(self.slack), records=[r.info() for r in self.records])

# ---------------------------------------------------------------- files
def stamp(): return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

def write_file(path, data, backup=True):
    """back up (one-time .pre-edit + timestamped .bak), write, read back and compare."""
    data = bytes(data)
    if backup and os.path.isfile(path):
        if not os.path.isfile(path + ".pre-edit"):
            shutil.copy2(path, path + ".pre-edit")
        shutil.copy2(path, f"{path}.bak-{stamp()}")
    with open(path, "wb") as f: f.write(data)
    with open(path, "rb") as f: back = f.read()
    if back != data: raise IOError(f"read-back mismatch writing {path}")
    return len(data)

def write_cmp(path, cmp, backup=True):
    cmp.prepare_for_write()
    return write_file(path, cmp.to_bytes(), backup)

def write_dir(path, sd, backup=True):
    """never shrink a directory the game (or a launcher) wrote"""
    cur = os.path.getsize(path) if os.path.isfile(path) else 0
    return write_file(path, sd.to_bytes(min_len=cur), backup)

# ---------------------------------------------------------------- catalog helpers
def catalog_for(part):
    """Return list of (label, apply_args) the record may become."""
    t = part.type
    sh = lambda key: (PARTS_INFO.get(key) or {}).get("short", "")
    if t == 2:  return [(f"{n:14} (dur {du}, wt {w:.0f})  {sh(df)}", (n, ty, c, df, du, w)) for n,c,df,ty,du,w in ENGINES]
    if t == 3:  return [(f"{n:14} (dur {du}, wt {w:.0f})  {sh(df)}", (n, ty, c, df, du, w)) for n,c,df,ty,du,w in SUSPENSIONS]
    if t == 4:  return [(f"{n:14} (dur {du}, wt {w:.0f})  {sh(df)}", (n, ty, c, df, du, w)) for n,c,df,ty,du,w in BRAKES]
    if t == 5:
        d = part.dfl
        fam = d[6] if d.startswith("wauto_") and len(d) > 6 else "1"
        return [(f"{n:14} (wauto_{fam}{l})  {sh('wauto_' + l)}", (n, 5, "whe01", f"wauto_{fam}{l}.wdf", WHEEL_DUR, WHEEL_WT))
                for l, n in WHEEL_DESIGNS]
    if t in (7, 8):
        return [(f"{n:17} [{m}] (dur {du}, wt {w:.0f})  {sh(df)}", (n, weapon_type(m), m, df, du, w))
                for n, m, df, du, w in WEAPONS]
    if t == 13:
        return [(f"{n:14} {sh(df)}  [{tag}]", (n, 13, "", df, 0, 0.0)) for n, df, tag in SPECIALS]
    return []

# ---------------------------------------------------------------- save-set discovery
def find_save_dirs(explicit):
    if explicit:
        return [explicit]
    dirs = []
    for base in (os.path.expanduser("~/Applications/Sikarugir"),
                 os.path.expanduser("~/Applications"), "/Applications"):
        if not os.path.isdir(base): continue
        for root, subdirs, files in os.walk(base):
            if root.count(os.sep) - base.count(os.sep) > 8:
                subdirs[:] = []; continue
            if root.endswith(os.path.join("drive_c", "GOG Games", "Interstate 76")):
                if glob.glob(os.path.join(root, "save*.cmp")):
                    dirs.append(root)
                subdirs[:] = []
    repo = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saves")
    if glob.glob(os.path.join(repo, "save*.cmp")):
        dirs.append(repo)
    seen, out = set(), []
    for d in dirs:
        r = os.path.realpath(d)
        if r not in seen:
            seen.add(r); out.append(d)
    return out

def load_dir(sdir):
    p = os.path.join(sdir, "savegame.dir")
    return SaveDir.load(p) if os.path.isfile(p) else SaveDir()

def plays(rec):
    """the scene the game starts when this record is loaded (sandbox-verified 2026-10-01)"""
    return rec["scene"] if rec["state"] == 8 else rec["scene"] + 1

def list_saves(sdir):
    sd = load_dir(sdir)
    rows = []
    for fn in sorted(glob.glob(os.path.join(sdir, "save*.cmp"))):
        base = os.path.splitext(os.path.basename(fn))[0]
        rec = sd.get(base)
        try:
            cmp = Cmp.load(fn); err = ""
        except (OSError, FormatError) as e:
            cmp = None; err = str(e)
        rows.append(dict(base=base, path=fn, rec=rec, cmp=cmp, err=err))
    return rows, sd

# ---------------------------------------------------------------- UI
def show_save(cmp, warnings=True):
    print(f"\n  Car: {cmp.car}  |  {cmp.variant}  |  id: {cmp.ident}  |  paint {cmp.vtf}  |  wheels {cmp.wdf[0]}")
    print("  Armor (tenths/10): " + ", ".join(f"{l} {v/10:.1f}" for l, v in zip(ARMOR_LABELS, cmp.armor)))
    print(f"  Weight: {cmp.total_weight():.0f} lbs (2910 + mounted parts + 1 lb/armor point)")
    eq = cmp.equipped
    print("  Equipped: " + ", ".join(f"{EQ_SLOTS[k]}={n}" for k, n in enumerate(eq) if n))
    for k, n in enumerate(eq):
        i = info_by_name(n) if n and k not in (4, 5, 6) else None        # the four tyres share one design
        if i: print(f"    {EQ_SLOTS[k] if k != 3 else 'Tires':11} {n:17} {i['short']}")
    print(f"  Inventory: {len(cmp.a)} records (section A) + {len(cmp.c)} repair-queue references (section C)")
    print(f"  {'#':>3} {'':3} {'item':22} {'kind':10} {'class':6} {'def':13} {'full':>4} {'cond':>5} {'state':>5} {'colour':6}  what it does")
    print(f"  {'-'*3} {'-'*3} {'-'*22} {'-'*10} {'-'*6} {'-'*13} {'-'*4} {'-'*5} {'-'*5} ------  ------------")
    for k, p in enumerate(cmp.a):
        print(f"  {k:>3} ({p.badge}) {p.name:22} {p.kind:10} {p.cls:6} {p.dfl:13} {p.full:>4} {p.cond:>5} {p.state:>5} {p.colour:6}  {does(p)}")
    if cmp.c:
        print("  Repair queue (section C, bench order): " + ", ".join(f"{p.name} {p.cond}/{p.full}" for p in cmp.c))
    if warnings:
        for w in cmp.check(): print(f"  FORMAT WARNING: {w}")
        for w in cmp.loadout_warnings(): print(f"  GARAGE WARNING: {w}")

def ask(prompt, valid=None):
    while True:
        s = input(prompt).strip()
        if valid is None or s in valid or (s and valid == "int" and s.lstrip("-").isdigit()):
            return s

def edit_record(cmp, k):
    p = cmp.a[k]
    while True:
        print(f"\n  [{k}] {p.name}  ({p.kind}, {p.dfl})  full={p.full} cond={p.cond} state={p.state} {STATE_LABEL.get(p.state,'')}")
        i = part_info(p.type, p.dfl, p.cls)
        if i: print(f"      what it does: {i['what']}")
        c = ask("  [s]wap item  [c]ondition  [l]ocation  [b]ack > ", ("s","c","l","b"))
        if c == "b": return
        if c == "s":
            options = catalog_for(p)
            if not options:
                print("  no catalog for this type"); continue
            for i, (label, _) in enumerate(options):
                print(f"    {i:>2}  {label}")
            s = ask("  new item # (or blank to cancel) > ")
            if not s.isdigit() or int(s) >= len(options): continue
            name, typ, cls, dfl, dur, wt = options[int(s)][1]
            p.set_identity(name, typ, cls, dfl, dur, wt)
            if p.type != 13: p.cond = dur
            print(f"  -> now {name} ({dfl}), condition {p.cond} (state untouched)")
        if c == "c":
            s = ask(f"  condition points (current {p.cond}, full {p.full or 'n/a'}) > ", "int")
            p.cond = max(0, int(s))
        if c == "l":
            s = ask(f"  state 1 car / 2 van / 3 repair / 4 salvage (current {p.state}) > ", ("1","2","3","4"))
            p.state = int(s)

def interactive(sdir):
    while True:
        rows, sd = list_saves(sdir)
        if not rows:
            print(f"no save*.cmp in {sdir}"); return
        print(f"\nSaves in {sdir}:")
        for i, r in enumerate(rows):
            print("  " + format_row(i, r))
        s = ask("\npick save # (or q) > ")
        if s.lower() == "q": return
        if not s.isdigit() or int(s) >= len(rows): continue
        row = rows[int(s)]
        if row["cmp"] is None:
            print(f"  cannot edit: {row['err']}"); continue
        cmp = row["cmp"]; fn = row["path"]
        orig = cmp.to_bytes()
        while True:
            show_save(cmp)
            cmd = ask("\nitem # to edit, [r]epair-all, [n]ame/scene, [w]rite, [q]uit save > ")
            if cmd.lower() == "q":
                if cmp.to_bytes() != orig and ask("  discard changes? y/n > ", ("y","n")) == "n":
                    continue
                break
            if cmd.lower() == "r":
                fixed = 0
                for p in cmp.a:
                    if p.type != 13 and p.full:
                        p.cond = p.full; fixed += 1
                print(f"  repaired {fixed} items to full condition (states untouched)")
            elif cmd.lower() == "n":
                rec = sd.get(row["base"])
                if rec is None:
                    print("  not listed in savegame.dir - add it:")
                    rec = sd.add(row["base"], 0, "", 8)
                s = ask(f"  scene (current {rec['scene']}, state {rec['state']}: plays {plays(rec)}) > ", "int")
                rec["scene"] = int(s)
                s = input(f"  name (current {rec['name']!r}, blank keeps) > ").strip()
                if s: rec["name"] = s[:31]
                write_dir(os.path.join(sdir, "savegame.dir"), sd)
                print("  savegame.dir written (backup kept)")
            elif cmd.lower() == "w":
                if cmp.to_bytes() == orig:
                    print("  no changes"); continue
                for w in cmp.loadout_warnings(): print(f"  GARAGE WARNING: {w}")
                for act in cmp.prepare_for_write(): print(f"  {act}")
                n = write_cmp(fn, cmp)
                orig = cmp.to_bytes()
                print(f"  written: {fn} ({n} bytes, backups kept)")
                print("  NOTE: if you edited the repo copy, run setup-saves.sh to install;"
                      " if you edited the live copy, run setup-saves.sh --backup to sync the repo.")
            elif cmd.isdigit() and int(cmd) < len(cmp.a):
                edit_record(cmp, int(cmd))

def format_row(i, r):
    rec = r["rec"]
    if rec: scene = f"scene {rec['scene']:>2} st {rec['state']} plays {plays(rec):>2}  {rec['name']!r:20}"
    else:   scene = "not in savegame.dir" + " " * 23
    if r["cmp"]:
        c = r["cmp"]
        states = {s: sum(1 for p in c.a if p.state == s) for s in (1, 2, 3, 4)}
        body = f"{c.car} / {c.variant}  ({len(c.a)} A + {len(c.c)} C: C{states[1]} V{states[2]} R{states[3]} S{states[4]})"
    else:
        body = f"UNREADABLE: {r['err']}"
    return f"{i:>2}  {r['base']:9} {scene}  {body}"

def cmd_json(paths):
    out = []
    for p in paths:
        data = open(p, "rb").read()
        if p.lower().endswith(".dir"):
            out.append(SaveDir(data).info(os.path.basename(p), len(data)))
        else:
            try:
                out.append(Cmp(data).info(os.path.basename(p), len(data)))
            except FormatError as e:
                out.append(dict(file=os.path.basename(p), size=len(data), error=str(e)))
    json.dump(out, sys.stdout, indent=1)
    print()

def cmd_check(sdir):
    bad = 0
    dp = os.path.join(sdir, "savegame.dir")
    if os.path.isfile(dp):
        sd = SaveDir.load(dp); size = os.path.getsize(dp)
        tag = "exact" if size == sd.exact_len else (f"short by {sd.exact_len - size}" if sd.short else f"+{len(sd.slack)} slack")
        rt = sd.to_bytes() == open(dp, "rb").read()
        print(f"savegame.dir: {len(sd.records)} records, {size} B ({tag}), round-trip {'OK' if rt else 'FAIL'}")
        bad += (not rt) or sd.short
        for r in sd.records:
            missing = "" if os.path.isfile(os.path.join(sdir, r["file"] + ".cmp")) else "  <- no .cmp, the board drops it"
            print(f"   {r['file']:9} scene {r['scene']:>2} state {r['state']} plays {plays(r):>2} {r['name']!r}{missing}")
    for fn in sorted(glob.glob(os.path.join(sdir, "save*.cmp")) + glob.glob(os.path.join(sdir, "*.spc"))):
        data = open(fn, "rb").read()
        try:
            c = Cmp(data)
        except FormatError as e:
            print(f"{os.path.basename(fn)}: FAIL {e}"); bad += 1; continue
        rt = c.to_bytes() == data
        w = c.check(); g = c.loadout_warnings()
        print(f"{os.path.basename(fn)}: {len(data)} B, nA {len(c.a)} nC {len(c.c)}, round-trip {'OK' if rt else 'FAIL'}"
              + (f", {len(w)} format warning(s): " + "; ".join(w) if w else "")
              + (f", {len(g)} garage warning(s): " + "; ".join(g) if g else ""))
        bad += not rt
    return bad

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dir", help="save directory (default: auto-find wrapper, then repo saves/)")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--dump", metavar="N", help="dump save slot N (index from --list) or saveNNN")
    ap.add_argument("--check", action="store_true", help="validate every file in --dir")
    ap.add_argument("--json", nargs="+", metavar="FILE", help="JSON dump of the given .cmp/.spc/.dir files")
    ap.add_argument("--parts", action="store_true", help="print what every part does (docs/PARTS-REFERENCE.md)")
    ap.add_argument("--parts-json", action="store_true", help="print PARTS_INFO as the JSON the HTML editor embeds")
    a = ap.parse_args()

    if a.parts:
        return print_parts_reference()
    if a.parts_json:
        return print(parts_json())

    if a.json:
        return cmd_json(a.json)
    dirs = find_save_dirs(a.dir)
    if not dirs:
        sys.exit("no save directories found (use --dir)")
    sdir = dirs[0]
    if len(dirs) > 1 and not (a.list or a.check or a.dump is not None):
        print("Save locations:")
        for i, dd in enumerate(dirs): print(f"  {i}  {dd}")
        s = ask("pick location # > ")
        sdir = dirs[int(s)] if s.isdigit() and int(s) < len(dirs) else dirs[0]

    if a.check:
        sys.exit(1 if cmd_check(sdir) else 0)
    if a.list:
        rows, _ = list_saves(sdir)
        for i, r in enumerate(rows): print(format_row(i, r))
        return
    if a.dump is not None:
        rows, _ = list_saves(sdir)
        if a.dump.isdigit(): row = rows[int(a.dump)]
        else:
            m = [r for r in rows if r["base"] == a.dump]
            if not m: sys.exit(f"{a.dump} not in {sdir}")
            row = m[0]
        if row["cmp"] is None: sys.exit(f"{row['base']}: {row['err']}")
        print(format_row(0, row))
        show_save(row["cmp"])
        return
    interactive(sdir)

if __name__ == "__main__":
    main()
