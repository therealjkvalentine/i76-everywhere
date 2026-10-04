"""
dump-vehicle-config.py - map the vehicle-logic object: components, armor, and car identity.

Known going in (docs/ENGINE-REFERENCE.md): logic = [entity+0x108] holds 16 component records of
stride 0x90 covering engine/suspension/brakes/tyres/armor, with armor and chassis stored as
integer TENTHS (20.0 -> 200). The exact per-field offsets were never established.

Strategy: the CHASSIS CONFIGURATION FORM shows what the values must be, so look for those exact
numbers rather than guessing offsets. On a stock ABX Leprechaun every armor and chassis face
reads 20.0, i.e. eight 200s. Report every 200 in the logic object with its offset modulo 0x90,
so a consistent field position inside the record shows up as a repeated remainder.

Also hunts the vehicle's identity: asset-name strings (.vtf / .vdf / .gdf) reachable from the
entity and logic, which is how "which car is this" can be answered without a name table.
"""
import ctypes, struct, sys, subprocess, collections

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
REC_STRIDE = 0x90


def find_pid(name='i76.exe'):
    out = subprocess.check_output(['tasklist', '/FI', f'IMAGENAME eq {name}', '/FO', 'CSV'],
                                  text=True, errors='ignore')
    for line in out.splitlines()[1:]:
        parts = [p.strip('"') for p in line.split('","')]
        if len(parts) > 1 and parts[0].lower() == name:
            return int(parts[1])
    return None


class Proc:
    def __init__(self, pid):
        self.h = k32.OpenProcess(0x0010 | 0x0400, False, pid)

    def read(self, a, n):
        b = ctypes.create_string_buffer(n); g = ctypes.c_size_t(0)
        k32.ReadProcessMemory(self.h, ctypes.c_void_p(a), b, n, ctypes.byref(g))
        return b.raw[:g.value]

    def u32(self, a):
        b = self.read(a, 4)
        return struct.unpack('<I', b)[0] if len(b) == 4 else 0


def cstr(b, off=0, maxlen=32):
    s = []
    for i in range(off, min(off + maxlen, len(b))):
        c = b[i]
        if c == 0:
            break
        if c < 32 or c > 126:
            return ''
        s.append(chr(c))
    return ''.join(s)


def main():
    pid = find_pid()
    if not pid:
        print("i76 not running"); return 1
    p = Proc(pid)
    target = int(sys.argv[1], 16) if len(sys.argv) > 1 else 200   # 20.0 in tenths
    span = 0x20000

    player = p.u32(p.u32(p.u32(0x54A264)) + 0x70)
    logic = p.u32(player + 0x108)
    print(f"pid {pid}   player 0x{player:X}   logic 0x{logic:X}")
    print(f"looking for int32 == {target} (armor tenths) in logic +0..0x{span:X}\n")

    data = p.read(logic, span)
    print(f"read {len(data):#x} bytes")
    hits = []
    for o in range(0, len(data) - 4, 4):
        if struct.unpack_from('<I', data, o)[0] == target:
            hits.append(o)
    print(f"{len(hits)} matches\n")

    # cluster: consecutive-ish hits are the armor block
    runs, run = [], []
    for o in hits:
        if run and o - run[-1] <= 0x90:
            run.append(o)
        else:
            if len(run) >= 3:
                runs.append(run)
            run = [o]
    if len(run) >= 3:
        runs.append(run)

    print("=== clusters of >=3 matches (candidate armor blocks) ===")
    for r in runs:
        gaps = [r[i+1] - r[i] for i in range(len(r) - 1)]
        print(f"  logic+0x{r[0]:05X} .. +0x{r[-1]:05X}   {len(r)} values, gaps {[hex(g) for g in gaps]}")
    if not runs:
        print("  none")

    # offset modulo the documented record stride
    mod = collections.Counter(o % REC_STRIDE for o in hits)
    print(f"\n=== offsets modulo 0x{REC_STRIDE:X} (a real field repeats) ===")
    for m, c in mod.most_common(8):
        print(f"  +0x{m:02X} inside record  x{c}")

    # identity: asset strings near the vehicle
    print("\n=== asset-name strings reachable from entity/logic ===")
    seen = set()
    for label, base, length in (('entity', player, 0x1000), ('logic', logic, span)):
        blk = p.read(base, length)
        for o in range(0, len(blk) - 4, 4):
            v = struct.unpack_from('<I', blk, o)[0]
            if 0x400000 < v < 0x40000000 and v not in seen:
                s = cstr(p.read(v, 32))
                if s and ('.' in s) and any(s.lower().endswith(e) for e in ('.vtf', '.vdf', '.gdf', '.sdf', '.vcf')):
                    seen.add(v)
                    print(f"  {label}+0x{o:05X} -> 0x{v:08X}  '{s}'")
    if not seen:
        print("  none found")
    return 0


if __name__ == '__main__':
    sys.exit(main())
