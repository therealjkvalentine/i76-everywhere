"""
vcf.py - read (and edit) Interstate '76 .VCF vehicle-config files.

This is the car configuration in plain form - variant name, chassis model, texture, wheels,
armor, and the weapon loadout - and it is far easier to work with than chasing damage state
through the heap. The game WRITES ADDON/vehscn.vcf when a melee starts, so it is also the
authoritative record of what the player actually took into the mission.

Chunked format, each chunk = 4-char tag + u32 size (size INCLUDES the 8-byte header):

  BWD2                     file magic
  REV    -> u32 revision   (3)
  VCFC   -> the vehicle:
             +0x00  char[16]  variant name        ("Econo")
             +0x10  cstr      chassis model .vdf  ("valeprec.vdf")  <- WHICH CAR
             +...   cstr      texture .vtf        ("leprecn1.vtf")  <- WHICH SKIN
             +...   u32 x3    (0, 1, 1)
             +...   cstr      front wheel .wdf / "null" / rear wheel .wdf
             +...   u32 x8    ARMOR, integer TENTHS (200 = 20.0)
  SPEC   -> a special slot (empty ones still present)
  WEPN   -> u32 flags/hardpoint, then cstr gdf name ("gmlight.gdf")
  EXIT   -> terminator

Armor is confirmed tenths here: a stock ABX Leprechaun shows 20.0 on every face in the CHASSIS
CONFIGURATION FORM and stores eight 0xC8 (=200) values.

Usage:
  vcf.py dump <file>
  vcf.py set-armor <file> <value_tenths> [-o out]
"""
import struct, sys, os

TAGS = (b'BWD2', b'REV\0', b'REV', b'VCFC', b'SPEC', b'WEPN', b'EXIT')


def cstr(b, off):
    e = b.find(b'\0', off)
    if e < 0:
        e = len(b)
    return b[off:e].decode('latin1'), e + 1


def chunks(data):
    """Walk top-level chunks. Returns (tag, payload_offset, size, absolute_offset)."""
    o = 0
    out = []
    while o + 8 <= len(data):
        tag = data[o:o + 4]
        # tags are NUL-padded to 4 ("REV\0"), so allow 0 as padding - rejecting it stops the
        # walk at the second chunk and you silently see only the file magic
        if not all(c == 0 or 32 <= c < 127 for c in tag):
            break
        size = struct.unpack_from('<I', data, o + 4)[0]
        if size < 8 or o + size > len(data) + 8:
            size = 8
        out.append((tag.decode('latin1').rstrip('\0'), o + 8, size, o))
        o += size
    return out


def armor_offset(data):
    """Armor is the run of 8 u32 immediately after the last wheel .wdf string."""
    last = data.rfind(b'.wdf')
    if last < 0:
        return None
    o = data.find(b'\0', last) + 1
    return o


def dump(path):
    data = open(path, 'rb').read()
    print(f"{path}  ({len(data)} bytes)\n")
    for tag, po, size, ao in chunks(data):
        print(f"  @0x{ao:04X}  {tag:<5} size={size}")
        if tag == 'REV':
            print(f"           revision {struct.unpack_from('<I', data, po)[0]}")
        elif tag == 'VCFC':
            name = data[po:po + 16].split(b'\0')[0].decode('latin1')
            o = po + 16
            vdf, o = cstr(data, o)
            vtf, o = cstr(data, o)
            print(f"           variant : {name}")
            print(f"           chassis : {vdf}     <- which car")
            print(f"           texture : {vtf}     <- which skin")
        elif tag == 'WEPN':
            flags = struct.unpack_from('<I', data, po)[0]
            gdf, _ = cstr(data, po + 4)
            print(f"           flags={flags}  weapon={gdf}")
        elif tag == 'SPEC':
            print(f"           (special slot, empty)" if size <= 12 else "           special")

    ao = armor_offset(data)
    if ao:
        vals = [struct.unpack_from('<I', data, ao + i * 4)[0] for i in range(8)]
        print(f"\n  ARMOR @0x{ao:04X} (u32 x8, TENTHS):")
        print(f"    raw     {vals}")
        print(f"    as 0.1s {[v / 10 for v in vals]}")
        print("    (form shows FRONT/RIGHT/LEFT/REAR armor + the same four chassis)")
    return data


def set_armor(path, value, out=None):
    data = bytearray(open(path, 'rb').read())
    ao = armor_offset(data)
    if not ao:
        print("could not locate armor block"); return 1
    old = [struct.unpack_from('<I', data, ao + i * 4)[0] for i in range(8)]
    for i in range(8):
        struct.pack_into('<I', data, ao + i * 4, value)
    dst = out or path
    open(dst, 'wb').write(bytes(data))
    print(f"armor {old} -> {[value]*8}  ({value/10} each)")
    print(f"written to {dst}")
    return 0


def main():
    if len(sys.argv) < 3:
        print(__doc__); return 1
    cmd, path = sys.argv[1], sys.argv[2]
    if cmd == 'dump':
        dump(path); return 0
    if cmd == 'set-armor':
        out = None
        if '-o' in sys.argv:
            out = sys.argv[sys.argv.index('-o') + 1]
        return set_armor(path, int(sys.argv[3]), out)
    print(__doc__); return 1


if __name__ == '__main__':
    sys.exit(main())
