#!/usr/bin/env python3
"""make-patches.py - the I'76 Mac Kit's binary patches, built from pristine GOG installs by this repo's own tools (maintainer, PC).

    python tools/mac-kit/make-patches.py --gog-gold <GOG Gold folder> --gog-nitro <GOG Nitro Pack folder> --out <dir>

The Mac Kit (tools/mac-kit/i76-mac-kit.sh) cannot run the PowerShell / Python patchers on a stock Mac (no PowerShell, and
python3 is only a stub until the Xcode tools are installed), and the patched files cannot be shipped: they are GOG's files.
So the patched files are made HERE, on the PC, by exactly the steps the Windows Patch Kit / Build-From-GOG run, and shipped
as BSDIFF40 patches against the user's own GOG file (macOS has /usr/bin/bspatch). A patch holds only the difference: the
"extra" bytes (new bytes not copied from the source) are counted and printed per patch, and the run refuses a patch whose
extra block is more than 64 KiB (a sign that it would carry game data).

  Gold  i76.exe       Apply-Shell-Keys.ps1 + fix-shell-textentry.ps1 (shell), then u32x\\deploy-u32x.ps1 -U32xDll u32x_full.dll
        i76shell.dll  (import USER32 -> u32x in both); the Patch Kit's result on GOG 2.1.0.17: i76.exe 64165126, shell 64923d95;
                      + for Wine only, i76.exe's PIT probe call skipped (5 bytes at 0x499b25, see below)
        ADDON\\auto01..07.lvl, coop01..17.lvl   tools/coop-install.py's builds (coop-mission.py), from miss16\\S0n / T0n .MSN.
                      The Hope Springs (N AI) arenas are left out, as on the Macs since 2026-10-25 (NITRO-LAN-WEEKEND.md).
  Nitro nitshell.dll  tools/patch-nitshell-f7.py then tools/patch-nitshell-modals.py (f804f50d -> a32ffba6, the Macs' shell)

Writes <out>/<name>.bsdiff and <out>/patches.txt: one line per patch, tab separated:
    app  target path (game-relative, / separators)  source path  source md5  target md5  patch file
Needs: Windows PowerShell 5.1 (the .ps1 steps), python bsdiff4 (pip install --user bsdiff4).
"""
import argparse, bz2, hashlib, importlib.util, os, shutil, struct, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
EXTRA_LIMIT = 64 * 1024


def md5(p):
    return hashlib.md5(open(p, 'rb').read()).hexdigest()


def find(folder, name):
    for f in os.listdir(folder):
        if f.lower() == name.lower():
            return os.path.join(folder, f)
    return None


def ps(script, *argv):
    r = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', script] + list(argv),
                       capture_output=True, text=True)
    print('   ', os.path.basename(script), '->', r.returncode, (r.stdout.strip().splitlines() or [''])[-1][:160])
    if r.returncode not in (0, 2):
        sys.exit(r.stdout + r.stderr)


def extra_bytes(patch):
    b = open(patch, 'rb').read()
    assert b[:8] == b'BSDIFF40', patch
    lc, ld, _ = struct.unpack('<qqq', b[8:32])
    return len(bz2.decompress(b[32 + lc + ld:]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--gog-gold', required=True)
    ap.add_argument('--gog-nitro', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    import bsdiff4
    os.makedirs(a.out, exist_ok=True)
    rows = []

    def patch(app, src, dst, rel_dst, rel_src, name):
        p = os.path.join(a.out, name + '.bsdiff')
        bsdiff4.file_diff(src, dst, p)
        chk = tempfile.mktemp()
        bsdiff4.file_patch(src, chk, p)
        assert md5(chk) == md5(dst), name
        os.remove(chk)
        x = extra_bytes(p)
        if x > EXTRA_LIMIT:
            sys.exit('%s: %d extra bytes - refusing (would carry data that is not in the source file)' % (name, x))
        rows.append('\t'.join((app, rel_dst, rel_src, md5(src), md5(dst), name + '.bsdiff')))
        print('  %-14s %s -> %s  %6d B patch, %5d extra bytes' % (name, md5(src)[:8], md5(dst)[:8], os.path.getsize(p), x))

    work = tempfile.mkdtemp(prefix='mackit-patches-')
    # ---- Gold ----
    g = os.path.join(work, 'gold')
    shutil.copytree(a.gog_gold, g)
    for n, want in (('i76.exe', '9a232dcc2c164648cff20c414c1f9698'), ('i76shell.dll', 'deb41008321cf018ba33c27bfbbfa074')):
        if md5(find(g, n)) != want:
            sys.exit('%s is not the GOG 2.1.0.17 file (%s)' % (n, want[:8]))
    print('Gold (GOG 2.1.0.17):')
    ps(os.path.join(REPO, 'tools', 'patch-kit', 'Apply-Shell-Keys.ps1'), '-GameDir', g)
    ps(os.path.join(REPO, 'tools', 'fix-shell-textentry.ps1'), '-GameDir', g)
    ps(os.path.join(REPO, 'u32x', 'deploy-u32x.ps1'), '-GameDir', g, '-U32xDll', os.path.join(REPO, 'u32x', 'u32x_full.dll'))
    # The Mac-only change: the frame-0 PIT CPU-speed probe (0x499950: cli / out 0x43 / in 0x42) is FATAL under Wine on GOG
    # 2.1.0.17 ("Program Error" + winedbg at exe+0x99997, kit test 2026-10-25; on Windows the game gets past it). The family
    # Macs never met it: their AiO-based exe (6319abf7) jumps over the call. Here the call at 0x499b25 becomes `or eax,-1`
    # (the probe's own failure value), so the caller stores 200 MHz at 0x5a7ca4, as Nitro's I76_NITRO_PIT_SKIP does. Gold's
    # proxy detects the exe by its PE stamp and checks every site's own bytes; none is at 0x499b25.
    exe = find(g, 'i76.exe')
    import pefile
    pe = pefile.PE(exe, fast_load=True)
    off = pe.get_offset_from_rva(0x499b25 - 0x400000)
    pe.close()
    b = bytearray(open(exe, 'rb').read())
    if bytes(b[off:off + 5]) != bytes.fromhex('e826feffff') or bytes(b[off + 5:off + 10]) != bytes.fromhex('3d66fdffff'):
        sys.exit('i76.exe: the probe call at 0x499b25 is not GOG 2.1.0.17\'s')
    b[off:off + 5] = bytes.fromhex('83c8ff9090')
    open(exe, 'wb').write(b)
    print('    Wine PIT skip: 0x499b25 call 0x499950 -> or eax,-1 (file offset 0x%x)' % off)
    for n in ('i76.exe', 'i76shell.dll'):
        patch('gold', find(a.gog_gold, n), find(g, n), n, n, n.split('.')[0])
    spec = importlib.util.spec_from_file_location('coop_install', os.path.join(REPO, 'tools', 'coop-install.py'))
    ci = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ci)
    addon = find(g, 'ADDON')
    src16 = find(g, 'miss16')
    jobs = []
    for name, mission, title in ci.SCENARIOS:
        extra = [] if name in ci.SCEN_NO_COPIES else ['--copies', str(ci.SCEN_COPIES)]
        jobs.append((name, mission, ['--title', ci.SCEN_TITLE % title, '--count', str(ci.SCEN_SPAWNS)] + extra))
    for n in range(1, ci.COUNT + 1):
        jobs.append(('coop%02d' % n, 'T%02d' % n, ['--title', ci.COOP_TITLE % n, '--count', str(ci.COOP_SPAWNS),
                                                     '--copies', str(ci.COOP_COPIES)]))
    for name, mission, args in jobs:
        src = find(src16, mission + '.MSN')
        dst = ci.build(addon, name, src, args)
        patch('gold', src, dst, 'ADDON/%s.lvl' % name, 'miss16/%s' % os.path.basename(src), name)
    # ---- Nitro ----
    print('Nitro:')
    ns = find(a.gog_nitro, 'nitshell.dll')
    if md5(ns) != 'f804f50d026d3986c0152971847af5db':
        sys.exit('nitshell.dll is not the GOG Nitro Pack file (f804f50d)')
    f7, out = os.path.join(work, 'nit-f7.dll'), os.path.join(work, 'nitshell.dll')
    for cmd in ([os.path.join(REPO, 'tools', 'patch-nitshell-f7.py'), ns, f7],
                [os.path.join(REPO, 'tools', 'patch-nitshell-modals.py'), f7, out]):
        subprocess.run([sys.executable] + cmd, check=True, stdout=subprocess.DEVNULL)
    patch('nitro', ns, out, 'nitshell.dll', 'nitshell.dll', 'nitshell')
    with open(os.path.join(a.out, 'patches.txt'), 'w', newline='\n') as f:
        f.write('# I\'76 Mac Kit patches (tools/mac-kit/make-patches.py): app, target, source, source md5, target md5, patch\n')
        f.write('\n'.join(rows) + '\n')
    shutil.rmtree(work, ignore_errors=True)
    print('%d patches -> %s' % (len(rows), a.out))


if __name__ == '__main__':
    main()
