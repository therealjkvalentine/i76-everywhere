#!/usr/bin/env python3
# Register Interstate '76 as a non-Steam game on the Deck: append to shortcuts.vdf
# (binary KeyValues, no deps), set GE-Proton compat mapping, place library artwork
# and the controller config. SAFE: round-trip self-test before writing, backups first.
# RUN WITH STEAM SHUT DOWN.
import os, sys, zlib, struct, shutil, glob, re, time

def _detect_userid():
    env = os.environ.get("STEAM_USERID")
    if env: return env
    base = os.path.expanduser("~/.steam/steam/userdata")
    cands = [d for d in (os.listdir(base) if os.path.isdir(base) else [])
             if d.isdigit() and d != "0"
             and os.path.exists(os.path.join(base, d, "config", "shortcuts.vdf"))]
    if not cands:
        cands = [d for d in os.listdir(base) if d.isdigit() and d != "0"]
    if not cands:
        raise SystemExit("no Steam user found under userdata/")
    # newest localconfig.vdf wins (most recently used account)
    cands.sort(key=lambda d: os.path.getmtime(os.path.join(base, d, "config", "localconfig.vdf"))
               if os.path.exists(os.path.join(base, d, "config", "localconfig.vdf")) else 0,
               reverse=True)
    return cands[0]

STEAM_USERID = _detect_userid()
USERCFG = os.path.expanduser(f"~/.steam/steam/userdata/{STEAM_USERID}/config")
STEAMCFG = os.path.expanduser("~/.steam/steam/config")
TEMPLATES = os.path.expanduser("~/.steam/steam/controller_base/templates")
BUNDLE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAMEDIR = os.path.expanduser("~/Games/Interstate76/game")
EXE = os.path.join(GAMEDIR, "i76.exe")
NAME = "Interstate 76"
def _detect_compat():
    env = os.environ.get("I76_COMPAT")
    if env: return env
    ct = os.path.expanduser("~/.steam/steam/compatibilitytools.d")
    ge = sorted([d for d in (os.listdir(ct) if os.path.isdir(ct) else [])
                 if d.startswith("GE-Proton")], reverse=True)
    return ge[0] if ge else "proton_experimental"

COMPAT = _detect_compat()

# ---------- binary VDF (KeyValues) ----------
def read_str(b, i):
    j = b.index(0, i); return b[i:j].decode("utf-8", "replace"), j+1
def parse_map(b, i):
    d = []
    while True:
        t = b[i]; i += 1
        if t == 0x08: return d, i
        key, i = read_str(b, i)
        if t == 0x00:
            v, i = parse_map(b, i); d.append((0x00, key, v))
        elif t == 0x01:
            v, i = read_str(b, i); d.append((0x01, key, v))
        elif t == 0x02:
            v = struct.unpack("<i", b[i:i+4])[0]; i += 4; d.append((0x02, key, v))
        else:
            raise ValueError(f"bad type {t} at {i}")
def dump_map(d):
    out = bytearray()
    for t, key, v in d:
        out.append(t); out += key.encode("utf-8") + b"\x00"
        if t == 0x00: out += dump_map(v)
        elif t == 0x01: out += v.encode("utf-8") + b"\x00"
        elif t == 0x02: out += struct.pack("<i", v)
    out.append(0x08); return bytes(out)

def find(d, key):
    for t,k,v in d:
        if k.lower()==key.lower(): return v
    return None

# ---------- appid ----------
def shortcut_ids(exe, name):
    # steam-rom-manager / BoilR algorithm
    key = ('"%s"%s' % (exe, name)).encode("utf-8")
    top = (zlib.crc32(key) & 0xFFFFFFFF) | 0x80000000    # unsigned 32-bit (grid art id)
    signed = top - 0x100000000                            # signed int32 for the "appid" field
    return top, signed

def main():
    sc_path = os.path.join(USERCFG, "shortcuts.vdf")
    raw = open(sc_path, "rb").read()
    # parse: root map has one entry "shortcuts" -> map of indexed shortcuts
    root, _ = parse_map(raw, 0)
    # SELF-TEST round trip
    if dump_map(root) != raw:
        print("!! VDF round-trip mismatch - ABORT (won't risk corrupting shortcuts.vdf)")
        sys.exit(2)
    print("round-trip OK; existing shortcuts preserved")

    shortcuts = find(root, "shortcuts")
    # already present?
    existing_idx = None
    for t,k,v in shortcuts:
        if t==0x00 and (find(v,"AppName")==NAME or find(v,"appname")==NAME):
            existing_idx = k
    top, signed = shortcut_ids(EXE, NAME)
    entry = [
        (0x02,"appid",signed),
        (0x01,"AppName",NAME),
        (0x01,"Exe",'"%s"'%EXE),
        (0x01,"StartDir",'"%s"'%GAMEDIR),
        (0x01,"icon",os.path.join(USERCFG,"grid","%d_icon.png"%top)),
        (0x01,"ShortcutPath",""),
        (0x01,"LaunchOptions","-glide"),
        (0x02,"IsHidden",0),(0x02,"AllowDesktopConfig",1),(0x02,"AllowOverlay",1),
        (0x02,"OpenVR",0),(0x02,"Devkit",0),(0x01,"DevkitGameID",""),
        (0x02,"DevkitOverrideAppID",0),(0x02,"LastPlayTime",0),(0x01,"FlatpakAppID",""),
        (0x00,"tags",[]),
    ]
    if existing_idx is not None:
        shortcuts[:] = [(t,k,(entry if k==existing_idx else v)) for t,k,v in shortcuts]
        print(f"updated existing shortcut idx {existing_idx}")
    else:
        idx = str(len([1 for t,k,v in shortcuts if t==0x00]))
        shortcuts.append((0x00, idx, entry))
        print(f"appended shortcut idx {idx}")

    shutil.copy2(sc_path, sc_path+".i76bak")
    open(sc_path,"wb").write(dump_map(root))
    print(f"shortcuts.vdf written (appid unsigned={top}, signed={signed})")

    # ---------- artwork ----------
    grid = os.path.join(USERCFG,"grid"); os.makedirs(grid, exist_ok=True)
    art = os.path.join(BUNDLE,"artwork")
    pairs = [("capsule_p.png","%dp.png"%top),("header.png","%d.png"%top),
             ("hero.png","%d_hero.png"%top),("logo.png","%d_logo.png"%top),
             ("icon.png","%d_icon.png"%top)]
    for src,dst in pairs:
        s=os.path.join(art,src)
        if os.path.exists(s): shutil.copy2(s, os.path.join(grid,dst)); print("  art:",dst)

    # ---------- compat tool mapping (text config.vdf) ----------
    cfg_path=os.path.join(STEAMCFG,"config.vdf")
    try:
        cfg=open(cfg_path,encoding="utf-8").read()
        if '"CompatToolMapping"' in cfg and ('"%d"'%top) not in cfg:
            block='\t\t\t\t\t"%d"\n\t\t\t\t\t{\n\t\t\t\t\t\t"name"\t\t"%s"\n\t\t\t\t\t\t"config"\t\t""\n\t\t\t\t\t\t"priority"\t\t"250"\n\t\t\t\t\t}\n'%(top,COMPAT)
            cfg=re.sub(r'("CompatToolMapping"\s*\{\n)', r'\1'+block, cfg, count=1)
            shutil.copy2(cfg_path, cfg_path+".i76bak"); open(cfg_path,"w",encoding="utf-8").write(cfg)
            print(f"compat mapping -> {COMPAT}")
        else:
            print("compat mapping already present or CompatToolMapping missing (set Proton in UI)")
    except Exception as e:
        print("compat mapping skipped:", e)

    # ---------- controller config template ----------
    cc=os.path.join(BUNDLE,"config","controller_neptune_i76.vdf")
    if os.path.exists(cc) and os.path.isdir(TEMPLATES):
        shutil.copy2(cc, os.path.join(TEMPLATES,"controller_neptune_i76.vdf"))
        print("controller template installed (selectable in-game as 'Interstate 76 (full driving+combat)')")
    # ---------- ZERO-TAP controller apply (Steam ROM Manager mechanism) ----------
    # configset_controller_neptune.vdf maps lowercased app name -> template file.
    try:
        csdir = os.path.expanduser(
            f"~/.steam/steam/steamapps/common/Steam Controller Configs/{STEAM_USERID}/config")
        os.makedirs(csdir, exist_ok=True)
        cs = os.path.join(csdir, "configset_controller_neptune.vdf")
        key = NAME.lower()
        entry = '\t"%s"\n\t{\n\t\t"template"\t\t"controller_neptune_i76.vdf"\n\t}\n' % key
        if os.path.exists(cs):
            body = open(cs, encoding="utf-8", errors="replace").read()
            if key not in body.lower():
                body = body.rstrip()
                if body.endswith("}"):
                    body = body[:-1] + entry + "}\n"
                shutil.copy2(cs, cs + ".i76bak")
                open(cs, "w", encoding="utf-8").write(body)
                print("controller config AUTO-APPLIED via configset (zero taps)")
            else:
                print("configset already maps the app")
        else:
            open(cs, "w", encoding="utf-8").write(
                '"controller_config"\n{\n' + entry + "}\n")
            print("configset created; controller config AUTO-APPLIED (zero taps)")
    except Exception as e:
        print("configset step skipped:", e, "- apply the template manually (3 taps)")
    print(f"DONE (user {STEAM_USERID}, compat {COMPAT}). Restart Steam.")

if __name__=="__main__": main()
