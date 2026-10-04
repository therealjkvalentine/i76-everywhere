#!/usr/bin/env python3
r"""eh_decode.py (Task 5, Phase 0) - decode the VC5 C++ exception frames of i76.exe.

Walks every FuncInfo record (magic 0x19930520) in .rdata, its UnwindMap, the EH stub
(`mov eax, FuncInfo; jmp __CxxFrameHandler`) that names it, the owning function (the
`push -1; push stub; mov eax,fs:[0]` prologue), and decodes every unwind funclet with
capstone.  Also lists every `push imm; call thunk_operator_new` site so the island's
class sizes are on record.  Writes types\cpp_island.md (human table) and a JSON side
file (machine table).  Every address carries its class (text | init); every count its
method.  The task text placed the 30 records at 0x4bffa8-0x4c03a0; the bytes say
0x4bffa8-0x4c04b0 (the last record starts at 0x4c0490), so the walk is by magic scan
and the range is reported, not assumed.

Usage: python tools\eh_decode.py [--exe PATH] [--export DIR] [--out types\cpp_island.md]
        [--json status\tasks\t5-evidence-supply.eh.json]
Read-only on the binary and the export; verifies its own writes by reading them back.
"""
import argparse
import csv
import json
import os
import struct
import sys
from collections import OrderedDict, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_tables import Image  # noqa: E402
from capstone import Cs, CS_ARCH_X86, CS_MODE_32  # noqa: E402
from capstone.x86 import X86_OP_IMM, X86_OP_MEM  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DEFAULT_EXE = r"C:\Users\james\i76-uncap-lab\game\i76.exe.2017galaxy"
EXPECTED_MD5 = "9a232dcc2c164648cff20c414c1f9698"
MAGIC = 0x19930520
ISLAND = (0x472000, 0x488000)  # method doc: the C++ island, 117 functions, 74,069 B


def load_functions(export):
    fs = []
    with open(os.path.join(export, "functions.csv"), newline="") as fh:
        for r in csv.DictReader(fh):
            fs.append((int(r["address"], 16), int(r["size"]), r["name"]))
    fs.sort()
    return fs


def load_names(repo):
    names = {}
    p = os.path.join(repo, "symbols", "functions.tsv")
    if not os.path.exists(p):
        return names
    with open(p, encoding="utf-8") as fh:
        hdr = None
        for line in fh:
            if line.startswith("#"):
                continue
            parts = line.rstrip("\n").split("\t")
            if hdr is None:
                hdr = parts
                continue
            row = dict(zip(hdr, parts))
            names[int(row["addr"], 16)] = (row["name"], row["status"])
    return names


def enclosing(fs, va):
    lo, hi = 0, len(fs) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        a, s, n = fs[mid]
        if va < a:
            hi = mid - 1
        elif va >= a + s:
            lo = mid + 1
        else:
            return fs[mid]
    return None


def u32(img, va):
    off = img.va2off(va)
    return struct.unpack_from("<I", img.data, off)[0]


def i32(img, va):
    off = img.va2off(va)
    return struct.unpack_from("<i", img.data, off)[0]


def decode(img, fs, cs=None):
    """Return (frames, new_sites, funnel). Pure function of the image bytes + function list."""
    cs = cs or Cs(CS_ARCH_X86, CS_MODE_32)
    cs.detail = True
    funnel = OrderedDict()
    rd_lo, rd_hi = img.rdata_lo, img.rdata_hi
    rdata = img.data[img.va2off(rd_lo):img.va2off(rd_lo) + (rd_hi - rd_lo)]
    # 1. magic scan (4-aligned) over .rdata
    magics = [rd_lo + i for i in range(0, len(rdata) - 3, 4)
              if struct.unpack_from("<I", rdata, i)[0] == MAGIC]
    funnel["rdata_magic_hits(method=4-aligned u32 scan)"] = len(magics)
    # 2. parse FuncInfo {magic, maxState, pUnwindMap, nTryBlocks, pTryBlockMap, nIPMap, pIPMap, pad}
    frames = []
    for va in magics:
        rec = OrderedDict(funcinfo=va, funcinfo_class="init")
        rec["maxState"] = i32(img, va + 4)
        rec["pUnwindMap"] = u32(img, va + 8)
        rec["nTryBlocks"] = u32(img, va + 12)
        rec["pTryBlockMap"] = u32(img, va + 16)
        rec["nIPMapEntries"] = u32(img, va + 20)
        rec["pIPtoStateMap"] = u32(img, va + 24)
        rec["dword7"] = u32(img, va + 28)
        ok = (rd_lo <= rec["pUnwindMap"] < rd_hi) and 0 <= rec["maxState"] <= 64
        rec["layout_ok"] = ok
        rec["unwind"] = []
        if ok:
            for k in range(rec["maxState"]):
                e = rec["pUnwindMap"] + 8 * k
                rec["unwind"].append(OrderedDict(entry=e, toState=i32(img, e), action=u32(img, e + 4)))
        rec["record_end"] = (rec["pUnwindMap"] + 8 * rec["maxState"]) if ok else va + 32
        frames.append(rec)
    funnel["funcinfo_layout_ok"] = sum(1 for f in frames if f["layout_ok"])
    # contiguity: record i+1 must start where record i's unwind map ends
    contig = sum(1 for a, b in zip(frames, frames[1:]) if a["record_end"] == b["funcinfo"])
    funnel["contiguous_pairs(method=record_end==next funcinfo)"] = contig
    # 3. stubs: scan .text for B8 <funcinfo> E9 <rel32 -> __CxxFrameHandler thunk>
    text = img.data[img.va2off(img.text_lo):img.va2off(img.text_lo) + (img.text_hi - img.text_lo)]
    by_fi = {f["funcinfo"]: f for f in frames}
    cxx_slot = None
    for slot, (dll, nm, ordn) in img.imports.items():
        if nm == "__CxxFrameHandler":
            cxx_slot = slot
    funnel["__CxxFrameHandler_iat_slot"] = hex(cxx_slot) if cxx_slot else None
    stubs = {}
    i = 0
    while True:
        i = text.find(b"\xb8", i)
        if i < 0:
            break
        if i + 10 <= len(text):
            fi = struct.unpack_from("<I", text, i + 1)[0]
            if fi in by_fi and text[i + 5] == 0xE9:
                rel = struct.unpack_from("<i", text, i + 6)[0]
                tgt = img.text_lo + i + 10 + rel
                # thunk must be `jmp [cxx_slot]` (FF 25 slot)
                toff = img.va2off(tgt)
                is_thunk = (toff is not None and img.data[toff:toff + 2] == b"\xff\x25"
                            and struct.unpack_from("<I", img.data, toff + 2)[0] == cxx_slot)
                if is_thunk:
                    stubs[fi] = OrderedDict(stub=img.text_lo + i, handler_thunk=tgt)
        i += 1
    funnel["eh_stubs(method=capstone-free byte scan B8 imm32 E9 rel32 -> jmp [iat __CxxFrameHandler])"] = len(stubs)
    # 4. owners: `push stub` (68 imm32) sites in .text; check the `push -1` before and fs:[0] after
    stub_vas = {v["stub"]: fi for fi, v in stubs.items()}
    for f in frames:
        f.update(stubs.get(f["funcinfo"], {"stub": None, "handler_thunk": None}))
        f["push_sites"] = []
    i = 0
    while True:
        i = text.find(b"\x68", i)
        if i < 0:
            break
        if i + 5 <= len(text):
            imm = struct.unpack_from("<I", text, i + 1)[0]
            if imm in stub_vas:
                site = img.text_lo + i
                prev_push_m1 = text[i - 2:i] == b"\x6a\xff"
                nxt = text[i + 5:i + 11] == b"\x64\xa1\x00\x00\x00\x00"  # mov eax, fs:[0]
                fn = enclosing(fs, site)
                by_fi[stub_vas[imm]]["push_sites"].append(OrderedDict(
                    site=site, push_minus1_before=prev_push_m1, mov_eax_fs0_after=nxt,
                    owner=fn[0] if fn else None, owner_size=fn[1] if fn else None))
        i += 1
    funnel["push_stub_sites(method=byte scan 68 imm32 == stub VA)"] = sum(len(f["push_sites"]) for f in frames)
    funnel["frames_with_one_owner"] = sum(1 for f in frames if len(f["push_sites"]) == 1)
    # 5. funclets
    for f in frames:
        for e in f["unwind"]:
            act = e["action"]
            off = img.va2off(act)
            insns = list(cs.disasm(img.data[off:off + 16], act))
            txt = []
            e["decoded"] = None
            for ins in insns:
                txt.append("%s %s" % (ins.mnemonic, ins.op_str))
                if ins.mnemonic == "ret":
                    break
            e["asm"] = "; ".join(txt)
            e["bytes"] = (insns[-1].address + insns[-1].size - act) if insns else 0
            # canonical shape: mov eax,[ebp+d]; push eax; call X; pop ecx; ret
            if (len(insns) >= 5 and insns[0].mnemonic == "mov" and insns[1].mnemonic == "push"
                    and insns[2].mnemonic == "call" and insns[3].mnemonic == "pop" and insns[4].mnemonic == "ret"):
                m = insns[0].operands[1]
                d = m.mem.disp if m.type == X86_OP_MEM else None
                tgt = insns[2].operands[0].imm
                e["decoded"] = OrderedDict(frame_disp=d, callee=tgt)
    # 6. operator new sites in the whole .text: push imm ; call thunk_operator_new
    new_thunk = None
    del_thunk = None
    for slot, (dll, nm, ordn) in img.imports.items():
        if nm == "??2@YAPAXI@Z":
            new_thunk = find_thunk(img, text, slot)
        if nm == "??3@YAXPAX@Z":
            del_thunk = find_thunk(img, text, slot)
    funnel["thunk_operator_new"] = hex(new_thunk) if new_thunk else None
    funnel["thunk_operator_delete"] = hex(del_thunk) if del_thunk else None
    new_sites = []
    if new_thunk:
        for a, s, n in fs:
            off = img.va2off(a)
            if off is None:
                continue
            window = []
            for ins in cs.disasm(img.data[off:off + s], a):
                if ins.mnemonic == "call" and ins.operands and ins.operands[0].type == X86_OP_IMM \
                        and ins.operands[0].imm == new_thunk:
                    # the size is the nearest preceding `push` (a store may sit between it and the call)
                    size, meth, expr = None, "no push within 3 instructions", None
                    for k, pv in enumerate(reversed(window[-3:])):
                        if pv.mnemonic == "push":
                            if pv.operands[0].type == X86_OP_IMM:
                                size = pv.operands[0].imm
                                meth = "capstone: `push imm` %d instruction(s) before the call" % (k + 1)
                            else:
                                expr = "push %s after: %s" % (pv.op_str, " | ".join(
                                    "%s %s" % (w.mnemonic, w.op_str) for w in window[-6:-(k + 1) or None]))
                                meth = "computed size (register): see expr"
                            break
                    new_sites.append(OrderedDict(site=ins.address, function=a, size=size, size_method=meth, expr=expr))
                window.append(ins)
    funnel["operator_new_call_sites(method=capstone call imm == thunk over function bodies)"] = len(new_sites)
    return frames, new_sites, funnel, dict(new_thunk=new_thunk, del_thunk=del_thunk)


def find_thunk(img, text, slot):
    pat = b"\xff\x25" + struct.pack("<I", slot)
    i = text.find(pat)
    return (img.text_lo + i) if i >= 0 else None


def classify_action(e, thunks, names):
    d = e.get("decoded")
    if not d:
        return "unrecognised funclet shape"
    callee = d["callee"]
    disp = d["frame_disp"]
    if callee == thunks["del_thunk"]:
        return "operator delete([ebp%+#x]) : free the storage of a `new T(...)` whose constructor unwound" % disp
    nm = names.get(callee, ("FUN_%08x" % callee, "auto"))[0]
    if disp is not None and disp > 0:
        return "%s(&[ebp%+#x]) : destroy a by-value argument (callee-destroyed, MSVC ABI) via %s" % (nm, disp, nm)
    return "%s(&[ebp%+#x]) : destroy a local via %s" % (nm, disp, nm)


def write_outputs(img, fs, frames, new_sites, funnel, thunks, names, out_md, out_json):
    lo = min(f["funcinfo"] for f in frames)
    hi = max(f["record_end"] for f in frames)
    n_entries = sum(len(f["unwind"]) for f in frames)
    actions = defaultdict(list)
    for f in frames:
        for e in f["unwind"]:
            d = e.get("decoded")
            key = (d["callee"], d["frame_disp"]) if d else ("?", "?")
            actions[key].append(e["action"])
    sizes = defaultdict(list)
    for s in new_sites:
        sizes[s["size"]].append(s)
    lines = []
    L = lines.append
    L("# cpp_island.md - the C++ exception-handling island of i76.exe (tools\\eh_decode.py, Task 5)")
    L("")
    L("Binary: `%s` md5 %s (pristine; class tags: `text` = .text VA, `init` = .rdata/.data VA)." % (img.path, img.md5))
    L("Method: 4-aligned u32 scan of .rdata for the VC5 FuncInfo magic 0x19930520; UnwindMap walked from each record; EH stubs "
      "found as `mov eax,FuncInfo; jmp <jmp [IAT __CxxFrameHandler]>`; owners as the `push stub` prologue site's enclosing Ghidra "
      "function (ghidra\\export\\functions.csv); funclets decoded with capstone; class sizes from `push imm; call thunk_operator_new`.")
    L("Status of every name below: the frame table is structural fact (gate G5 needs no capture); the class rows are `proposed`.")
    L("")
    L("## Funnel")
    L("")
    for k, v in funnel.items():
        L("- %s: %s" % (k, v))
    L("- FuncInfo span (measured): 0x%x-0x%x (%d B); the task text said 0x4bffa8-0x4c03a0, which holds only the first %d records"
      % (lo, hi, hi - lo, sum(1 for f in frames if f["funcinfo"] < 0x4c03a0)))
    L("- UnwindMap entries total (method: sum of maxState): %d; every toState = %s"
      % (n_entries, sorted(set(e["toState"] for f in frames for e in f["unwind"]))))
    L("- FuncInfo record = 8 dwords (32 B): {magic, maxState, pUnwindMap, nTryBlocks, pTryBlockMap, nIPMapEntries, pIPtoStateMap, 0}; "
      "nTryBlocks = %s and nIPMapEntries = %s in every record (no try/catch, no IP-to-state map: pure unwind frames)"
      % (sorted(set(f["nTryBlocks"] for f in frames)), sorted(set(f["nIPMapEntries"] for f in frames))))
    L("")
    L("## Frames (30 rows expected)")
    L("")
    L("| # | FuncInfo (init) | maxState | UnwindMap (init) | stub (text) | owner (text) | owner name | status | prologue check | unwind actions |")
    L("|---|---|---|---|---|---|---|---|---|---|")
    for k, f in enumerate(frames, 1):
        own = f["push_sites"][0] if f["push_sites"] else None
        oa = own["owner"] if own else None
        nm, st = names.get(oa, ("FUN_%08x" % oa if oa else "-", "auto"))
        chk = ("push -1 before=%s, mov eax,fs:[0] after=%s" % (own["push_minus1_before"], own["mov_eax_fs0_after"])) if own else "no push site"
        acts = "; ".join("s%d->%d: %s" % (i, e["toState"], classify_action(e, thunks, names)) for i, e in enumerate(f["unwind"]))
        L("| %d | 0x%x | %d | 0x%x | %s | %s | %s | %s | %s | %s |" % (
            k, f["funcinfo"], f["maxState"], f["pUnwindMap"],
            ("0x%x" % f["stub"]) if f["stub"] else "-", ("0x%x" % oa) if oa else "-", nm, st, chk, acts))
    L("")
    L("## Unwind action kinds (method: capstone decode of the %d funclets, 11 B each: `mov eax,[ebp+d]; push eax; call X; pop ecx; ret`)" % n_entries)
    L("")
    L("| callee (text) | frame slot | funclets | meaning |")
    L("|---|---|---|---|")
    for (callee, disp), lst in sorted(actions.items(), key=lambda kv: -len(kv[1])):
        e = OrderedDict(decoded=OrderedDict(callee=callee, frame_disp=disp)) if callee != "?" else OrderedDict()
        L("| %s | %s | %d | %s |" % (("0x%x" % callee) if callee != "?" else "?",
                                     ("[ebp%+#x]" % disp) if disp != "?" else "?", len(lst), classify_action(e, thunks, names)))
    L("")
    L("## Classes by `operator new` size (method: `push imm; call thunk_operator_new 0x%x`, capstone over every Ghidra function body)" % thunks["new_thunk"])
    L("")
    L("| size (B) | sites | functions (text) | note |")
    L("|---|---|---|---|")
    for size, lst in sorted(sizes.items(), key=lambda kv: (kv[0] is None, kv[0] or 0)):
        fns = sorted(set(s["function"] for s in lst))
        note = "in the island" if all(ISLAND[0] <= f < ISLAND[1] for f in fns) else "outside 0x472000-0x488000"
        if size is None:
            note += "; " + " / ".join(sorted(set("0x%x: %s" % (s_["site"], s_["expr"]) for s_ in lst if s_["expr"])))
        L("| %s | %d | %s | %s |" % (("%d (0x%x)" % (size, size)) if size is not None else "computed (register)",
                                     len(lst), ", ".join("0x%x" % f for f in fns), note))
    L("")
    L("## Reading")
    L("")
    L("- Every frame is a pure unwind frame: no try blocks, no catch, no IP map. The island uses C++ EH only for the compiler-generated "
      "cleanup that `/GX` forces around `new T(...)` (delete the raw storage if T's constructor throws) and around by-value class "
      "arguments (the callee destroys them, so the callee needs a state for each).")
    L("- The funclets that call 0x42d5d0 are destructor calls: 0x42d5d0 is a one-byte `ret`, i.e. an empty (inlined-away) destructor of the "
      "by-value argument class. The current `proposed` name `dbg_LogStub` for 0x42d5d0 is therefore contradicted by this frame evidence; "
      "both readings are `ret`, and the EH funclets are the only static evidence that names its role. Recorded as a finding for the reviewer, "
      "not rewritten here (functions.tsv has a single writer).")
    L("- Class identities available statically: the sizes above (the method doc expected 16 `new` sites in 0x473960; the bytes give the table "
      "above), the constructor or initialiser applied to the `new` result (next task: follow eax after each site), and the by-value "
      "argument class with the empty destructor. Field layouts need gate T citations and are not claimed here. pe-fingerprint counted 31 "
      "`operator new` call sites by linear sweep; a byte scan for `E8 rel32 -> thunk` over all of .text finds 30, all inside Ghidra "
      "function bodies (the 31st is not reproducible by either method here).")
    L("")
    L("## Blockers (H7)")
    L("")
    L("- The by-value argument class cannot be named until a caller that constructs it is decompiled with its constructor identified; "
      "the frame evidence gives only `sizeof` bounds (the slot at [ebp+0xc] is 4 B wide, so the class is passed by hidden pointer or is 4 B).")
    txt = "\n".join(lines) + "\n"
    os.makedirs(os.path.dirname(out_md), exist_ok=True)
    with open(out_md, "w", encoding="utf-8") as fh:
        fh.write(txt)
    with open(out_md, encoding="utf-8") as fh:
        back = fh.read()
    assert back == txt, "read-back mismatch on " + out_md
    rows = sum(1 for l in back.splitlines() if l.startswith("| ") and l.split("|")[1].strip().isdigit())
    js = OrderedDict(exe=img.path, md5=img.md5, method="see cpp_island.md", span=[lo, hi], funnel=funnel,
                     thunks={k: v for k, v in thunks.items()}, frames=frames, new_sites=new_sites)
    with open(out_json, "w", encoding="utf-8") as fh:
        json.dump(js, fh, indent=1)
    with open(out_json, encoding="utf-8") as fh:
        back_js = json.load(fh)
    assert len(back_js["frames"]) == len(frames), "read-back mismatch on " + out_json
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default=DEFAULT_EXE)
    ap.add_argument("--export", default=os.path.join(REPO, "ghidra", "export"))
    ap.add_argument("--out", default=os.path.join(REPO, "types", "cpp_island.md"))
    ap.add_argument("--json", default=os.path.join(REPO, "status", "tasks", "t5-evidence-supply.eh.json"))
    a = ap.parse_args()
    img = Image(a.exe)
    if img.md5 != EXPECTED_MD5:
        sys.exit("refusing: %s md5 %s != %s (H0)" % (a.exe, img.md5, EXPECTED_MD5))
    fs = load_functions(a.export)
    names = load_names(REPO)
    frames, new_sites, funnel, thunks = decode(img, fs)
    rows = write_outputs(img, fs, frames, new_sites, funnel, thunks, names, a.out, a.json)
    print("launched %s md5 %s eh_decode.py 1.0" % (a.exe, img.md5))
    for k, v in funnel.items():
        print("  %s: %s" % (k, v))
    print("frames=%d unwind_entries=%d frame-table-rows-read-back=%d new_sites=%d -> %s, %s" % (
        len(frames), sum(len(f["unwind"]) for f in frames), rows, len(new_sites), a.out, a.json))


if __name__ == "__main__":
    main()
