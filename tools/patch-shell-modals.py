"""patch-shell-modals.py - keyboard exits and two 1997 defects in the shell's other modal popups.

    python tools/patch-shell-modals.py <in i76shell.dll> <out i76shell.dll> [--only M1,K2,...] [--emulate]
    python tools/patch-shell-modals.py <i76shell.dll> --emulate          (emulate an already patched file)
    python tools/patch-shell-modals.py <i76shell.dll> --check            (report which patches are present)

Companion of patch-shell-f7.py (Modal_ImageOk / Modal_Ok Enter+Space, caves in the .text slack). This script does
NOT touch those two loops or that slack, so the two compose in either order. Audit: lab
docs\\DIALOG-AND-CLICK-AUDIT.md.

  M1  Modal_VehicleRejected 0x1000b980 draws art frame 0x22 of shape table 0x24, which has 34 frames (0..0x21) in
      Gold's DATABASE.MW2. Mcga_DrawRleSprite 0x1003a8f4 does no bounds check, so it reads a wild frame offset
      (0x00ab0087 from the table) and either faults at 0x1003a9a9 (the MULTIPLAYER-LOCAL-TEST F1 crash signature:
      read at table+0xab008f) or draws nothing. Patch: push 0x22 -> push 0x11 (the blank OK panel Modal_Ok uses;
      its OK button lies on this modal's hit rect, UI 298..340 x 255..269).            1 byte  at 0x1000b9a1
  M2  Modal_Ok 0x1000b660 draws a second "OK" with Display_DrawText(310, 294) under the panel (the panel's own OK is
      at UI 298..341 x 255..270, which is the hit rect). Clicking the stray label does nothing (MULTIPLAYER-LOCAL-
      TEST F2: 320,302 missed, 318,261 closed). Patch: the call -> add esp,0x14 (Display_DrawText is ret 0x14).
                                                                                        5 bytes at 0x1000b6d7
  K1  Modal_VehicleRejected: Enter / Space close it (as F7 does for Modal_ImageOk).
  K2  Modal_CdRetry 0x1000bad0 ("SUGAR, PUT DISC 2 IN NOW", OK / CANCEL): Enter = OK, Esc = CANCEL.
  K3  Modal_YesNo 0x1000bc40 (overwrite bookmark / variant, leave salvage, exceed detail defaults): Y = YES,
      N or Esc = NO. Same keys as F3 (i76-map shell\\FIXES.md); Enter is deliberately NOT yes. Skipped with a note
      when the file already carries F3 (the hook then holds a jmp).
  K4  Modal_OneButton 0x1000bdd0 = the CHOOSE A TEAM picker of the melee/net entry forms: Enter = DONE (keeps the
      current team), Esc = CANCEL.

Every K cave: cmp eax,1 / je HIT (the unchanged mouse path), then KeyInput_Poll 0x1001c110 on the KeyInput object
[0x100cc50c] (position-independent: call $+5 / pop), key compares, else back to the loop top. KeyInput_Poll peeks
WM_KEYFIRST..WM_KEYLAST, so these loops now also retrieve sent messages (a WM_ACTIVATEAPP 1 can reopen the input
gate, GARAGE-POPUP-STUCK.md section 3). esi is free at each loop top (reloaded on the hit path; the epilogues pop it).
Caves live in VDriver_UnusedMethod 0x10038630..0x100387cf (dead: no call, no rel32/imm32, no 4-byte value equal
to it anywhere in the file; same cave as i76-map patch_shell.py F4, so F4 and this script exclude each other).
Its base relocations are neutralised (type 0), so the result is correct at any load base.

Fail closed: every site must hold exactly the stock bytes (or exactly this script's bytes), the dead function must
hash to the stock bytes (or be exactly this script's cave image), else nothing is written. After writing, the file
is read back and every differing byte must lie in a planned range.
"""
import hashlib, struct, sys

BASE = 0x10000000
KEYOBJ = 0x100cc50c
KEYPOLL = 0x1001c110
DEAD0, DEAD_LEN = 0x10038630, 0x1a0
DEAD_MD5 = '27c107a2c28232b19284233b9b63758c'
HOOK_ORIG = {  # hook VA: original 5 bytes (cmp eax,1 ; jne top)
    0x1000ba6d: '83f80175e5', 0x1000bbbb: '83f80175e5', 0x1000bd51: '83f80175d7', 0x1000bfcb: '83f80175cc'}

# name, hook, top, hit, [(key value, target)], esc target or None
KSITES = [
    ('K1', 'Modal_VehicleRejected', 0x1000ba6d, 0x1000ba57, 0x1000ba72, [(0x0d, 0x1000ba9f), (0x20, 0x1000ba9f)], None),
    ('K2', 'Modal_CdRetry',         0x1000bbbb, 0x1000bba5, 0x1000bbc0, [(0x0d, 0x1000bc07)], 0x1000bc0e),
    ('K3', 'Modal_YesNo',           0x1000bd51, 0x1000bd2d, 0x1000bd56,
     [(ord('y'), 0x1000bd92), (ord('Y'), 0x1000bd92), (ord('n'), 0x1000bd99), (ord('N'), 0x1000bd99)], 0x1000bd99),
    ('K4', 'Modal_OneButton (team picker)', 0x1000bfcb, 0x1000bf9c, 0x1000bfd0, [(0x0d, 0x1000c0e9)], 0x1000c0ed),
]
BYTE_PATCHES = [  # name, VA, original hex, new hex
    ('M1', 0x1000b9a0, '6a22', '6a11'),
    ('M2', 0x1000b6d7, 'e8d4de0200', '83c4149090'),
]
ALL = ['M1', 'M2', 'K1', 'K2', 'K3', 'K4']


def rel32(src_next, dst):
    return struct.pack('<i', dst - src_next)


def cave_bytes(va, top, hit, keys, esc):
    b = bytearray()
    def here(): return va + len(b)
    b += b'\x83\xf8\x01'                                     # cmp eax,1
    b += b'\x0f\x84' + rel32(here() + 6, hit)                # je hit
    b += b'\xe8\x00\x00\x00\x00'                             # call $+5
    anchor = here()
    b += b'\x58'                                             # pop eax
    b += b'\x8b\xb0' + struct.pack('<i', KEYOBJ - anchor)    # mov esi,[eax+disp] = [0x100cc50c]
    b += b'\x8b\xce'                                         # mov ecx,esi
    b += b'\xe8' + rel32(here() + 5, KEYPOLL)                # call KeyInput_Poll (0 none, 1 key, 3 Esc)
    b += b'\x85\xc0'                                         # test eax,eax
    b += b'\x0f\x84' + rel32(here() + 6, top)                # je top
    if esc:
        b += b'\x83\xf8\x03'                                 # cmp eax,3
        b += b'\x0f\x84' + rel32(here() + 6, esc)            # je esc
    b += b'\x8b\x06'                                         # mov eax,[esi]  (the ToAscii char)
    for k, t in keys:
        b += b'\x83\xf8' + bytes([k])                        # cmp eax,k
        b += b'\x0f\x84' + rel32(here() + 6, t)              # je t
    b += b'\xe9' + rel32(here() + 5, top)                    # jmp top
    return bytes(b)


def layout(sel):
    """Fixed cave addresses (all four K caves are always laid out, so a cave's address never depends on --only)."""
    out, va = [], DEAD0
    for k in KSITES:
        code = cave_bytes(va, k[3], k[4], k[5], k[6])
        out.append((k, va, code))
        va += (len(code) + 15) & ~15
    assert va <= DEAD0 + DEAD_LEN
    img = bytearray(b'\xcc' * DEAD_LEN)
    for (k, cva, code) in out:
        if k[0] in sel:
            img[cva - DEAD0:cva - DEAD0 + len(code)] = code
    return out, bytes(img)


def sections(data):
    e = struct.unpack_from('<I', data, 0x3c)[0]
    n = struct.unpack_from('<H', data, e + 6)[0]
    opt = struct.unpack_from('<H', data, e + 20)[0]
    s0 = e + 24 + opt
    return e, [struct.unpack_from('<8sIIII', data, s0 + 40 * i) for i in range(n)]


def file_off(data, va):
    _, secs = sections(data)
    rva = va - BASE
    for name, vs, sva, rs, ro in secs:
        if sva <= rva < sva + max(vs, rs) and rva - sva < rs:
            return ro + rva - sva
    raise ValueError('VA %#x not in a section' % va)


def reloc_entries(data):
    """[(file offset of the u16 entry, type, VA)] for every base relocation."""
    e, secs = sections(data)
    ddir = e + 24 + 96 + 5 * 8
    rva_dir, size_dir = struct.unpack_from('<II', data, ddir)
    p0 = file_off(data, BASE + rva_dir)
    out, p = [], 0
    while p < size_dir:
        page, bsz = struct.unpack_from('<II', data, p0 + p)
        if bsz < 8: break
        for k in range((bsz - 8) // 2):
            eo = p0 + p + 8 + 2 * k
            v = struct.unpack_from('<H', data, eo)[0]
            out.append((eo, v >> 12, BASE + page + (v & 0xfff)))
        p += bsz
    return out


def plan(data, sel):
    if struct.unpack_from('<I', data, sections(data)[0] + 52)[0] != BASE:
        raise SystemExit('ImageBase is not 0x10000000 - not an i76shell.dll')
    edits, notes = [], []
    for name, va, old, new in BYTE_PATCHES:
        if name not in sel: continue
        o = file_off(data, va); cur = data[o:o + len(bytes.fromhex(old))].hex()
        if cur == old: edits.append((o, bytes.fromhex(old), bytes.fromhex(new), '%s %#x' % (name, va)))
        elif cur == new: notes.append('%s already applied' % name)
        else: raise SystemExit('%s: bytes at %#x are %s, expected %s - NOTHING written' % (name, va, cur, old))
    caves, img = layout(sel)
    od = file_off(data, DEAD0)
    curdead = bytes(data[od:od + DEAD_LEN])
    dead_needed = any(k[0][0] in sel for k in caves)
    for (k, cva, code) in caves:
        name, label, hook, top = k[0], k[1], k[2], k[3]
        if name not in sel: continue
        oh = file_off(data, hook); cur = data[oh:oh + 5]
        new = b'\xe9' + rel32(hook + 5, cva)
        if cur.hex() == HOOK_ORIG[hook]:
            edits.append((oh, bytes(cur), new, '%s %s hook %#x -> cave %#x' % (name, label, hook, cva)))
        elif cur == new:
            notes.append('%s hook already applied' % name)
        elif name == 'K3' and cur[0] == 0xe9:
            notes.append('K3 skipped: Modal_YesNo already hooked (F3, jmp %#x)' % (hook + 5 + struct.unpack('<i', cur[1:])[0]))
            sel = [s for s in sel if s != 'K3']
        else:
            raise SystemExit('%s: hook bytes at %#x are %s, expected %s - NOTHING written' % (name, hook, cur.hex(), HOOK_ORIG[hook]))
    if dead_needed:
        caves, img = layout(sel)
        if hashlib.md5(curdead).hexdigest() == DEAD_MD5:
            edits.append((od, curdead, img, 'cave image VDriver_UnusedMethod %#x (+%#x)' % (DEAD0, DEAD_LEN)))
            for eo, typ, va in reloc_entries(data):
                if typ != 0 and DEAD0 - 3 <= va < DEAD0 + DEAD_LEN:
                    edits.append((eo, bytes(data[eo:eo + 2]), b'\0\0', 'reloc at %#x neutralised' % va))
        elif curdead == img:
            notes.append('cave image already present')
        else:
            raise SystemExit('VDriver_UnusedMethod 0x10038630 is not the stock bytes (F4 or another patch uses it, md5 %s)'
                             ' - NOTHING written' % hashlib.md5(curdead).hexdigest())
    sites = [(o, len(new), label) for o, old, new, label in edits if not label.startswith(('reloc', 'cave image'))]
    for eo, typ, va in reloc_entries(data):  # no live relocation (4 bytes at va) may touch any other patched range
        if typ == 0: continue
        r = file_off(data, va)
        for o, ln, label in sites:
            if r < o + ln and o < r + 4:
                raise SystemExit('relocation at %#x overlaps %s - NOTHING written' % (va, label))
    return edits, notes


def check(data):
    caves, _ = layout(ALL)
    for name, va, old, new in BYTE_PATCHES:
        o = file_off(data, va); cur = data[o:o + len(bytes.fromhex(new))].hex()
        print('  %s %s' % (name, 'present' if cur == new else 'stock' if cur == old else 'OTHER ' + cur))
    for (k, cva, code) in caves:
        o = file_off(data, k[2]); cur = data[o:o + 5]
        oc = file_off(data, cva)
        print('  %s %s' % (k[0], 'present' if cur == b'\xe9' + rel32(k[2] + 5, cva) and data[oc:oc + len(code)] == code
                           else 'stock' if cur.hex() == HOOK_ORIG[k[2]] else 'OTHER hook ' + cur.hex()))


def emulate(path, sel):
    import pefile
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
    from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_EAX, UC_X86_REG_ESI
    img = pefile.PE(path).get_memory_mapped_image()
    OBJ, STACK = 0x30000000, 0x40000000
    bad = n = 0
    for name, label, hook, top, hit, keys, esc in KSITES:
        if name not in sel: continue
        T = {hit: 'hit-test', top: 'loop top'}
        for k, t in keys: T[t] = 'key %#x target %#x' % (k, t) if t not in T else T[t]
        names = {top: 'TOP', hit: 'HIT'}
        for k, t in keys: names.setdefault(t, 'T%#x' % t)
        if esc: names.setdefault(esc, 'ESC%#x' % esc)
        def run(click, code, key):
            mu = Uc(UC_ARCH_X86, UC_MODE_32)
            mu.mem_map(BASE, 0x100000); mu.mem_write(BASE, bytes(img[:0x100000]))
            mu.mem_write(KEYPOLL, b'\xc7\x01' + struct.pack('<I', key) + b'\xb8' + struct.pack('<I', code) + b'\xc3')
            mu.mem_map(OBJ, 0x1000); mu.mem_write(KEYOBJ, struct.pack('<I', OBJ))
            mu.mem_map(STACK, 0x10000); mu.reg_write(UC_X86_REG_ESP, STACK + 0x8000)
            mu.reg_write(UC_X86_REG_EAX, click); mu.reg_write(UC_X86_REG_ESI, 0x5a5a5a5a)
            got = []
            def h(uc, addr, size, ud):
                if addr in names: got.append(addr); uc.emu_stop()
            mu.hook_add(UC_HOOK_CODE, h)
            mu.emu_start(hook, 0xffffffff, count=300)
            return (names[got[0]] if got else 'none'), mu.reg_read(UC_X86_REG_ESP) == STACK + 0x8000
        cases = [(1, 0, 0, hit), (0, 0, 0, top), (2, 0, 0, top), (0, 3, 0x1b, esc or top),
                 (0, 1, 0x0d, dict(keys).get(0x0d, top)), (0, 1, 0x20, dict(keys).get(0x20, top)),
                 (0, 1, ord('y'), dict(keys).get(ord('y'), top)), (0, 1, ord('Y'), dict(keys).get(ord('Y'), top)),
                 (0, 1, ord('n'), dict(keys).get(ord('n'), top)), (0, 1, ord('x'), top), (0, 1, 0x0a, top),
                 (0, 1, 0x10d, top), (0, 1, 0x0d00 | ord('y'), top)]
        for c, code, key, exp in cases:
            got, bal = run(c, code, key)
            ok = got == names[exp] and bal
            bad += not ok; n += 1
            print('  %-3s click=%d poll=%d key=0x%04x -> %-12s expected %-12s stack %s %s'
                  % (name, c, code, key, got, names[exp], 'balanced' if bal else 'MOVED', 'OK' if ok else 'MISMATCH'))
    # M2: the replaced call must leave esp exactly as Display_DrawText's ret 0x14 would
    if 'M2' in sel:
        mu = Uc(UC_ARCH_X86, UC_MODE_32)
        mu.mem_map(BASE, 0x100000); mu.mem_write(BASE, bytes(img[:0x100000]))
        mu.mem_map(STACK, 0x10000); mu.reg_write(UC_X86_REG_ESP, STACK + 0x8000 - 0x14)
        mu.emu_start(0x1000b6d7, 0x1000b6dc)
        ok = mu.reg_read(UC_X86_REG_ESP) == STACK + 0x8000
        bad += not ok; n += 1
        print('  M2  esp after 0x1000b6d7..0x1000b6dc %s' % ('= ret 0x14 OK' if ok else 'WRONG MISMATCH'))
    print('emulation n=%d mismatches=%d' % (n, bad))
    return bad == 0


def main():
    av = sys.argv[1:]
    sel = ALL
    if '--only' in av:
        i = av.index('--only'); sel = av[i + 1].split(','); del av[i:i + 2]
        unknown = [s for s in sel if s not in ALL]
        if unknown: raise SystemExit('unknown patch ids %s' % unknown)
    args = [a for a in av if not a.startswith('--')]
    if len(args) == 1 and '--check' in av:
        check(open(args[0], 'rb').read()); return
    if len(args) == 1 and '--emulate' in av:
        sys.exit(0 if emulate(args[0], sel) else 1)
    if len(args) != 2:
        print(__doc__); sys.exit(2)
    src, dst = args
    data = bytearray(open(src, 'rb').read())
    print('in  %s md5 %s' % (src, hashlib.md5(data).hexdigest()))
    edits, notes = plan(data, sel)
    for n_ in notes: print('  note: ' + n_)
    if not edits:
        print('nothing to do - nothing written'); return
    for off, old, new, label in edits:
        data[off:off + len(new)] = new
        print('  %-58s file %#07x  %s -> %s' % (label, off, old.hex()[:16], new.hex()[:16] + ('..' if len(new) > 8 else '')))
    open(dst, 'wb').write(data)
    out, orig = open(dst, 'rb').read(), open(src, 'rb').read()
    allowed = set()
    for off, _, new, _ in edits: allowed.update(range(off, off + len(new)))
    diff = [i for i in range(len(orig)) if orig[i] != out[i]]
    if len(out) != len(orig) or any(i not in allowed for i in diff):
        raise SystemExit('READ-BACK FAILED')
    print('out %s md5 %s (%d bytes differ, all in planned ranges)' % (dst, hashlib.md5(out).hexdigest(), len(diff)))
    if '--emulate' in av:
        sys.exit(0 if emulate(dst, sel) else 1)


if __name__ == '__main__':
    main()
