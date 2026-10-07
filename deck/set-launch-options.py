#!/usr/bin/env python3
# Set LaunchOptions on one existing non-Steam shortcut. RUN WITH STEAM SHUT DOWN
# (Steam rewrites shortcuts.vdf from memory on exit and would undo this).
#
#   python3 set-launch-options.py "Interstate 76" '"/home/deck/Games/Interstate76/i76-deck-launch.sh" %command% -glide'
#
# Reuses add-to-steam.py's binary-VDF reader/writer and its round-trip self-test;
# keeps a timestamped backup beside the file. Touches nothing but that one field.
import importlib.util, os, shutil, sys, time

here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("ats", os.path.join(here, "add-to-steam.py"))
ats = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ats)            # module level only detects the user + paths

def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__ or "usage: set-launch-options.py <AppName> <options>")
    name, opts = sys.argv[1], sys.argv[2]
    path = os.path.join(ats.USERCFG, "shortcuts.vdf")
    raw = open(path, "rb").read()
    root, _ = ats.parse_map(raw, 0)
    if ats.dump_map(root) != raw:
        raise SystemExit("VDF round-trip mismatch - not writing")
    hits = 0
    for t, k, entry in ats.find(root, "shortcuts"):
        if t != 0x00:
            continue
        if (ats.find(entry, "AppName") or ats.find(entry, "appname")) != name:
            continue
        for i, (et, ek, ev) in enumerate(entry):
            if ek.lower() == "launchoptions":
                print("  %s: LaunchOptions %r -> %r" % (name, ev, opts))
                entry[i] = (0x01, ek, opts)
                hits += 1
    if hits != 1:
        raise SystemExit("expected exactly one '%s' shortcut with LaunchOptions, found %d" % (name, hits))
    shutil.copy2(path, path + ".i76bak-" + time.strftime("%Y%m%d-%H%M%S"))
    open(path, "wb").write(ats.dump_map(root))
    print("  shortcuts.vdf written (backup beside it)")

if __name__ == "__main__":
    main()
