"""emu_f3.py - check of the F3 Modal_YesNo keyboard cave: Unicorn runs from 0x1000bd51 (after the mouse-click poll,
eax = click state) until the code reaches a known target, with KeyInput_Poll 0x1001c110 replaced by a stub that
stores the key at [ecx] and returns the poll code (0 none, 1 key, 3 Esc; per 0x1001c17a-0x1001c186)."""
import sys, struct, pefile
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import *
pe = pefile.PE(sys.argv[1]); img = pe.get_memory_mapped_image()
BASE = 0x10000000; OBJ = 0x30000000; STACK = 0x40000000
T = {0x1000bd56: 'mouse hit-test', 0x1000bd92: 'YES', 0x1000bd99: 'NO', 0x1000bd2d: 'keep looping'}
def run(click, code, key):
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    mu.mem_map(BASE, 0x100000); mu.mem_write(BASE, img[:0x100000])
    stub = b'\xc7\x01' + struct.pack('<I', key) + b'\xb8' + struct.pack('<I', code) + b'\xc3'
    mu.mem_write(0x1001c110, stub)
    mu.mem_map(OBJ, 0x1000); mu.mem_write(0x100cc50c, struct.pack('<I', OBJ))
    mu.mem_map(STACK, 0x10000); mu.reg_write(UC_X86_REG_ESP, STACK + 0x8000)
    mu.reg_write(UC_X86_REG_EAX, click)
    hit = []
    def hook(uc, addr, size, ud):
        if addr in T and addr != 0x1000bd51:
            hit.append(addr); uc.emu_stop()
    mu.hook_add(UC_HOOK_CODE, hook)
    mu.emu_start(0x1000bd51, 0xffffffff, count=200)
    return T.get(hit[0], hex(hit[0])) if hit else 'none', mu.reg_read(UC_X86_REG_ESP) == STACK + 0x8000
cases = [(1,0,0,'mouse hit-test'),(0,0,0,'keep looping'),(0,3,0x1b,'NO'),(0,1,ord('y'),'YES'),(0,1,ord('Y'),'YES'),
         (0,1,ord('n'),'NO'),(0,1,ord('N'),'NO'),(0,1,0x0d,'keep looping'),(0,1,ord('a'),'keep looping'),(2,0,0,'keep looping')]
bad = 0
for c, code, key, exp in cases:
    got, bal = run(c, code, key)
    ok = got == exp and bal; bad += not ok
    print('click=%d poll=%d key=0x%02x -> %-15s expected %-15s %s' % (c, code, key, got, exp, 'OK' if ok else 'MISMATCH'))
print('n=%d mismatches=%d' % (len(cases), bad))
