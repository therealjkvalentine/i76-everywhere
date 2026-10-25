#!/usr/bin/env python3
"""make-deck-patches.py - the Deck Kit's i76.exe / i76shell.dll patches (maintainer, PC). The Mac Kit's patch set
(tools/mac-kit/make-patches.py) with ONE step left out: u32x (USER32 imports renamed to u32x.dll in the exe and the shell).

Why (Deck kit test 2026-10-25): with u32x the proxy's pad menu finds no PeekMessageA to chain in either module ("exe PeekMessageA
NOT found", "i76shell.dll PeekMessageA NOT found") and its cursor map stands down for u32x, so on the Deck (no mouse; the left stick
drives the menu pointer) the menus could not be worked. The owner's Deck has run without u32x since 2026-07 with the proxy's own
cursor map + pad menu. Kept: Apply-Shell-Keys.ps1 + fix-shell-textentry.ps1 (the shell's key / text-entry fixes) and the Wine PIT
skip (0x499b25), exactly as make-patches.py does them. The arena patches (ADDON auto / coop) are copied from a make-patches.py
output folder unchanged.

    python deck/kit/tools/make-deck-patches.py --gog-gold <GOG Gold folder> --mac-patches <make-patches.py out> --out <dir>
Needs: Windows PowerShell 5.1, python bsdiff4 + pefile (as make-patches.py).
"""
import argparse, importlib.util, os, shutil, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
spec = importlib.util.spec_from_file_location('mkp', os.path.join(REPO, 'tools', 'mac-kit', 'make-patches.py'))
mkp = importlib.util.module_from_spec(spec); spec.loader.exec_module(mkp)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--gog-gold', required=True); ap.add_argument('--mac-patches', required=True); ap.add_argument('--out', required=True)
    a = ap.parse_args()
    import bsdiff4, pefile
    os.makedirs(a.out, exist_ok=True)
    work = tempfile.mkdtemp(prefix='deckkit-patches-'); g = os.path.join(work, 'gold')
    shutil.copytree(a.gog_gold, g)
    for n, want in (('i76.exe', '9a232dcc2c164648cff20c414c1f9698'), ('i76shell.dll', 'deb41008321cf018ba33c27bfbbfa074')):
        if mkp.md5(mkp.find(g, n)) != want: sys.exit('%s is not the GOG 2.1.0.17 file (%s)' % (n, want[:8]))
    mkp.ps(os.path.join(REPO, 'tools', 'patch-kit', 'Apply-Shell-Keys.ps1'), '-GameDir', g)
    mkp.ps(os.path.join(REPO, 'tools', 'fix-shell-textentry.ps1'), '-GameDir', g)
    exe = mkp.find(g, 'i76.exe')
    pe = pefile.PE(exe, fast_load=True); off = pe.get_offset_from_rva(0x499b25 - 0x400000); pe.close()
    b = bytearray(open(exe, 'rb').read())
    if bytes(b[off:off + 5]) != bytes.fromhex('e826feffff') or bytes(b[off + 5:off + 10]) != bytes.fromhex('3d66fdffff'):
        sys.exit("i76.exe: the probe call at 0x499b25 is not GOG 2.1.0.17's")
    b[off:off + 5] = bytes.fromhex('83c8ff9090'); open(exe, 'wb').write(b)
    for n in ('i76.exe', 'i76shell.dll'):
        if b'u32x' in open(mkp.find(g, n), 'rb').read().lower(): sys.exit('%s imports u32x - the step was not left out' % n)
    rows = []
    for n in ('i76.exe', 'i76shell.dll'):
        src, dst = mkp.find(a.gog_gold, n), mkp.find(g, n); name = n.split('.')[0]; p = os.path.join(a.out, name + '.bsdiff')
        bsdiff4.file_diff(src, dst, p); chk = tempfile.mktemp(); bsdiff4.file_patch(src, chk, p)
        assert mkp.md5(chk) == mkp.md5(dst), name; os.remove(chk)
        x = mkp.extra_bytes(p)
        if x > mkp.EXTRA_LIMIT: sys.exit('%s: %d extra bytes - refusing' % (name, x))
        rows.append('\t'.join(('gold', n, n, mkp.md5(src), mkp.md5(dst), name + '.bsdiff')))
        print('  %-14s %s -> %s  %6d B patch, %5d extra bytes' % (name, mkp.md5(src)[:8], mkp.md5(dst)[:8], os.path.getsize(p), x))
    for line in open(os.path.join(a.mac_patches, 'patches.txt')):
        f = line.rstrip('\n').split('\t')
        if line.startswith('#') or len(f) < 6 or f[0] != 'gold' or f[1] in ('i76.exe', 'i76shell.dll'): continue
        shutil.copyfile(os.path.join(a.mac_patches, f[5]), os.path.join(a.out, f[5])); rows.append('\t'.join(f))
    with open(os.path.join(a.out, 'patches.txt'), 'w', newline='\n') as o:
        o.write("# I'76 Deck Kit patches (deck/kit/tools/make-deck-patches.py: the Mac Kit's set without u32x): app, target, source, source md5, target md5, patch\n")
        o.write('\n'.join(rows) + '\n')
    shutil.rmtree(work, ignore_errors=True)
    print('%d patches -> %s' % (len(rows), a.out))


if __name__ == '__main__':
    main()
