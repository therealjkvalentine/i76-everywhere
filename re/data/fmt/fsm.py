"""fsm.py - the mission script (ADEF/FSM chunk): byte-exact parse/serialise, disassembler, assembler.

Layout = the reader bwd2_h_FSM_409740 -> 0x410720 (+ 0x4105a0 entities, 0x4102d0 paths, 0x410490 machines).
The reader walks the body as a dword cursor (base 0x5244d0, index 0x5244d4), so every field is dword aligned
and strings are copied a dword at a time. Semantics of the VM: see data\\FSM.md and OPCODES below.
"""
import struct
from schema import Struct, Field, Arr, U32, I32, F32, Str, parse_exact, FloatV, StrV

C_ACT = "0x410743 count; 0x4107a3/0x4107df copy 10 dwords per name (0x4107a7 loop 9+1) into 84-byte records (0x410761 n*84)"
C_ENT = "0x4105b8 count; 0x4105ff 10-dword label copy; 0x410681/0x4106c4 two dwords -> u64 instance key at rec+0x50 (0x4106f8 __allshl 32); alloc (n+200)*0x60 (0x4105be)"
C_SND = "0x410843 count; 0x410898/0x4108d4 10-dword copy (0x41089c)"
C_PATH = "0x4102d0 reader: count, alloc n*88 (0x4102fe); name 10 dwords, u32 nNodes, nNodes x 3 floats (0x4103bf n*12)"
C_MACH = "0x4104a6 count; per machine 0x410531 startIP -> state+0x10a8, 0x41054e nArgs, 0x410559..0x410577 copies 40 dwords to the stack base; SP = base + nArgs*4 (0x41057d)"
C_CONST = "0x41094b count; 0x410988 i32 each (array base = the pointer the args are rebased onto, 0x41252f)"
C_CODE = "0x4109ad count; 0x4109c2 n*8 bytes; 0x4109ef copies 2n dwords; executed by fsm_OpcodeSwitch 0x414670"

VEC3 = Struct("vec3", [Field("x", F32), Field("y", F32), Field("z", F32)])
ENTITY = Struct("fsm_entity", [
    Field("label", Str(40), "script-side name used by the mission designer", C_ENT),
    Field("instance", Str(8), "ODEF OBJ name of the placed object this label binds to (bit 7 of each byte = id bits)", C_ENT + "; 0x412425 lookup 0x457630 by key, 'FSM - instance id for %s does not exist in mission file'"),
])
PATH = Struct("fsm_path", [
    Field("name", Str(40), "path name", C_PATH),
    Field("n_nodes", U32, "node count", C_PATH),
    Field("nodes", Arr(VEC3, "n_nodes"), "world-space points", C_PATH),
])
MACHINE = Struct("fsm_machine", [
    Field("start", U32, "entry instruction index (IP = code + start*8, 0x412556)", C_MACH),
    Field("n_args", U32, "argument count: slots [0,n_args) are constant indices rebased to pointers at init (0x412529..0x41253e)", C_MACH),
    Field("args", Arr(U32, 40), "40 stack slots copied verbatim; only the first n_args are used as arguments", C_MACH),
])
INSTR = Struct("fsm_instr", [Field("op", U32, "opcode 1..14 (switch table 0x4149b8)", C_CODE), Field("arg", I32, "operand", C_CODE)])

FSM = Struct("FSM", [
    Field("n_actions", U32, "action-name count", C_ACT),
    Field("actions", Arr(Str(40), "n_actions"), "action names; ACTION operand indexes this table; each name is matched to an engine prototype by match_prototype 0x410a10 (0x4125cf)", C_ACT),
    Field("n_entities", U32, "entity count", C_ENT),
    Field("entities", Arr(ENTITY, "n_entities"), "script entity table", C_ENT),
    Field("n_sounds", U32, "sound count", C_SND),
    Field("sounds", Arr(Str(40), "n_sounds"), "sound clip names", C_SND),
    Field("n_paths", U32, "path count", C_PATH),
    Field("paths", Arr(PATH, "n_paths"), "AI paths", C_PATH),
    Field("n_machines", U32, "machine (thread) count", C_MACH),
    Field("machines", Arr(MACHINE, "n_machines"), "one VM state (0x10bc bytes) per record, linked at +0x10b8", C_MACH),
    Field("n_consts", U32, "constant count", C_CONST),
    Field("consts", Arr(I32, "n_consts"), "constant pool; machine args point into it", C_CONST),
    Field("n_code", U32, "instruction count", C_CODE),
    Field("code", Arr(INSTR, "n_code"), "bytecode, 8 bytes per instruction", C_CODE),
])


def parse(body):
    """Empty FSM chunks (0 bytes: multiplayer / melee missions) parse to None."""
    if len(body) == 0:
        return None
    return parse_exact(FSM, body)


def serialise(v):
    if v is None:
        return b""
    return FSM.emit(v, {})


# ---- opcodes (fsm_OpcodeSwitch 0x414670, jump table 0x4149b8) --------------------------------------------------
OPCODES = {
    1: ("push", "0x4146d5: *SP = arg; SP += 4"),
    2: ("pusha", "0x414701: *SP = &BP[arg]; SP += 4 (push the address of a frame slot)"),
    3: ("pushv", "0x414736: *SP = BP[arg]; SP += 4 (push the contents of a frame slot)"),
    4: ("arga", "0x41476b: *AQ = &BP[arg]; AQ += 4 (queue the address of a frame slot as an action argument)"),
    5: ("argv", "0x4147a0: *AQ = BP[arg]; AQ += 4 (queue the contents of a frame slot)"),
    6: ("alloc", "0x4147d5: SP += arg*4 (reserve locals)"),
    7: ("drop", "0x4147f7: SP -= arg*4"),
    8: ("jmp", "0x41481b: IP = code + arg*8"),
    9: ("jz", "0x414832: if result == 0: IP = code + arg*8 else IP += 8"),
    10: ("yield", "0x414989: IP = code + arg*8; return 0 (end of this machine's slice for the frame)"),
    11: ("call", "0x414874: push BP; BP = SP; push IP+8; IP = code + arg*8"),
    12: ("ret", "0x4148c7: IP = [BP]; SP = BP - (arg+1)*4; BP = [BP-4]; return 1 (machine finished) when SP == stack base"),
    13: ("action", "0x4148fe: result = fsm_ActionDispatch 0x412ce0(state, arg = index into the action table, ...)"),
    14: ("not", "0x414853: result = (result == 0)"),
}
MNEM = {v[0]: k for k, v in OPCODES.items()}
JUMPS = {8, 9, 10, 11}


def _q(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _strtok(v):
    """String field in assembler syntax; raw bytes appended when they carry anything past the NUL."""
    raw = v.raw if isinstance(v, StrV) else None
    s = _q(str(v))
    if raw is not None and raw != str(v).encode("latin1").ljust(len(raw), b"\0"):
        s += " raw=" + raw.hex()
    return s


def _ftok(f):
    if isinstance(f, FloatV):
        if struct.pack("<f", float(f)) == f.raw and repr(float(f)) != "nan":
            return repr(float(f))
        return "0x" + f.raw[::-1].hex()
    return repr(float(f))


def annotate(v):
    """Static dataflow over each machine: which values each ACTION receives. Returns ({ip: comment}, {machine: {param: kind}}).

    Per the compiler's two argument forms (fsm-actions.md section 0): `argv k<0` passes machine parameter
    k + n_args + 1 by reference into the global pool; `push imm; arga k>=0` passes a literal temporary."""
    from fsm_protos import ACTIONS
    code, acts = v["code"], [str(a) for a in v["actions"]]
    notes, pkinds = {}, {}
    for mi, m in enumerate(v["machines"]):
        nargs = m["n_args"]
        seen = set()
        work = [(m["start"], 1, {}, [])]  # ip, sp (slot index relative to BP), known slots {k: literal}, queue
        kinds = pkinds.setdefault(mi, {})
        while work:
            ip, sp, slots, q = work.pop()
            while 0 <= ip < len(code) and (ip, sp) not in seen:
                seen.add((ip, sp))
                op, arg = code[ip]["op"], code[ip]["arg"]
                nxt = ip + 1
                if op == 1:
                    slots = dict(slots); slots[sp] = arg; sp += 1
                elif op in (2, 3):
                    sp += 1
                elif op == 4:
                    q = q + [("lit", slots.get(arg)) if arg >= 0 else ("pref", arg + nargs + 1)]
                elif op == 5:
                    q = q + [("param", arg + nargs + 1) if arg < 0 else ("local", arg)]
                elif op == 6:
                    sp += arg
                elif op == 7:
                    sp -= arg
                elif op == 8:
                    nxt = arg
                elif op == 9:
                    work.append((arg, sp, slots, q))
                elif op == 10:
                    work.append((arg, sp, slots, []))
                    break
                elif op == 12:
                    break
                elif op == 13:
                    name = acts[arg] if 0 <= arg < len(acts) else "?"
                    sig = ACTIONS.get(name, (None, "", "-", 0, ""))[1]
                    parts = []
                    for i, a in enumerate(q):
                        k = sig[i] if i < len(sig) else "?"
                        if a[0] == "param":
                            kinds.setdefault(a[1], set()).add(k)
                            parts.append("%s:p%d" % (k, a[1]))
                        elif a[0] == "lit":
                            parts.append("%s:%s" % (k, _litname(v, k, a[1])))
                        else:
                            parts.append("%s:%s%d" % (k, a[0], a[1]))
                    notes.setdefault(ip, set()).add("(" + ", ".join(parts) + ")")
                    q = []
                ip = nxt
    return {k: " | ".join(sorted(x)) for k, x in notes.items()}, pkinds


def _litname(v, kind, val):
    if val is None:
        return "?"
    try:
        if kind == "S":
            return "%d=%s" % (val, v["sounds"][val])
        if kind == "E":
            return "%d=%s" % (val, v["entities"][val]["label"])
        if kind == "P":
            return "%d=%s" % (val, v["paths"][val]["name"])
    except (IndexError, TypeError):
        pass
    return str(val)


def disassemble(v, name=""):
    """Readable, re-assemblable text. `assemble(disassemble(v))` serialises to the same bytes."""
    L = ["; I'76 mission script %s" % name, "; syntax: data\\FSM.md. Re-assemble with data\\fmt\\fsm.py assemble()"]
    if v is None:
        L.append("empty")
        return "\n".join(L) + "\n"
    L.append("")
    L.append("section actions        ; ACTION operand -> name -> engine prototype (match_prototype 0x410a10)")
    for i, a in enumerate(v["actions"]):
        L.append("  %3d %s" % (i, _strtok(a)))
    L.append("section entities       ; label = placed-object instance name")
    for i, e in enumerate(v["entities"]):
        L.append("  %3d %s %s" % (i, _strtok(e["label"]), _strtok(e["instance"])))
    L.append("section sounds")
    for i, s in enumerate(v["sounds"]):
        L.append("  %3d %s" % (i, _strtok(s)))
    L.append("section paths")
    for i, p in enumerate(v["paths"]):
        L.append("  %3d %s %d" % (i, _strtok(p["name"]), p["n_nodes"]) + ("" if p["n_nodes"] == len(p["nodes"]) else " ;count mismatch"))
        for n in p["nodes"]:
            L.append("        %s %s %s" % (_ftok(n["x"]), _ftok(n["y"]), _ftok(n["z"])))
    L.append("section consts")
    for i, c in enumerate(v["consts"]):
        L.append("  %3d %d" % (i, c))
    # labels
    code = v["code"]
    targets = {}
    for m_i, m in enumerate(v["machines"]):
        targets.setdefault(m["start"], "m%d" % m_i)
    for ins in code:
        if ins["op"] in JUMPS and 0 <= ins["arg"] < len(code):
            targets.setdefault(ins["arg"], ("sub_%d" if ins["op"] == 11 else "L%d") % ins["arg"])
    try:
        notes, pkinds = annotate(v)
    except Exception as ex:  # noqa: BLE001  annotation is advisory; never block a dump
        notes, pkinds = {}, {}
        L.append("; (annotation failed: %s)" % ex)
    L.append("section machines       ; start label, n_args, arg slots (global-pool indices); pad = slots past n_args when non-zero")
    for i, m in enumerate(v["machines"]):
        args = m["args"][:m["n_args"]] if m["n_args"] <= 40 else m["args"]
        pad = m["args"][m["n_args"]:] if m["n_args"] <= 40 else []
        argtxt = " ".join("%d" % a for a in args)
        s = "  %3d %s %d [%s]" % (i, targets.get(m["start"], str(m["start"])), m["n_args"], argtxt)
        if any(pad):
            s += " pad=[%s]" % " ".join(str(x) for x in pad)
        # comment: resolved constant values
        vals = []
        for pi, a in enumerate(args):
            val = v["consts"][a] if 0 <= a < len(v["consts"]) else None
            ks = "".join(sorted(pkinds.get(i, {}).get(pi, set()) - {"?"}))
            txt = "p%d=g%d" % (pi, a)
            if val is not None:
                txt += "=" + (_litname(v, ks, val) if len(ks) == 1 else str(val))
            if ks:
                txt += "/" + ks
            vals.append(txt)
        s += "   ; " + ", ".join(vals)
        L.append(s)
    L.append("section code")
    for ip, ins in enumerate(code):
        if ip in targets:
            L.append("%s:" % targets[ip])
        op, arg = ins["op"], ins["arg"]
        mn = OPCODES.get(op, ("op%d" % op,))[0]
        if op == 13 and 0 <= arg < len(v["actions"]):
            txt = "action %s" % v["actions"][arg]
            if not str(v["actions"][arg]).replace("_", "").isalnum():
                txt = "action #%d" % arg
        elif op in JUMPS and arg in targets:
            txt = "%s %s" % (mn, targets[arg])
        elif op == 14:
            txt = "not" if arg == 0 else "not %d" % arg
        else:
            txt = "%s %d" % (mn, arg)
        L.append("  %-40s ; %d%s" % (txt, ip, ("  " + notes[ip]) if ip in notes else ""))
    return "\n".join(L) + "\n"


def _tokens(line):
    """Split a line into tokens honouring "quoted strings"; drop ; comments."""
    out, i, n = [], 0, len(line)
    while i < n:
        c = line[i]
        if c == ";":
            break
        if c.isspace():
            i += 1; continue
        if c == '"':
            j = i + 1; buf = []
            while line[j] != '"':
                if line[j] == "\\":
                    j += 1
                buf.append(line[j]); j += 1
            out.append(("s", "".join(buf))); i = j + 1
            continue
        j = i
        while j < n and not line[j].isspace() and line[j] != ";":
            j += 1
        out.append(("w", line[i:j])); i = j
    return out


def _mkstr(tok, rest, n):
    s = tok[1]
    for t in rest:
        if t[1].startswith("raw="):
            return StrV(bytes.fromhex(t[1][4:]))
    e = s.encode("latin1")
    if len(e) > n:
        raise ValueError("string %r longer than %d" % (s, n))
    return StrV(e.ljust(n, b"\0"))


def _mkfloat(w):
    if w.startswith("0x"):
        return FloatV(bytes.fromhex(w[2:])[::-1])
    return FloatV(struct.pack("<f", float(w)))


def assemble(text):
    """Inverse of disassemble(). Returns the FSM value (serialise() it for bytes)."""
    sec = None
    v = {"actions": [], "entities": [], "sounds": [], "paths": [], "machines": [], "consts": [], "code": []}
    labels, fix = {}, []
    lines = text.splitlines()
    empty = False
    for raw in lines:
        t = _tokens(raw)
        if not t:
            continue
        if t[0] == ("w", "empty"):
            empty = True; continue
        if t[0] == ("w", "section"):
            sec = t[1][1]; continue
        if sec == "actions":
            v["actions"].append(_mkstr(t[1], t[2:], 40))
        elif sec == "entities":
            # entity line: idx "label" [raw=] "inst" [raw=]
            toks = t[1:]
            strs = []
            k = 0
            while k < len(toks):
                if toks[k][0] == "s":
                    extra = [toks[k + 1]] if k + 1 < len(toks) and toks[k + 1][1].startswith("raw=") else []
                    strs.append((toks[k], extra)); k += 1 + len(extra)
                else:
                    k += 1
            v["entities"].append({"label": _mkstr(strs[0][0], strs[0][1], 40), "instance": _mkstr(strs[1][0], strs[1][1], 8)})
        elif sec == "sounds":
            v["sounds"].append(_mkstr(t[1], t[2:], 40))
        elif sec == "paths":
            if t[0][0] == "w" and t[0][1].isdigit() and len(t) >= 3 and t[1][0] == "s":
                extra = [x for x in t[2:] if x[1].startswith("raw=")]
                nums = [x for x in t[2:] if not x[1].startswith("raw=")]
                v["paths"].append({"name": _mkstr(t[1], extra, 40), "n_nodes": int(nums[0][1]), "nodes": []})
            else:
                x, y, z = (_mkfloat(w[1]) for w in t[:3])
                v["paths"][-1]["nodes"].append({"x": x, "y": y, "z": z})
        elif sec == "consts":
            v["consts"].append(int(t[1][1]))
        elif sec == "machines":
            start = t[1][1]; nargs = int(t[2][1])
            rest = " ".join(w for _, w in t[3:])
            a_txt = rest[rest.index("[") + 1:rest.index("]")]
            args = [int(x) for x in a_txt.split()]
            pad = []
            if "pad=[" in rest:
                p = rest[rest.index("pad=[") + 5:]
                pad = [int(x) for x in p[:p.index("]")].split()]
            full = args + pad
            full += [0] * (40 - len(full))
            m = {"start": start, "n_args": nargs, "args": full[:40]}
            v["machines"].append(m)
        elif sec == "code":
            if len(t) == 1 and t[0][1].endswith(":"):
                labels[t[0][1][:-1]] = len(v["code"]); continue
            mn = t[0][1]
            op = MNEM.get(mn) if not mn.startswith("op") else int(mn[2:])
            if mn == "not":
                arg = int(t[1][1]) if len(t) > 1 else 0
            elif mn == "action":
                a = t[1][1]
                if a.startswith("#"):
                    arg = int(a[1:])
                else:
                    names = [str(x) for x in v["actions"]]
                    arg = names.index(a)
            else:
                w = t[1][1]
                try:
                    arg = int(w)
                except ValueError:
                    arg = w; fix.append(len(v["code"]))
            v["code"].append({"op": op, "arg": arg})
    if empty:
        return None
    for i in fix:
        v["code"][i]["arg"] = labels[v["code"][i]["arg"]]
    for m in v["machines"]:
        if isinstance(m["start"], str):
            m["start"] = labels[m["start"]] if m["start"] in labels else int(m["start"])
    out = {}
    for k in ("actions", "entities", "sounds", "paths", "machines", "consts", "code"):
        cnt = {"actions": "n_actions", "entities": "n_entities", "sounds": "n_sounds", "paths": "n_paths",
               "machines": "n_machines", "consts": "n_consts", "code": "n_code"}[k]
        out[cnt] = len(v[k]); out[k] = v[k]
    return out
