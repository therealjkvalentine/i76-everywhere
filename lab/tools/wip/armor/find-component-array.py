"""
find-component-array.py - locate the 0x90-stride component record array inside the vehicle
logic object, by detecting the REPEAT rather than guessing an offset.

Two candidate clusters have already been rejected the honest way (write + watch the HUD damage
panel): 0x030F7234 (four 200s, stride 0x58) and 0x04C1B570 (eight 47s, stride 0x48). Both look
like armor and neither moves the player's panel. Guess-and-check is too slow.

An array of N identical-layout records has a signature: many dwords at offset o equal the dword
at o+stride, for a long stretch. Slide a correlator over the logic object and report where that
self-similarity peaks. Also validates the logic pointer itself using the documented
AI-aggression field at logic+0xA818 (int 0..4) - if that is nonsense, the pointer is wrong and
everything downstream is noise.
"""
import ctypes, struct, sys, subprocess

k32 = ctypes.WinDLL('kernel32', use_last_error=True)


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


def main():
    pid = find_pid()
    if not pid:
        print("i76 not running"); return 1
    p = Proc(pid)
    stride = int(sys.argv[1], 0) if len(sys.argv) > 1 else 0x90
    span = 0x30000

    player = p.u32(p.u32(p.u32(0x54A264)) + 0x70)
    logic = p.u32(player + 0x108)
    print(f"player 0x{player:X}   logic 0x{logic:X}")
    aggr = p.u32(logic + 0xA818)
    print(f"logic+0xA818 (documented AI aggression, expect 0..4) = {aggr}"
          f"{'   <- plausible' if aggr <= 4 else '   <- SUSPECT: logic pointer may be wrong'}")

    data = p.read(logic, span)
    print(f"read 0x{len(data):X} bytes; correlating at stride 0x{stride:X}\n")

    words = stride // 4
    best = []
    for o in range(0, len(data) - 2 * stride, 4):
        same = 0
        nz = 0
        for k in range(words):
            i = o + k * 4
            a = struct.unpack_from('<I', data, i)[0]
            b = struct.unpack_from('<I', data, i + stride)[0]
            if a == b:
                same += 1
            if a:
                nz += 1
        if same >= words * 0.5 and nz >= 4:
            best.append((same, nz, o))
    best.sort(reverse=True)
    print(f"top self-similar offsets at stride 0x{stride:X} (record starts):")
    seen = []
    for same, nz, o in best:
        if any(abs(o - s) < stride for s in seen):
            continue
        seen.append(o)
        print(f"  logic+0x{o:05X}  ({0x0 + logic + o:#010x})  {same}/{words} dwords repeat, {nz} nonzero")
        if len(seen) >= 12:
            break
    if not seen:
        print("  no repeating structure found at this stride")
        print("  try other strides:  find-component-array.py 0x48 / 0x4C / 0x60")
    return 0


if __name__ == '__main__':
    sys.exit(main())
