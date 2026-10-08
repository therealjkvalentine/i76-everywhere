#!/usr/bin/env python3
# Add the second library entry, "Interstate 76 (pad layer)", next to the existing "Interstate 76".
# Same game folder and Proton; its launch options set I76_PROFILE=pad (i76-deck-launch.sh then starts
# the shared pad layer and puts the shared input.map in place), and its controller layout is the v9
# template (controller_neptune_i76_pad.vdf). RUN WITH STEAM SHUT DOWN. Idempotent: an existing entry of
# that name is updated in place. Backups beside every file written.
import importlib.util, os, re, shutil, sys, time

here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("ats", os.path.join(here, "add-to-steam.py"))
ats = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ats)

BASE = "Interstate 76"
NAME = "Interstate 76 (pad layer)"
TEMPLATE = "controller_neptune_i76_pad.vdf"
WRAPPER = os.path.expanduser("~/Games/Interstate76/i76-deck-launch.sh")
OPTS = 'I76_PROFILE=pad "%s" %%command%% -glide' % WRAPPER
STAMP = time.strftime("%Y%m%d-%H%M%S")

def backup(path):
    if os.path.exists(path):
        shutil.copy2(path, "%s.i76bak-%s" % (path, STAMP))

def main():
    sc_path = os.path.join(ats.USERCFG, "shortcuts.vdf")
    raw = open(sc_path, "rb").read()
    root, _ = ats.parse_map(raw, 0)
    if ats.dump_map(root) != raw:
        raise SystemExit("VDF round-trip mismatch - not writing")
    shortcuts = ats.find(root, "shortcuts")
    base = [v for t, k, v in shortcuts if t == 0x00 and ats.find(v, "AppName") == BASE]
    if len(base) != 1:
        raise SystemExit("expected one '%s' shortcut, found %d" % (BASE, len(base)))
    base = base[0]
    base_top = (ats.find(base, "appid") & 0xFFFFFFFF)
    top, signed = ats.shortcut_ids(ats.EXE, NAME)
    entry = []
    for t, k, v in base:
        if k == "appid": v = signed
        elif k == "AppName": v = NAME
        elif k.lower() == "launchoptions": v = OPTS
        elif k == "icon": v = os.path.join(ats.USERCFG, "grid", "%d_icon.png" % top)
        elif k == "LastPlayTime": v = 0
        entry.append((t, k, v))
    idx = None
    for t, k, v in shortcuts:
        if t == 0x00 and ats.find(v, "AppName") == NAME: idx = k
    if idx is None:
        idx = str(max([int(k) for t, k, v in shortcuts if t == 0x00 and k.isdigit()] + [-1]) + 1)
        shortcuts.append((0x00, idx, entry))
        print("  shortcut appended: idx %s, appid %d" % (idx, top))
    else:
        shortcuts[:] = [(t, k, (entry if k == idx else v)) for t, k, v in shortcuts]
        print("  shortcut updated: idx %s, appid %d" % (idx, top))
    backup(sc_path)
    open(sc_path, "wb").write(ats.dump_map(root))

    # artwork: the base entry's grid images under the new id
    grid = os.path.join(ats.USERCFG, "grid")
    n = 0
    for f in os.listdir(grid) if os.path.isdir(grid) else []:
        m = re.match(r"^%d(p|_hero|_logo|_icon)?\.(png|jpg)$" % base_top, f)
        if m:
            shutil.copy2(os.path.join(grid, f), os.path.join(grid, f.replace(str(base_top), str(top), 1))); n += 1
    print("  artwork: %d images copied" % n)

    # Proton: the same compat tool as the base entry
    cfg_path = os.path.join(ats.STEAMCFG, "config.vdf")
    cfg = open(cfg_path, encoding="utf-8").read()
    m = re.search(r'"%d"\s*\{\s*"name"\s*"([^"]+)"' % base_top, cfg)
    tool = m.group(1) if m else ats.COMPAT
    if ('"%d"' % top) not in cfg and '"CompatToolMapping"' in cfg:
        block = '\t\t\t\t\t"%d"\n\t\t\t\t\t{\n\t\t\t\t\t\t"name"\t\t"%s"\n\t\t\t\t\t\t"config"\t\t""\n\t\t\t\t\t\t"priority"\t\t"250"\n\t\t\t\t\t}\n' % (top, tool)
        backup(cfg_path)
        cfg = re.sub(r'("CompatToolMapping"\s*\{\n)', lambda mm: mm.group(1) + block, cfg, count=1)
        open(cfg_path, "w", encoding="utf-8").write(cfg)
        print("  compat tool: %s" % tool)
    else:
        print("  compat tool: already mapped (or no CompatToolMapping section)")

    # controller layout: the v9 template, applied with zero taps (Steam ROM Manager's configset)
    csdir = os.path.expanduser("~/.steam/steam/steamapps/common/Steam Controller Configs/%s/config" % ats.STEAM_USERID)
    cs = os.path.join(csdir, "configset_controller_neptune.vdf")
    key = NAME.lower()
    body = open(cs, encoding="utf-8", errors="replace").read() if os.path.exists(cs) else '"controller_config"\n{\n}\n'
    if ('"%s"' % key) not in body.lower():
        body = body.rstrip()
        body = body[:-1] + '\t"%s"\n\t{\n\t\t"template"\t\t"%s"\n\t}\n}\n' % (key, TEMPLATE)
        backup(cs)
        open(cs, "w", encoding="utf-8").write(body)
        print("  controller layout: %s applied to '%s'" % (TEMPLATE, NAME))
    else:
        print("  controller layout: already mapped")

if __name__ == "__main__":
    main()
