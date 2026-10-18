#!/usr/bin/env python3
"""Install (or remove) the co-op campaign in an Interstate '76 game folder. docs/COOP.md.

    python3 tools/coop-install.py "<game folder>"            build + install
    python3 tools/coop-install.py "<game folder>" --remove   put everything back
    python3 tools/coop-install.py "<game folder>" --check    report what is installed

Builds the co-op missions from THIS folder's own campaign files (miss16\\T01..T17.MSN, nothing is downloaded or
shipped) with tools/coop-mission.py and installs them as their own multiplayer arenas:

  ADDON\\COOP01.LVL .. COOP17.LVL = co-op T01..T17, titled "Co-op Scene 1" .. "Co-op Scene 17".

The shell lists every ADDON\\*.lvl after the 15 stock arenas (i76shell 0x10027c80, the builder's documented addon-map
route), so the co-op missions appear in MULTI MELEE > HOST under their own names and no stock arena changes. A joiner
loads the mission file the HOST names; for an addon .lvl its shell checks that it has the file and that the CRC-32
matches the host's, and says so if not ("You don't have mission COOP01.LVL!"), instead of quietly loading another
mission (docs/records/COOP-LIST-ENTRIES-2026-10-18.md). The campaign chain (I76_COOP_CHAIN) loads coop02 .. coop17.

The miss16 variants are used (sky / palette / horizon files of the 16-bit hardware renderers every pack machine runs);
one .lvl in ADDON serves both miss8 and miss16 modes.

The older layout (miss8\\ and miss16\\ M41..M57.MSN plus M01.MSN = co-op T01 in place of "The Crater") is removed and
the original M01.MSN put back, on install and on --remove. Every installed file gets a .coop marker next to it;
--remove deletes only files with a marker. Run it with the game closed, on every machine that plays (all machines need
identical mission files). Then start the game with I76_COOP_AI=1 and I76_COOP_CHAIN=1 (and optionally
I76_COOP_DAMAGE=0.5) and host a "Co-op Scene N" arena over IPX.
"""
import hashlib, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SUBS = ('miss8', 'miss16')          # where the old layout lived
SRC_SUB = 'miss16'                  # the campaign files the .lvl files are built from
COUNT = 17


def md5(p):
    return hashlib.md5(open(p, 'rb').read()).hexdigest()[:8]


def find(folder, name):
    """Case-insensitive file lookup (the GOG install uses upper case, Wine prefixes may not)."""
    if not os.path.isdir(folder):
        return None
    for f in os.listdir(folder):
        if f.lower() == name.lower():
            return os.path.join(folder, f)
    return None


def remove_old(game):
    """The 2026-10-07 layout: M41..M57 in miss8/miss16 and M01 = co-op T01 ("The Crater")."""
    for sub in SUBS:
        d = find(game, sub)
        if not d:
            continue
        n = 0
        for f in sorted(os.listdir(d)):
            if f.endswith('.coop'):
                target = os.path.join(d, f[:-5])
                if os.path.exists(target):
                    os.remove(target)
                os.remove(os.path.join(d, f))
                n += 1
        m01 = find(d, 'M01.MSN') or os.path.join(d, 'M01.MSN')
        restored = os.path.exists(m01 + '.pre-coop')
        if restored:
            os.replace(m01 + '.pre-coop', m01)
        if n or restored:
            print('%s: old layout removed (%d co-op files), M01 restored (%s)' % (sub, n, md5(m01)))


def install(game):
    src_dir = find(game, SRC_SUB)
    if not src_dir:
        sys.exit('no %s folder in %s' % (SRC_SUB, game))
    addon = find(game, 'ADDON') or os.path.join(game, 'ADDON')
    os.makedirs(addon, exist_ok=True)
    remove_old(game)
    for n in range(1, COUNT + 1):
        src = find(src_dir, 'T%02d.MSN' % n)
        if not src:
            sys.exit('missing %s/T%02d.MSN' % (SRC_SUB, n))
        dst = os.path.join(addon, 'COOP%02d.LVL' % n)
        if os.path.exists(dst) and not os.path.exists(dst + '.coop'):
            sys.exit('%s exists and is not ours - refusing' % dst)
        subprocess.run([sys.executable, os.path.join(HERE, 'coop-mission.py'), src, dst,
                        '--title', 'Co-op Scene %d' % n], check=True, stdout=subprocess.DEVNULL)
        open(dst + '.coop', 'w').write('installed by tools/coop-install.py\n')
    print('ADDON: COOP01..COOP%02d.LVL built from %s ("Co-op Scene 1".."Co-op Scene %d"); COOP01 %s' %
          (COUNT, SRC_SUB, COUNT, md5(os.path.join(addon, 'COOP01.LVL'))))
    print('Start the game with I76_COOP_AI=1 I76_COOP_CHAIN=1 on every machine and host "Co-op Scene N".')


def remove(game):
    remove_old(game)
    addon = find(game, 'ADDON')
    n = 0
    if addon:
        for f in sorted(os.listdir(addon)):
            if f.endswith('.coop'):
                target = os.path.join(addon, f[:-5])
                if os.path.exists(target):
                    os.remove(target)
                os.remove(os.path.join(addon, f))
                n += 1
    print('ADDON: removed %d co-op files' % n)


def check(game):
    addon = find(game, 'ADDON')
    ours = sorted(f[:-5] for f in os.listdir(addon) if f.endswith('.coop')) if addon else []
    print('ADDON: %d co-op arenas %s' % (len(ours), ', '.join('%s %s' % (f, md5(os.path.join(addon, f)))
                                                              for f in ours if os.path.exists(os.path.join(addon, f)))))
    for sub in SUBS:
        d = find(game, sub)
        if not d:
            print('%s: missing' % sub)
            continue
        old = [f for f in os.listdir(d) if f.endswith('.coop')]
        m01 = find(d, 'M01.MSN')
        print('%s: old-layout files %d, M01 %s%s' % (sub, len(old), md5(m01) if m01 else 'missing',
                                                     ' (still the co-op T01: run install or --remove)'
                                                     if m01 and os.path.exists(m01 + '.pre-coop') else ''))


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    g = sys.argv[1]
    if '--remove' in sys.argv:
        remove(g)
    elif '--check' in sys.argv:
        check(g)
    else:
        install(g)
