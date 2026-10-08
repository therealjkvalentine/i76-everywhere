#!/usr/bin/env python3
# One Deck layout (owner, 2026-10-08): point the "Interstate 76" library entry at the gamepad layout
# (controller_neptune_i76_pad.vdf) and remove the temporary "Interstate 76 (pad layer)" entry that
# add-pad-shortcut.py made on 2026-10-07 (its shortcut, its controller mapping, its artwork).
# RUN WITH STEAM SHUT DOWN. Idempotent; a backup beside every file it writes.
import importlib.util, os, re, shutil, time

here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("ats", os.path.join(here, "add-to-steam.py"))
ats = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ats)

BASE, OLD = "Interstate 76", "Interstate 76 (pad layer)"
TEMPLATE = "controller_neptune_i76_pad.vdf"
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
    # Steam renamed the entry to plain "Interstate 76" on its next save (seen on the owner's Deck 2026-10-08),
    # so it is recognised by its launch options, which only it had.
    def is_old(v):
        return ats.find(v, "AppName") == OLD or "I76_PROFILE=pad" in str(ats.find(v, "LaunchOptions") or "")
    old = [(k, v) for t, k, v in shortcuts if t == 0x00 and is_old(v)]
    if len(old) > 1:
        raise SystemExit("more than one pad-layer entry - sort it in Steam by hand")
    if old:
        old_top = ats.find(old[0][1], "appid") & 0xFFFFFFFF
        shortcuts[:] = [(t, k, v) for t, k, v in shortcuts if not (t == 0x00 and is_old(v))]
        backup(sc_path)
        open(sc_path, "wb").write(ats.dump_map(root))
        grid = os.path.join(ats.USERCFG, "grid")
        n = 0
        for f in os.listdir(grid) if os.path.isdir(grid) else []:
            if f.startswith(str(old_top)):
                os.remove(os.path.join(grid, f)); n += 1
        print("  removed '%s' (appid %d) and %d artwork images" % (OLD, old_top, n))
    else:
        print("  no '%s' entry" % OLD)

    cs = os.path.expanduser("~/.steam/steam/steamapps/common/Steam Controller Configs/%s/config/configset_controller_neptune.vdf" % ats.STEAM_USERID)
    body = open(cs, encoding="utf-8", errors="replace").read()
    new = re.sub(r'\n\t"%s"\n\t\{\n[^}]*\}' % re.escape(OLD.lower()), "", body)
    new, k = re.subn(r'(\n\t"%s"\n\t\{\n\t\t"template"\t\t")[^"]+(")' % re.escape(BASE.lower()), r"\g<1>%s\g<2>" % TEMPLATE, new)
    if k != 1:
        raise SystemExit("expected one '%s' template line in %s, found %d" % (BASE.lower(), cs, k))
    if new != body:
        backup(cs)
        open(cs, "w", encoding="utf-8").write(new)
    print("  controller layout for '%s': %s" % (BASE, TEMPLATE))

if __name__ == "__main__":
    main()
