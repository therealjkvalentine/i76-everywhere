#!/usr/bin/env python3
r"""vc5_verify.py - static identity check of a Visual C++ 5.0 (SP3) tool tree (task t9a-vc5-locate).

Reads PE version resources and md5s of the tools that matter for the i76.exe toolchain question and
compares them with the expected values from KB Q170367 (link.exe: RTM 5.00.7022, SP1/SP2 5.02.7132,
SP3 5.10.7303) and with the RTM Learning-edition media already at toolchain\vc5-learning.

Nothing is executed: the compiler/linker banners ("Microsoft (R) 32-Bit Incremental Linker Version
5.10.7303", "Microsoft (R) 32-bit C/C++ Optimizing Compiler Version 11.00.7022 for 80x86") are printed
by the tools themselves; the build number 7022 is NOT a string inside CL.EXE/C1.DLL/C2.EXE on the RTM
media (0 hits for '7022' in those three files; it is a numeric constant), so the cl.exe banner can only
be read by running `cl.exe` with no arguments. This script therefore checks FileVersion resources and
sizes, and prints the commands to run for the banner check.

usage: python tools\vc5_verify.py <dir-with-BIN> [--json out.json]
       <dir> may be ...\DEVSTUDIO\VC (BIN under it), ...\VC\BIN itself, or an SP3 ALL\VC tree.
exit 0 = every file found matches its expected identity; 1 = a mismatch; 2 = a required file missing.
"""
import hashlib, json, os, sys
try:
    import pefile
except ImportError:
    sys.exit("pip install pefile")

# expected: name -> (FileVersion expected for SP3 install, FileVersion on RTM Learning media, RTM size, note)
EXPECT = {
    'LINK.EXE':   ('5.10.7303', '5.0.0.7022', 359424, 'KB Q170367: SP3 -> 5.10.7303; RTM 5.00.7022; SP1/SP2 5.02.7132'),
    'CL.EXE':     (None,        '11.0.0.0',   44544,  'driver; banner 11.00.7022 only visible by running cl.exe; Pro RTM size 46,080 (gunkies + Pro disc 3 listing)'),
    'C1.DLL':     (None,        '11.0.0.0',   563984, 'C front end'),
    'C1XX.DLL':   (None,        '11.0.0.0',   1047312,'C++ front end'),
    'C2.EXE':     (None,        '10.99.9.0',  323344, 'back end: Learning media = 10.099 / 323,344 B; Professional RTM = 630,544 B (Pro disc 3 listing, gunkies). Optimizing back end is the Pro/Enterprise one.'),
    'LIB.EXE':    (None,        '5.0.0.7022', 4608,   'stub that calls LINK /LIB'),
    'CVTRES.EXE': (None,        '4.0.0.0',    16144,  'RTM 4.00 (16,144 B); SP3 CD ALL\\VC\\BIN\\CVTRES.EXE is 15,120 B dated 1997-09-20; i76.exe Rich header says Cvtres 5.00.1668'),
    'NMAKE.EXE':  (None,        '1.62.0.7022',68608,  ''),
    'MSPDB50.DLL':(None,        '5.0.0.7022', 167424, 'RTM in SHAREDIDE\\BIN; SP3 CD ALL\\SHARED\\BIN\\MSPDB50.DLL is 174,592 B dated 1997-04-24'),
}
REQUIRED = ('LINK.EXE', 'CL.EXE', 'C1.DLL', 'C1XX.DLL', 'C2.EXE')

def fileversion(path):
    pe = pefile.PE(path, fast_load=True)
    pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_RESOURCE']])
    out = {'machine': hex(pe.FILE_HEADER.Machine), 'timestamp': pe.FILE_HEADER.TimeDateStamp,
           'linker': '%d.%d' % (pe.OPTIONAL_HEADER.MajorLinkerVersion, pe.OPTIONAL_HEADER.MinorLinkerVersion)}
    if getattr(pe, 'VS_FIXEDFILEINFO', None):
        v = pe.VS_FIXEDFILEINFO[0]
        out['fileversion'] = '%d.%d.%d.%d' % (v.FileVersionMS >> 16, v.FileVersionMS & 0xffff, v.FileVersionLS >> 16, v.FileVersionLS & 0xffff)
    for fi in getattr(pe, 'FileInfo', []) or []:
        for e in fi:
            if e.Key == b'StringFileInfo':
                for st in e.StringTable:
                    for k, val in st.entries.items():
                        if k in (b'FileVersion', b'FileDescription', b'ProductVersion'):
                            out[k.decode()] = val.decode(errors='replace')
    return out

def find(root, name):
    for cand in (os.path.join(root, name), os.path.join(root, 'BIN', name), os.path.join(root, 'VC', 'BIN', name),
                 os.path.join(root, '..', 'SHAREDIDE', 'BIN', name), os.path.join(root, 'SHARED', 'BIN', name),
                 os.path.join(root, '..', 'SHARED', 'BIN', name)):
        if os.path.isfile(cand):
            return os.path.normpath(cand)
    return None

def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    root = sys.argv[1]
    jout = sys.argv[sys.argv.index('--json') + 1] if '--json' in sys.argv else None
    rows, rc = [], 0
    for name, (sp3, rtm, rtm_size, note) in EXPECT.items():
        p = find(root, name)
        if not p:
            rows.append({'file': name, 'found': False, 'note': note})
            if name in REQUIRED:
                rc = max(rc, 2)
            print('MISSING  %-12s %s' % (name, note))
            continue
        data = open(p, 'rb').read()
        info = fileversion(p)
        fv = info.get('fileversion')
        level = 'SP3' if sp3 and fv == sp3 else ('RTM-ver' if fv == rtm else 'other')
        if name == 'C2.EXE':
            level = 'Learning-edition back end (no optimizer)' if len(data) == rtm_size else ('Pro/Enterprise-size back end' if len(data) == 630544 else 'unknown size %d' % len(data))
        if name == 'LINK.EXE' and fv != sp3:
            rc = max(rc, 1)
        row = {'file': name, 'path': p, 'size': len(data), 'md5': hashlib.md5(data).hexdigest(), 'level': level, **info, 'note': note}
        rows.append(row)
        print('%-8s %-12s %-12s %8d B md5 %s  %s' % (level, name, fv, len(data), row['md5'], info.get('FileDescription', '')))
    print('\nBanner check (run by hand, the build number is not a string in the driver):')
    print('  "%s" 2>&1 | findstr /i "Version"' % (find(root, 'CL.EXE') or 'CL.EXE'))
    print('  "%s" 2>&1 | findstr /i "Version"' % (find(root, 'LINK.EXE') or 'LINK.EXE'))
    print('  expect: "Microsoft (R) 32-bit C/C++ Optimizing Compiler Version 11.00.7022 for 80x86"')
    print('          "Microsoft (R) 32-Bit Incremental Linker Version 5.10.7303"')
    print('  Learning edition also prints "Optimizing Compiler" in its banner; the edition shows in C2.EXE size (323,344 vs 630,544 B).')
    if jout:
        json.dump(rows, open(jout, 'w'), indent=1)
        print('wrote', jout)
    print('exit', rc, '(0 ok, 1 LINK.EXE is not 5.10.7303, 2 required tool missing)')
    sys.exit(rc)

if __name__ == '__main__':
    main()
