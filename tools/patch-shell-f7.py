"""patch-shell-f7.py - shell fix F7: Enter / Space close the shell's OK popups.

    python tools/patch-shell-f7.py <in i76shell.dll> <out i76shell.dll> [--no-modal-ok] [--emulate]

Modal_ImageOk 0x1000b800 (the garage DONE refusals "CAN'T GET VERY FAR WITHOUT AN ENGINE" etc., the
"REMEMBER, USE THE SAVE BOOKMARK BUTTON" reminder after ACCEPT SALVAGE in scene 2, and four more
callers) and Modal_Ok 0x1000b660 ("Game Server Not Responding") spin on Mouse_Update +
Mouse_GetLeftClick and read no key (1997 design; lab docs\\GARAGE-POPUP-STUCK.md sections 2, 4, 8).
F7 replaces each loop's `cmp eax,1 ; jne top` (5 bytes) with a jmp to a cave in the .text slack:

    cmp eax,1 ; je HIT                    ; the unchanged mouse path (hit test)
    call $+5 ; pop eax                    ; position-independent: no relocation needed
    mov esi,[eax + (0x100cc50c - here)]   ; the KeyInput object
    mov ecx,esi ; call KeyInput_Poll 0x1001c110   ; PeekMessageA(WM_KEYFIRST..WM_KEYLAST) + ToAscii
    test eax,eax ; je TOP                 ; no key
    mov eax,[esi] ; cmp eax,0x0d ; je CLOSE ; cmp eax,0x20 ; je CLOSE   ; Enter / Space
    jmp TOP                               ; anything else, Esc included, is consumed and ignored

Esc is deliberately NOT an exit (garage: Esc opens Control Configuration, which corrupts input.map);
KeyInput_Poll consumes it, so it no longer queues up for the garage either. esi is free in both
loops (pushed in the prologue, popped in the epilogue, not read between). Because KeyInput_Poll
peeks, the loop now retrieves sent messages: a WM_ACTIVATEAPP 0 may close the input gate
[0x10043224], and the next WM_ACTIVATEAPP 1 is delivered by the same peek and reopens it.

Caves: 0x10040380 (Modal_ImageOk, 61 bytes) and 0x100403c0 (Modal_Ok, 61 bytes), after the pack's
P1 cave (0x10040340..0x10040379) in the .text raw slack; .text VirtualSize 0x3f340 -> 0x3f400
(= SizeOfRawData). The script refuses any file whose bytes at every site are not exactly the
expected originals (or already exactly F7 - then it reports and copies nothing).
"""
import hashlib, struct, sys

BASE = 0x10000000
KEYOBJ = 0x100cc50c
KEYPOLL = 0x1001c110

# (name, hook VA, loop top, hit test, close, cave VA)
SITES = [
    ('Modal_ImageOk', 0x1000b916, 0x1000b900, 0x1000b91b, 0x1000b946, 0x10040380),
    ('Modal_Ok',      0x1000b79f, 0x1000b789, 0x1000b7a4, 0x1000b7d1, 0x100403c0),
]
HOOK_ORIG = bytes.fromhex('83F80175E5')     # cmp eax,1 ; jne -0x1b (both loops)
TEXT_VS_OFF = 0x1c0                          # .text VirtualSize in the section header
TEXT_VS_OLD, TEXT_VS_NEW = 0x3f340, 0x3f400


def rel32(src_next, dst):
    return struct.pack('<i', dst - src_next)


def cave_bytes(top, hit, close, cave):
    b = bytearray()
    def here(): return cave + len(b)
    b += b'\x83\xf8\x01'                                     # cmp eax,1
    b += b'\x0f\x84' + rel32(here() + 6, hit)                # je hit
    b += b'\xe8\x00\x00\x00\x00'                             # call $+5
    anchor = here()
    b += b'\x58'                                             # pop eax
    b += b'\x8b\xb0' + struct.pack('<i', KEYOBJ - anchor)    # mov esi,[eax+disp]
    b += b'\x8b\xce'                                         # mov ecx,esi
    b += b'\xe8' + rel32(here() + 5, KEYPOLL)                # call KeyInput_Poll
    b += b'\x85\xc0'                                         # test eax,eax
    b += b'\x0f\x84' + rel32(here() + 6, top)                # je top
    b += b'\x8b\x06'                                         # mov eax,[esi]
    b += b'\x83\xf8\x0d'                                     # cmp eax,0x0d
    b += b'\x0f\x84' + rel32(here() + 6, close)              # je close
    b += b'\x83\xf8\x20'                                     # cmp eax,0x20
    b += b'\x0f\x84' + rel32(here() + 6, close)              # je close
    b += b'\xe9' + rel32(here() + 5, top)                    # jmp top
    assert len(b) == 61
    return bytes(b)


def hook_bytes(hook, cave):
    return b'\xe9' + rel32(hook + 5, cave)


def file_off(pe_bytes, va):
    """VA -> file offset through the section table (no pefile dependency)."""
    e_lfanew = struct.unpack_from('<I', pe_bytes, 0x3c)[0]
    nsec = struct.unpack_from('<H', pe_bytes, e_lfanew + 6)[0]
    optsz = struct.unpack_from('<H', pe_bytes, e_lfanew + 20)[0]
    sec = e_lfanew + 24 + optsz
    rva = va - BASE
    for i in range(nsec):
        s = sec + 40 * i
        vs, va_s, rs, ro = struct.unpack_from('<IIII', pe_bytes, s + 8)
        if va_s <= rva < va_s + max(vs, rs) and rva - va_s < rs:
            return ro + (rva - va_s)
    raise ValueError('VA %#x not in any section' % va)


def plan(data, sites):
    """Return [(file offset, original bytes, new bytes, label)] or raise if anything is unexpected."""
    edits = []
    imgbase = struct.unpack_from('<I', data, struct.unpack_from('<I', data, 0x3c)[0] + 52)[0]
    if imgbase != BASE:
        raise SystemExit('ImageBase %#x, expected %#x' % (imgbase, BASE))
    if data[TEXT_VS_OFF - 8:TEXT_VS_OFF] != b'.text\0\0\0':
        raise SystemExit('section header at %#x is not .text' % (TEXT_VS_OFF - 8))
    vs = struct.unpack_from('<I', data, TEXT_VS_OFF)[0]
    if vs not in (TEXT_VS_OLD, TEXT_VS_NEW):
        raise SystemExit('.text VirtualSize %#x, expected %#x or %#x' % (vs, TEXT_VS_OLD, TEXT_VS_NEW))
    edits.append((TEXT_VS_OFF, struct.pack('<I', vs), struct.pack('<I', TEXT_VS_NEW), '.text VirtualSize'))
    for name, hook, top, hit, close, cave in sites:
        new_c = cave_bytes(top, hit, close, cave)
        new_h = hook_bytes(hook, cave)
        oh, oc = file_off(data, hook), file_off(data, cave)
        cur_h, cur_c = data[oh:oh + 5], data[oc:oc + len(new_c)]
        if cur_h == HOOK_ORIG and cur_c == b'\0' * len(new_c):
            pass
        elif cur_h == new_h and cur_c == new_c:
            pass                                             # already F7 at this site
        else:
            raise SystemExit('%s: unexpected bytes - hook %s (want %s), cave %s... - NOT patched'
                             % (name, cur_h.hex(), HOOK_ORIG.hex(), cur_c[:8].hex()))
        edits.append((oh, cur_h, new_h, name + ' hook %#x' % hook))
        edits.append((oc, cur_c, new_c, name + ' cave %#x' % cave))
    # no base relocation may land in a replaced range (the caves are position-independent)
    try:
        import pefile
        pe = pefile.PE(data=bytes(data))
        for blk in getattr(pe, 'DIRECTORY_ENTRY_BASERELOC', []):
            for e in blk.entries:
                if e.type == 0:
                    continue
                for name, hook, _, _, _, cave in sites:
                    for lo, hi in ((hook - BASE - 3, hook - BASE + 5), (cave - BASE - 3, cave - BASE + 61)):
                        if lo <= e.rva < hi:
                            raise SystemExit('%s: base relocation at rva %#x inside a patched range' % (name, e.rva))
    except ImportError:
        print('  (pefile not installed - relocation check skipped)')
    return edits


def emulate(path, sites):
    """Unicorn: run each cave from the hook with a KeyInput_Poll stub; check the target and the stack."""
    import pefile
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
    from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_EAX, UC_X86_REG_ESI
    img = pefile.PE(path).get_memory_mapped_image()
    OBJ, STACK = 0x30000000, 0x40000000
    bad = n = 0
    for name, hook, top, hit, close, cave in sites:
        T = {hit: 'hit-test', close: 'CLOSE', top: 'loop top'}
        def run(click, code, key):
            mu = Uc(UC_ARCH_X86, UC_MODE_32)
            mu.mem_map(BASE, 0x100000); mu.mem_write(BASE, bytes(img[:0x100000]))
            # stub: store the key at [ecx], return the poll code (0 none, 1 key, 3 Esc - 0x1001c17a..86)
            mu.mem_write(KEYPOLL, b'\xc7\x01' + struct.pack('<I', key) + b'\xb8' + struct.pack('<I', code) + b'\xc3')
            mu.mem_map(OBJ, 0x1000); mu.mem_write(KEYOBJ, struct.pack('<I', OBJ))
            mu.mem_map(STACK, 0x10000); mu.reg_write(UC_X86_REG_ESP, STACK + 0x8000)
            mu.reg_write(UC_X86_REG_EAX, click); mu.reg_write(UC_X86_REG_ESI, 0x5a5a5a5a)
            hit_ = []
            def h(uc, addr, size, ud):
                if addr in T:
                    hit_.append(addr); uc.emu_stop()
            mu.hook_add(UC_HOOK_CODE, h)
            mu.emu_start(hook, 0xffffffff, count=200)
            return (T.get(hit_[0], hex(hit_[0])) if hit_ else 'none'), mu.reg_read(UC_X86_REG_ESP) == STACK + 0x8000
        cases = [(1, 0, 0, 'hit-test'), (0, 0, 0, 'loop top'), (2, 0, 0, 'loop top'),
                 (0, 1, 0x0d, 'CLOSE'), (0, 1, 0x20, 'CLOSE'), (0, 3, 0x1b, 'loop top'),
                 (0, 1, ord('y'), 'loop top'), (0, 1, ord('n'), 'loop top'), (0, 1, 0x0a, 'loop top'),
                 (0, 1, 0x10d, 'loop top'), (0, 1, 0x0d20, 'loop top')]
        for c, code, key, exp in cases:
            got, bal = run(c, code, key)
            ok = got == exp and bal
            bad += not ok; n += 1
            print('  %-13s click=%d poll=%d key=0x%04x -> %-9s expected %-9s stack %s %s'
                  % (name, c, code, key, got, exp, 'balanced' if bal else 'MOVED', 'OK' if ok else 'MISMATCH'))
    print('emulation n=%d mismatches=%d' % (n, bad))
    return bad == 0


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    sites = SITES if '--no-modal-ok' not in sys.argv else SITES[:1]
    if len(args) == 1 and '--emulate' in sys.argv:
        sys.exit(0 if emulate(args[0], sites) else 1)
    if len(args) != 2:
        print(__doc__); sys.exit(2)
    src, dst = args
    data = bytearray(open(src, 'rb').read())
    print('in  %s md5 %s' % (src, hashlib.md5(data).hexdigest()))
    edits = plan(data, sites)
    if all(o == nw for _, o, nw, _ in edits):
        print('already F7 - nothing written'); sys.exit(0)
    for off, old, new, label in edits:
        data[off:off + len(new)] = new
        print('  %-28s file %#07x  %s -> %s' % (label, off, old.hex()[:24], new.hex()[:24] + ('...' if len(new) > 12 else '')))
    open(dst, 'wb').write(data)
    # read back and diff: only the planned ranges may differ
    out = open(dst, 'rb').read()
    orig = open(src, 'rb').read()
    allowed = set()
    for off, _, new, _ in edits:
        allowed.update(range(off, off + len(new)))
    diff = [i for i in range(len(orig)) if orig[i] != out[i]]
    stray = [i for i in diff if i not in allowed]
    if len(out) != len(orig) or stray:
        raise SystemExit('READ-BACK FAILED: %d stray differing bytes' % len(stray))
    print('out %s md5 %s (%d bytes differ, all at F7 sites)' % (dst, hashlib.md5(out).hexdigest(), len(diff)))
    if '--emulate' in sys.argv:
        sys.exit(0 if emulate(dst, sites) else 1)


if __name__ == '__main__':
    main()
