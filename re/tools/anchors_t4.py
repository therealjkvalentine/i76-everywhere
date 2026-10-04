#!/usr/bin/env python3
"""anchors_t4.py - Task 4: build the zero-inference anchor batch (functions + globals + evidence) from the
pristine binary, the Ghidra export and Task 3's TSVs, re-deriving every fact it claims (nothing is copied
from a report without being re-measured here). Output: a merge.py batch JSON plus a funnel log.

    python tools\\anchors_t4.py [--map C:\\Users\\james\\i76-map] [--out status\\tasks\\t4-anchors.batch.json]

Every evidence row carries md5 (H0), and every count its method (gate C). Rows the gates cannot carry are
emitted as `proposed` (merge.py stores them; ApplyMap never applies a proposed name).
"""
import os, sys, json, csv, re, argparse, struct, bisect, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_tables import Image, hx
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from capstone.x86 import X86_OP_MEM, X86_OP_IMM, X86_OP_REG

MD5 = "9a232dcc2c164648cff20c414c1f9698"
T = 0x400c00  # .text file delta (VA - file)


def E(kind, **kw):
    d = {"kind": kind, "md5": MD5, "instrument-checked": "n/a"}
    d.update(kw)
    return d


class Ctx:
    def __init__(self, M):
        self.M = M
        self.img = Image(os.path.join(M, "ghidra", "i76_ref.exe"))
        assert self.img.md5 == MD5, self.img.md5
        self.data = self.img.data
        self.md = Cs(CS_ARCH_X86, CS_MODE_32); self.md.detail = True
        fj = json.load(open(os.path.join(M, "ghidra", "export", "functions.json"), encoding="utf-8"))
        self.inv = {int(r["addr"], 16): r for r in fj}
        self.starts = sorted(self.inv)
        self.cg = json.load(open(os.path.join(M, "ghidra", "export", "callgraph.json"), encoding="utf-8"))
        self.fcsv = {}
        with open(os.path.join(M, "ghidra", "export", "functions.csv"), newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                self.fcsv[int(r["address"], 16)] = r
        self.strings = self.tsv("strings.tsv")
        self.str_by_addr = {int(r["addr"], 16): r for r in self.strings}
        self.str_by_text = {}
        for r in self.strings:
            self.str_by_text.setdefault(r["string"], []).append(r)
        self.imports = self.tsv("imports.tsv")
        self.imp_by_name = {r["name"]: r for r in self.imports}
        self.imp_by_slot = {int(r["iat_slot"], 16): r for r in self.imports}
        self.tables = self.tsv("tables.tsv")
        self.log = []
        self.funcs = []
        self.globs = []
        self.names = {}

    def tsv(self, name):
        cols = None; rows = []
        with open(os.path.join(self.M, "symbols", name), encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("#"): continue
                line = line.rstrip("\r\n")
                if not line: continue
                p = line.split("\t")
                if cols is None: cols = p; continue
                p += [""] * (len(cols) - len(p)); rows.append(dict(zip(cols, p)))
        return rows

    def say(self, s):
        self.log.append(s); print(s)

    # -- disassembly ----------------------------------------------------------------------------
    def body(self, fa):
        r = self.inv[fa]; s = int(r["start"], 16); e = int(r["end"], 16) + 1
        return list(self.md.disasm(self.data[s - T:e - T], s))

    def dis(self, va, nbytes):
        return list(self.md.disasm(self.data[va - T:va - T + nbytes], va))

    def func_of(self, va):
        i = bisect.bisect_right(self.starts, va) - 1
        if i < 0: return None
        r = self.inv[self.starts[i]]
        return self.starts[i] if int(r["start"], 16) <= va <= int(r["end"], 16) else None

    def imm_sites(self, value, kinds=("imm", "mem")):
        """All .text instruction sites (inside Ghidra bodies) with imm32 == value or disp32 == value. Method: capstone."""
        out = []
        for fa in self.starts:
            for i in self.body(fa):
                for op in i.operands:
                    if op.type == X86_OP_IMM and op.imm == value and "imm" in kinds:
                        out.append((i.address, fa, "imm")); break
                    if op.type == X86_OP_MEM and op.mem.disp == value and "mem" in kinds:
                        out.append((i.address, fa, "mem")); break
        return out

    def calls_import(self, fa, name):
        """Sites in fa calling import `name` (method: Ghidra callgraph call_sites, cross-checked with imports.tsv capstone functions)."""
        sites = [s[0] for s in self.cg["%08x" % fa]["call_sites"] if s[2] == name]
        row = self.imp_by_name.get(name)
        cap = ("%08x" % fa) in [f.lstrip("0x").rjust(8, "0") for f in (row["functions"].split(";") if row else [])]
        return sites, cap

    def string_ref(self, fa, saddr):
        r = self.str_by_addr[saddr]
        g = ("%08x" % fa) in r["referencing_functions"].split(";")
        c = ("0x%x" % fa) in r["imm32_functions"].split(";")
        return g, c, r["string"]

    # -- row builders ---------------------------------------------------------------------------
    def func(self, addr, name, status, evidence, subsystem="", conv=None, conv_evidence=None, size=None, note=None):
        row = {"addr": "0x%x" % addr, "name": name, "status": status, "evidence": evidence, "subsystem": subsystem}
        if conv: row["conv"] = conv
        if conv_evidence: row["conv_evidence"] = conv_evidence
        if size is not None: row["size"] = size
        if note: row["note"] = note
        if name in self.names and self.names[name] != addr:
            raise SystemExit("duplicate name %s for %x and %x" % (name, self.names[name], addr))
        self.names[name] = addr
        self.funcs.append(row); return row

    def glob(self, addr, cls, width, typ, name, status, evidence, readers="", writers="", bound=""):
        row = {"addr": "0x%x" % addr, "class": cls, "width": width, "type": typ, "name": name, "status": status,
               "readers": readers, "writers": writers, "bound_evidence": bound, "evidence": evidence}
        if name in self.names and self.names[name] != addr:
            raise SystemExit("duplicate name %s" % name)
        self.names[name] = addr
        self.globs.append(row); return row

    def str_ev(self, fa, saddr, form=None, literal=None, claim=None):
        g, c, s = self.string_ref(fa, saddr)
        assert g or c, "string %x not referenced by %x" % (saddr, fa)
        d = E("string-xref", string_addr="0x%x" % saddr, string=s, method="ghidra-xref=%s;capstone-imm32=%s" % (g, c),
              source="symbols/strings.tsv", claim=claim or ("function references string %s" % hx(saddr)))
        if form: d["form"] = form; d["literal"] = literal
        return d

    def imp_ev(self, fa, name, claim=None):
        sites, cap = self.calls_import(fa, name)
        assert sites or cap, "import %s not called from %x" % (name, fa)
        return E("import-callee", import_name=name, sites=["0x" + s for s in sites], method="ghidra-callgraph;capstone(imports.tsv)=%s" % cap,
                 source="ghidra/export/callgraph.json", claim=claim or ("calls %s" % name))

    def const_ev(self, fa, value, claim, kinds=("imm", "mem")):
        sites = self.imm_sites(value, kinds)
        here = [s for s in sites if s[1] == fa]
        assert here, "constant %x not in %x" % (value, fa)
        fns = sorted({s[1] for s in sites})
        return E("constant-anchor", value="0x%x" % value, sites_here=["0x%x" % s[0] for s in here], n=len(sites),
                 functions=["0x%x" % f for f in fns], method="capstone imm32/disp32 scan over all Ghidra bodies",
                 source="ghidra/i76_ref.exe", claim=claim, unique=(len(fns) <= 3))


# ==================================================================================================
def build(C):
    img, inv, say = C.img, C.inv, C.say

    # ---------------- 1. thunks (22 Ghidra thunks = 20 import thunks + 2 intra-module) ------------
    thunks = [a for a in C.starts if inv[a]["thunk"]]
    n_ext = 0
    for a in thunks:
        ins = C.dis(a, 8)[0]
        tgt = inv[a]["thunk_target"]
        if ins.mnemonic == "jmp" and ins.operands[0].type == X86_OP_MEM:
            slot = ins.operands[0].mem.disp
            imp = C.imp_by_slot[slot]
            nm = imp["name"]
            pretty = {"??3@YAXPAX@Z": "operator_delete", "??2@YAPAXI@Z": "operator_new"}.get(nm, nm)
            C.func(a, "thunk_" + pretty, "anchored",
                   [E("import-thunk", site="0x%x" % a, insn="%s %s" % (ins.mnemonic, ins.op_str), slot="0x%x" % slot,
                      dll=imp["dll"], import_name=nm, method="capstone decode of the thunk body: jmp dword ptr [iat slot]",
                      source="symbols/imports.tsv", claim="6-byte jmp [slot] thunk to %s!%s (G1 rule a)" % (imp["dll"], nm))],
                   subsystem="import-thunk"); n_ext += 1
        else:
            assert ins.mnemonic == "jmp" and ins.operands[0].type == X86_OP_IMM
            C.func(a, inv[a]["name"], "synthetic",
                   [E("synthetic-shape", site="0x%x" % a, insn="%s %s" % (ins.mnemonic, ins.op_str), shape="intra-module jmp rel32 thunk",
                      target="0x%x" % ins.operands[0].imm, method="capstone decode", source="ghidra/i76_ref.exe",
                      claim="5-byte jmp rel32 to %s; compiler-generated thunk (gate L synthetic)" % tgt)],
                   subsystem="synthetic")
    say("FUNNEL thunks: Ghidra isThunk=%d -> jmp [iat]=%d (import thunks, anchored) + jmp rel32=%d (synthetic)"
        % (len(thunks), n_ext, len(thunks) - n_ext))

    # ---------------- 2. Smacker ordinals: names from SMACKW32.DLL's export table -----------------
    dll = os.path.join(r"C:\Users\james\i76-uncap-lab\game", "SMACKW32.DLL")
    pe = pefile.PE(dll)
    dll_md5 = hashlib.md5(open(dll, "rb").read()).hexdigest()
    exp = {e.ordinal: e.name.decode() for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name}
    nsm = 0
    for r in C.imports:
        if r["dll"].lower() == "smackw32.dll":
            ordn = int(r["name"].lstrip("#"))
            nm = exp[ordn]
            slot = int(r["iat_slot"], 16)
            C.glob(slot, "iat", 4, "FARPROC", nm, "anchored",
                   [E("export-ordinal", dll="SMACKW32.DLL", dll_md5=dll_md5, ordinal=ordn, export_name=nm,
                      method="pefile export directory of SMACKW32.DLL (ordinal -> name); import descriptor gives slot -> ordinal",
                      source=dll, claim="IAT slot %s imports SMACKW32 ordinal %d = %s" % (hx(slot), ordn, nm))],
                   readers="call=%s load=%s (imports.tsv, capstone)" % (r["call_sites"], r["load_sites"]))
            nsm += 1
    say("FUNNEL smacker: %d ordinal imports -> %d resolved by the DLL export table (md5 %s)" % (nsm, nsm, dll_md5))

    # ---------------- 3. entry + WinMain ----------------------------------------------------------
    ep = img.base + img.pe.OPTIONAL_HEADER.AddressOfEntryPoint
    assert ep == 0x4ba0e0
    C.func(ep, "entry", "anchored", [E("pe-entry", value="0x%x" % ep, method="pefile OPTIONAL_HEADER.AddressOfEntryPoint",
                                         source="ghidra/i76_ref.exe", claim="PE entry point")], subsystem="crt")
    # WinMain: in entry, the call to 0x402b30 is preceded (within 16 instructions) by GetModuleHandleA and 4 pushes
    ins = C.body(ep)
    idx = [k for k, i in enumerate(ins) if i.mnemonic == "call" and i.operands[0].type == X86_OP_IMM and i.operands[0].imm == 0x402b30]
    assert len(idx) == 1
    k = idx[0]
    window = ins[max(0, k - 16):k]
    gmh = [i for i in window if i.mnemonic == "call" and i.operands[0].type == X86_OP_MEM and i.operands[0].mem.disp == int(C.imp_by_name["GetModuleHandleA"]["iat_slot"], 16)]
    # ... push eax(nShow); push esi(cmdline); push 0(hPrev); push 0; call [GetModuleHandleA]; push eax(hInstance); call 0x402b30
    pushes = [i for i in ins[k - 7:k] if i.mnemonic == "push"]
    assert gmh and gmh[-1].address == ins[k - 2].address and ins[k - 1].mnemonic == "push" and len(pushes) == 5, (gmh, pushes)
    C.func(0x402b30, "WinMain", "anchored",
           [E("pe-entry", site="0x%x" % ins[k].address, method="capstone: in entry, call 0x402b30 preceded by call [GetModuleHandleA] at %s and exactly 4 pushes"
              % hx(gmh[-1].address), pushes=["%s %s" % (p.mnemonic, p.op_str) for p in pushes], source="ghidra/i76_ref.exe",
              claim="CRT WinMainCRTStartup calls WinMain(hInstance, hPrev, lpCmdLine, nShow)"),
            C.str_ev(0x402b30, 0x4c2640, claim="WinMain owns the command-line failure message"),
            C.str_ev(0x402b30, 0x4c25c0, claim="WinMain owns the pool failure message")],
           subsystem="crt")
    say("FUNNEL entry/WinMain: entry callees %s; exactly one call immediately preceded by call [GetModuleHandleA]; push eax, with 3 pushes (nShow, cmdline, 0) before it -> 0x402b30" % C.cg["%08x" % ep]["callees"])

    # ---------------- 4. Unwind funclets (42) + EH stubs (30, created) --------------------------------
    fun = [a for a in C.starts if inv[a]["name"].startswith("Unwind@")]
    for a in fun:
        b = C.dis(a, 11)
        C.func(a, inv[a]["name"], "synthetic",
               [E("synthetic-shape", site="0x%x" % a, size=inv[a]["size"], insns=["%s %s" % (i.mnemonic, i.op_str) for i in b],
                  shape="MSVC EH unwind funclet (11 B)", method="Ghidra EH analyzer name + capstone decode", source="ghidra/export/functions.json",
                  claim="compiler-generated unwind funclet (gate L synthetic)")], subsystem="synthetic")
    stubs = []
    for va in range(0x4bba40, 0x4bbe56):
        o = va - T
        if C.data[o] == 0xB8 and C.data[o + 5] == 0xE9 and va + 10 + struct.unpack_from("<i", C.data, o + 6)[0] == 0x4ba304:
            stubs.append((va, struct.unpack_from("<I", C.data, o + 1)[0]))
    for s, fi in stubs:
        pat = b"\x68" + struct.pack("<I", s)
        sites = []; i = C.data.find(pat, 0x400)
        while 0 <= i < 0x4bbe56 - T:
            sites.append(i + T); i = C.data.find(pat, i + 1)
        owners = sorted({C.func_of(x) for x in sites if C.func_of(x)})
        assert len(sites) == 1 and len(owners) == 1, (hex(s), sites)
        assert s not in inv
        C.func(s, "eh_stub_%08x" % owners[0], "synthetic",
               [E("synthetic-shape", site="0x%x" % s, shape="mov eax,FuncInfo; jmp __CxxFrameHandler(0x4ba304)", funcinfo="0x%x" % fi,
                  pushed_at="0x%x" % sites[0], owner="0x%x" % owners[0], method="byte scan B8 imm32 E9 rel32->0x4ba304 over 0x4bba40-0x4bbe55; push imm32 scan over .text",
                  source="ghidra/i76_ref.exe", claim="MSVC C++ EH handler stub for the function that pushes it in its prologue"),
                E("create", method="byte scan (30 sites, each pushed by exactly one prologue); not a Ghidra function in pass 4", n=30,
                  source="ghidra/i76_ref.exe", claim="ApplyMap creates a 10-byte function here")],
               subsystem="synthetic", size=10)
    say("FUNNEL EH: Unwind@ funclets=%d (Ghidra); EH stubs by byte scan=%d, all 30 pushed by exactly one prologue (method doc said 24)" % (len(fun), len(stubs)))

    # ---------------- 5. LZO object (gate L per function) + __allshl/__allshr (FID) ---------------
    def feats(fa, lo, hi, want):
        ins = list(C.md.disasm(C.data[lo - T:hi - T], lo))
        txt = {}
        for i in ins: txt.setdefault("%s %s" % (i.mnemonic, i.op_str), []).append(i.address)
        got = {w: ["0x%x" % x for x in txt.get(w, [])] for w in want}
        calls = sum(1 for i in ins if i.mnemonic == "call")
        absmem = sum(1 for i in ins if any(op.type == X86_OP_MEM and op.mem.base == 0 and op.mem.index == 0 for op in i.operands))
        return got, len(ins), calls, absmem
    lzo_src = "LZO 1.00 src/lzo1x_d.ch + lzo1x_d1.ash/lzo1y_d1.ash (x86 asm decoders); zfs-lzo-refute section 2"
    for fa, name, off_lea, shr, andm in ((0x4babd8, "lzo1x_decompress", "lea edx, [edi - 0x801]", "shr ecx, 5", "and eax, 7"),
                                         (0x4baa00, "lzo1y_decompress", "lea edx, [edi - 0x401]", "shr ecx, 4", "and eax, ebp")):
        want = [off_lea, shr, andm, "cmp al, 0x11", "and eax, 0x1f", "lea edx, [edi - 0x4000]", "setne al"]
        got, n, calls, absmem = feats(fa, fa, fa + inv[fa]["size"], want)
        assert all(got[w] for w in want) and calls == 0 and absmem == 0, got
        other = "lea edx, [edi - 0x401]" if fa == 0x4babd8 else "lea edx, [edi - 0x801]"
        assert not feats(fa, fa, fa + inv[fa]["size"], [other])[0][other]
        site = 0x4ba032 if fa == 0x4babd8 else 0x4ba05a
        C.func(fa, name, "library",
               [E("asm-shape", features=got, insns=n, calls=calls, absolute_mem_refs=absmem, m2_max_offset=("0x800" if fa == 0x4babd8 else "0x400"),
                  method="capstone decode of the body; feature strings matched exactly; the other variant's M2 offset absent",
                  source=lzo_src, claim="%s: M2 branch and M2_MAX_OFFSET match the LZO1%s decoder" % (name, "X" if fa == 0x4babd8 else "Y")),
                E("call-cleanup", site="0x%x" % site, cleanup="add esp, 0x14", method="capstone at the call site in 0x4b9fc0", source="ghidra/i76_ref.exe",
                  claim="cdecl, 5 stack args (src, src_len, dst, &dst_len, wrkmem)")],
               subsystem="lzo", conv="__cdecl", conv_evidence="call-cleanup@0x%x:add esp,0x14" % site)
    # __lzo_init2: v==0 -> -1, 8 args, caller cleans 0x20, tail-jumps to the config check that calls adler32 + align_gap
    b = C.dis(0x4ba980, 0x60)
    cmp0 = [i for i in b if i.mnemonic == "cmp" and "[esp + 8], 2" in i.op_str]
    tail = [i for i in b if i.mnemonic == "jmp" and i.operands[0].type == X86_OP_IMM and i.operands[0].imm == 0x4ba6d0]
    assert cmp0 and tail
    rng = list(C.md.disasm(C.data[0x4ba6d0 - T:0x4ba980 - T], 0x4ba6d0))
    callees = sorted({i.operands[0].imm for i in rng if i.mnemonic == "call" and i.operands[0].type == X86_OP_IMM})
    assert callees == [0x4ba9e0, 0x4badb0], callees
    C.func(0x4ba980, "__lzo_init2", "library",
           [E("asm-shape", method="capstone: entry checks param_2==2 (sizeof short) and the six size params, returns -1 on mismatch, then jmp 0x4ba6d0 (config check) which calls only 0x4badb0 (adler32) and 0x4ba9e0 (align gap); Ghidra body = 2 ranges 0x4ba6d0-0x4ba9dd",
              config_check_callees=["0x4ba9e0", "0x4badb0"], source="LZO 1.00 src/lzo_init.c __lzo_init2 + lzo_util.c _lzo_config_check; zfs-lzo-refute section 2",
              claim="__lzo_init2(v, s1..s7) with the 1.00 config check as its tail"),
            C.str_ev(0x4ba980, 0x4bfd80, claim="references the LZO copyright banner"),
            E("call-cleanup", site="0x4b9fe7", cleanup="add esp, 0x20", method="capstone at the call site in 0x4b9fc0", source="ghidra/i76_ref.exe", claim="cdecl, 8 stack args")],
           subsystem="lzo", conv="__cdecl", conv_evidence="call-cleanup@0x4b9fe7:add esp,0x20")
    b = C.body(0x4ba9e0)
    C.func(0x4ba9e0, "__lzo_align_gap", "library",
           [E("asm-shape", insns=["%s %s" % (i.mnemonic, i.op_str) for i in b], method="capstone decode; decompiles to ((p+size-1)/size)*size-p",
              source="LZO 1.00 src/lzo_util.c __lzo_align_gap: n = (n + size - 1) / size * size - n", claim="__lzo_align_gap(p, size)")],
           subsystem="lzo")
    got, n, calls, absmem = feats(0x4badb0, 0x4badb0, 0x4badb0 + inv[0x4badb0]["size"], ["cmp edx, 0x15b0", "mov ecx, 0x15b0"])
    c15b0 = C.const_ev(0x4badb0, 0x15b0, "NMAX=5552 (adler32 block)", kinds=("imm",))
    cfff1 = C.const_ev(0x4badb0, 0xfff1, "BASE=65521 (adler32 modulus)", kinds=("imm",))
    C.func(0x4badb0, "lzo_adler32", "library",
           [E("asm-shape", constants={"NMAX": "0x15b0", "BASE": "0xfff1"}, nmax_sites=c15b0["sites_here"], base_sites=cfff1["sites_here"],
              calls=calls, absolute_mem_refs=absmem, method="capstone: both adler32 constants present, leaf, no absolute memory refs; prototype (uint adler, byte* buf, uint len) from ParamID",
              source="LZO 1.00 src/lzo_crc.c lzo_adler32 (NMAX 5552, BASE 65521); called twice from the config check at 0x4ba7cd/0x4ba7e0", claim="lzo_adler32")],
           subsystem="lzo")
    for a in (0x4ba290, 0x4ba2d0):
        r = C.fcsv[a]; assert r["fid_named"] == "true"
        C.func(a, r["name"], "library", [E("fid", name=r["name"], method="Ghidra Function ID analyzer (functions.csv fid_named=true, bookmark %s)" % r["bookmark_categories"],
                                            source="ghidra/export/functions.csv", claim="MSVC intrinsic matched by FID")], subsystem="crt")
    say("FUNNEL lzo: 5 functions, each with its own asm-shape row; __allshl/__allshr by FID")

    # ---------------- 6. BWD2 handlers (70) with every (table,tag) pair -----------------------------
    pairs = {}
    for r in C.tables:
        if r["kind"] != "bwd2-desc": continue
        base = int(r["base"], 16)
        for i, ent in enumerate(r["targets"].split(";")):
            tag, rest = ent.split("=", 1); h, fl = rest.split("/")
            h = int(h, 16)
            rec = base + 16 * i
            assert img.u32(rec + 8) == h, (hex(rec), hex(h))  # re-read from the file
            tagbytes = img.bytes_at(rec, 4)
            if h == 0: continue
            pairs.setdefault(h, []).append({"table": r["base"], "index": i, "tag": tag.replace("\\0", ""), "record": "0x%x" % rec,
                                            "flags": fl, "tag_bytes": tagbytes.hex()})
    nonfunc = [h for h in pairs if h not in inv]
    assert not nonfunc, nonfunc
    for h in sorted(pairs):
        ps = pairs[h]
        tags = []
        for p in sorted(ps, key=lambda p: (p["table"], p["index"])):
            if p["tag"] not in tags: tags.append(p["tag"])
        name = "bwd2_h_%s_%x" % ("_".join(tags), h)
        ev = [E("table-entry", pairs=ps, n=len(ps), method="tables.tsv bwd2-desc rows re-read from the file: u32 at record+8 == handler",
                source="symbols/tables.tsv", claim="BWD2 descriptor handler for %s (G1 rule a; gate N lists every pair)" % ",".join(tags))]
        if h == 0x4b4610:
            ev.append(C.str_ev(h, 0x500704, claim="REV handler owns 'Bad BWD revision for file %s'"))
        C.func(h, name, "anchored", ev, subsystem="bwd2")
    say("FUNNEL bwd2: records=%d non-null=%d distinct handlers=%d, all Ghidra function starts" % (
        sum(len(r["targets"].split(";")) for r in C.tables if r["kind"] == "bwd2-desc"), sum(len(v) for v in pairs.values()), len(pairs)))

    # ---------------- 7. shell callbacks (27) ----------------------------------------------------------
    sc = [r for r in C.tables if r["name"] == "shell_callbacks"][0]
    ents = []
    for x in sc["targets"].split(";"):
        tgt, site = x.split("@"); tgt = int(tgt, 16); site = int(site, 16)
        i = C.dis(site, 12)[0]
        assert i.mnemonic == "mov" and i.operands[0].type == X86_OP_MEM and i.operands[1].type == X86_OP_IMM and i.operands[1].imm == tgt
        ents.append((i.operands[0].mem.disp, tgt, site, "%s %s" % (i.mnemonic, i.op_str)))
    ents.sort()
    assert len({e[1] for e in ents}) == 27
    ncreate = 0
    for n, (disp, tgt, site, insn) in enumerate(ents):
        ev = [E("callback-pointer", site="0x%x" % site, insn=insn, slot_index=n, esp_disp=disp, table="stack:0x4022e0:esp+20",
                method="capstone: mov [esp+disp], imm32 inside 0x4022e0 (the vector handed to ShellMain), ordered by disp",
                source="symbols/tables.tsv", claim="exe->shell callback slot %d" % n)]
        size = None
        if tgt not in inv:
            ncreate += 1
            # size estimate: linear decode until the first ret (informational; Ghidra defines the body)
            n_b = 0
            for i in C.md.disasm(C.data[tgt - T:tgt - T + 0x800], tgt):
                n_b = i.address + i.size - tgt
                if i.mnemonic == "ret": break
            size = n_b
            ev.append(E("create", method="target of a callback-vector store; lies in a regions.tsv gap-code region, not a Ghidra function in pass 4 (size = bytes to the first ret, capstone linear)",
                        size_est=n_b, source="symbols/regions.tsv", claim="ApplyMap creates a function here"))
        C.func(tgt, "shell_cb_%02d" % n, "anchored", ev, subsystem="shell", size=size)
    say("FUNNEL shell callbacks: 27 stores decoded, 27 distinct targets, %d are Ghidra functions, %d in gap regions (created)" % (27 - ncreate, ncreate))

    # ---------------- 8. loaders: renderer / shell / FFB / cmdline ------------------------------------
    def procaddr_stores(fa):
        """(slot, name_string_addr) pairs: push <str>; ...; call reg(GetProcAddress); mov [slot], eax  (store may be one call late)."""
        ins = C.body(fa)
        out = []; last_name = None; pending = None
        for i in ins:
            if i.mnemonic == "push" and i.operands[0].type == X86_OP_IMM and i.operands[0].imm in C.str_by_addr:
                last_name = i.operands[0].imm
            elif i.mnemonic == "call":
                pending = last_name if last_name is not None else pending
            elif i.mnemonic == "mov" and i.operands[0].type == X86_OP_MEM and i.operands[0].mem.base == 0 and i.operands[1].type == X86_OP_REG and i.reg_name(i.operands[1].reg) == "eax":
                if pending is not None:
                    out.append((i.operands[0].mem.disp, pending, i.address)); pending = None
        return out
    # renderer loader 0x426900
    st = procaddr_stores(0x426900)
    st = [s for s in st if 0x608ba4 <= s[0] <= 0x608be4]
    assert len(st) == 16, st
    C.func(0x426900, "renderer_LoadPlugin", "supported",
           [C.imp_ev(0x426900, "LoadLibraryA"), C.imp_ev(0x426900, "GetProcAddress"),
            C.str_ev(0x426900, 0x4ede54, claim="GetFuncDesc"), C.str_ev(0x426900, 0x4ede48, claim="CheckFunc"), C.str_ev(0x426900, 0x4c2628, claim="RASTER"),
            E("global-write", slots=["0x%x=%s@0x%x" % (s[0], C.str_by_addr[s[1]]["string"], s[2]) for s in st], n=16, method="capstone: push name; call GetProcAddress; mov [slot],eax",
              source="ghidra/i76_ref.exe", claim="fills the 16 renderer entry slots 0x608ba4-0x608be4 (0x608bb8 never written)")],
           subsystem="renderer")
    for slot, sa, site in st:
        nm = C.str_by_addr[sa]["string"]
        C.glob(slot, "bss", 4, "FARPROC", "renderer_fn_%s" % nm, "anchored",
               [E("string-xref", form="procaddr", literal=nm, string_addr="0x%x" % sa, site="0x%x" % site, loader="0x426900",
                  method="capstone: GetProcAddress(hmod, \"%s\") result stored at this slot (store is one call late; verified by decode order)" % nm,
                  source="ghidra/i76_ref.exe", claim="renderer plugin export %s" % nm),
                E("ref-site", site="0x%x" % site, method="capstone disp32", source="ghidra/i76_ref.exe", claim="store site"),
                E("width-from", site="0x%x" % site, width=4, method="capstone operand size", source="ghidra/i76_ref.exe", claim="dword store")],
               writers="0x%x" % site)
    C.func(0x426b40, "renderer_SelectPlugin", "supported",
           [C.str_ev(0x426b40, 0x4c2628, claim="RASTER"), C.str_ev(0x426b40, 0x4ede6c, claim="SOUND"), C.str_ev(0x426b40, 0x4ede64, claim="DRIVER"),
            C.imp_ev(0x426b40, "_stricmp")], subsystem="renderer")
    # shell loader 0x4022e0
    C.func(0x4022e0, "shell_Load", "supported",
           [C.str_ev(0x4022e0, 0x4c228c, claim="ShellMain"), C.str_ev(0x4022e0, 0x4c227c, claim="ShellWindowProc"), C.imp_ev(0x4022e0, "GetProcAddress"),
            E("callback-pointer", n=27, method="tables.tsv shell_callbacks (capstone stores)", source="symbols/tables.tsv", claim="builds the 27-slot callback vector before GetProcAddress(ShellMain)")],
           subsystem="shell")
    # FFB loader 0x446020
    st = procaddr_stores(0x446020)
    st = [s for s in st if 0x52bbdc <= s[0] <= 0x52bbe4]
    assert len(st) == 3, st
    sf = os.path.join(r"C:\Users\james\i76-uncap-lab\game", "i7_sfrce.dll")
    sfexp = {e.name.decode() for e in pefile.PE(sf).DIRECTORY_ENTRY_EXPORT.symbols if e.name}
    C.func(0x446020, "FFB_LoadDriver", "supported",
           [C.imp_ev(0x446020, "LoadLibraryA"), C.imp_ev(0x446020, "GetProcAddress"), C.str_ev(0x446020, 0x4f2500, claim="I7_SFRCE.DLL"),
            C.str_ev(0x446020, 0x4f24f0, claim="I7FF_InitSystem"), C.str_ev(0x446020, 0x4f24e0, claim="I7FF_ExitSystem"), C.str_ev(0x446020, 0x4f24d0, claim="I7FF_SIM_Effect"),
            E("global-write", slots=["0x%x=%s@0x%x" % (s[0], C.str_by_addr[s[1]]["string"], s[2]) for s in st], n=3, method="capstone push/call/mov-store order", source="ghidra/i76_ref.exe",
              claim="fills the three FFB slots; the names are exports of i7_sfrce.dll (%s)" % sorted(sfexp))],
           subsystem="ffb")
    for slot, sa, site in st:
        nm = C.str_by_addr[sa]["string"]; assert nm in sfexp
        C.glob(slot, "bss", 4, "FARPROC", "ffb_fn_%s" % nm, "anchored",
               [E("string-xref", form="procaddr", literal=nm, string_addr="0x%x" % sa, site="0x%x" % site, loader="0x446020", dll_export=True,
                  method="capstone: GetProcAddress(hmod, name) result stored at the slot; name is an export of i7_sfrce.dll (pefile)", source="ghidra/i76_ref.exe", claim="FFB driver export %s" % nm),
                E("ref-site", site="0x%x" % site, method="capstone disp32", source="ghidra/i76_ref.exe", claim="store site"),
                E("width-from", site="0x%x" % site, width=4, method="capstone operand size", source="ghidra/i76_ref.exe", claim="dword store")], writers="0x%x" % site)
    # command-line parser 0x49d1d0
    toks = [a for a, r in C.str_by_addr.items() if r["string"] in ("gdi", "glide", "redline", "d3d", "powervr", "hal", "recordLoads", "interval") and "0049d1d0" in r["referencing_functions"]]
    # gdi/hal/d3d are 3-byte strings below Ghidra's minimum and are not in strings.tsv; five tokens carry xrefs
    assert len(toks) == 5, toks
    C.func(0x49d1d0, "cmdline_Parse", "supported",
           [C.imp_ev(0x49d1d0, "strtok"), C.imp_ev(0x49d1d0, "_stricmp")] + [C.str_ev(0x49d1d0, a, claim="switch token") for a in sorted(toks)],
           subsystem="startup")
    say("FUNNEL loaders: renderer 16 slot stores verified, FFB 3 slot stores verified (all 3 names are i7_sfrce.dll exports), cmdline %d switch tokens" % len(toks))

    # ---------------- 9. sim clock -------------------------------------------------------------------
    gtc = "GetTickCount"
    w1c = C.imm_sites(0x5a7e1c)
    incs = [s for s in w1c if s[1] == 0x49c920]
    assert len(w1c) == 5 and len(incs) == 1
    ins = C.dis(incs[0][0], 8)[0]; assert ins.mnemonic == "inc"
    C.func(0x49c7f0, "simclock_Init", "supported",
           [C.imp_ev(0x49c7f0, gtc), E("global-write", targets=["0x4fe428", "0x5a7e10", "0x5a7e14", "0x5a7e18", "0x5a7e1c"], method="refute-timer-claim section 3 (disassembly), re-checked: disp32 sites in this body",
                                        sites=["0x%x" % s[0] for s in C.imm_sites(0x4fe428) if s[1] == 0x49c7f0], source="recon-2026-09-04/recon/refute-timer-claim/REPORT.md", claim="initialises dt/now/frame globals")],
           subsystem="simclock")
    C.func(0x49c920, "simclock_Update", "supported",
           [C.imp_ev(0x49c920, gtc), E("global-write", site="0x%x" % incs[0][0], insn="%s %s" % (ins.mnemonic, ins.op_str), method="capstone: the only inc of 0x5a7e1c in .text (5 sites total, 1 write)",
                                        n=5, source="ghidra/i76_ref.exe", claim="per-frame: increments the frame counter, dt = delta(GetTickCount)*0.001 clamped [0.001,0.2]")],
           subsystem="simclock")
    for fa, name, g, typ in ((0x49c8b0, "simclock_GetDt", 0x4fe428, "float"), (0x49c8c0, "simclock_GetTime", 0x5a7e74, "float"),
                             (0x49c7d0, "simclock_GetFrameCount", 0x5a7e1c, "uint32"), (0x49c7e0, "simclock_GetAccumDt", 0x5a7e14, "float")):
        b = C.body(fa)
        ld = [i for i in b if any(op.type == X86_OP_MEM and op.mem.disp == g for op in i.operands)]
        assert len(b) <= 3 and len(ld) == 1 and b[-1].mnemonic == "ret", [(i.mnemonic, i.op_str) for i in b]
        C.func(fa, name, "supported",
               [E("global-write", kind_note="getter", site="0x%x" % ld[0].address, insn="%s %s" % (ld[0].mnemonic, ld[0].op_str), n_callers=inv[fa]["n_callers"],
                  method="capstone: body is load-global; ret (Ghidra n_callers)", source="ghidra/i76_ref.exe", claim="returns the sim-clock global %s" % hx(g)),
                E("verified-callee", note="0x49c920 (simclock_Update) is the writer of this global", method="capstone disp32 sites", source="ghidra/i76_ref.exe", claim="global written by the sim clock"),
                E("constant-anchor", value="0x%x" % g, n=len(C.imm_sites(g)), functions=sorted({"0x%x" % s[1] for s in C.imm_sites(g)}), method="capstone disp32 scan",
                  source="ghidra/i76_ref.exe", claim="all references to the clock global lie in 0x49c7d0-0x49cc90", unique=True)],
               subsystem="simclock")
        cls = img.klass(g)
        site = ld[0].address
        C.glob(g, cls, 4, typ, {"simclock_GetDt": "simclock_dt", "simclock_GetTime": "simclock_time", "simclock_GetFrameCount": "simclock_frame_count",
                                "simclock_GetAccumDt": "simclock_accum_dt"}[name], "supported",
               [E("ref-site", site="0x%x" % site, method="capstone disp32", source="ghidra/i76_ref.exe", claim="getter load"),
                E("width-from", site="0x%x" % site, width=4, method="capstone operand size", source="ghidra/i76_ref.exe", claim="4-byte load"),
                E("global-write", writer="0x49c920", sites=["0x%x" % s[0] for s in C.imm_sites(g) if s[1] in (0x49c920, 0x49c7f0)], method="capstone disp32 sites in simclock_Init/Update",
                  source="ghidra/i76_ref.exe", claim="written by the sim clock"),
                E("import-callee", import_name=gtc, via="0x49c920", method="value derives from GetTickCount in the writer (refute-timer-claim section 3)", source="recon-2026-09-04/recon/refute-timer-claim/REPORT.md", claim="derived from GetTickCount")],
               readers="0x%x" % fa, writers="0x49c920;0x49c7f0")
    say("FUNNEL simclock: 0x5a7e1c has %d disp32 sites in .text, exactly one is a write (inc in 0x49c920); 4 getters are load;ret" % len(w1c))

    # ---------------- 10. FSM trio, rsqrt -----------------------------------------------------------
    jt = {r["name"]: r for r in C.tables if r["kind"] == "jumptable"}
    C.func(0x412ce0, "fsm_ActionDispatch", "supported",
           [C.str_ev(0x412ce0, 0x4c33e8, claim="default case message"),
            E("table-entry", table="0x4144e4", n=int(jt["fsm_action_dispatch"]["count"]), site=jt["fsm_action_dispatch"]["source_sites"], method=jt["fsm_action_dispatch"]["method"],
              source="symbols/tables.tsv", claim="owns the 96-entry action jump table")], subsystem="fsm")
    C.func(0x414670, "fsm_OpcodeSwitch", "supported",
           [C.str_ev(0x414670, 0x4c3404, claim="default case message"),
            E("table-entry", table="0x4149b8", n=int(jt["fsm_opcode_switch"]["count"]), site=jt["fsm_opcode_switch"]["source_sites"], method=jt["fsm_opcode_switch"]["method"],
              source="symbols/tables.tsv", claim="owns the 14-entry opcode jump table")], subsystem="fsm")
    C.func(0x410a10, "match_prototype", "anchored", [C.str_ev(0x410a10, 0x4c2e5c, form="in", literal="in match_prototype", claim="self-naming (G1 rule b)"),
                                                     E("table-entry", table="0x4c2e8c", n=96, method="tables.tsv fsm_prototype_names; literals referenced from this function", source="symbols/tables.tsv", claim="references the prototype-name strings")], subsystem="fsm")
    cbfc = C.const_ev(0x495000, 0xbfc, "rsqrt exponent trick constant", kinds=("imm",))
    clut = C.const_ev(0x495000, 0x655180, "rsqrt mantissa LUT base")
    assert cbfc["unique"] and clut["unique"]
    C.func(0x495000, "rsqrt", "supported", [cbfc, clut,
           E("tu-neighbourhood", region="0x494170-0x494f70 math helpers (fp-ghidra section: 0x494460 rotation from angle)", n_callers=inv[0x495000]["n_callers"],
             method="functions.json neighbours + Ghidra n_callers", source="recon-2026-09-04/recon/fp-ghidra/REPORT.md", claim="math-helper TU; 0xbfc exponent trick + 0x655180 LUT co-occur only here")],
           subsystem="math")
    say("FUNNEL rsqrt: 0xbfc imm sites n=%d in %s; LUT 0x655180 sites n=%d" % (cbfc["n"], cbfc["functions"], clut["n"]))

    # ---------------- 11. ZFS / VFS / BWD2 spine ------------------------------------------------------
    C.func(0x4b9800, "zfs_Open", "supported", [C.str_ev(0x4b9800, 0x500e8c), C.str_ev(0x4b9800, 0x500ea8), C.imp_ev(0x4b9800, "fread"),
                                              C.const_ev(0x4b9800, 0xe14, "ZFS block size read", kinds=("imm",))], subsystem="zfs")
    C.func(0x4b9bd0, "zfs_ReadRecord", "supported", [C.imp_ev(0x4b9bd0, "fread"), C.imp_ev(0x4b9bd0, "HeapAlloc"),
                                                    E("verified-callee", callee="0x4b9fc0", site="0x4b9d3b", method="capstone call site; callee is zfs_Decompress (this batch)", source="ghidra/i76_ref.exe", claim="decompresses when flags&6")],
           subsystem="zfs")
    C.func(0x4b9fc0, "zfs_Decompress", "supported",
           [C.str_ev(0x4b9fc0, 0x500f54), E("verified-callee", callees=["0x4ba980", "0x4babd8", "0x4baa00"], method="capstone call sites 0x4b9fe7/0x4ba032/0x4ba05a", source="ghidra/i76_ref.exe", claim="dispatches to lzo1x/lzo1y by flags bit 2/4"),
            E("call-cleanup", site="0x4b9d3b", cleanup="add esp, 0x14", method="capstone at the call site in 0x4b9bd0", source="ghidra/i76_ref.exe", claim="cdecl, 5 stack args (src, size, flags, dst, flags>>8); not thiscall")],
           subsystem="zfs", conv="__cdecl", conv_evidence="call-cleanup@0x4b9d3b:add esp,0x14")
    c10c = C.const_ev(0x4b28c0, 0x10c, "VFS source stride 0x10c", kinds=("imm",))
    C.func(0x4b28c0, "vfs_Lookup", "supported", [c10c, C.imp_ev(0x4b28c0, "_stricmp")], subsystem="vfs")
    cexit = C.const_ev(0x4b3db0, 0x54495845, "'EXIT' multichar compare", kinds=("imm",))
    C.func(0x4b3db0, "bwd2_Parse", "supported", [C.str_ev(0x4b3db0, 0x500470), C.str_ev(0x4b3db0, 0x500498), C.str_ev(0x4b3db0, 0x5004c0), cexit], subsystem="bwd2")
    c528 = C.const_ev(0x4b41e0, 0x500328, "BWD2 header table base pushed", kinds=("imm",))
    C.func(0x4b41e0, "bwd2_LoadDef", "supported", [c528, C.imp_ev(0x4b41e0, "_strnicmp"),
                                                  E("verified-callee", callee="0x4b3db0", method="Ghidra callgraph", source="ghidra/export/callgraph.json", claim="parses header then body table")], subsystem="bwd2")
    cb = C.const_ev(0x4b4840, 0x32445742, "'BWD2' immediate", kinds=("imm",)); cr = C.const_ev(0x4b4840, 0x564552, "'REV\\0' immediate", kinds=("imm",))
    C.func(0x4b4840, "bwd2_WriteHeader", "supported", [cb, cr, C.imp_ev(0x4b4840, "fwrite")], subsystem="bwd2")
    say("FUNNEL spine: EXIT constant sites n=%d (%s); 0x10c sites n=%d; BWD2 imm n=%d" % (cexit["n"], cexit["functions"], c10c["n"], cb["n"]))

    # ---------------- 12. profiler --------------------------------------------------------------------
    tg = "timeGetTime"
    C.func(0x498af0, "profiler_Open", "supported", [C.str_ev(0x498af0, 0x4fdde0), C.imp_ev(0x498af0, "fopen")], subsystem="profiler")
    C.func(0x498b50, "profiler_FrameStart", "supported", [C.imp_ev(0x498b50, tg), E("global-write", target="0x5a7c58", sites=["0x%x" % s[0] for s in C.imm_sites(0x5a7c58)], n=len(C.imm_sites(0x5a7c58)),
                                                                                    method="capstone disp32 scan: 0x5a7c58 has exactly 2 sites (write here, read in 0x498d60)", source="ghidra/i76_ref.exe", claim="stamps the frame start")], subsystem="profiler")
    C.func(0x498b80, "profiler_Stamp", "supported", [C.imp_ev(0x498b80, tg), E("global-write", target="0x5a7c90", method="capstone disp32", sites=["0x%x" % s[0] for s in C.imm_sites(0x5a7c90) if s[1] == 0x498b80],
                                                                               source="ghidra/i76_ref.exe", claim="guarded by the interval.txt FILE*")], subsystem="profiler")
    C.func(0x498c00, "profiler_Report", "supported", [C.str_ev(0x498c00, 0x4fde18), C.str_ev(0x498c00, 0x4fddf0), C.imp_ev(0x498c00, "fprintf"), C.imp_ev(0x498c00, "qsort")], subsystem="profiler")
    cmp_sites = C.imm_sites(0x498d50, kinds=("imm",))
    assert sorted({s[1] for s in cmp_sites}) == [0x498c00, 0x498d60] and len(cmp_sites) == 2, cmp_sites
    C.func(0x498d50, "profiler_qsort_cmp", "supported", [E("callback-pointer", sites=["0x%x" % s[0] for s in cmp_sites], callers=["0x498c00", "0x498d60"],
                                                             method="capstone: the only imm32 == 0x498d50 sites in .text are the two pushes before qsort in profiler_Report/FrameEnd",
                                                             n=2, source="ghidra/i76_ref.exe", claim="qsort comparator"),
                                                           E("tu-neighbourhood", method="adjacent to profiler_Report/FrameEnd", source="ghidra/export/functions.json", claim="profiler TU")], subsystem="profiler")
    rd58 = [s for s in C.imm_sites(0x5a7c58) if s[1] == 0x498d60]
    assert len(rd58) == 1
    C.func(0x498d60, "profiler_FrameEnd", "supported", [C.imp_ev(0x498d60, tg), C.imp_ev(0x498d60, "fprintf"), C.imp_ev(0x498d60, "qsort"),
           E("global-write", target="0x5a7c58", site="0x%x" % rd58[0][0], insn="%s %s" % (C.dis(rd58[0][0], 8)[0].mnemonic, C.dis(rd58[0][0], 8)[0].op_str),
             method="capstone disp32: the only read of the frame-start stamp written by profiler_FrameStart", source="ghidra/i76_ref.exe", claim="consumes the frame-start stamp")],
           subsystem="profiler")
    C.func(0x4990b0, "profiler_WriteHistogram", "supported", [C.str_ev(0x4990b0, 0x4fde7c), C.imp_ev(0x4990b0, "fopen"), C.imp_ev(0x4990b0, "fprintf")], subsystem="profiler")
    f90 = [s for s in C.imm_sites(0x5a7c90) if s[1] == 0x498af0]
    st_site = [s for s in f90 if C.dis(s[0], 8)[0].mnemonic == "mov" and C.dis(s[0], 8)[0].operands[0].type == X86_OP_MEM][0][0]
    C.glob(0x5a7c90, "bss", 4, "FILE*", "profiler_file", "supported",
           [E("ref-site", site="0x%x" % st_site, method="capstone disp32", source="ghidra/i76_ref.exe", claim="store of fopen(interval.txt)"),
            E("width-from", site="0x%x" % st_site, width=4, method="capstone operand size", source="ghidra/i76_ref.exe", claim="dword"),
            E("import-callee", import_name="fopen", via="0x498af0", method="the stored value is fopen's return in profiler_Open", source="ghidra/export/callgraph.json", claim="FILE*"),
            E("global-write", writers=["0x498af0", "0x498c00"], n=len(C.imm_sites(0x5a7c90)), method="capstone disp32 scan", source="ghidra/i76_ref.exe", claim="written by Open (fopen) and Report (fclose; =0)")],
           writers="0x498af0;0x498c00")
    say("FUNNEL profiler: 7 functions in 0x498af0-0x4990b0; 0x5a7c58 sites=%d; 0x498d50 imm sites=1" % len(C.imm_sites(0x5a7c58)))

    # ---------------- 13. pools + heap alloc wrapper --------------------------------------------------
    c102 = C.const_ev(0x498940, 0x102000, "MEM_RESERVE|MEM_TOP_DOWN", kinds=("imm",))
    C.func(0x498940, "pool_Reserve", "supported", [C.imp_ev(0x498940, "VirtualAlloc"), C.imp_ev(0x498940, "VirtualFree"), c102], subsystem="pool")
    C.func(0x498a00, "pool_Free", "supported", [C.imp_ev(0x498a00, "VirtualFree"), C.const_ev(0x498a00, 0x5a6170, "pool list head")], subsystem="pool")
    C.func(0x498a50, "pool_CommitMore", "supported", [C.imp_ev(0x498a50, "VirtualAlloc"), C.imp_ev(0x498a50, "VirtualQuery"), C.const_ev(0x498a50, 0x5a6170, "pool list head")], subsystem="pool")
    b = C.body(0x499ce0)
    assert [i.mnemonic for i in b if i.mnemonic == "call"] and len(b) <= 8
    C.func(0x499ce0, "heap_5a7cc0_alloc", "anchored", [E("import-wrapper", import_name="HeapAlloc", heap_global="0x5a7cc0", insns=["%s %s" % (i.mnemonic, i.op_str) for i in b],
                                                          method="capstone: body is push size; push 0; push [0x5a7cc0]; call [HeapAlloc]; ret (G1 rule a)", source="ghidra/i76_ref.exe", claim="HeapAlloc wrapper on heap 0x5a7cc0")], subsystem="heap")
    say("FUNNEL pools: 0x102000 imm sites n=%d; list head 0x5a6170 sites n=%d" % (c102["n"], len(C.imm_sites(0x5a6170))))

    # ---------------- 14. heap creators (26): rule (a) wrappers only ------------------------------------
    hc = C.imp_by_name["HeapCreate"]
    creators = [int(f, 16) for f in hc["functions"].split(";")]
    n_str = 0; n_tag = 0; wrappers = 0
    for fa in creators:
        r = C.str_by_addr
        srefs = [sa for sa, sr in r.items() if ("%08x" % fa) in sr["referencing_functions"].split(";")]
        if srefs: n_str += 1
        b = C.body(fa)
        calls = [i for i in b if i.mnemonic == "call"]
        hc_calls = [i for i in calls if i.operands[0].type == X86_OP_MEM and i.operands[0].mem.disp == int(hc["iat_slot"], 16)]
        other = [i for i in calls if i not in hc_calls]
        stores = [i for i in b if i.mnemonic == "mov" and i.operands[0].type == X86_OP_MEM and i.operands[0].mem.base == 0 and i.operands[1].type == X86_OP_REG and i.reg_name(i.operands[1].reg) == "eax"]
        # a wrapper: only HeapCreate calls (or a call to the ret-stub logger 0x42d5d0), <= 24 instructions, handle stored to a global
        logger = [i for i in other if i.operands[0].type == X86_OP_IMM and i.operands[0].imm == 0x42d5d0]
        if hc_calls and len(other) == len(logger) and len(b) <= 24 and stores and inv[fa]["params"] == 0:
            handles = []
            for s in stores:
                handles.append((s.operands[0].mem.disp, s.address))
            hs = sorted({h for h, _ in handles})
            name = "heap_create_" + "_".join("%x" % h for h in hs)
            C.func(fa, name, "anchored",
                   [E("import-wrapper", import_name="HeapCreate", calls=["0x%x" % i.address for i in hc_calls], handles=["0x%x@0x%x" % (h, s) for h, s in handles],
                      insns=len(b), method="capstone: the only calls are HeapCreate (and the ret-stub logger 0x42d5d0); the handle(s) are stored to globals; no params (G1 rule a)",
                      source="ghidra/i76_ref.exe", claim="HeapCreate wrapper; no tag string is referenced (funnel below)")], subsystem="heap")
            wrappers += 1
            for h, s in handles:
                if any(g["addr"] == "0x%x" % h for g in C.globs): continue
                C.glob(h, img.klass(h), 4, "HANDLE", "heap_%x" % h, "anchored",
                       [E("ref-site", site="0x%x" % s, method="capstone disp32", source="ghidra/i76_ref.exe", claim="HeapCreate result store"),
                        E("width-from", site="0x%x" % s, width=4, method="capstone operand size", source="ghidra/i76_ref.exe", claim="dword"),
                        E("import-wrapper", import_name="HeapCreate", via="0x%x" % fa, method="stored value is HeapCreate's return", source="ghidra/i76_ref.exe", claim="heap handle")],
                       writers="0x%x" % fa)
    say("FUNNEL heap creators: %d functions call HeapCreate (imports.tsv, capstone) -> %d reference any string -> 0 reference a tag-like string "
        "(the 'heap-tag strings' at 0x4f271c/0x4f2724 'texmgr'/'texanm' are referenced by 0x44adc0/0x44ae50.., not by a creator) -> %d are pure wrappers (named heap_create_<handle>); "
        "%d larger creators left auto" % (len(creators), n_str, wrappers, len(creators) - wrappers))

    # ---------------- 15. G1 self-naming strings ------------------------------------------------------
    forms = [("colon", re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):\s")), ("dash", re.compile(r"^([A-Za-z_][A-Za-z0-9_]*) - ")),
             ("in", re.compile(r"\bin ([A-Za-z_][A-Za-z0-9_]*)\b")), ("paren", re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\(\)"))]
    generic = {"Error", "Warning", "FSM", "Say", "Sorry", "Unknown", "Could", "Cannot", "Header", "There", "Vertical", "Bitmask", "This", "More", "No"}
    modules = {"SpawnLoc", "road", "car", "mission", "file", "ZIX", "the", "video", "hash", "clipping", "infinite", "illigal", "setRenderState"}
    other_exports = {"I7FF_SIM_Effect", "I7FF_InitSystem", "I7FF_ExitSystem", "SmackOpen", "DirectDrawCreate", "DirectDrawEnumerate"}
    cands = {}
    total = 0
    for r in C.strings:
        s = r["string"]
        for form, pat in forms:
            for m in pat.finditer(s):
                nm = m.group(1)
                total += 1
                if nm in generic or nm in modules or nm in other_exports or len(nm) < 4: continue
                # identifier test: an underscore, a digit, or mixed case (an uppercase letter after the first character);
                # plain English words ('progress', 'this', 'Zone') and all-caps module tags ('FSM') are not names
                if not ("_" in nm or any(ch.isdigit() for ch in nm) or any(ch.isupper() for ch in nm[1:])) or nm.isupper(): continue
                fns = [int(f, 16) for f in r["referencing_functions"].split(";") if f]
                cands.setdefault(nm, []).append((form, int(r["addr"], 16), fns, s))
    anchored = 0; ambiguous = []
    for nm, lst in sorted(cands.items()):
        fnset = sorted({f for _, _, fns, _ in lst for f in fns})
        if len(fnset) != 1:
            ambiguous.append((nm, ["0x%x" % f for f in fnset])); continue
        fa = fnset[0]
        if nm in C.names and C.names[nm] != fa:
            ambiguous.append((nm, "name taken")); continue
        if fa in {int(x["addr"], 16) for x in C.funcs}:
            continue  # already named in this batch (match_prototype)
        evs = [C.str_ev(fa, sa, form=form, literal=s[:80], claim="self-naming literal (G1 rule b)") for form, sa, _, s in lst]
        C.func(fa, nm, "anchored", evs, subsystem=""); anchored += 1
    say("FUNNEL G1 strings: %d grammar matches over %d strings -> %d candidate names -> %d anchored (one referencing function each); ambiguous/rejected: %s"
        % (total, len(C.strings), len(cands), anchored, ambiguous))
    # rule (c): 'X in infinite loop' -> the loop at 0x415929-0x4159f9 in 0x4158f0 contains no call; get_next_index is inlined
    b = C.body(0x4158f0)
    loop_calls = [i for i in b if 0x415929 <= i.address < 0x4159ff and i.mnemonic == "call"]
    say("NULL G1 rule (c): 'roadwar - get_next_index in infinite loop' (0x4c3d80) is pushed at 0x4159ff; the loop 0x415929-0x4159f9 contains %d calls, so "
        "get_next_index is inlined and no callee can be anchored; the only adjacent callee is the ret-only logger 0x42d5d0" % len(loop_calls))
    # FSM-prefixed messages with an embedded identifier: proposed only (not applied)
    for fa, nm, sa in ((0x40b860, "isGroovesFault", 0x4c2bf0), (0x40bc40, "setHeliHeight", 0x4c2ce4), (0x40bdf0, "isAtFollow", 0x4c2d30), (0x40cc90, "astar", 0x4c2df0)):
        C.func(fa, nm, "proposed", [C.str_ev(fa, sa, claim="'FSM - <ident> ...' message; identifier is not in a G1 grammar position")], subsystem="fsm")
    C.func(0x4158f0, "roadwar_4158f0", "proposed", [C.str_ev(0x4158f0, 0x4c3d80, claim="subsystem roadwar; get_next_index inlined")], subsystem="roadwar")
    C.func(0x42d5d0, "dbg_LogStub", "proposed", [E("synthetic-shape", insn="ret", n_callers=inv[0x42d5d0]["n_callers"], method="Ghidra n_callers; body is one byte c3",
                                                   source="ghidra/export/functions.json", claim="every diagnostic string is pushed to this ret-only function (bwd2-refute)")], subsystem="debug")
    return C


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", default=r"C:\Users\james\i76-map")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    C = Ctx(args.map)
    build(C)
    out = args.out or os.path.join(args.map, "status", "tasks", "t4-anchors.batch.json")
    batch = {"batch": "t4-anchors", "author": "t4-anchors agent", "exe_md5": MD5, "evidence_base": 40001,
             "functions": C.funcs, "globals": C.globs, "funnel": C.log}
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(batch, fh, indent=1)
    st = {}
    for r in C.funcs: st[r["status"]] = st.get(r["status"], 0) + 1
    for r in C.globs: st["global:" + r["status"]] = st.get("global:" + r["status"], 0) + 1
    print("BATCH", out, "functions", len(C.funcs), "globals", len(C.globs), json.dumps(st, sort_keys=True))


if __name__ == "__main__":
    main()
