#!/usr/bin/env python3
"""Generate the two CALIBRATION saves that let the game itself answer the open
save-format questions (docs/SAVE-FORMAT-GAPS.md, 2026-07-14):

  save006 "COLOR CAL"  - salvage-pool guns become identical 50cal MGs with a
                         condition gradient 10..100% (+ two wheels at 120%/200%,
                         + distinct conditions on the salvage-pool suspensions
                         to crack the V-vs-S rule).
  save007 "WEIGHT CAL" - byte-identical to the base save except FRONT armor
                         +10.0 points -> the form's total-weight delta yields
                         the armor lbs/point coefficient (read BOTH totals:
                         the base save's and this one's).
  (save005 is the user's recovered in-game save - not touched.)
  Dir entries are written WITH display names ("COLOR CAL"/"WEIGHT CAL",
  savegame.dir entry +28) so they're identifiable on the game's LOAD board.

Base = save004.cmp (the field-verified reference save). Writes save005/006 +
savegame.dir entries (scene 7), with timestamped backups of anything replaced.
Never touches the repair section, the truncated tail record, or the corrupt
NitrousOxide slot @9588.

Usage: i76-calibration-saves.py [--dir GAMEDIR]   (default: auto-find wrapper)
"""
import argparse, datetime, glob, os, shutil, struct

REC = 116
def cstr(b, o, n):
    s = b[o:o+n]; z = s.find(b"\0")
    return (s if z < 0 else s[:z]).decode("latin1")

def find_game_dir():
    for base in (os.path.expanduser("~/Applications/Sikarugir"),):
        for root, dirs, files in os.walk(base):
            if root.endswith(os.path.join("drive_c", "GOG Games", "Interstate 76")):
                return root
    return None

def scan(buf):
    KIND = {2,3,4,5,7,8,13}
    recs, i = [], 0
    while i + REC <= len(buf):
        t = struct.unpack_from("<I", buf, i+30)[0]
        n = 0
        while n < 30 and buf[i+n] != 0: n += 1
        plaus = 3 <= n <= 29 and all(32 <= c < 127 for c in buf[i:i+n])
        if t in KIND and plaus and buf[i+34:i+46] == b"\0"*12:
            cls = cstr(buf, i+46, 13); dfl = cstr(buf, i+59, 13)
            if dfl and ((cls == "" and dfl.startswith("spc")) or cls):
                recs.append(i); i += REC; continue
        i += 2
    return recs

def write_identity(buf, o, name, typ, cls, dfl, dur, wt):
    buf[o:o+30] = name.encode("latin1").ljust(30, b"\0")[:30]
    struct.pack_into("<I", buf, o+30, typ)
    buf[o+46:o+59] = cls.encode().ljust(13, b"\0")[:13]
    buf[o+59:o+72] = dfl.encode().ljust(13, b"\0")[:13]
    struct.pack_into("<I", buf, o+76, dur)
    struct.pack_into("<f", buf, o+80, wt)

def backup(p):
    if os.path.isfile(p):
        b = p + ".bak-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.copy2(p, b); return os.path.basename(b)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir")
    ap.add_argument("--perfect", action="store_true",
                    help="write save006 'ALL PERFECT': every non-special record "
                         "cond = its max (dur). Expect ZERO colors in the stable "
                         "panes (Car/Van + Repair); salvage may still color (re-rolled).")
    a = ap.parse_args()
    g = os.path.abspath(a.dir) if a.dir else find_game_dir()
    assert g and os.path.isdir(g), "game dir not found"
    if a.perfect:
        base = bytearray(open(os.path.join(g, "save004.cmp"), "rb").read())
        n = 0
        for o in scan(bytes(base)):
            t = struct.unpack_from("<I", base, o+30)[0]
            dur = struct.unpack_from("<I", base, o+76)[0]
            if t == 13 or not dur: continue        # specials: cond means something else
            if o + 100 > len(base): continue       # truncated tail record
            struct.pack_into("<I", base, o+96, dur); n += 1
        p = os.path.join(g, "save006.cmp")
        bk = backup(p); open(p, "wb").write(base)
        print(f"wrote save006.cmp ALL PERFECT ({n} records set to 100%)" + (f" (old kept as {bk})" if bk else ""))
        dirp = os.path.join(g, "savegame.dir")
        d = bytearray(open(dirp, "rb").read())
        count = struct.unpack_from("<I", d, 0)[0]
        for k in range(count):
            if cstr(d, 0x28+60*k, 16) == "save006":
                d[0x08+60*k:0x08+60*k+32] = b"ALL PERFECT".ljust(32, b"\0")
        backup(dirp); open(dirp, "wb").write(d)
        print("dir entry renamed: save006 = 'ALL PERFECT'")
        return
    base = bytearray(open(os.path.join(g, "save004.cmp"), "rb").read())
    recs = scan(bytes(base))
    loc  = lambda b, o: struct.unpack_from("<I", b, o+100)[0]
    typ  = lambda b, o: struct.unpack_from("<I", b, o+30)[0]
    MAIN_END = 9588   # corrupt slot + repair section start beyond here - untouched

    # ---------- save006: COLOR CAL v3 ----------
    # v1 (identical 50cals): display-order ambiguity. v2 (unique guns in
    # SALVAGE): the salvage pane RE-ROLLS its colors at load - not stored
    # state (proven: same bytes, different colors across two loads) - and the
    # game AUTO-MOUNTED the mountable probes into the car. v3: seven unique
    # TURRET-class weapons (unmountable on the Piranha - the game ejects
    # turrets to Empty, field-proven) placed in the VAN (loc2, whose colors
    # ARE stable across loads), overwriting only records whose names are NOT
    # in the equipped block (no auto-mount consumption, no cap breach).
    # All durs = gdf maxHP @ offset 76, extracted from the game's own files.
    CAL_GUNS = [  # (name, type, cls, dfl, dur, wt, pct)
        ("30cal Turret", 7, "slg01", "tmlight.gdf",  200,  32.0,  10),
        ("50cal Turret", 7, "slg02", "tmmedium.gdf", 400,  47.0,  25),
        ("7.62 Turret",  7, "slg03", "tmheavy.gdf",  600,  91.0,  40),
        ("25mm Turret",  7, "slg05", "tcmedium.gdf", 400,  89.0,  55),
        ("30mm Turret",  7, "slg06", "tcheavy.gdf",  600, 150.0,  70),
        ("HADES Turret", 7, "slg07", "tchades.gdf",  600, 150.0,  85),
        ("Howitzer",     7, "slg06", "tthowitz.gdf", 900, 170.0, 100),
    ]
    s5 = bytearray(base)
    equipped = {cstr(bytes(s5), 1024+k*30, 30) for k in range(14)}
    guns = [o for o in recs if o < MAIN_END and typ(s5, o) in (7, 8)
            and loc(s5, o) == 2 and cstr(bytes(s5), o, 30) not in equipped]
    assert len(guns) >= len(CAL_GUNS), f"need 7 free van guns, found {len(guns)}"
    for o, (nm, t, cls, dfl, dur, wt, pct) in zip(guns, CAL_GUNS):
        write_identity(s5, o, nm, t, cls, dfl, dur, wt)
        struct.pack_into("<I", s5, o+96, dur*pct//100)
    wheels = [o for o in recs if o < MAIN_END and typ(s5, o) == 5 and loc(s5, o) == 4]
    for o, cond in zip(wheels[:2], (120, 200)):        # dur=100 -> 120% and 200%
        struct.pack_into("<I", s5, o+96, cond)
    sus = [o for o in recs if o < MAIN_END and typ(s5, o) == 3 and loc(s5, o) == 4]
    for o, cond in zip(sus, (55, 105, 155, 25)):       # dur=200 -> 27.5/52.5/77.5/12.5%
        struct.pack_into("<I", s5, o+96, cond)

    # ---------- save006: WEIGHT CAL ----------
    s6 = bytearray(base)
    front = struct.unpack_from("<I", s6, 2044)[0]
    struct.pack_into("<I", s6, 2044, front + 100)      # +10.0 armor points

    # ---------- write saves + NAMED dir entries ----------
    for name, data in (("save006.cmp", s5), ("save007.cmp", s6)):
        p = os.path.join(g, name)
        bk = backup(p)
        open(p, "wb").write(data)
        print(f"wrote {name}" + (f" (old kept as {bk})" if bk else ""))
    dirp = os.path.join(g, "savegame.dir")
    d = bytearray(open(dirp, "rb").read())
    count = struct.unpack_from("<I", d, 0)[0]
    have = {cstr(d, 0x28+60*k, 16) for k in range(count)}
    # scene: mirror the base save's entry so the cal saves load the same mission
    base_scene = 6
    for k in range(count):
        if cstr(d, 0x28+60*k, 16) == "save004":
            off = 0x28+60*k+24
            if off+4 <= len(d): base_scene = struct.unpack_from("<I", d, off)[0]
    for slot, disp in (("save006", "COLOR CAL"), ("save007", "WEIGHT CAL")):
        if slot in have: continue
        off = 0x28 + 60*count
        if len(d) < off + 60: d += b"\0" * (off + 60 - len(d))
        d[off:off+60] = b"\0" * 60
        d[off:off+16] = slot.encode().ljust(16, b"\0")
        struct.pack_into("<I", d, off+16, 1)
        struct.pack_into("<I", d, off+24, base_scene)
        # display name PRECEDES the entry: name(save_k) @ 0x08+60k = off-32
        d[off-32:off] = disp.encode().ljust(32, b"\0")
        count += 1
    struct.pack_into("<I", d, 0, count)
    # the game DROPS the last entry when the file ends exactly at it (its
    # reader over-reads; its own writer truncates) - always leave 56B slack
    need = 0x28 + 60*count + 56
    if len(d) < need: d += b"\0" * (need - len(d))
    backup(dirp); open(dirp, "wb").write(d)
    print(f"savegame.dir now lists {count} slots (006=COLOR CAL, 007=WEIGHT CAL, scene {base_scene}), padded to {len(d)}B")

if __name__ == "__main__":
    main()
