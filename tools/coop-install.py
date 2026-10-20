#!/usr/bin/env python3
"""Install (or remove) the co-op campaign and the auto-melee scenarios as network arenas. docs/COOP.md.

    python3 tools/coop-install.py "<game folder>"            build + install
    python3 tools/coop-install.py "<game folder>" --remove   put everything back
    python3 tools/coop-install.py "<game folder>" --check    report what is installed

Builds the missions from THIS folder's own files (miss16\\T01..T17.MSN and S01..S07.MSN, nothing is downloaded or
shipped) with tools/coop-mission.py and installs them as their own multiplayer arenas:

  ADDON\\auto01.lvl .. auto07.lvl = the 7 single-player auto-melee scenarios in the game's own scenario order (the
                                  shell's table 0x1004b7e0), titled "<stock name> (Scenario)", e.g.
                                  "Oil Well Well (Scenario)" (SCENARIOS below)
  ADDON\\ai_hs2.lvl, ai_hs4.lvl, ai_hs6.lvl = AI melee: "Hope Springs (2 AI)" / "(4 AI)" / "(6 AI)", a stock arena plus N
                                  AI cars the host's proxy runs (tools/aimelee-mission.py, its own .aimelee markers;
                                  records/AI-MELEE-M1-2026-10-19.md)
  ADDON\\coop01.lvl .. coop17.lvl = co-op T01..T17, titled "Scene 1 (Co-op)" .. "Scene 17 (Co-op)" (the trip missions
                                  carry no title of their own; "Scene N" is the game's own name for them, bookmarks);
                                  3 joiner start points and 3 parked copies of every enemy car (co-op scaling)

Owner, 2026-10-19: the name first, then the kind in parentheses. Titles longer than 15 characters grow the WRLD body
(coop-mission.py --title, up to 31 characters).

The names are LOWER CASE on purpose: both shells test the extension with a case-sensitive compare against ".lvl"
(host 0x1004c6ec, joiner 0x1004c7dc); "COOP01.LVL" skipped the file and CRC check on both ends (measured 2026-10-18:
host CRC slot 0, a join went through unchecked).

The shell lists every ADDON\\*.lvl after the 15 stock arenas (i76shell 0x10027c80, the builder's documented addon-map
route) in findfirst order, alphabetical on NTFS, so auto* comes before coop*: the host list reads the 15 stock
arenas, the 7 scenarios, the 17 co-op scenes. A joiner loads the mission file the HOST names; for an addon .lvl its
shell checks that it has the file and that the CRC-32 matches the host's, and says so if not ("You don't have mission
coop01.lvl!"), instead of quietly loading another mission (docs/records/COOP-LIST-ENTRIES-2026-10-18.md). The
campaign chain (I76_COOP_CHAIN) loads coop02 .. coop17; it never touches autoNN.lvl.

A scenario is the stock mission plus SCEN_SPAWNS spawn points beside the scenario's own car (the host drives that
car, joiners take the spawn points); its script is not changed. With I76_COOP_CHAIN=1 a joiner respawns by itself
after a death, as in a co-op scene; the host does not: the script watches the host's car (entity "user"), so the
host's death (or any other loss) is the scenario's loss and the proxy reloads the same scenario for everybody; a win
ends the game normally. No chain to another file (records/COOP-LIST-ENTRIES-2026-10-18.md section 8).

The miss16 variants are used (sky / palette / horizon files of the 16-bit hardware renderers every pack machine runs);
one .lvl in ADDON serves both miss8 and miss16 modes.

The older layout (miss8\\ and miss16\\ M41..M57.MSN plus M01.MSN = co-op T01 in place of "The Crater") is removed and
the original M01.MSN put back, on install and on --remove. Every installed file gets a .coop marker next to it;
--remove deletes only files with a marker. Run it with the game closed, on every machine that plays (all machines need
identical mission files). Then start the game with I76_COOP_AI=1 and I76_COOP_CHAIN=1 (and optionally
I76_COOP_DAMAGE=0.5) and host a "... (Co-op)" or "... (Scenario)" arena over IPX.
"""
import hashlib, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SUBS = ('miss8', 'miss16')          # where the old layout lived
SRC_SUB = 'miss16'                  # the campaign files the .lvl files are built from
COUNT = 17
COOP_TITLE = 'Scene %d (Co-op)'
# (file, source mission, stock title) in the order of the shell's scenario table 0x1004b7e0 (AUTO MELEE > SCENARIO)
SCENARIOS = (('auto01', 'S03', 'Oil Well Well'), ('auto02', 'S02', 'Mondo Burger'), ('auto03', 'S04', 'Seminole'),
             ('auto04', 'S05', 'Pretty Bus'), ('auto05', 'S06', 'Race No Shoot'), ('auto06', 'S01', 'Trailer Pk. Madness'),
             ('auto07', 'S07', 'Milk Toast'))
SCEN_TITLE = '%s (Scenario)'
SCEN_SPAWNS = 3                     # host (the scenario's car) + 3 joiners = the host form's default NO. DRIVERS 4
COOP_SPAWNS = 3                     # the same for the co-op scenes (was 2 until 2026-10-20: a 4th human had no start point)
COOP_COPIES = 3                     # co-op scaling: parked copies of every enemy car, one per joiner up to 3 (coop-mission.py
                                    # --copies, proxy I76_COOP_SCALE; records/MP-OVERNIGHT-2026-10-20.md)


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


def build(addon, name, src, args):
    dst = os.path.join(addon, name + '.lvl')
    old = find(addon, name + '.lvl')
    mark = find(addon, name + '.lvl.coop')
    if old and not mark:
        sys.exit('%s exists and is not ours - refusing' % old)
    if old:                                          # ours: delete first, NTFS keeps an old name's case on overwrite
        os.remove(old)
        os.remove(mark)
    subprocess.run([sys.executable, os.path.join(HERE, 'coop-mission.py'), src, dst] + args, check=True,
                   stdout=subprocess.DEVNULL)
    open(dst + '.coop', 'w').write('installed by tools/coop-install.py\n')
    return dst


def install(game):
    src_dir = find(game, SRC_SUB)
    if not src_dir:
        sys.exit('no %s folder in %s' % (SRC_SUB, game))
    addon = find(game, 'ADDON') or os.path.join(game, 'ADDON')
    os.makedirs(addon, exist_ok=True)
    remove_old(game)
    for name, mission, title in SCENARIOS:
        src = find(src_dir, mission + '.MSN')
        if not src:
            sys.exit('missing %s/%s.MSN' % (SRC_SUB, mission))
        dst = build(addon, name, src, ['--title', SCEN_TITLE % title, '--count', str(SCEN_SPAWNS)])
        print('ADDON: %s.lvl = %s "%s", %s' % (name, mission, SCEN_TITLE % title, md5(dst)))
    for n in range(1, COUNT + 1):
        src = find(src_dir, 'T%02d.MSN' % n)
        if not src:
            sys.exit('missing %s/T%02d.MSN' % (SRC_SUB, n))
        build(addon, 'coop%02d' % n, src, ['--title', COOP_TITLE % n, '--count', str(COOP_SPAWNS), '--copies', str(COOP_COPIES)])
    print('ADDON: coop01..coop%02d.lvl built from %s ("%s".."%s"); coop01 %s' %
          (COUNT, SRC_SUB, COOP_TITLE % 1, COOP_TITLE % COUNT, md5(os.path.join(addon, 'coop01.lvl'))))
    # AI melee arenas "Hope Springs (2 AI)" .. (tools/aimelee-mission.py ARENAS, records/AI-MELEE-M1-2026-10-19.md)
    subprocess.run([sys.executable, os.path.join(HERE, 'aimelee-mission.py'), '--install', game], check=True)
    print('Start the game with I76_COOP_AI=1 I76_COOP_CHAIN=1 on every machine and host a "(Co-op)", "(Scenario)" or "(N AI)" arena.')


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
    print('ADDON: removed %d co-op / scenario files' % n)
    subprocess.run([sys.executable, os.path.join(HERE, 'aimelee-mission.py'), '--remove', game], check=True)


def check(game):
    addon = find(game, 'ADDON')
    ours = sorted(f[:-5] for f in os.listdir(addon) if f.endswith('.coop')) if addon else []
    print('ADDON: %d co-op / scenario arenas %s' % (len(ours), ', '.join('%s %s' % (f, md5(os.path.join(addon, f)))
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
