"""find-import-call.py - locate calls to a named DLL import and show their argument setup.

    python find-import-call.py grSstWinOpen [n_context]

Parses the PE import directory to find the IAT slot for the named function, then scans .text
for `call dword ptr [IAT]` / `jmp dword ptr [IAT]` and prints the instructions leading up to
each call - which for stdcall APIs is the argument push sequence, i.e. exactly the constants
the game passes. Built to read the Glide mode/refresh a game requests, but generic.
"""
import sys, struct, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from xref import load_sections

EXE = r"C:\Users\james\i76-uncap-lab\game\i76.exe"


def imports(path):
    """{func_name: iat_va} from the import directory."""
    blob = open(path, "rb").read()
    pe = struct.unpack_from("<I", blob, 0x3C)[0]
    base = struct.unpack_from("<I", blob, pe + 24 + 28)[0]
    # data directory 1 = imports
    imp_rva, imp_sz = struct.unpack_from("<II", blob, pe + 24 + 96 + 8 * 1)
    # rva->file offset via section table
    nsec = struct.unpack_from("<H", blob, pe + 6)[0]
    optsz = struct.unpack_from("<H", blob, pe + 20)[0]
    secs = []
    off = pe + 24 + optsz
    for i in range(nsec):
        h = blob[off + i * 40: off + (i + 1) * 40]
        vsize, va, rawsz, rawoff = struct.unpack_from("<IIII", h, 8)
        secs.append((va, max(vsize, rawsz), rawoff))

    def fo(rva):
        for va, size, raw in secs:
            if va <= rva < va + size:
                return raw + (rva - va)
        return None

    out = {}
    d = fo(imp_rva)
    while True:
        ilt, ts, fc, name_rva, iat = struct.unpack_from("<IIIII", blob, d)
        if ilt == 0 and iat == 0:
            break
        dll = blob[fo(name_rva):fo(name_rva) + 64].split(b"\0")[0].decode("latin1")
        thunk = ilt or iat
        i = 0
        while True:
            e = struct.unpack_from("<I", blob, fo(thunk) + i * 4)[0]
            if e == 0:
                break
            if not (e & 0x80000000):
                nm = blob[fo(e) + 2: fo(e) + 130].split(b"\0")[0].decode("latin1")
                out[nm] = (base + iat + i * 4, dll)
            i += 1
        d += 20
    return out


def main():
    target = sys.argv[1]
    ctx = int(sys.argv[2]) if len(sys.argv) > 2 else 24
    imp = imports(EXE)
    if target not in imp:
        hits = [k for k in imp if target.lower() in k.lower()]
        print(f"'{target}' not found. near-matches: {hits[:20]}")
        print(f"total imports: {len(imp)}; DLLs: {sorted(set(v[1] for v in imp.values()))}")
        return
    iat_va, dll = imp[target]
    print(f"{target} ({dll}) IAT slot = 0x{iat_va:08X}")

    base, secs = load_sections(EXE)
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    for va, size, off, name, data in secs:
        if not (name.startswith('.text') or name in ('CODE', 'text')):
            continue
        insns = list(md.disasm(data, va))
        for i, ins in enumerate(insns):
            if ins.mnemonic in ('call', 'jmp') and f"[0x{iat_va:x}]" in ins.op_str:
                print("=" * 70)
                print(f"{ins.mnemonic.upper()} SITE at 0x{ins.address:08X}")
                for j in range(max(0, i - ctx), i + 2):
                    mark = ">>" if j == i else "  "
                    print(f"  {mark} 0x{insns[j].address:08X}  {insns[j].mnemonic:<7} {insns[j].op_str}")


if __name__ == '__main__':
    main()
