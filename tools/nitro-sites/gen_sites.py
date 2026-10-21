#!/usr/bin/env python3
"""gen_sites.py - the Gold -> Nitro site map for the Strlkup proxy (nitro-port lane, 2026-10-21).

For every exe address the proxy names (music-fix/*.c and u32x/u32x_full.c, comments and strings stripped), find the
address in nitro.exe (28b8ae27) that plays the same role, and the bytes there, so the proxy can verify a site before it
patches it.

Method (static, re-runnable; docs/records/NITRO-PORT-2026-10-21.md s.1):
  1. Function pairs Gold -> Nitro: lab emu/tools/memtrace/exe_diff_map.json (Ghidra VT vt-nitro + call-graph
     propagation, NITRO-VS-RETAIL s.1). Function bounds: i76-map ghidra/export{,-nitro}/functions.csv.
  2. Inside each pair both functions are disassembled (capstone) and aligned instruction by instruction on a
     normalised token (mnemonic + operands, in-image addresses masked, entity fields +0x444..+0x5ff folded), difflib.
  3. Code site -> the aligned Nitro instruction (+ the same offset inside the instruction when the lengths agree).
  4. Data site -> votes: every aligned instruction pair that names absolute in-image addresses in both exes votes
     gold_addr -> nitro_addr; IAT slots map by import name (Gold WINMM -> Nitro WIN32.dll). A data address with no vote
     of its own takes a voted neighbour's delta when the voted neighbours below and above (within 0x400, same section)
     agree ("bracketed"), else the one below within 0x40 ("near").
  5. Signature: the whole instructions from the site through >= 16 bytes in Gold (6319abf7, the shipped exe the proxy
     expects) and the same count of instructions at the Nitro address. status = exact (bytes equal), reloc (equal once
     absolute and relative operands are masked), differs, unmapped. The header carries the Nitro bytes; the proxy
     compares them with memory before it uses a code site (music-fix/nitro.c).

  python -I tools/nitro-sites/gen_sites.py     (defaults below; writes music-fix/sites_nitro.h + tools/nitro-sites/sites_nitro.csv)
"""
import argparse, bisect, csv, difflib, hashlib, json, os, re, sys, zlib
from collections import Counter, defaultdict

import pefile
import capstone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
D = dict(
    gold=r'C:/Users/james/Games/I76/release-candidate/Interstate 76/i76.exe',
    nitro=r'C:/Users/james/i76-map/ghidra/nitro.exe',
    gold_funcs=r'C:/Users/james/i76-map/ghidra/export/functions.csv',
    nitro_funcs=r'C:/Users/james/i76-map/ghidra/export-nitro/functions.csv',
    pairs=r'C:/Users/james/i76-uncap-lab/emu/tools/memtrace/exe_diff_map.json',
    header=os.path.join(REPO, 'music-fix', 'sites_nitro.h'),
    csv=os.path.join(HERE, 'sites_nitro.csv'),
    extra=os.path.join(HERE, 'extra_sites.txt'),
    manual=os.path.join(HERE, 'manual_sites.txt'),
)
GOLD_MD5 = '6319abf7bf96e32f994fe7609cf99a7a'
NITRO_MD5 = '28b8ae276e88f4ffb13f17df159f09dc'


def md5(p):
    return hashlib.md5(open(p, 'rb').read()).hexdigest()


class Exe:
    def __init__(self, path, funcs_csv):
        self.pe = pefile.PE(path, fast_load=False)
        self.base = self.pe.OPTIONAL_HEADER.ImageBase
        self.end = self.base + self.pe.OPTIONAL_HEADER.SizeOfImage
        self.img = self.pe.get_memory_mapped_image()
        self.secs = [(s.Name.rstrip(b'\0').decode(), self.base + s.VirtualAddress,
                      self.base + s.VirtualAddress + max(s.Misc_VirtualSize, s.SizeOfRawData)) for s in self.pe.sections]
        self.text = [(a, b) for n, a, b in self.secs if n == '.text'][0]
        self.text_vsize = [s.Misc_VirtualSize for s in self.pe.sections if s.Name.startswith(b'.text')][0]
        self.funcs = []
        for r in csv.DictReader(open(funcs_csv)):
            self.funcs.append((int(r['address'], 16), int(r['size'])))
        self.funcs.sort()
        self.fstarts = [a for a, _ in self.funcs]
        self.iat = {}          # slot va -> (dll, name)
        self.iat_by_name = {}  # name -> slot va
        for e in self.pe.DIRECTORY_ENTRY_IMPORT:
            for i in e.imports:
                if i.name:
                    self.iat[i.address] = (e.dll.decode(), i.name.decode())
                    self.iat_by_name[i.name.decode()] = i.address
        self.md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        self.md.detail = True
        self._dis = {}

    def sec(self, va):
        for n, a, b in self.secs:
            if a <= va < b:
                return n
        return None

    def bytes(self, va, n):
        o = va - self.base
        return bytes(self.img[o:o + n])

    def func_of(self, va):
        i = bisect.bisect_right(self.fstarts, va) - 1
        if i < 0:
            return None
        a, s = self.funcs[i]
        return (a, s) if a <= va < a + max(s, 1) else None

    def dis(self, fa, size):
        if fa not in self._dis:
            self._dis[fa] = list(self.md.disasm(self.bytes(fa, size), fa))
        return self._dis[fa]


HEXNUM = re.compile(r'0x[0-9a-f]+')


def is_rel_branch(ins):
    b = ins.bytes
    return b[0] in (0xe8, 0xe9, 0xeb) or 0x70 <= b[0] <= 0x7f or (b[0] == 0x0f and len(b) > 1 and 0x80 <= b[1] <= 0x8f) \
        or b[0] in (0xe0, 0xe1, 0xe2, 0xe3)


def abs_addrs(ins, exe):
    """absolute in-image addresses named by an instruction (memory displacements and immediates), in operand order;
    relative branch targets are left out (they pair through the function map)."""
    out = []
    if is_rel_branch(ins):
        return out
    for op in ins.operands:
        if op.type == capstone.x86.X86_OP_MEM and exe.base <= (op.mem.disp & 0xffffffff) < exe.end:
            out.append(op.mem.disp & 0xffffffff)
        elif op.type == capstone.x86.X86_OP_IMM and exe.base <= (op.imm & 0xffffffff) < exe.end:
            out.append(op.imm & 0xffffffff)
    return out


def token(ins, exe):
    if is_rel_branch(ins):
        return ins.mnemonic + ' R'
    def rep(m):
        v = int(m.group(0), 16)
        if exe.base <= v < exe.end:
            return 'A'
        if 0x444 <= v < 0x600:
            return 'F'
        return m.group(0)
    return ins.mnemonic + ' ' + HEXNUM.sub(rep, ins.op_str)


def masked(ins, exe):
    """bytes with absolute in-image operands and relative branch displacements zeroed (for 'reloc' equality)"""
    b = bytearray(ins.bytes)
    if is_rel_branch(ins):
        n = 4 if len(b) >= 5 else 1
        b[len(b) - n:] = b'\0' * n
        return bytes(b)
    for a in abs_addrs(ins, exe):
        k = a.to_bytes(4, 'little')
        i = bytes(b).find(k)
        if i >= 0:
            b[i:i + 4] = b'\0\0\0\0'
    return bytes(b)


def align(gold, nitro, gf, nf):
    gi = gold.dis(*gf)
    ni = nitro.dis(*nf)
    gt = [token(i, gold) for i in gi]
    nt = [token(i, nitro) for i in ni]
    sm = difflib.SequenceMatcher(None, gt, nt, autojunk=False)
    m = {}
    for tag, a0, a1, b0, b1 in sm.get_opcodes():
        if tag == 'equal' or (tag == 'replace' and a1 - a0 == b1 - b0):
            for k in range(a1 - a0):
                g, n = gi[a0 + k], ni[b0 + k]
                if tag == 'replace' and g.mnemonic != n.mnemonic:
                    continue
                m[g.address] = (n, g, tag == 'equal')
    return gi, ni, m


def extract_sites(paths, lo, hi):
    """address literal -> list of (file, line, enclosing function); comments and strings stripped"""
    sites = defaultdict(list)
    lit = re.compile(r'\b0x([0-9a-fA-F]{6,8})\b')
    fn = re.compile(r'^(?:static\s+)?(?:[A-Za-z_][\w\*]*\s+)+\**([A-Za-z_]\w*)\s*\(')
    for p in paths:
        src = open(p, encoding='latin-1').read()

        def blank(m):
            return re.sub(r'[^\n]', ' ', m.group(0))
        src = re.sub(r'/\*.*?\*/', blank, src, flags=re.S)
        src = re.sub(r'//[^\n]*', blank, src)
        src = re.sub(r'"(?:\\.|[^"\\\n])*"', blank, src)
        cur = '?'
        for ln, line in enumerate(src.split('\n'), 1):
            if line and not line[0].isspace() and '(' in line and not line.startswith('#'):
                mm = fn.match(line)
                if mm and not line.rstrip().endswith(';'):
                    cur = mm.group(1)
            if 'nitro_patch_call(' in line:             # Nitro-only call sites: the literals are Nitro addresses, not Gold
                continue
            for mm in lit.finditer(line):
                v = int(mm.group(1), 16)
                if lo <= v < hi:
                    sites[v].append((os.path.relpath(p, REPO).replace('\\', '/'), ln, cur))
            # addresses embedded little-endian in byte arrays ({ 0xFF, 0x15, 0x40, 0xC3, 0x4B, 0x00 } names 0x4bc340)
            for bl in re.finditer(r'\{([^{}]*)\}', line):
                toks = [t.strip() for t in bl.group(1).split(',') if t.strip()]
                if len(toks) < 4 or not all(re.fullmatch(r'0x[0-9a-fA-F]{1,2}|\d{1,3}', t) for t in toks):
                    continue
                vals = [int(t, 16) if t.startswith('0x') else int(t) for t in toks]
                for i in range(len(vals) - 3):
                    v = vals[i] | vals[i + 1] << 8 | vals[i + 2] << 16 | vals[i + 3] << 24
                    if lo <= v < hi and vals[i + 3] == 0 and vals[i + 2] >= 0x40:
                        sites[v].append((os.path.relpath(p, REPO).replace('\\', '/'), ln, cur + ' (in bytes)'))
    return sites


def main():
    ap = argparse.ArgumentParser()
    for k, v in D.items():
        ap.add_argument('--' + k, default=v)
    a = ap.parse_args()
    assert md5(a.gold) == GOLD_MD5, 'gold exe is not 6319abf7'
    assert md5(a.nitro) == NITRO_MD5, 'nitro exe is not 28b8ae27'
    gold = Exe(a.gold, a.gold_funcs)
    nitro = Exe(a.nitro, a.nitro_funcs)
    nf_size = dict(nitro.funcs)
    gfs = dict(gold.funcs)
    pairs, how = {}, {}
    for f in json.load(open(a.pairs))['functions']:
        n = f.get('nitro')
        if n and n.get('va'):
            g = int(f['gold'], 16)
            pairs[g] = int(n['va'], 16)
            how[g] = (n.get('how', ''), n.get('normalised', ''), f.get('name', ''))

    # instruction maps for every pair (they also carry the data votes) ----------------------------------------------
    imap = {}
    votes = defaultdict(Counter)
    for g, n in pairs.items():
        if g not in gfs or n not in nf_size:
            continue
        gi, ni, m = align(gold, nitro, (g, gfs[g]), (n, nf_size[n]))
        imap.update(m)
        for ga, (nins, gins, eq) in m.items():
            if not eq:          # votes only from token-equal pairs (same mnemonic, same non-address operands)
                continue
            x, y = abs_addrs(gins, gold), abs_addrs(nins, nitro)
            if len(x) == len(y):
                for u, v in zip(x, y):
                    votes[u][v] += 1
    for slot, (dll, name) in gold.iat.items():
        if name in nitro.iat_by_name:
            votes[slot] = Counter({nitro.iat_by_name[name]: 1000})
    dmap = {}
    for u, c in votes.items():
        v, k = c.most_common(1)[0]
        dmap[u] = (v, k, sum(c.values()))
    dkeys = sorted(k for k in dmap if gold.sec(k) != '.text')

    manual = {}
    if os.path.exists(a.manual):    # hand-verified pairs: "gold nitro ok note" (overrides the generated row; ok = bytes
        for line in open(a.manual):  # from the site that were read side by side and play the same role)
            line = line.split('#')[0].strip()
            if line:
                p = line.split(None, 3)
                manual[int(p[0], 16)] = (int(p[1], 16), int(p[2]), p[3] if len(p) > 3 else 'manual')

    def gold_ins_at(va):
        f = gold.func_of(va)
        if not f:
            return None, None
        for ins in gold.dis(*f):
            if ins.address <= va < ins.address + ins.size:
                return f, ins
        return f, None

    files = sorted(os.path.join(REPO, 'music-fix', x) for x in os.listdir(os.path.join(REPO, 'music-fix')) if x.endswith('.c') and not x.startswith('nitro'))   # nitro*.c name Nitro addresses
    files.append(os.path.join(REPO, 'u32x', 'u32x_full.c'))
    sites = extract_sites(files, gold.base, gold.end)
    if os.path.exists(a.extra):
        for line in open(a.extra):
            line = line.split('#')[0].strip()
            if line:
                sites.setdefault(int(line, 16), []).append(('tools/nitro-sites/extra_sites.txt', 0, 'extra'))
    for g in manual:
        sites.setdefault(g, []).append(('tools/nitro-sites/manual_sites.txt', 0, 'manual'))

    def branch_ok(gi_, ni_):
        """a relative call / jump is 'the same' only if its targets correspond: a call to the paired function, a
        branch to the aligned instruction (nitro-mp-design lane 2026-10-21: 0x452d9f was mapped to a call of another
        function because call displacements were masked)"""
        if not is_rel_branch(gi_):
            return True
        gt = [o.imm & 0xffffffff for o in gi_.operands if o.type == capstone.x86.X86_OP_IMM]
        nt = [o.imm & 0xffffffff for o in ni_.operands if o.type == capstone.x86.X86_OP_IMM]
        if not gt or not nt:
            return False
        if pairs.get(gt[0]) == nt[0]:
            return True
        h = imap.get(gt[0])
        return bool(h) and h[0].address == nt[0]

    def code_sig(fa, ins, nfa, nins, off):
        """Gold bytes, Nitro bytes (whole instructions through >= 16 bytes past the site), status, and ok = how many
        bytes from the site on are covered by consecutive instructions that are equal up to relocation"""
        glist = [i for i in gold.dis(*fa) if i.address >= ins.address]
        nlist = [i for i in nitro.dis(nfa, nf_size[nfa]) if i.address >= nins.address]
        k, tot = 0, 0
        while k < len(glist) and tot < 16 + off:
            tot += glist[k].size
            k += 1
        k = min(k, len(nlist))
        ok, exact = 0, True
        for j in range(k):
            if masked(glist[j], gold) != masked(nlist[j], nitro) or glist[j].size != nlist[j].size                     or not branch_ok(glist[j], nlist[j]):
                break
            exact = exact and bytes(glist[j].bytes) == bytes(nlist[j].bytes)
            ok += glist[j].size
        ok = max(0, ok - off)
        gs = b''.join(bytes(i.bytes) for i in glist[:k])
        ns = b''.join(bytes(i.bytes) for i in nlist[:k])
        st = ('exact' if exact else 'reloc') if ok >= min(8, len(gs) - off) else 'differs'
        return gs[off:], ns[off:], st, min(ok, 48)

    rows = []
    for va in sorted(sites):
        sec = gold.sec(va)
        r = dict(gold=va, sec=sec or '-', nitro=0, kind='', status='unmapped', how='', gsig=b'', nsig=b'',
                 func='', nfunc='', uses=sites[va])
        if sec == '.text':
            f, ins = gold_ins_at(va)
            r['kind'] = 'code'
            if f:
                r['func'] = '0x%x %s' % (f[0], how.get(f[0], ('', '', ''))[2])
            if not f:
                r['how'] = 'no gold function'
            elif f[0] not in pairs:
                r['how'] = 'gold function unmatched'
            elif not ins:
                r['how'] = 'not on an instruction'
            else:
                r['nfunc'] = '0x%x' % pairs[f[0]]
                hit = imap.get(ins.address)
                if ins.address == f[0] and (not hit or hit[0].address != pairs[f[0]]):
                    # a function entry pairs with the paired function's entry, also when the aligner matched the entry
                    # instruction to a later one (Nitro 0x44caf0 net_RequestRespawn gained a prologue: the entry
                    # instruction aligned to 0x44cb06, mid-function; nitro-mp lane 2026-10-21). Callers need the entry;
                    # a patch on the entry bytes is held to the entry's own signature (refused if they differ).
                    nins0 = nitro.dis(pairs[f[0]], nf_size[pairs[f[0]]])[0]
                    hit = (nins0, ins, nins0.mnemonic == ins.mnemonic)
                if not hit:
                    r['how'] = 'instruction not aligned (function %s)' % how[f[0]][1]
                else:
                    nins, gins, eq = hit
                    off = va - ins.address
                    if off and nins.size != gins.size:
                        r['how'] = 'mid-instruction, lengths differ'
                    else:
                        r['nitro'] = nins.address + off
                        r['gsig'], r['nsig'], r['status'], r['ok'] = code_sig(f, ins, pairs[f[0]], nins, off)
                        r['how'] = 'aligned' + ('' if eq else ' (replace block)') + ', function ' + how[f[0]][1]
            # a code address that is a vote target (a function pointer / jump table entry named by both exes)
            if not r['nitro'] and va in dmap:
                r['nitro'] = dmap[va][0]
                r['status'] = 'voted'
                r['how'] = 'code address voted %d/%d' % (dmap[va][1], dmap[va][2])
        elif sec in ('.rdata', '.data', '.rsrc'):
            r['kind'] = 'data'
            if va in dmap:
                v, k, tot = dmap[va]
                r['nitro'] = v
                r['how'] = ('voted %d/%d' % (k, tot)) if k < 1000 else ('import %s!%s' % gold.iat[va])
                r['status'] = 'voted' if k == tot else 'voted-split'
            else:
                i = bisect.bisect_left(dkeys, va)
                lo_ = dkeys[i - 1] if i > 0 else None
                hi_ = dkeys[i] if i < len(dkeys) else None
                dl = (dmap[lo_][0] - lo_) if lo_ is not None and gold.sec(lo_) == sec and va - lo_ <= 0x400 else None
                dh = (dmap[hi_][0] - hi_) if hi_ is not None and gold.sec(hi_) == sec and hi_ - va <= 0x400 else None
                if dl is not None and dl == dh:
                    r['nitro'], r['status'] = va + dl, 'bracketed'
                    r['how'] = 'between 0x%x and 0x%x, delta %+#x' % (lo_, hi_, dl)
                elif dl is not None and va - lo_ <= 0x40:
                    r['nitro'], r['status'] = va + dl, 'near'
                    r['how'] = '0x%x below, delta %+#x' % (lo_, dl)
                else:
                    r['how'] = 'no vote, no agreeing neighbours'
            if r['nitro']:
                r['gsig'], r['nsig'] = gold.bytes(va, 4), nitro.bytes(r['nitro'], 4)
        else:
            r['kind'] = 'header'
            r['how'] = 'PE header / outside sections'
        if va in manual:
            nv, ok, note = manual[va]
            r['nitro'], r['status'], r['how'], r['ok'] = nv, ('manual' if nv else 'unmapped'), 'hand-read: ' + note, ok
            if r['kind'] == 'code' and nv:
                r['gsig'], r['nsig'] = gold.bytes(va, max(ok, 8)), nitro.bytes(nv, max(ok, 8))
            elif not nv:
                r['gsig'], r['nsig'] = b'', b''
        rows.append(r)

    # data-site audit: how each exe USES the global (every instruction in every function that names it, the address
    # masked). A Nitro use kind that Gold never has (e.g. `test dword ptr [A], 0x2000` where Gold only reads the word)
    # means the global's meaning may have changed (nitro-mp-design lane, 0x541010): flagged 'use-differs' for a hand read.
    def uses_of(exe, want):
        out = defaultdict(Counter)
        for fa, sz in exe.funcs:
            for ins in exe.dis(fa, sz):
                for x in abs_addrs(ins, exe):
                    if x in want:
                        out[x][HEXNUM.sub(lambda m: 'A' if int(m.group(0), 16) == x else m.group(0), ins.mnemonic + ' ' + ins.op_str)] += 1
        return out
    dsites = [r for r in rows if r['kind'] == 'data' and r['nitro']]
    gu = uses_of(gold, {r['gold'] for r in dsites})
    nu = uses_of(nitro, {r['nitro'] for r in dsites})
    for r in dsites:
        g, n = gu.get(r['gold'], Counter()), nu.get(r['nitro'], Counter())
        extra = sorted(set(n) - set(g))
        r['uses_g'], r['uses_n'] = sum(g.values()), sum(n.values())
        if extra and r['status'] != 'manual':
            r['how'] += ' | USE-DIFFERS: nitro-only uses ' + '; '.join(extra[:4])
            r['use_differs'] = 1

    # outputs -------------------------------------------------------------------------------------------------------
    with open(a.csv, 'w', newline='') as fo:
        w = csv.writer(fo)
        w.writerow(['gold', 'nitro', 'kind', 'status', 'ok', 'how', 'gold_func', 'nitro_func', 'gold_sig', 'nitro_sig', 'uses'])
        for r in rows:
            w.writerow(['0x%06x' % r['gold'], '0x%06x' % r['nitro'] if r['nitro'] else '', r['kind'], r['status'], r.get('ok', ''), r['how'],
                        r['func'], r['nfunc'], r['gsig'].hex(), r['nsig'].hex(),
                        '; '.join(sorted({'%s:%d %s' % u for u in r['uses']}))[:600]])
    st = Counter((r['kind'], r['status']) for r in rows)
    tn = nitro.bytes(nitro.text[0], nitro.text_vsize)
    tg = gold.bytes(gold.text[0], gold.text_vsize)
    K = {'unmapped': 0, 'exact': 1, 'reloc': 2, 'differs': 3, 'voted': 4, 'voted-split': 5, 'bracketed': 6, 'near': 7, 'manual': 8}
    with open(a.header, 'w', newline='\n') as fo:
        fo.write('/* sites_nitro.h - GENERATED by tools/nitro-sites/gen_sites.py; do not edit, re-run the script.\n')
        fo.write(' * Gold exe 6319abf7 -> nitro.exe 28b8ae27. %d proxy addresses:\n' % len(rows))
        for k, v in sorted(st.items()):
            fo.write(' *   %-6s %-12s %d\n' % (k[0], k[1], v))
        fo.write(' * Row: gold va, nitro va (0 = unmapped), status (SN_*), ok = bytes from the site that are the same instructions in both\n')
        fo.write(' * exes up to relocation (a patch longer than ok is refused), then the bytes AT THE NITRO ADDRESS and (gsig) the Gold bytes of the same instructions (code: the whole\n')
        fo.write(' * instructions from the site through >= 16 bytes, checked against memory before a site is used; data: the 4\n')
        fo.write(' * initial file bytes, informative only). Sorted by gold va. Record: docs/records/NITRO-PORT-2026-10-21.md. */\n')
        fo.write('#ifndef SITES_NITRO_H\n#define SITES_NITRO_H\n')
        fo.write('#define NITRO_TEXT_CRC32 0x%08xu   /* crc32 of nitro.exe .text, 0x%x bytes at 0x%x */\n' % (zlib.crc32(tn) & 0xffffffff, len(tn), nitro.text[0]))
        fo.write('#define NITRO_TEXT_SIZE  0x%xu\n' % len(tn))
        fo.write('#define GOLD_TEXT_CRC32  0x%08xu   /* crc32 of the Gold exe 6319abf7 .text, 0x%x bytes */\n' % (zlib.crc32(tg) & 0xffffffff, len(tg)))
        fo.write('#define GOLD_TEXT_SIZE   0x%xu\n' % len(tg))
        fo.write('#define NITRO_PE_STAMP 0x%08xu\n#define GOLD_PE_STAMP  0x%08xu\n' % (nitro.pe.FILE_HEADER.TimeDateStamp, gold.pe.FILE_HEADER.TimeDateStamp))
        for k, v in K.items():
            fo.write('#define SN_%s %d\n' % (k.upper().replace('-', '_'), v))
        fo.write('typedef struct { unsigned gold, nitro; unsigned char status, ok, len, sig[48], gsig[48]; } nitro_site_t;\n')
        fo.write('static const nitro_site_t g_nitro_sites[] = {\n')
        for r in rows:
            sig = r["nsig"][:48] if r['kind'] == 'code' and r['nitro'] else b''
            gsig = r['gsig'][:len(sig)]
            fo.write('    { 0x%06x, 0x%06x, %d, %d, %d, { %s }, { %s } },\n' % (
                r['gold'], r['nitro'], K[r['status']], r.get('ok', 0), len(sig),
                ', '.join('0x%02x' % c for c in sig) if sig else '0', ', '.join('0x%02x' % c for c in gsig) if gsig else '0'))
        fo.write('};\n#define NITRO_SITE_COUNT %d\n#endif\n' % len(rows))
    for k, v in sorted(st.items()):
        print('%-6s %-12s %d' % (k[0], k[1], v))
    print('total', len(rows), '->', a.header)


if __name__ == '__main__':
    main()
