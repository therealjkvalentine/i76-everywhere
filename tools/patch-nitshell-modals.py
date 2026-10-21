"""patch-nitshell-modals.py - the Nitro Pack's NITSHELL.DLL (f804f50d): byte fixes from tools/patch-shell-modals.py that
apply to its shell (nitro-port lane 2026-10-21, docs/records/NITRO-PORT-2026-10-21.md s.7).

    python tools/patch-nitshell-modals.py <in nitshell.dll> <out nitshell.dll> [--check]

  M2  Modal_Ok (NITSHELL loop 0x1002257a; Gold 0x1000b660) draws a second "OK" with Display_DrawText(310, 294) under the
      panel, exactly as Gold's (push 0 / eax / [obj+0x408] / 0x126 / 0x136; call 0x10012dc0, which returns `ret 0x14` like
      Gold's 0x100395b0). Patch: the call -> add esp,0x14 (5 bytes at 0x100224c8).

Not ported (yet): M1 (the vehicle-rejected panel's frame 0x22: NITSHELL draws from its own DATABASE.TVF, whose frame count
was not checked), K1-K4 (the keyboard exits of the other modals: their caves and targets are not read yet). Run after or
before patch-nitshell-f7.py (they touch different bytes). Fail closed: the bytes at each site must be exactly the stock ones
(or exactly this script's), no base relocation may fall in a patched range, and the output is read back and diffed.
"""
import hashlib, struct, sys

BASE = 0x10000000
PATCHES = [  # name, VA, original hex, new hex
    ('M2', 0x100224c8, 'e8f308ffff', '83c4149090'),
]


def file_off(data, va):
    e = struct.unpack_from('<I', data, 0x3c)[0]
    nsec = struct.unpack_from('<H', data, e + 6)[0]; opt = struct.unpack_from('<H', data, e + 20)[0]
    for i in range(nsec):
        s = e + 24 + opt + 40 * i
        vs, va_s, rs, ro = struct.unpack_from('<IIII', data, s + 8)
        if va_s <= va - BASE < va_s + max(vs, rs) and va - BASE - va_s < rs:
            return ro + (va - BASE - va_s)
    raise SystemExit('VA %#x not in any section' % va)


def plan(data):
    edits = []
    for name, va, old, new in PATCHES:
        o = file_off(data, va); old, new = bytes.fromhex(old), bytes.fromhex(new)
        cur = bytes(data[o:o + len(old)])
        if cur not in (old, new):
            raise SystemExit('%s at %#x: unexpected bytes %s (want %s) - NOTHING patched' % (name, va, cur.hex(), old.hex()))
        edits.append((o, cur, new, '%s %#x' % (name, va)))
    try:
        import pefile
        pe = pefile.PE(data=bytes(data))
        for blk in getattr(pe, 'DIRECTORY_ENTRY_BASERELOC', []):
            for e in blk.entries:
                if e.type == 0:
                    continue
                for name, va, old, _ in PATCHES:
                    if va - BASE - 3 <= e.rva < va - BASE + len(old) // 2:
                        raise SystemExit('%s: base relocation at rva %#x inside the patch - NOTHING patched' % (name, e.rva))
    except ImportError:
        print('  (pefile not installed - relocation check skipped)')
    return edits


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if '--check' in sys.argv and len(args) == 1:
        data = open(args[0], 'rb').read()
        for name, va, old, new in PATCHES:
            o = file_off(data, va); cur = data[o:o + len(old) // 2].hex()
            print('%s %#x: %s' % (name, va, 'present' if cur == new else 'stock' if cur == old else 'OTHER ' + cur))
        return
    if len(args) != 2:
        print(__doc__); sys.exit(2)
    src, dst = args
    data = bytearray(open(src, 'rb').read())
    print('in  %s md5 %s' % (src, hashlib.md5(data).hexdigest()))
    edits = plan(data)
    for o, old, new, label in edits:
        data[o:o + len(new)] = new
        print('  %-14s file %#07x  %s -> %s' % (label, o, old.hex(), new.hex()))
    open(dst, 'wb').write(data)
    out, orig = open(dst, 'rb').read(), open(src, 'rb').read()
    allowed = set()
    for o, _, new, _ in edits:
        allowed.update(range(o, o + len(new)))
    stray = [i for i in range(len(orig)) if orig[i] != out[i] and i not in allowed]
    if len(out) != len(orig) or stray:
        raise SystemExit('READ-BACK FAILED: %d stray bytes' % len(stray))
    print('out %s md5 %s' % (dst, hashlib.md5(out).hexdigest()))


if __name__ == '__main__':
    main()
