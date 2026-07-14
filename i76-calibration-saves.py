#!/usr/bin/env python3
"""Generate the two CALIBRATION saves that let the game itself answer the open
save-format questions (docs/SAVE-FORMAT-GAPS.md, 2026-07-14):

  save005 "COLOR CAL"  - salvage-pool guns become identical 50cal MGs with a
                         condition gradient 10..100% (+ two wheels at 120%/200%,
                         + distinct conditions on the four salvage-pool
                         suspensions to crack the V-vs-S rule).
  save006 "WEIGHT CAL" - byte-identical to the base save except FRONT armor
                         +10.0 points -> the form's total-weight delta yields
                         the armor lbs/point coefficient.

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
    ap.add_argument("--dir"); a = ap.parse_args()
    g = os.path.abspath(a.dir) if a.dir else find_game_dir()
    assert g and os.path.isdir(g), "game dir not found"
    base = bytearray(open(os.path.join(g, "save004.cmp"), "rb").read())
    recs = scan(bytes(base))
    loc  = lambda b, o: struct.unpack_from("<I", b, o+100)[0]
    typ  = lambda b, o: struct.unpack_from("<I", b, o+30)[0]
    MAIN_END = 9588   # corrupt slot + repair section start beyond here - untouched

    # ---------- save005: COLOR CAL ----------
    s5 = bytearray(base)
    guns = [o for o in recs if o < MAIN_END and typ(s5, o) in (7, 8) and loc(s5, o) == 4]
    grads = [10, 25, 40, 55, 70, 85, 100]
    assert len(guns) >= len(grads), f"need 7 salvage guns, found {len(guns)}"
    for o, pct in zip(guns, grads):
        write_identity(s5, o, "50cal MG", 7, "slg02", "gmmedium.gdf", 400, 47.0)
        struct.pack_into("<I", s5, o+96, 400*pct//100)
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

    # ---------- write saves + dir entries ----------
    for name, data in (("save005.cmp", s5), ("save006.cmp", s6)):
        p = os.path.join(g, name)
        bk = backup(p)
        open(p, "wb").write(data)
        print(f"wrote {name}" + (f" (old kept as {bk})" if bk else ""))
    dirp = os.path.join(g, "savegame.dir")
    d = bytearray(open(dirp, "rb").read())
    count = struct.unpack_from("<I", d, 0)[0]
    have = {cstr(d, 0x28+60*k, 16) for k in range(count)}
    for slot in ("save005", "save006"):
        if slot in have: continue
        off = 0x28 + 60*count
        if len(d) < off + 60: d += b"\0" * (off + 60 - len(d))
        d[off:off+16] = slot.encode().ljust(16, b"\0")
        struct.pack_into("<I", d, off+16, 1)
        struct.pack_into("<I", d, off+24, 7)           # scene 7 done, like save004
        count += 1
    struct.pack_into("<I", d, 0, count)
    backup(dirp); open(dirp, "wb").write(d)
    print(f"savegame.dir now lists {count} slots (005/006 = scene 7)")

if __name__ == "__main__":
    main()
