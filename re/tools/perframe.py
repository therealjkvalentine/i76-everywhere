r"""perframe.py - what runs once per rendered frame outside the physics substeps, and which of it advances state
by a constant per call instead of by elapsed time (2026-09-27).

    python tools\perframe.py [--out status\perframe.tsv]

Roots (all static, capstone over md5 9a232dcc):
  * every direct call in WinMain's gameplay loop body 0x4039a0..0x403f20 (one iteration = one rendered frame);
  * the object-class table 0x4f76e0 (0x34-byte records, type at +0): slot +0xc is the per-object tick that
    0x461c80 calls for every live object each frame, slot +0x10 the post-tick 0x461d50 calls;
  * the camera controller [0x4c2720] (default 0x406ab0).
Functions reachable from physics_StepVehicle 0x438fd0 / entity_UpdateState 0x465370 get their dt as the substep
argument and are reported separately (scope "substep").

Per function it records:
  dt       reads of a frame/sim delta (simclock_GetDt/GetSimDt/GetSimRate/GetAccumDt, or 0x4fe420/24/28/2c,
           0x5a7e14, 0x504a28)
  time     reads of an absolute clock (simclock_GetTime/GetSimTime, 0x5a7e74, 0x5a7e70)
  frames   reads of simclock_frame_count 0x5a7e1c
  step     fld [M] ... fadd/fsub <constant> ... fstp [M] on the same non-stack M within 8 instructions
  decay    fld [M] ... fmul <constant> ... fstp [M] (multiplicative damping per call)
  count    inc/dec/add/sub [M], imm on non-stack memory
A function with step/decay/count sites and no dt read is a candidate frame-rate dependency; its callers may still
scale by dt, so candidates are read by hand before any claim. The "hint" column never removes a candidate; it
flags a shape that has fooled a hand read (2026-09-27):
  clock    the function also reads an absolute clock; possibly a catch-up loop `while (next < time) next += c`,
           which is frame-rate neutral (type-34 post-tick 0x460c80). Also check each step target is not rewritten
           from fresh values earlier on the same path (0x477ed0 lifts a freshly computed point by 25 each call).
"""
import csv, json, os, re, struct, sys, collections
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from capstone.x86 import X86_OP_MEM, X86_OP_IMM, X86_REG_ESP, X86_REG_EBP, X86_REG_INVALID

M = r"C:\Users\james\i76-map"
EXE = r"C:\Users\james\i76-uncap-lab\game\i76.exe.2017galaxy"
pe = pefile.PE(EXE)
BASE = pe.OPTIONAL_HEADER.ImageBase
md = Cs(CS_ARCH_X86, CS_MODE_32); md.detail = True
rd = lambda va, n: pe.__data__[pe.get_offset_from_rva(va - BASE):pe.get_offset_from_rva(va - BASE) + n]
FN = {int(r["addr"], 16): r for r in csv.DictReader((l for l in open(os.path.join(M, "symbols", "functions.tsv"), encoding="utf-8") if not l.startswith("#")), delimiter="\t")}
CG = json.load(open(os.path.join(M, "ghidra", "export", "callgraph.json"), encoding="utf-8"))
name = lambda a: FN.get(a, {}).get("name", "FUN_%08x" % a)

DT_CALLS = {0x49c8b0: "GetDt", 0x49c7a0: "GetSimDt", 0x49c7b0: "GetSimRate", 0x49c7e0: "GetAccumDt"}
TIME_CALLS = {0x49c8c0: "GetTime", 0x49c7c0: "GetSimTime"}
DT_MEM = {0x4fe420, 0x4fe424, 0x4fe428, 0x4fe42c, 0x5a7e14, 0x504a28}
TIME_MEM = {0x5a7e74, 0x5a7e70}
FRAME_MEM = {0x5a7e1c}


def callees(a):
    return [int(c, 16) for c in CG.get("%08x" % a, {}).get("callees", []) if int(c, 16) >= 0x401000]


def reach(roots):
    seen, stack = set(), list(roots)
    while stack:
        a = stack.pop()
        if a in seen or a not in FN:
            continue
        seen.add(a); stack.extend(callees(a))
    return seen


def disasm(a):
    size = int(FN[a]["size"] or 0)
    return list(md.disasm(rd(a, size), a)) if size else []


def mem_abs(op):
    """absolute address of a memory operand with no base register (index allowed), else None"""
    if op.type != X86_OP_MEM:
        return None
    m = op.mem
    if m.base != X86_REG_INVALID:
        return None
    return m.disp & 0xffffffff


def mem_key(ins, op):
    """a comparable key for a non-stack memory operand"""
    m = op.mem
    if m.base in (X86_REG_ESP, X86_REG_EBP):
        return None
    return (m.base, m.index, m.scale, m.disp)


def is_const(addr):
    return addr is not None and 0x4bc000 <= addr < 0x4c2000   # .rdata; initialised .data holds variables too


def scan(a):
    r = collections.defaultdict(list)
    ins = disasm(a)
    for i, x in enumerate(ins):
        if x.mnemonic == "call" and x.operands and x.operands[0].type == X86_OP_IMM:
            t = x.operands[0].imm & 0xffffffff
            if t in DT_CALLS: r["dt"].append("%x:%s" % (x.address, DT_CALLS[t]))
            if t in TIME_CALLS: r["time"].append("%x:%s" % (x.address, TIME_CALLS[t]))
        for op in x.operands:
            ab = mem_abs(op)
            if ab in DT_MEM: r["dt"].append("%x:[%x]" % (x.address, ab))
            if ab in TIME_MEM: r["time"].append("%x:[%x]" % (x.address, ab))
            if ab in FRAME_MEM: r["frames"].append("%x" % x.address)
        # counters
        if x.mnemonic in ("inc", "dec", "add", "sub") and x.operands and x.operands[0].type == X86_OP_MEM:
            k = mem_key(x, x.operands[0])
            if k and (x.mnemonic in ("inc", "dec") or (len(x.operands) == 2 and x.operands[1].type == X86_OP_IMM)):
                if not (FRAME_MEM & {mem_abs(x.operands[0])}):
                    r["count"].append("%x:%s %s" % (x.address, x.mnemonic, x.op_str))
        # fld [M] ... fadd/fsub/fmul const ... fstp [M]
        if x.mnemonic == "fld" and x.operands and x.operands[0].type == X86_OP_MEM:
            k = mem_key(x, x.operands[0])
            if not k or is_const(mem_abs(x.operands[0])):
                continue
            kinds = set()
            for y in ins[i + 1:i + 9]:
                if y.mnemonic in ("fadd", "fsub", "fsubr", "fmul") and y.operands and y.operands[-1].type == X86_OP_MEM \
                        and is_const(mem_abs(y.operands[-1])):
                    kinds.add("decay" if y.mnemonic == "fmul" else "step")
                if y.mnemonic in ("fadd", "fsub", "fmul", "fdiv") and y.operands and y.operands[-1].type == X86_OP_MEM \
                        and mem_key(y, y.operands[-1]) is None:
                    kinds.add("stackmix")   # mixes in a local (often dt) - not a constant step
                if y.mnemonic in ("fstp", "fst") and y.operands and y.operands[0].type == X86_OP_MEM and mem_key(y, y.operands[0]) == k:
                    for kd in kinds - {"stackmix"}:
                        if "stackmix" not in kinds:
                            r[kd].append("%x..%x %s" % (x.address, y.address, x.op_str))
                    break
                if y.mnemonic in ("call", "ret", "jmp"):
                    break
    # rmw: a window of <= 8 instructions ending in fst/fstp [M] (persistent M) in which M is also an operand
    # earlier (fld/fadd/fsub/fsubr/fmul [M]), some constant from .rdata/.data is an arithmetic operand, and no
    # stack-memory operand (dt is normally a local) or dt/time call appears - e.g. the free-look camera
    # `fild [input]; fmul [-1 deg]; fsubr [pitch]; fst [pitch]` at 0x405bc4..0x405bdc
    for i, x in enumerate(ins):
        if x.mnemonic not in ("fst", "fstp") or not x.operands or x.operands[0].type != X86_OP_MEM:
            continue
        k = mem_key(x, x.operands[0])
        if not k or is_const(mem_abs(x.operands[0])):
            continue
        win = ins[max(0, i - 8):i]
        uses_m = any(y.operands and y.operands[-1].type == X86_OP_MEM and mem_key(y, y.operands[-1]) == k
                     and y.mnemonic in ("fld", "fadd", "fsub", "fsubr", "fmul") for y in win)
        const = any(y.mnemonic in ("fmul", "fadd", "fsub", "fsubr", "fdiv", "fdivr") and y.operands and
                    y.operands[-1].type == X86_OP_MEM and is_const(mem_abs(y.operands[-1])) for y in win)
        local = any(y.mnemonic in ("fld", "fild", "fadd", "fsub", "fsubr", "fmul", "fdiv", "fdivr") and y.operands and
                    y.operands[-1].type == X86_OP_MEM and mem_key(y, y.operands[-1]) is None for y in win)
        callx = any(y.mnemonic in ("call", "ret", "jmp") for y in win)
        if uses_m and const and not local:
            r["rmw"].append("%x %s" % (x.address, x.op_str))
    return r


def main():
    # roots
    loop = []
    for x in disasm(0x402b30):
        if 0x4039a0 <= x.address <= 0x403f20 and x.mnemonic == "call" and x.operands and x.operands[0].type == X86_OP_IMM:
            t = x.operands[0].imm & 0xffffffff
            if t in FN: loop.append(t)
    tick, post = {}, {}
    va = 0x4f76e0
    while va < 0x4f7c5c:
        rec = struct.unpack("<13I", rd(va, 0x34))
        if rec[3] in FN: tick[rec[3]] = rec[0]
        if rec[4] in FN: post[rec[4]] = rec[0]
        va += 0x34
    roots = {r: "loop" for r in loop}
    roots.update({r: "tick(type %d)" % t for r, t in tick.items()})
    roots.update({r: "post(type %d)" % t for r, t in post.items()})
    # indirect per-frame targets: every function whose address is stored by an immediate into the camera controller
    # [0x4c2720] (camera modes) or the 0x5a7ee0 slot
    for a0, row in FN.items():
        for x in disasm(a0):
            if x.mnemonic == "mov" and len(x.operands) == 2 and x.operands[1].type == X86_OP_IMM and x.operands[0].type == X86_OP_MEM:
                tgt, dst = x.operands[1].imm & 0xffffffff, mem_abs(x.operands[0])
                if tgt in FN and dst in (0x4c2720, 0x5a7ee0):
                    roots[tgt] = ("camera mode" if dst == 0x4c2720 else "slot 0x5a7ee0")
    sub = reach([0x438fd0, 0x465370])
    owner = {}
    for r in roots:
        for f in reach([r]):
            owner.setdefault(f, set()).add(roots[r] + " " + name(r))
    rows = []
    for f, owners in owner.items():
        s = scan(f)
        scope = "substep" if f in sub else "frame"
        cand = scope == "frame" and (s["rmw"] or (not s["dt"] and (s["step"] or s["decay"] or s["count"])))
        rows.append({"addr": "0x%x" % f, "name": name(f), "scope": scope, "candidate": "yes" if cand else "", "hint": "clock" if cand and s["time"] else "",
                     "dt": len(s["dt"]), "time": len(s["time"]), "frames": len(s["frames"]), "step": len(s["step"]),
                     "decay": len(s["decay"]), "count": len(s["count"]), "rmw": len(s["rmw"]),
                     "sites": " | ".join((s["rmw"] + s["step"] + s["decay"] + s["count"] + s["frames"])[:6]),
                     "roots": "; ".join(sorted(owners))[:200]})
    rows.sort(key=lambda r: (r["scope"], r["candidate"] != "yes", r["addr"]))
    out = os.path.join(M, sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else r"status\perframe.tsv")
    with open(out, "w", encoding="utf-8", newline="") as fh:
        fh.write("# perframe.tsv - per-frame reachable functions outside/inside the physics substeps; tools/perframe.py over md5 9a232dcc\n")
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), delimiter="\t"); w.writeheader(); w.writerows(rows)
    c = collections.Counter((r["scope"], r["candidate"]) for r in rows)
    print("roots: %d loop calls, %d class ticks, %d post-ticks, camera; reachable %d (substep %d)" % (len(loop), len(tick), len(post), len(rows), sum(1 for r in rows if r["scope"] == "substep")))
    print("frame-scope candidates (constant step/decay/count, no dt read): %d (%d also read a clock)" % (
        c[("frame", "yes")], sum(1 for r in rows if r["hint"])))
    print("frame-scope functions reading frames counter: %d" % sum(1 for r in rows if r["frames"] and r["scope"] == "frame"))
    print(out)


if __name__ == "__main__":
    main()
