"""emu_f4.py - gate-E style check of the F4 mouse-mapping cave in a patched shell: Unicorn runs the cave from the
patched jump at 0x1001fca9 to its return target 0x1001fcaf with GetClientRect stubbed (IAT 0x100411f0 -> stub that
writes the client rect and does ret 8). Oracle: the letterbox model (uniform scale, centred)."""
import sys, struct, pefile
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import *
P = sys.argv[1]
pe = pefile.PE(P); img = pe.get_memory_mapped_image()
BASE = 0x10000000; STUB = 0x30000000; STACK = 0x40000000
def run(w, h, x, y):
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    mu.mem_map(BASE, 0x100000); mu.mem_write(BASE, img[:0x100000])
    mu.mem_map(STUB, 0x1000)
    # stub: mov eax,[esp+8]; mov dword [eax],0; mov dword [eax+4],0; mov dword [eax+8],w; mov dword [eax+0xc],h; mov eax,1; ret 8
    stub = bytes.fromhex('8b442408') + b'\xc7\x00' + struct.pack('<I',0) + b'\xc7\x40\x04' + struct.pack('<I',0) + \
           b'\xc7\x40\x08' + struct.pack('<I',w) + b'\xc7\x40\x0c' + struct.pack('<I',h) + b'\xb8\x01\x00\x00\x00\xc2\x08\x00'
    mu.mem_write(STUB, stub)
    mu.mem_write(0x100411f0, struct.pack('<I', STUB))
    mu.mem_write(0x100f702c, struct.pack('<I', 0x1234))
    mu.mem_map(STACK, 0x10000)
    esp = STACK + 0x8000
    mu.mem_write(esp + 0x14, struct.pack('<ii', x, y))
    mu.reg_write(UC_X86_REG_ESP, esp); mu.reg_write(UC_X86_REG_EDI, 0); mu.reg_write(UC_X86_REG_EBX, 0xB0B0)
    mu.emu_start(0x1001fca9, 0x1001fcaf, count=500)
    rx, ry = struct.unpack('<ii', mu.mem_read(esp + 0x14, 8))
    assert mu.reg_read(UC_X86_REG_ESP) == esp, "stack imbalance"
    assert mu.reg_read(UC_X86_REG_EBX) == 0xB0B0, "ebx clobbered"
    assert mu.reg_read(UC_X86_REG_ECX) & 0xffffffff == rx & 0xffffffff, "ecx != x at return"
    return rx, ry
def oracle(w, h, x, y):
    s = min(w / 640, h / 480); ox = (w - 640 * s) / 2; oy = (h - 480 * s) / 2
    return int((x - ox) / s), int((y - oy) / s)
cases = [(640,480,100,50),(640,480,639,479),(3440,1440,760+300,150),(3440,1440,2679,1439),(3440,1440,100,700),
         (1280,1024,200,32+80),(1920,1080,240+960,540),(650,490,320,240),(800,600,400,300)]
bad = 0
for c in cases:
    got = run(*c); exp = oracle(*c)
    ok = abs(got[0]-exp[0]) <= 1 and abs(got[1]-exp[1]) <= 1
    bad += not ok
    print('client %4dx%-4d pt(%4d,%4d) -> cave %-12s oracle %-12s %s' % (c[0],c[1],c[2],c[3],got,exp,'OK' if ok else 'MISMATCH'))
print('n=%d mismatches=%d (tolerance 1 px: integer vs float division)' % (len(cases), bad))
