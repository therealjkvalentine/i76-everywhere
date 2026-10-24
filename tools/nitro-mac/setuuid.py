# setuuid.py <macho> <uuid-from-macho> - nitro-mp-design lane 2026-10-24: copy LC_UUID (0x1b) from one thin arm64 Mach-O into another,
# then re-sign: codesign -f -s - <macho>. Why: macOS Local Network privacy remembers an app's permission by its main executable's
# Mach-O UUID, and every swiftc build of a launch stub gets a new one. A rebuilt Nitro launcher therefore loses the permission the
# user gave the old one; until someone answers the new prompt at the Mac, Nitro's IPX unicasts are dropped and every join stalls
# (the session still lists: broadcasts pass). Measured 2026-10-24 on the laptop (docs/records/NITRO-MAC-2026-10-21.md s.8,
# NITRO-MP-DESIGN s.0.5.20): old stub 384a0f8e and a one-byte edit of it (same UUID) joined 5 of 5; the rebuilt stubs, the same
# source rebuilt included, 0 of 13; the fixed stub with 384a0f8e's UUID patched in joined (e61e4e57). Keep 03B81E57-0956-3BBA-
# 8D89-3C8EDF8713C4 for the Nitro app's launcher: python3 setuuid.py new-stub old-stub && codesign -f -s - new-stub
import struct, sys
def uuid_at(b):
    ncmds = struct.unpack_from('<I', b, 16)[0]; off = 32
    for _ in range(ncmds):
        cmd, size = struct.unpack_from('<II', b, off)
        if cmd == 0x1b: return off + 8
        off += size
    raise SystemExit('no LC_UUID')
dst = bytearray(open(sys.argv[1], 'rb').read()); src = open(sys.argv[2], 'rb').read()
assert struct.unpack_from('<I', dst, 0)[0] == 0xfeedfacf and struct.unpack_from('<I', src, 0)[0] == 0xfeedfacf
i, j = uuid_at(dst), uuid_at(src)
print('dst uuid', dst[i:i+16].hex(), '-> src uuid', src[j:j+16].hex())
dst[i:i+16] = src[j:j+16]; open(sys.argv[1], 'wb').write(dst)
