r"""Task 6(d): Unicorn x86-32 emulation test. Test 1: 10 integer instructions with a hand-computed
expected register state. Test 2: 5 x87 instructions (H7 item 'Unicorn on x87 leaves', first data point).
Prints one JSON line; exit 1 on mismatch."""
import json, struct, sys
import unicorn
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
from unicorn.x86_const import *

res = {"unicorn": unicorn.__version__}
BASE, STACK = 0x1000, 0x8000
# Test 1: 10 instructions
code1 = bytes.fromhex(
    "b805000000"   # 1 mov eax,5
    "b907000000"   # 2 mov ecx,7
    "01c8"         # 3 add eax,ecx        -> 12
    "6bc003"       # 4 imul eax,eax,3     -> 36
    "50"           # 5 push eax
    "5b"           # 6 pop ebx            -> ebx 36
    "31d2"         # 7 xor edx,edx
    "42"           # 8 inc edx            -> 1
    "d1e3"         # 9 shl ebx,1          -> 72
    "29d3"         # 10 sub ebx,edx       -> 71
)
n1 = [0]
def hook_code(uc, addr, size, ud): n1[0] += 1
mu = Uc(UC_ARCH_X86, UC_MODE_32)
mu.mem_map(0, 0x10000)
mu.mem_write(BASE, code1)
mu.reg_write(UC_X86_REG_ESP, STACK)
mu.hook_add(unicorn.UC_HOOK_CODE, hook_code)
mu.emu_start(BASE, BASE + len(code1))
got = {"eax": mu.reg_read(UC_X86_REG_EAX), "ebx": mu.reg_read(UC_X86_REG_EBX),
       "ecx": mu.reg_read(UC_X86_REG_ECX), "edx": mu.reg_read(UC_X86_REG_EDX),
       "esp": mu.reg_read(UC_X86_REG_ESP)}
exp = {"eax": 36, "ebx": 71, "ecx": 7, "edx": 1, "esp": STACK}
res["test1_instructions_executed"] = n1[0]
res["test1_expected"] = exp; res["test1_got"] = got
res["test1_pass"] = (got == exp and n1[0] == 10)

# Test 2: x87: fld1; fld1; faddp st1,st0; fld dword [0x3000] (=1.5); fmulp st1,st0; fstp dword [0x3004]  -> 3.0
code2 = bytes.fromhex("d9e8" "d9e8" "dec1" "d90500300000" "dec9" "d91d04300000")
mu2 = Uc(UC_ARCH_X86, UC_MODE_32)
mu2.mem_map(0, 0x10000)
mu2.mem_write(BASE, code2)
mu2.mem_write(0x3000, struct.pack("<f", 1.5))
n2 = [0]
mu2.hook_add(unicorn.UC_HOOK_CODE, lambda uc, a, s, u: n2.__setitem__(0, n2[0] + 1))
mu2.emu_start(BASE, BASE + len(code2))
out = struct.unpack("<f", mu2.mem_read(0x3004, 4))[0]
res["test2_x87_instructions_executed"] = n2[0]
res["test2_x87_result"] = out
res["test2_x87_pass"] = (out == 3.0 and n2[0] == 6)
res["pass"] = res["test1_pass"] and res["test2_x87_pass"]
print(json.dumps(res))
sys.exit(0 if res["pass"] else 1)
