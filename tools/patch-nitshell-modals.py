"""patch-nitshell-modals.py - the Nitro Pack's NITSHELL.DLL (f804f50d): the modal fixes of tools/patch-shell-modals.py, as
they apply to its shell (nitro-port lane 2026-10-21, docs/records/NITRO-PORT-2026-10-21.md s.8).

    python tools/patch-nitshell-f7.py     <stock nitshell.dll> <f7.dll>
    python tools/patch-nitshell-modals.py <f7.dll> <out nitshell.dll> [--only M2,K1,...] [--emulate]
    python tools/patch-nitshell-modals.py <nitshell.dll> --check | --emulate

Read side by side with Gold's shell (NITSHELL's modal family sits at 0x10022440..0x100232ab):
  M1  NOT NEEDED. Nitro's Modal_VehicleRejected 0x10022770 draws frame 0x21 of its modal art table (DATABASE.TVF item 0x1e,
      48 frames, loaded at 0x10025a45 where Gold loads MW2 item 0x24, 34 frames). Frame 0x21 is the 282 x 93 panel
      "CHEATING BASTARD ALERT! YOU CANNOT PLAY WITH A HACKED VEHICLE" with its OK button on the hit rect (rendered:
      lab captures/nitro-port-20261021/nitshell-art). Gold's out-of-range frame 0x22 is fixed in Nitro.
  M2  Modal_Ok draws a second "OK" with Display_DrawText(310, 294) under its panel (push 0 / eax / [obj+0x408] / 0x126 /
      0x136; call 0x10012dc0, `ret 0x14` as Gold's 0x100395b0). Patch: the call -> add esp,0x14 (5 bytes at 0x100224c8).
  K1  Modal_VehicleRejected (top 0x10022847, `cmp eax,1 ; jne top` at 0x1002285d, hit test 0x10022862, close 0x1002288f):
      Enter / Space close it.
  K2  Modal_CdRetry 0x10022ae0 ("SUGAR, PUT IN THE NITRO PACK CD NOW", frames 0x13 / 0x2f, OK / CANCEL; called by the CD
      check at 0x1000899e / 0x100089da). Its no-click path is 0x10022c28 (a pump call, then the loop top 0x10022bc8), not
      the top as in Gold. Enter = OK (0x10022c2f), Esc = CANCEL (0x10022c36).
  K3  Modal_YesNo (top 0x10022d5d, hook 0x10022d81, hit 0x10022d86, YES 0x10022dc2, NO 0x10022dc9): Y = YES, N or Esc = NO
      (Enter deliberately not YES), as Gold's K3.
  K4  the list picker 0x10022e00 (Nitro's Modal_OneButton, generalised: type 0x12 = CHOOSE A TEAM, 8 items, DONE / CANCEL
      indexes 0xc / 0xd; types 0x2c..0x2e 2-4 items, 0xe / 0xf). Hook 0x100230ff (`cmp eax,1 ; jne rel32 0x1002322f`; the
      jne's last 4 bytes become unreachable, no branch lands in them), hit 0x10023108. Enter = DONE (0x10023241: returns
      the current selection, as clicking DONE), Esc = CANCEL (0x10023239: -1). esi / ebx / ebp are live in this loop.
Not ported: the three-button modal 0x100228c0 (callers 0x1002f45a / 0x10030b15) has no Gold counterpart.

Every K cave: cmp eax,1 / je HIT (the unchanged mouse path), push esi, KeyInput_Poll 0x1000ae30 on [0x1013047c]
(position-independent: call $+5 / pop), the ToAscii char into ecx, pop esi, then 0 -> the no-click path, 3 (Esc) -> the
Esc target, char compares (both cases written out), else the no-click path. esi is preserved (K4 needs it); eax and ecx
are dead at every target (each reloads them before use). Caves: the .text raw slack after patch-nitshell-f7.py's two,
0x100396c0..0x100397ff (zero in the stock file); .text VirtualSize -> 0x38800. Run F7 first: its script refuses any
VirtualSize but the stock 0x38635 / its own 0x38700. Fail closed: every hook must hold exactly the stock bytes (or exactly
this script's), every cave must be zero (or exactly this script's), no base relocation may touch a patched range, and the
output is read back and diffed.
"""
import hashlib, struct, sys

BASE = 0x10000000
KEYOBJ, KEYPOLL = 0x1013047c, 0x1000ae30
TEXT_VS_OFF, TEXT_VS_OK, TEXT_VS_NEW = 0x1c0, (0x38635, 0x38700, 0x38800), 0x38800
CAVE0, CAVE_END = 0x100396c0, 0x10039800      # F7 ends at 0x100396bd; raw .text ends at 0x10039800
IMG_MAP = 0x180000
BYTE_PATCHES = [('M2', 0x100224c8, 'e8f308ffff', '83c4149090')]
# name, label, hook, no-click target, hit, [(key, target)], esc target
KSITES = [
    ('K1', 'Modal_VehicleRejected', 0x1002285d, 0x10022847, 0x10022862, [(0x0d, 0x1002288f), (0x20, 0x1002288f)], None),
    ('K2', 'Modal_CdRetry', 0x10022bde, 0x10022c28, 0x10022be3, [(0x0d, 0x10022c2f)], 0x10022c36),
    ('K3', 'Modal_YesNo', 0x10022d81, 0x10022d5d, 0x10022d86,
     [(ord('y'), 0x10022dc2), (ord('Y'), 0x10022dc2), (ord('n'), 0x10022dc9), (ord('N'), 0x10022dc9)], 0x10022dc9),
    ('K4', 'list picker (CHOOSE A TEAM)', 0x100230ff, 0x1002322f, 0x10023108, [(0x0d, 0x10023241)], 0x10023239),
]
HOOK_ORIG = {0x1002285d: '83f80175e5', 0x10022bde: '83f8017545', 0x10022d81: '83f80175d7', 0x100230ff: '83f8010f85'}
ALL = ['M2', 'K1', 'K2', 'K3', 'K4']


def rel32(src_next, dst):
    return struct.pack('<i', dst - src_next)


def cave_bytes(va, top, hit, keys, esc):
    b = bytearray()
    def here(): return va + len(b)
    b += b'\x83\xf8\x01' + b'\x0f\x84' + rel32(here() + 9, hit)        # cmp eax,1 ; je hit
    b += b'\x56'                                                       # push esi
    b += b'\xe8\x00\x00\x00\x00'; anchor = here(); b += b'\x58'        # call $+5 ; pop eax
    b += b'\x8b\xb0' + struct.pack('<i', KEYOBJ - anchor)              # mov esi,[eax+disp] = [KEYOBJ]
    b += b'\x8b\xce' + b'\xe8' + rel32(here() + 7, KEYPOLL)            # mov ecx,esi ; call KeyInput_Poll
    b += b'\x8b\x0e' + b'\x5e'                                         # mov ecx,[esi] (the char) ; pop esi
    b += b'\x85\xc0' + b'\x0f\x84' + rel32(here() + 8, top)            # test eax,eax ; je no-click path
    if esc:
        b += b'\x83\xf8\x03' + b'\x0f\x84' + rel32(here() + 9, esc)    # cmp eax,3 ; je esc
    for k, t in keys:
        b += b'\x83\xf9' + bytes([k]) + b'\x0f\x84' + rel32(here() + 9, t)  # cmp ecx,k ; je t
    b += b'\xe9' + rel32(here() + 5, top)                              # jmp no-click path
    return bytes(b)


def layout():
    """fixed cave addresses: all four are always laid out, so a cave's address never depends on --only"""
    out, va = {}, CAVE0
    for k in KSITES:
        code = cave_bytes(va, k[3], k[4], k[5], k[6])
        out[k[0]] = (va, code)
        va += (len(code) + 15) & ~15
    assert va <= CAVE_END, hex(va)
    return out


def file_off(data, va):
    e = struct.unpack_from('<I', data, 0x3c)[0]
    nsec = struct.unpack_from('<H', data, e + 6)[0]; opt = struct.unpack_from('<H', data, e + 20)[0]
    for i in range(nsec):
        s = e + 24 + opt + 40 * i
        vs, va_s, rs, ro = struct.unpack_from('<IIII', data, s + 8)
        if va_s <= va - BASE < va_s + max(vs, rs) and va - BASE - va_s < rs:
            return ro + (va - BASE - va_s)
    raise SystemExit('VA %#x not in any section' % va)


def plan(data, sel):
    edits = []
    if data[TEXT_VS_OFF - 8:TEXT_VS_OFF] != b'.text\0\0\0':
        raise SystemExit('section header at %#x is not .text - NOTHING written' % (TEXT_VS_OFF - 8))
    vs = struct.unpack_from('<I', data, TEXT_VS_OFF)[0]
    if vs not in TEXT_VS_OK:
        raise SystemExit('.text VirtualSize %#x unexpected - NOTHING written' % vs)
    if any(k[0] in sel for k in KSITES) and vs != TEXT_VS_NEW:
        edits.append((TEXT_VS_OFF, struct.pack('<I', vs), struct.pack('<I', TEXT_VS_NEW), '.text VirtualSize'))
    for name, va, old, new in BYTE_PATCHES:
        if name not in sel:
            continue
        o = file_off(data, va); old, new = bytes.fromhex(old), bytes.fromhex(new); cur = bytes(data[o:o + len(old)])
        if cur not in (old, new):
            raise SystemExit('%s at %#x: unexpected bytes %s (want %s) - NOTHING written' % (name, va, cur.hex(), old.hex()))
        if cur == old:
            edits.append((o, cur, new, '%s %#x' % (name, va)))
    caves = layout()
    for name, label, hook, top, hit, keys, esc in KSITES:
        if name not in sel:
            continue
        cave, code = caves[name]
        oh, oc = file_off(data, hook), file_off(data, cave)
        new_h = b'\xe9' + rel32(hook + 5, cave)
        cur_h, cur_c = bytes(data[oh:oh + 5]), bytes(data[oc:oc + len(code)])
        if cur_h == new_h and cur_c == code:
            continue
        if not (cur_h.hex() == HOOK_ORIG[hook] and cur_c == b'\0' * len(code)):
            raise SystemExit('%s %s: hook %s (want %s) / cave %s... - NOTHING written'
                             % (name, label, cur_h.hex(), HOOK_ORIG[hook], cur_c[:8].hex()))
        edits.append((oh, cur_h, new_h, '%s hook %#x' % (name, hook)))
        edits.append((oc, cur_c, code, '%s cave %#x (%d B)' % (name, cave, len(code))))
    import pefile
    pe = pefile.PE(data=bytes(data))
    ranges = [(va - BASE, va - BASE + len(bytes.fromhex(o))) for n_, va, o, _ in BYTE_PATCHES if n_ in sel]
    ranges += [(k[2] - BASE, k[2] - BASE + 5) for k in KSITES if k[0] in sel]
    ranges += [(caves[k[0]][0] - BASE, caves[k[0]][0] - BASE + len(caves[k[0]][1])) for k in KSITES if k[0] in sel]
    for blk in getattr(pe, 'DIRECTORY_ENTRY_BASERELOC', []):
        for e in blk.entries:
            if e.type and any(lo - 3 <= e.rva < hi for lo, hi in ranges):
                raise SystemExit('base relocation at rva %#x inside a patched range - NOTHING written' % e.rva)
    return edits


def check(data):
    for name, va, old, new in BYTE_PATCHES:
        o = file_off(data, va); cur = data[o:o + len(old) // 2].hex()
        print('  %s %s' % (name, 'present' if cur == new else 'stock' if cur == old else 'OTHER ' + cur))
    caves = layout()
    for name, label, hook, *_r in KSITES:
        cave, code = caves[name]
        o = file_off(data, hook); cur = data[o:o + 5]; oc = file_off(data, cave)
        print('  %s %s' % (name, 'present' if cur == b'\xe9' + rel32(hook + 5, cave) and data[oc:oc + len(code)] == code
                           else 'stock' if cur.hex() == HOOK_ORIG[hook] else 'OTHER ' + cur.hex()))


def emulate(path, sel):
    import pefile
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
    from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_EAX, UC_X86_REG_ESI, UC_X86_REG_EBX, UC_X86_REG_EBP
    img = pefile.PE(path).get_memory_mapped_image()
    OBJ, STACK = 0x30000000, 0x40000000
    bad = n = 0
    for name, label, hook, top, hit, keys, esc in KSITES:
        if name not in sel:
            continue
        names = {top: 'NOCLICK', hit: 'HIT'}
        for k, t in keys:
            names.setdefault(t, 'T%#x' % t)
        if esc:
            names.setdefault(esc, 'T%#x' % esc)

        def run(click, code, key):
            mu = Uc(UC_ARCH_X86, UC_MODE_32)
            mu.mem_map(BASE, IMG_MAP); mu.mem_write(BASE, bytes(img[:IMG_MAP]))
            # KeyInput_Poll stub (thiscall): [ecx] = char, eax = code
            mu.mem_write(KEYPOLL, b'\xc7\x01' + struct.pack('<I', key) + b'\xb8' + struct.pack('<I', code) + b'\xc3')
            mu.mem_map(OBJ, 0x1000); mu.mem_write(KEYOBJ, struct.pack('<I', OBJ))
            mu.mem_map(STACK, 0x10000); mu.reg_write(UC_X86_REG_ESP, STACK + 0x8000)
            mu.reg_write(UC_X86_REG_EAX, click); mu.reg_write(UC_X86_REG_ESI, 0x5a5a5a5a)
            mu.reg_write(UC_X86_REG_EBX, 0x3b3b3b3b); mu.reg_write(UC_X86_REG_EBP, 0x4e4e4e4e)
            got = []

            def h(uc, addr, size, ud):
                if addr in names:
                    got.append(addr); uc.emu_stop()
            mu.hook_add(UC_HOOK_CODE, h)
            mu.emu_start(hook, 0xffffffff, count=300)
            kept = (mu.reg_read(UC_X86_REG_ESI), mu.reg_read(UC_X86_REG_EBX), mu.reg_read(UC_X86_REG_EBP)) == \
                (0x5a5a5a5a, 0x3b3b3b3b, 0x4e4e4e4e)
            return (names[got[0]] if got else 'none'), mu.reg_read(UC_X86_REG_ESP) == STACK + 0x8000, kept
        kd = dict(keys)
        cases = [(1, 0, 0, hit), (0, 0, 0, top), (2, 0, 0, top), (0, 3, 0x1b, esc or top),
                 (0, 1, 0x0d, kd.get(0x0d, top)), (0, 1, 0x20, kd.get(0x20, top)), (0, 1, ord('y'), kd.get(ord('y'), top)),
                 (0, 1, ord('Y'), kd.get(ord('Y'), top)), (0, 1, ord('n'), kd.get(ord('n'), top)),
                 (0, 1, ord('N'), kd.get(ord('N'), top)), (0, 1, ord('x'), top), (0, 1, 0x0a, top), (0, 1, 0x10d, top)]
        for c, code, key, exp in cases:
            got, bal, kept = run(c, code, key)
            ok = got == names[exp] and bal and kept
            bad += not ok; n += 1
            print('  %-3s click=%d poll=%d key=0x%04x -> %-12s expected %-12s stack %s, esi/ebx/ebp %s %s'
                  % (name, c, code, key, got, names[exp], 'balanced' if bal else 'MOVED', 'kept' if kept else 'CHANGED',
                     'OK' if ok else 'MISMATCH'))
    if 'M2' in sel:
        mu = Uc(UC_ARCH_X86, UC_MODE_32)
        mu.mem_map(BASE, IMG_MAP); mu.mem_write(BASE, bytes(img[:IMG_MAP]))
        mu.mem_map(STACK, 0x10000); mu.reg_write(UC_X86_REG_ESP, STACK + 0x8000 - 0x14)
        mu.emu_start(0x100224c8, 0x100224cd)
        ok = mu.reg_read(UC_X86_REG_ESP) == STACK + 0x8000
        bad += not ok; n += 1
        print('  M2  esp after 0x100224c8..0x100224cd %s' % ('= ret 0x14 OK' if ok else 'WRONG MISMATCH'))
    print('emulation n=%d mismatches=%d' % (n, bad))
    return bad == 0


def main():
    av = sys.argv[1:]
    sel = list(ALL)
    if '--only' in av:
        i = av.index('--only'); sel = av[i + 1].split(','); del av[i:i + 2]
        if any(s not in ALL for s in sel):
            raise SystemExit('unknown ids %s (M1 does not apply to NITSHELL: see the docstring)' % sel)
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
    edits = plan(data, sel)
    if not edits:
        print('nothing to do - nothing written'); return
    for o, old, new, label in edits:
        data[o:o + len(new)] = new
        print('  %-28s file %#07x  %s -> %s' % (label, o, old.hex()[:24], new.hex()[:24] + ('...' if len(new) > 12 else '')))
    open(dst, 'wb').write(data)
    out, orig = open(dst, 'rb').read(), open(src, 'rb').read()
    allowed = set()
    for o, _, new, _ in edits:
        allowed.update(range(o, o + len(new)))
    stray = [i for i in range(len(orig)) if orig[i] != out[i] and i not in allowed]
    if len(out) != len(orig) or stray:
        raise SystemExit('READ-BACK FAILED: %d stray bytes' % len(stray))
    print('out %s md5 %s' % (dst, hashlib.md5(out).hexdigest()))
    if '--emulate' in av:
        sys.exit(0 if emulate(dst, sel) else 1)


if __name__ == '__main__':
    main()
