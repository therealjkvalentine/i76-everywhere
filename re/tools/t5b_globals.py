"""t5b_globals.py - port Roanish's nitro.exe globals to the reference exe by OPERAND ALIGNMENT (Task 5b).

Why: the byte-level data correlators only match *defined* data of >= 5 identical bytes (strings, tables); Roanish's
globals are BSS or small init scalars, so no data correlator can ever match them (read the null: vt-nitro.json has
0 accepted DATA rows at any of his 41 global addresses). Complement: for a function pair accepted by the Exact
Function Bytes or Exact Function Instructions correlator (identical instruction stream, only operands differ), the
k-th instruction of the nitro function corresponds to the k-th instruction of the reference function; a global
referenced as an imm32/disp32 operand at index k therefore maps to the reference operand at the same index and
slot. Every site is decoded (capstone 5, linear decode over the Ghidra body start..end); a global is ported only
when all its sites agree on one reference VA (n_sites, n_funcs and the spread are recorded; H6 wants n >= 2).
Output: status/t5b/globals-port.tsv (nitro_va name ref_va ref_class n_sites n_funcs candidates method).
"""
import json, io, csv, sys, collections, pefile, capstone
ROOT = "C:/Users/james/i76-map"
NITRO = ROOT + "/ghidra/nitro.exe"; REF = ROOT + "/ghidra/i76_ref.exe"

class Img:
    def __init__(self, path):
        self.d = open(path, "rb").read(); pe = pefile.PE(data=self.d); self.base = pe.OPTIONAL_HEADER.ImageBase
        self.secs = [(s.Name.rstrip(b"\0").decode(), self.base + s.VirtualAddress, self.base + s.VirtualAddress + max(s.Misc_VirtualSize, s.SizeOfRawData), s.PointerToRawData, s.SizeOfRawData) for s in pe.sections]
        self.text = [s for s in self.secs if s[0] == ".text"][0]
    def off(self, va):
        for n, lo, hi, raw, rawsz in self.secs:
            if lo <= va < hi: return va - lo + raw
        return None
    def data_range(self, va):
        for n, lo, hi, raw, rawsz in self.secs:
            if n in (".data", ".rdata") and lo <= va < hi: return True
        return False

def ref_cls(va):
    if 0x401000 <= va < 0x4bbe55: return "text"
    if 0x4bc000 <= va < 0x4c1788: return "rdata"
    if 0x4c2000 <= va < 0x501800: return "init"
    if 0x501800 <= va < 0x669ef8: return "bss"
    return "outside"

md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32); md.detail = True
def decode(img, start, end):
    """linear decode of [start, end] (Ghidra body start/end inclusive); returns list of (addr, mnemonic, [operand values])"""
    off = img.off(start); n = end - start + 1
    out = []
    for ins in md.disasm(img.d[off:off + n], start):
        vals = []
        for op in ins.operands:
            if op.type == capstone.x86.X86_OP_IMM: vals.append(("imm", op.imm & 0xffffffff))
            elif op.type == capstone.x86.X86_OP_MEM: vals.append(("disp", op.mem.disp & 0xffffffff))
            else: vals.append(("reg", None))
        out.append((ins.address, ins.mnemonic, vals))
    return out

def main():
    nit, ref = Img(NITRO), Img(REF)
    fn_n = {int(f["start"], 16): f for f in json.load(io.open(ROOT + "/ghidra/export-nitro/functions.json", encoding="utf-8"))}
    fn_r = {int(f["start"], 16): f for f in json.load(io.open(ROOT + "/ghidra/export/functions.json", encoding="utf-8"))}
    j = json.load(io.open(ROOT + "/status/vt-nitro.json", encoding="utf-8"))
    pairs = {}  # nitro fn -> (ref fn, correlator)
    for c in j["correlators"]:
        if c["correlator"] not in ("Exact Function Bytes Match", "Exact Function Instructions Match"): continue
        for r in c["rows"]:
            if r["verdict"] == "accepted" and r["type"] == "FUNCTION":
                pairs.setdefault(int(r["dst"], 16), (int(r["src"], 16), c["correlator"]))
    globs = {}
    for l in io.open(ROOT + "/status/t5b/roanish-items.tsv", encoding="utf-8"):
        if not l.startswith("0x"): continue
        c = l.rstrip("\n").split("\t")
        if c[2] == "global" and c[3]: globs[int(c[0], 16)] = c[3]
    want = set(globs)
    sites = collections.defaultdict(list)   # global -> [(nitro fn, idx, slot, ref candidate, mnemonic ok)]
    funnel = {"pairs_instruction_identical": len(pairs), "pairs_decoded": 0, "pairs_len_mismatch": 0, "sites_found": 0, "sites_aligned": 0, "sites_slot_mismatch": 0}
    for nfn, (rfn, corr) in sorted(pairs.items()):
        fn = fn_n.get(nfn); fr = fn_r.get(rfn)
        if not fn or not fr: continue
        ins_n = decode(nit, nfn, int(fn["end"], 16))
        hits = [(i, k, v) for i, (a, m, vals) in enumerate(ins_n) for k, (t, v) in enumerate(vals) if t in ("imm", "disp") and v in want]
        if not hits: continue
        ins_r = decode(ref, rfn, int(fr["end"], 16))
        funnel["pairs_decoded"] += 1
        if len(ins_r) != len(ins_n): funnel["pairs_len_mismatch"] += 1; continue
        for i, k, v in hits:
            funnel["sites_found"] += 1
            a_n, m_n, vals_n = ins_n[i]; a_r, m_r, vals_r = ins_r[i]
            if m_n != m_r or k >= len(vals_r) or vals_r[k][0] != vals_n[k][0]: funnel["sites_slot_mismatch"] += 1; continue
            cand = vals_r[k][1]
            if not ref.data_range(cand): funnel["sites_slot_mismatch"] += 1; continue
            funnel["sites_aligned"] += 1
            sites[v].append((nfn, rfn, i, a_n, a_r, cand, corr))
    # tier 2: globals with no site in an instruction-identical pair -> any accepted pair whose mnemonic stream is
    # identical (same length, same mnemonic at every index); flagged in the method column, never mixed with tier 1
    pairs2 = {}
    for c in j["correlators"]:
        for r in c["rows"]:
            if r["verdict"] == "accepted" and r["type"] == "FUNCTION":
                d = int(r["dst"], 16)
                if d not in pairs: pairs2.setdefault(d, (int(r["src"], 16), c["correlator"]))
    left = set(g for g in globs if g not in sites)
    funnel["tier2_pairs"] = len(pairs2); funnel["tier2_globals_tried"] = len(left); funnel["tier2_sites"] = 0; funnel["tier2_mnemonic_mismatch"] = 0
    if left:
        for nfn, (rfn, corr) in sorted(pairs2.items()):
            fn = fn_n.get(nfn); fr = fn_r.get(rfn)
            if not fn or not fr: continue
            ins_n = decode(nit, nfn, int(fn["end"], 16))
            hits = [(i, k, v) for i, (a, m, vals) in enumerate(ins_n) for k, (t, v) in enumerate(vals) if t in ("imm", "disp") and v in left]
            if not hits: continue
            ins_r = decode(ref, rfn, int(fr["end"], 16))
            if len(ins_r) != len(ins_n) or any(a[1] != b[1] for a, b in zip(ins_n, ins_r)): funnel["tier2_mnemonic_mismatch"] += 1; continue
            for i, k, v in hits:
                vals_r = ins_r[i][2]
                if k >= len(vals_r) or vals_r[k][0] != ins_n[i][2][k][0] or not ref.data_range(vals_r[k][1]): continue
                funnel["tier2_sites"] += 1
                sites[v].append((nfn, rfn, i, ins_n[i][0], ins_r[i][0], vals_r[k][1], corr + " [tier2]"))
    rows = []
    for g, name in sorted(globs.items()):
        s = sites.get(g, [])
        cands = collections.Counter(x[5] for x in s)
        if not s:
            rows.append((g, name, None, "", 0, 0, "", "no site in an instruction-identical matched function pair"))
            continue
        nf = len(set(x[0] for x in s))
        if len(cands) == 1:
            cand = next(iter(cands))
            tier = "operand-alignment-tier2 (mnemonic-identical pair)" if any("tier2" in x[6] for x in s) else "operand-alignment (instruction-identical pair)"
            rows.append((g, name, cand, ref_cls(cand), len(s), nf, "0x%06x" % cand, tier + "; sites " + ",".join("%x@%x->%x" % (x[3], x[0], x[4]) for x in s[:4]) + ("..." if len(s) > 4 else "")))
        else:
            rows.append((g, name, None, "", len(s), nf, ";".join("0x%06x:%d" % (c, n) for c, n in cands.most_common()), "AMBIGUOUS: sites disagree"))
    out = ROOT + "/status/t5b/globals-port.tsv"
    with io.open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write("# operand-alignment port of Roanish globals nitro -> i76_ref (tools/t5b_globals.py). funnel: %s\n" % json.dumps(funnel))
        f.write("nitro_va\tname\tref_va\tref_class\tn_sites\tn_funcs\tcandidates\tmethod\n")
        for g, name, cand, cl, ns, nf, cs, note in rows:
            f.write("0x%06x\t%s\t%s\t%s\t%d\t%d\t%s\t%s\n" % (g, name, ("0x%06x" % cand) if cand else "", cl, ns, nf, cs, note))
    ported = [r for r in rows if r[2]]
    print("funnel", funnel)
    print("globals %d: ported %d (n_sites>=2: %d, n_funcs>=2: %d), ambiguous %d, no-site %d" % (len(rows), len(ported), sum(1 for r in ported if r[4] >= 2), sum(1 for r in ported if r[5] >= 2), sum(1 for r in rows if r[6] and not r[2]), sum(1 for r in rows if r[4] == 0)))
    for r in rows: print("  0x%06x %-24s -> %-10s %-5s n=%d f=%d %s" % (r[0], r[1], ("0x%06x" % r[2]) if r[2] else "-", r[3], r[4], r[5], r[6] if not r[2] else ""))

if __name__ == "__main__":
    main()
