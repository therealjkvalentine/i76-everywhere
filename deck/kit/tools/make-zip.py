#!/usr/bin/env python3
"""make-zip.py STAGE_PARENT TOP_NAME OUT.zip - the Deck Kit zip with forward-slash names and Unix modes (dirs 0755, *.sh / *.py
0755, the rest 0644). PowerShell 5.1's Compress-Archive writes backslash names and no Unix modes: unzipped on the Deck its
directories came out without the x bit (payload/ unreadable, 2026-10-25). Used by tools/package-deck-kit.ps1."""
import os, sys, time, zipfile
parent, top, out = sys.argv[1:4]
with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
    for root, dirs, files in os.walk(os.path.join(parent, top)):
        dirs.sort(); rel = os.path.relpath(root, parent).replace(os.sep, '/')
        zi = zipfile.ZipInfo(rel + '/', time.localtime()[:6]); zi.external_attr = (0o40755 << 16) | 0x10; zi.create_system = 3
        z.writestr(zi, b'')
        for f in sorted(files):
            p = os.path.join(root, f); zi = zipfile.ZipInfo(rel + '/' + f, time.localtime(os.path.getmtime(p))[:6])
            mode = 0o755 if f.endswith(('.sh', '.py')) else 0o644
            zi.external_attr = (0o100000 | mode) << 16; zi.create_system = 3; zi.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(zi, open(p, 'rb').read())
print(out)
