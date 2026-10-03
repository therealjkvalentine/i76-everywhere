#!/usr/bin/env python3
"""zglide_tmu_patch.py - write a COPY of ZGLIDE.DLL whose texture allocator can use more than 4 MB of TMU memory.

The bug (lab docs\\TEXTURE-DELIVERY.md section 2): ZGLIDE's bump allocator 0x10001930 keeps textures from crossing a
2 MB boundary (a Voodoo 1 rule) with
    10001a8a  mov eax,[0x1001fd38] / test / jne 0x10001ab9      ; 75 24  (skip when PreloadTexture set the flag)
    10001a95  ecx = [0x1001f898] << 20 ; if (end > ecx) {
    10001aa7      mov dword [0x1001fd20], 0x200000              ; next free = 2 MB  <- always 2 MB, not ecx
    10001ab1      [0x1001f898] += 2 }
At the first crossing (2 MB) that is right; at the second (4 MB) it rewinds the allocator onto textures still marked
resident at 2..4 MB, so with MemorySizeOfTMU > 4096 every later upload overwrites a live texture. Under dgVoodoo the
2 MB rule protects nothing (no real TMU), so the patch skips the whole block: 0x10001a93 75 24 (jne) -> eb 24 (jmp).
Relative jump, no relocation involved, one byte.

Usage: python zglide_tmu_patch.py <ZGLIDE.DLL in> <out path>     (refuses unless the input md5 and bytes match)
Runtime equivalent for the proxy (by RVA after LoadLibrary, bytes verified): see TEXTURE-DELIVERY.md section 6.
"""
import hashlib, sys
import pefile

STOCK_MD5 = "05c1dde499cd8da3248557a76ba42f31"
RVA, OLD, NEW = 0x1A93, bytes.fromhex("7524"), bytes.fromhex("eb24")


def main():
    src, dst = sys.argv[1], sys.argv[2]
    data = bytearray(open(src, "rb").read())
    md5 = hashlib.md5(data).hexdigest()
    if md5 != STOCK_MD5:
        sys.exit(f"{src}: md5 {md5}, expected the stock ZGLIDE {STOCK_MD5}; not patching")
    off = pefile.PE(data=bytes(data)).get_offset_from_rva(RVA)
    if data[off:off + 2] != OLD:
        sys.exit(f"bytes at RVA 0x{RVA:x} (file 0x{off:x}) are {data[off:off+2].hex()}, expected {OLD.hex()}")
    data[off:off + 2] = NEW
    open(dst, "wb").write(data)
    back = open(dst, "rb").read()
    assert back[off:off + 2] == NEW
    print(f"{dst}: RVA 0x{RVA:x} (file 0x{off:x}) {OLD.hex()} -> {NEW.hex()}, md5 {hashlib.md5(back).hexdigest()}")


if __name__ == "__main__":
    main()
