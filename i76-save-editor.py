#!/usr/bin/env python3
"""Interstate '76 save editor - list saves, browse the garage inventory, swap any
item for any other allowed item, and set condition.

Format knowledge (reverse-engineered from this repo's saves + I76.ZFS defs + the
game's own garage screens, 2026-07):
  save###.cmp is UNCOMPRESSED structured binary:
    - header: car name[20], variant[20], id[16] (constant "doarmel"), u32 @56,
      u32 mounted-count @60
    - Mr. Damage component registry @64 (32B records: u32 idx, char[16] name,
      3 dwords - structural constants, grows as specials are installed)
    - EQUIPPED loadout @1024: 14 x char[30] names (engine, susp, brakes,
      wheels x4, weapons x4, specials x3) - what's ON the car
    - ARMOR @2044: 8 x u32 in TENTHS of the in-game DEFENSE panel numbers:
      armor F/R/L/Rear then chassis F/R/L/Rear (verified against the game UI)
    - inventory: 116-byte records, found by signature scan; they run in
      116-byte trains - the FIRST train is the van inventory (V), later
      trains are the repair order (R). AMMO IS NEVER STORED (bookmarks happen
      at the shack; weapons refill from their .gdf defaults each mission).
    - record layout:
        +0   char[30] display name (zero-padded; may carry junk after NUL)
        +30  u32     type  (2=engine 3=susp 4=brake 5=wheel 7=gun 8=dropper 13=special)
        +34  12 zero bytes
        +46  char[13] class id   ("eng01", "whe01", "slg02", "" for specials)
        +59  char[13] def file   ("gmmedium.gdf", "wauto_1b.wdf", "eng02", "spc05")
        +72  u32     (usually 0)
        +76  u32     max durability  == the def file's own maxHP (verified vs gdf/wdf/cdf)
        +80  f32     weight          == the def file's weight   (verified)
        +84  3 dwords: saved RUNTIME POINTERS (garbage; differ between twin saves - ignore)
        +96  u32     condition points (vs +76 durability -> the game's highlight
                     colors: full=none, then green/yellow/red as it drops)
        +100 u32     LOCATION flag (PROVEN in-game): 1=(C) on the car,
                     2=(C) in the car (rare), 3=(R) in repair, 4=(V) in the van.
                     Writing 1 everywhere piles every part into the car and the
                     game unmounts hardpoints - don't.
        +104 12 zero bytes
  savegame.dir: u32 count, entries at 0x28+60k: name[16] + u32 + u32 + u32 SCENE.
  The scene dword = last COMPLETED scene; loading plays the NEXT one (dword 7
  -> you play Scene 8). 0 -> Scene 1 with the scripted starter car. The game
  writes the newest entry's scene truncated.

Catalog sources: g*/t*.gdf (44 weapons), wauto_*.wdf (wheels: 4 designs x car-size
family digit), compnent.cdf (engines/susp/brakes), specials spc01..spc09 mapped from
the exe string table (spc02=NitrousOxide, spc04=X-Aust, spc05=Structo verified in
saves; the rest inferred from the same reversed order).

Usage:
  i76-save-editor.py                 interactive (auto-finds the Mac wrapper saves)
  i76-save-editor.py --dir DIR       operate on saves in DIR (e.g. the repo saves/)
  i76-save-editor.py --list          list saves and exit
  i76-save-editor.py --dump N        dump save slot N and exit

Every modified file gets a one-time <name>.pre-edit backup next to it.
"""
import argparse, glob, os, shutil, struct, sys

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
# wheels: def = wauto_<family><design>.wdf ; family digit is the CAR's tire size
# class - keep the save's own family digit when swapping, only change the design letter.
WHEEL_DESIGNS = [  # (letter, name)
    ("a", "13in Stock"), ("b", "14in Rally"), ("c", "15in Kragers"), ("d", "16in Billets"),
]
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
# specials: def "spcNN"; spc02/04/05 verified in saves, rest inferred (reversed exe table)
SPECIALS = [
    ("Radar Jammer", "spc01", "(inferred)"),
    ("NitrousOxide", "spc02", "verified"),
    ("Blower",       "spc03", "(inferred)"),
    ("X-Aust Brake", "spc04", "verified"),
    ("Structo Bmpr", "spc05", "verified"),
    ("Curb Feelers", "spc06", "(inferred)"),
    ("Mud Flaps",    "spc07", "(inferred)"),
    ("Heated Seats", "spc08", "(inferred)"),
    ("Cup Holders",  "spc09", "(inferred)"),
]
TYPE_NAMES = {2:"engine", 3:"suspension", 4:"brakes", 5:"wheel", 7:"weapon", 8:"weapon", 13:"special"}
KNOWN_TYPES = set(TYPE_NAMES)
# dropper-mounted weapons carry type 8, everything else observed is 7
def weapon_type(mount): return 8 if mount.startswith("drp") else 7

REC_LEN = 116

# ---------------------------------------------------------------- save parsing
def cstr(b): return b.split(b"\0")[0].decode("latin-1", "replace")

def plausible_name(b):
    s = b.split(b"\0")[0]
    return 2 < len(s) <= 29 and all(32 <= c < 127 for c in s)

def scan_inventory(d):
    """Signature-scan for 116-byte inventory records; robust to section layout."""
    recs, i = [], 0
    while i + REC_LEN <= len(d):
        typ = struct.unpack_from("<I", d, i + 30)[0]
        if (typ in KNOWN_TYPES and plausible_name(d[i:i+30])
                and d[i+34:i+46] == b"\0" * 12):
            cls  = cstr(d[i+46:i+59])
            dfl  = cstr(d[i+59:i+72])
            ok_ids = (cls == "" and dfl.startswith("spc")) or (
                cls != "" and all(c.isalnum() or c in "_." for c in cls + dfl))
            if ok_ids and dfl:
                recs.append(i)
                i += REC_LEN
                continue
        i += 2
    return recs

def rec_info(d, off):
    name = cstr(d[off:off+30])
    typ, = struct.unpack_from("<I", d, off+30)
    cls  = cstr(d[off+46:off+59])
    dfl  = cstr(d[off+59:off+72])
    dur, = struct.unpack_from("<I", d, off+76)
    wt,  = struct.unpack_from("<f", d, off+80)
    cond,grade = struct.unpack_from("<2I", d, off+96)
    return dict(off=off, name=name, type=typ, cls=cls, dfl=dfl,
                dur=dur, wt=wt, cond=cond, grade=grade)

def write_identity(d, off, name, typ, cls, dfl, dur, wt):
    d[off:off+30]      = name.encode("latin-1")[:30].ljust(30, b"\0")
    struct.pack_into("<I", d, off+30, typ)
    d[off+46:off+59]   = cls.encode()[:13].ljust(13, b"\0")
    d[off+59:off+72]   = dfl.encode()[:13].ljust(13, b"\0")
    struct.pack_into("<I", d, off+76, dur)
    struct.pack_into("<f", d, off+80, wt)

def parse_header(d):
    return cstr(d[0:20]), cstr(d[20:40]), cstr(d[40:56])

def parse_dir(path):
    """savegame.dir: u32 count, u32 active?, then 60-byte entries at 8+60k:
    name[20] @ +0x20, mission u32 @ +0x38 (the newest entry's mission dword is
    often truncated at EOF - report it as '?')."""
    out = {}
    try:
        d = open(path, "rb").read()
    except OSError:
        return out
    if len(d) < 8: return out
    count, = struct.unpack_from("<I", d, 0)
    for k in range(count):
        e = 8 + 60 * k
        if e + 0x20 + 20 > len(d): break
        nm = cstr(d[e+0x20:e+0x20+20])
        if not nm.startswith("save"): continue
        if e + 0x38 + 4 <= len(d):
            out[nm] = struct.unpack_from("<I", d, e+0x38)[0]
        else:
            out[nm] = "?"
    return out

# ---------------------------------------------------------------- catalog helpers
def catalog_for(rec):
    """Return list of (label, apply_args) the record may become."""
    t = rec["type"]
    if t == 2:  return [(f"{n:14} (dur {du}, wt {w:.0f})", (n, ty, c, df, du, w)) for n,c,df,ty,du,w in ENGINES]
    if t == 3:  return [(f"{n:14} (dur {du}, wt {w:.0f})", (n, ty, c, df, du, w)) for n,c,df,ty,du,w in SUSPENSIONS]
    if t == 4:  return [(f"{n:14} (dur {du}, wt {w:.0f})", (n, ty, c, df, du, w)) for n,c,df,ty,du,w in BRAKES]
    if t == 5:
        fam = rec["dfl"][6] if rec["dfl"].startswith("wauto_") and len(rec["dfl"]) > 6 else "1"
        return [(f"{n:14} (wauto_{fam}{l})", (n, 5, "whe01", f"wauto_{fam}{l}.wdf", WHEEL_DUR, WHEEL_WT))
                for l, n in WHEEL_DESIGNS]
    if t in (7, 8):
        return [(f"{n:17} [{m}] (dur {du}, wt {w:.0f})", (n, weapon_type(m), m, df, du, w))
                for n, m, df, du, w in WEAPONS]
    if t == 13:
        return [(f"{n:14} {tag}", (n, 13, "", df, 0, 0.0)) for n, df, tag in SPECIALS]
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

def list_saves(sdir):
    missions = parse_dir(os.path.join(sdir, "savegame.dir"))
    rows = []
    for fn in sorted(glob.glob(os.path.join(sdir, "save*.cmp"))):
        base = os.path.splitext(os.path.basename(fn))[0]
        try:
            d = open(fn, "rb").read()
            car, variant, _ = parse_header(d)
            n = len(scan_inventory(d))
        except OSError:
            car, variant, n = "?", "?", 0
        rows.append((base, fn, car, variant, missions.get(base, 0), n))
    return rows

# ---------------------------------------------------------------- UI
def backup_once(path):
    bak = path + ".pre-edit"
    if not os.path.exists(bak):
        shutil.copy2(path, bak)
        print(f"  (backup written: {os.path.basename(bak)})")

ARMOR_LABELS = ["front armor","right armor","left armor","rear armor",
                "front chassis","right chassis","left chassis","rear chassis"]

def split_sections(recs):
    """records run in 116-byte trains; the first train = van inventory (V), later
    trains = the repair order (R) - verified against the in-game garage forms."""
    van, repair = [], []
    cur = van
    for i, off in enumerate(recs):
        if i and off - recs[i-1] != REC_LEN:
            cur = repair
        cur.append(off)
    return van, repair

def show_save(d, recs):
    car, variant, mission = parse_header(d)
    armor = struct.unpack_from("<8I", d, 2044)
    print(f"\n  Car: {car}  |  {variant}  |  mission id: {mission}")
    print("  Armor (game shows tenths): " + ", ".join(
        f"{l} {v/10:.1f}" for l, v in zip(ARMOR_LABELS, armor)))
    eq = [cstr(d[1024+k*30:1024+k*30+30]) for k in range(14)]
    print(f"  On the car: {', '.join(n for n in eq if n)}")
    van, repair = split_sections(recs)
    print(f"  {'#':>3} {'':3} {'item':22} {'kind':10} {'class':6} {'def':13} {'dur':>4} {'cond':>5} {'grade':>5}")
    print(f"  {'-'*3} {'-'*3} {'-'*22} {'-'*10} {'-'*6} {'-'*13} {'-'*4} {'-'*5} {'-'*5}")
    for k, off in enumerate(recs):
        r = rec_info(d, off)
        kind = TYPE_NAMES.get(r["type"], f"type{r['type']}")
        loc = {1: "(C)", 2: "(C)", 3: "(R)", 4: "(V)"}.get(r["grade"], "(?)")
        print(f"  {k:>3} {loc:3} {r['name']:22} {kind:10} {r['cls']:6} {r['dfl']:13} {r['dur']:>4} {r['cond']:>5} {r['grade']:>5}")

def ask(prompt, valid=None):
    while True:
        s = input(prompt).strip()
        if valid is None or s in valid or (s and valid == "int" and s.lstrip("-").isdigit()):
            return s

def edit_record(d, recs, k):
    off = recs[k]
    while True:
        r = rec_info(d, off)
        print(f"\n  [{k}] {r['name']}  ({TYPE_NAMES.get(r['type'],'?')}, {r['dfl']})"
              f"  dur={r['dur']} cond={r['cond']} grade={r['grade']}")
        c = ask("  [s]wap item  [c]ondition  [g]rade  [b]ack > ", ("s","c","g","b"))
        if c == "b": return
        if c == "s":
            options = catalog_for(r)
            if not options:
                print("  no catalog for this type"); continue
            for i, (label, _) in enumerate(options):
                print(f"    {i:>2}  {label}")
            s = ask("  new item # (or blank to cancel) > ")
            if not s.isdigit() or int(s) >= len(options): continue
            name, typ, cls, dfl, dur, wt = options[int(s)][1]
            write_identity(d, off, name, typ, cls, dfl, dur, wt)
            if r["type"] != 13:
                struct.pack_into("<I", d, off+96, dur)   # fresh part: full points (location untouched)
            print(f"  -> now {name} ({dfl}), condition set to {dur if r['type']!=13 else r['cond']}/grade 4")
        if c == "c":
            s = ask(f"  condition value (current {r['cond']}, max-ish {r['dur'] or 'n/a'}) > ", "int")
            struct.pack_into("<I", d, off+96, max(0, int(s)))
        if c == "g":
            s = ask(f"  grade 1-4 (current {r['grade']}) > ", ("1","2","3","4"))
            struct.pack_into("<I", d, off+100, int(s))

def interactive(sdir):
    while True:
        rows = list_saves(sdir)
        if not rows:
            print(f"no save*.cmp in {sdir}"); return
        print(f"\nSaves in {sdir}:")
        for i, (base, fn, car, variant, mission, n) in enumerate(rows):
            print(f"  {i}  {base:9} mission {mission:>2}  {car} / {variant}  ({n} inventory items)")
        s = ask("\npick save # (or q) > ")
        if s.lower() == "q": return
        if not s.isdigit() or int(s) >= len(rows): continue
        base, fn, *_ = rows[int(s)]
        d = bytearray(open(fn, "rb").read())
        orig = bytes(d)
        recs = scan_inventory(d)
        while True:
            show_save(d, recs)
            cmd = ask("\nitem # to edit, [r]epair-all, [w]rite, [q]uit save > ")
            if cmd.lower() == "q":
                if bytes(d) != orig and ask("  discard changes? y/n > ", ("y","n")) == "n":
                    continue
                break
            if cmd.lower() == "r":
                fixed = 0
                for off in recs:
                    r = rec_info(d, off)
                    if r["type"] != 13 and r["dur"]:
                        struct.pack_into("<I", d, off+96, r["dur"]); fixed += 1
                print(f"  repaired {fixed} items to full condition/grade 4")
            elif cmd.lower() == "w":
                if bytes(d) == orig:
                    print("  no changes"); continue
                assert len(d) == len(orig), "size must never change"
                backup_once(fn)
                open(fn, "wb").write(d)
                orig = bytes(d)
                nd = sum(1 for a, b in zip(orig, bytes(d)) if a != b)
                print(f"  written: {fn}")
                print("  NOTE: if you edited the repo copy, run setup-saves.sh to install;"
                      " if you edited the live copy, run setup-saves.sh --backup to sync the repo.")
            elif cmd.isdigit() and int(cmd) < len(recs):
                edit_record(d, recs, int(cmd))

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dir", help="save directory (default: auto-find wrapper, then repo saves/)")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--dump", type=int, metavar="N", help="dump save slot N")
    a = ap.parse_args()

    dirs = find_save_dirs(a.dir)
    if not dirs:
        sys.exit("no save directories found (use --dir)")
    sdir = dirs[0]
    if len(dirs) > 1 and not (a.list or a.dump is not None):
        print("Save locations:")
        for i, dd in enumerate(dirs): print(f"  {i}  {dd}")
        s = ask("pick location # > ")
        sdir = dirs[int(s)] if s.isdigit() and int(s) < len(dirs) else dirs[0]

    if a.list:
        for base, fn, car, variant, mission, n in list_saves(sdir):
            print(f"{base:9} mission {mission:>2}  {car} / {variant}  ({n} items)")
        return
    if a.dump is not None:
        rows = list_saves(sdir)
        base, fn, *_ = rows[a.dump]
        d = open(fn, "rb").read()
        show_save(d, scan_inventory(d))
        return
    interactive(sdir)

if __name__ == "__main__":
    main()
