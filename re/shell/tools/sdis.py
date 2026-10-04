#!/usr/bin/env python3
"""sdis.py - capstone views of the PRISTINE i76shell.dll (md5 deb41008321cf018ba33c27bfbbfa074).

    python sdis.py dis  <va> [<end_va> | +N]      linear disassembly, annotated (IAT names, strings, class)
    python sdis.py fn   <va>                      disassemble the Ghidra function body containing <va>
    python sdis.py xref <va> [--any]              every instruction whose disp32/imm32 == <va> (--any: within +0x40)
    python sdis.py calls <va>                     every call/jmp rel32 whose target == <va>
    python sdis.py bytes <va> <n>                 raw bytes at <va> (and file offset)
    python sdis.py str  <regex>                   strings (>=4 printable) in .rdata/.data matching regex

Addresses are VAs in the DLL's preferred base 0x10000000 (class tags: text/rdata/data/bss/reloc; file offset =
VA - 0x10000000 - VirtualAddress + PointerToRawData, printed where it matters). Linear sweep of .text is used for
xref/calls (method recorded in every output line header), so counts are 'capstone linear-sweep operand sites'.
Strings are data, never instructions (G0).
"""
import sys, os, re, json, hashlib, bisect
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from capstone.x86 import X86_OP_MEM, X86_OP_IMM

HERE = os.path.dirname(os.path.abspath(__file__))
DLL = os.path.join(HERE, "..", "bin", "i76shell.dll")
PRISTINE = "deb41008321cf018ba33c27bfbbfa074"
EXPORT = os.path.join(HERE, "..", "ghidra", "export")


class Img:
    def __init__(self, path=DLL):
        self.data = open(path, "rb").read()
        self.md5 = hashlib.md5(self.data).hexdigest()
        pe = pefile.PE(data=self.data)
        self.base = pe.OPTIONAL_HEADER.ImageBase
        self.secs = []
        for s in pe.sections:
            nm = s.Name.rstrip(b"\0").decode()
            self.secs.append((nm, self.base + s.VirtualAddress, s.Misc_VirtualSize, s.PointerToRawData, s.SizeOfRawData))
        self.imports = {}
        for d in pe.DIRECTORY_ENTRY_IMPORT:
            for i in d.imports:
                self.imports[i.address] = (d.dll.decode(), i.name.decode() if i.name else "#%d" % i.ordinal)
        self.exports = {}
        for e in pe.DIRECTORY_ENTRY_EXPORT.symbols:
            self.exports[self.base + e.address] = e.name.decode()
        self._text = None

    def sec(self, va):
        for nm, v, vs, po, ps in self.secs:
            if v <= va < v + max(vs, ps):
                return nm, v, vs, po, ps
        return None

    def klass(self, va):
        if va in self.imports:
            return "iat"
        s = self.sec(va)
        if not s:
            return "none"
        nm, v, vs, po, ps = s
        if nm == ".data" and va - v >= ps:
            return "bss"
        return nm.lstrip(".")

    def off(self, va):
        s = self.sec(va)
        if not s:
            return None
        nm, v, vs, po, ps = s
        if va - v >= ps:
            return None
        return po + (va - v)

    def read(self, va, n):
        o = self.off(va)
        return b"" if o is None else self.data[o:o + n]

    def cstring(self, va, maxlen=100):
        b = self.read(va, maxlen + 1)
        if not b:
            return None
        e = b.find(b"\0")
        if e < 3:
            return None
        s = b[:e]
        if all(32 <= c < 127 or c in (9, 10, 13) for c in s):
            return s.decode("latin1")
        return None

    def text(self):
        if self._text is None:
            nm, v, vs, po, ps = [s for s in self.secs if s[0] == ".text"][0]
            self._text = (v, self.data[po:po + min(vs, ps)])
        return self._text


def md():
    m = Cs(CS_ARCH_X86, CS_MODE_32)
    m.detail = True
    return m


def annotate(img, ins):
    notes = []
    for op in ins.operands:
        tgt = None
        if op.type == X86_OP_MEM and op.mem.disp and img.klass(op.mem.disp & 0xffffffff) not in ("none", "text"):
            tgt = op.mem.disp & 0xffffffff
        elif op.type == X86_OP_IMM and not ins.mnemonic.startswith("j") and ins.mnemonic != "call":
            t = op.imm & 0xffffffff
            if img.klass(t) != "none":
                tgt = t
        if tgt is None:
            continue
        k = img.klass(tgt)
        tag = "%s:0x%x" % (k, tgt)
        if k == "iat":
            tag += " " + "!".join(img.imports[tgt])
        elif k in ("rdata", "data"):
            s = img.cstring(tgt)
            if s:
                tag += ' "%s"' % s.replace("\n", "\\n")[:70]
        elif k == "text" and tgt in img.exports:
            tag += " " + img.exports[tgt]
        notes.append(tag)
    if ins.mnemonic in ("call", "jmp") and ins.operands and ins.operands[0].type == X86_OP_IMM:
        t = ins.operands[0].imm & 0xffffffff
        nm = fname(t)
        if nm:
            notes.append(nm)
    return notes


_FN = None


def funcs():
    global _FN
    if _FN is None:
        p = os.path.join(EXPORT, "functions.json")
        _FN = {}
        if os.path.exists(p):
            for r in json.load(open(p, encoding="utf-8")):
                _FN[int(r["start"], 16)] = r
        # optional local names (symbols/functions.tsv)
        tsv = os.path.join(HERE, "..", "symbols", "functions.tsv")
        if os.path.exists(tsv):
            for ln in open(tsv, encoding="utf-8"):
                if ln.startswith("#") or ln.startswith("addr"):
                    continue
                c = ln.rstrip("\n").split("\t")
                if len(c) > 2:
                    a = int(c[0], 16)
                    _FN.setdefault(a, {"start": c[0], "end": c[0], "name": c[2]})
                    _FN[a]["name"] = c[2]
    return _FN


def fname(va):
    f = funcs().get(va)
    return f["name"] if f else None


def dis(img, start, end):
    o = img.off(start)
    code = img.data[o:o + (end - start)]
    out = []
    for ins in md().disasm(code, start):
        n = annotate(img, ins)
        out.append("%08x  %-7s %s%s" % (ins.address, ins.mnemonic, ins.op_str, ("    ; " + " | ".join(n)) if n else ""))
    return out


def containing(va):
    best = None
    for s, r in funcs().items():
        e = int(r["end"], 16)
        if s <= va <= e:
            if best is None or s > best[0]:
                best = (s, e + 1, r)
    return best


def sweep(img):
    v, code = img.text()
    m = md()
    m.skipdata = True
    for ins in m.disasm(code, v):
        if ins.id == 0:
            continue
        yield ins


def main(argv):
    img = Img()
    if img.md5 != PRISTINE:
        print("REFUSE: %s md5 %s is not the pristine GOG shell" % (DLL, img.md5))
        return 2
    cmd = argv[1]
    if cmd == "dis":
        s = int(argv[2], 16)
        e = argv[3] if len(argv) > 3 else "+0x80"
        e = s + int(e[1:], 0) if e.startswith("+") else int(e, 16)
        print("\n".join(dis(img, s, e)))
    elif cmd == "fn":
        c = containing(int(argv[2], 16))
        if not c:
            print("no function contains", argv[2]); return 1
        s, e, r = c
        print("; %s %s [0x%x,0x%x) size=%d md5=%s capstone linear over Ghidra body" % (r["start"], r["name"], s, e, e - s, img.md5))
        print("\n".join(dis(img, s, e)))
    elif cmd == "xref":
        t = int(argv[2], 16)
        span = 0x40 if "--any" in argv else 0
        n = 0
        print("; xref 0x%x method=capstone linear sweep of .text (skipdata), disp32|imm32 operand match%s" % (t, " within +0x40" if span else ""))
        for ins in sweep(img):
            for op in ins.operands:
                val = None
                if op.type == X86_OP_MEM:
                    val = op.mem.disp & 0xffffffff
                elif op.type == X86_OP_IMM and not ins.mnemonic.startswith("j") and ins.mnemonic != "call":
                    val = op.imm & 0xffffffff
                if val is not None and t <= val <= t + span:
                    c = containing(ins.address)
                    fn = ("%s %s" % (c[2]["start"], c[2]["name"])) if c else "?"
                    print("%08x  %-6s %-40s  in %s%s" % (ins.address, ins.mnemonic, ins.op_str, fn, "" if val == t else "  (+0x%x)" % (val - t)))
                    n += 1
                    break
        print("; %d sites" % n)
    elif cmd == "calls":
        t = int(argv[2], 16)
        n = 0
        for ins in sweep(img):
            if ins.mnemonic in ("call", "jmp") and ins.operands and ins.operands[0].type == X86_OP_IMM and (ins.operands[0].imm & 0xffffffff) == t:
                c = containing(ins.address)
                print("%08x  %s  in %s" % (ins.address, ins.mnemonic, ("%s %s" % (c[2]["start"], c[2]["name"])) if c else "?"))
                n += 1
        print("; %d direct call/jmp sites (capstone linear sweep)" % n)
    elif cmd == "bytes":
        va, n = int(argv[2], 16), int(argv[3], 0)
        print("va 0x%x file 0x%x: %s" % (va, img.off(va), img.read(va, n).hex(" ")))
    elif cmd == "str":
        rx = re.compile(argv[2], re.I)
        for nm, v, vs, po, ps in img.secs:
            if nm not in (".rdata", ".data"):
                continue
            blob = img.data[po:po + ps]
            for m_ in re.finditer(rb"[\x20-\x7e\t\r\n]{4,}", blob):
                s = m_.group().decode("latin1")
                if rx.search(s):
                    print("0x%08x %s %r" % (v + m_.start(), nm, s[:120]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
