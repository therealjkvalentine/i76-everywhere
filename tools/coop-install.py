#!/usr/bin/env python3
"""Install (or remove) the co-op campaign in an Interstate '76 game folder. docs/COOP.md.

    python3 tools/coop-install.py "<game folder>"            build + install
    python3 tools/coop-install.py "<game folder>" --remove   put everything back
    python3 tools/coop-install.py "<game folder>" --check    report what is installed

Builds the co-op missions from THIS folder's own campaign files (miss8\\ and miss16\\ T01..T17.MSN, nothing is
downloaded or shipped) with tools/coop-mission.py, and installs them as:
  - M41..M57.MSN = co-op T01..T17 (the campaign chain loads these in order, I76_COOP_CHAIN);
  - M01.MSN      = co-op T01, so the multiplayer arena "The Crater" starts the campaign. The original M01.MSN is kept
                   as M01.MSN.pre-coop and put back by --remove.
Every installed file gets a .coop marker next to it; --remove deletes only files with a marker. Run it with the game
closed, on every machine that plays (all machines need identical mission files). Then start the game with
I76_COOP_AI=1 and I76_COOP_CHAIN=1 (and optionally I76_COOP_DAMAGE=0.5) and host The Crater over IPX.
"""
import hashlib, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SUBS = ('miss8', 'miss16')


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


def install(game):
    built = 0
    for sub in SUBS:
        d = find(game, sub)
        if not d:
            sys.exit('no %s folder in %s' % (sub, game))
        for n in range(1, 18):
            src = find(d, 'T%02d.MSN' % n)
            if not src:
                sys.exit('missing %s/T%02d.MSN' % (sub, n))
            dst = os.path.join(d, 'M%02d.MSN' % (40 + n))
            if os.path.exists(dst) and not os.path.exists(dst + '.coop'):
                sys.exit('%s exists and is not ours - refusing' % dst)
            subprocess.run([sys.executable, os.path.join(HERE, 'coop-mission.py'), src, dst], check=True,
                           stdout=subprocess.DEVNULL)
            open(dst + '.coop', 'w').write('installed by tools/coop-install.py\n')
            built += 1
        m01 = find(d, 'M01.MSN') or os.path.join(d, 'M01.MSN')
        if os.path.exists(m01) and not os.path.exists(m01 + '.pre-coop'):
            os.replace(m01, m01 + '.pre-coop')
        with open(os.path.join(d, 'M41.MSN'), 'rb') as f:
            data = f.read()
        open(m01, 'wb').write(data)
        print('%s: M41..M57 built, M01 = co-op T01 (%s), original kept as M01.MSN.pre-coop' % (sub, md5(m01)))
    print('installed %d co-op missions. Start the game with I76_COOP_AI=1 I76_COOP_CHAIN=1 on every machine.' % built)


def remove(game):
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
        if os.path.exists(m01 + '.pre-coop'):
            os.replace(m01 + '.pre-coop', m01)
        print('%s: removed %d co-op files, M01 restored (%s)' % (sub, n, md5(m01) if os.path.exists(m01) else 'missing'))


def check(game):
    for sub in SUBS:
        d = find(game, sub)
        if not d:
            print('%s: missing' % sub)
            continue
        ours = [f[:-5] for f in os.listdir(d) if f.endswith('.coop')]
        m01 = find(d, 'M01.MSN')
        print('%s: %d co-op files, M01 %s, original kept: %s' % (sub, len(ours), md5(m01) if m01 else 'missing',
                                                                 os.path.exists((m01 or '') + '.pre-coop')))


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
