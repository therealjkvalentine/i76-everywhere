"""
make-test-variant.py - author a .VCF variant file directly, bypassing the in-game menu.

Why this exists: the CHASSIS CONFIGURATION FORM refuses to save a modified stock variant until
you rename it, and the rename field cannot be driven by injected keystrokes (keybd_event with
virtual keys, with KEYEVENTF_SCANCODE, and posted WM_CHAR all fail - the 2D shell ignores
injected keys). That blocked unattended loadout testing entirely.

But saved variants are just .VCF files in ADDON/ - "Jade's Car" is ADDON/valepre4.vcf. So write
the file and let the game find it.

Naming: variant files appear to be named after their chassis (valeprec.vdf -> valepre4.vcf), so
a new Leprechaun variant should be vale*.vcf.

Usage: make-test-variant.py <src.vcf> <dst.vcf> --name AUTOTEST [--armor 900] [--weapon g.gdf@1]
"""
import struct, sys


def armor_offset(d):
    i = d.rfind(b'.wdf')
    return d.find(b'\0', i) + 1 if i >= 0 else None


def main():
    if len(sys.argv) < 3:
        print(__doc__); return 1
    src, dst = sys.argv[1], sys.argv[2]
    d = bytearray(open(src, 'rb').read())

    if '--name' in sys.argv:
        nm = sys.argv[sys.argv.index('--name') + 1]
        # variant name is char[16] at the start of the VCFC payload (chunk @0x14, payload 0x1C)
        d[0x1C:0x1C + 16] = nm.encode('latin1')[:15].ljust(16, b'\0')
        print(f"variant name -> {nm}")

    if '--armor' in sys.argv:
        v = int(sys.argv[sys.argv.index('--armor') + 1])
        ao = armor_offset(d)
        if ao is None:
            print("no armor block found"); return 1
        old = [struct.unpack_from('<I', d, ao + i * 4)[0] for i in range(8)]
        for i in range(8):
            struct.pack_into('<I', d, ao + i * 4, v)
        print(f"armor {old} -> {[v]*8}  ({v/10} each)")

    if '--armor-list' in sys.argv:
        # Eight DISTINCT improbable values, one per face. Searching memory for the stock 200 is
        # hopeless (200 is everywhere); a unique fingerprint per face pins the block instantly
        # AND reveals the field ORDER in memory, which need not match the file order.
        vals = [int(x) for x in sys.argv[sys.argv.index('--armor-list') + 1].split(',')]
        ao = armor_offset(d)
        if ao is None or len(vals) != 8:
            print("need exactly 8 values, and an armor block"); return 1
        old = [struct.unpack_from('<I', d, ao + i * 4)[0] for i in range(8)]
        for i, v in enumerate(vals):
            struct.pack_into('<I', d, ao + i * 4, v)
        print(f"armor {old} -> {vals}")

    if '--weapon' in sys.argv:
        spec = sys.argv[sys.argv.index('--weapon') + 1]      # name.gdf@hardpoint
        gdf, _, hp = spec.partition('@')
        hp = int(hp or 0)
        i = d.find(b'WEPN')
        if i < 0:
            print("no WEPN chunk to replace"); return 1
        size = struct.unpack_from('<I', d, i + 4)[0]
        payload = struct.pack('<I', hp) + gdf.encode('latin1') + b'\0'
        payload = payload.ljust(size - 8, b'\0')[:size - 8]
        d[i + 8:i + size] = payload
        print(f"first WEPN -> {gdf} on hardpoint {hp}")

    open(dst, 'wb').write(bytes(d))
    print(f"wrote {dst} ({len(d)} bytes)")
    return 0


if __name__ == '__main__':
    sys.exit(main())
