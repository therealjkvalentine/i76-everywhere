#!/usr/bin/env python3
r"""fsmtool.py - mission script disassembler / assembler.

    python data\fmt\fsmtool.py dis <mission.msn> [out.fsm]         script -> text
    python data\fmt\fsmtool.py asm <script.fsm> <in.msn> <out.msn>  text -> script, spliced into a copy of in.msn
    python data\fmt\fsmtool.py dumpall [--out data\out\fsm]         every mission in the corpus
asm refuses to write inside a game folder; outputs belong in data\out.
"""
import os, sys, glob
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bwd2x, fsm  # noqa: E402

MAP = os.path.dirname(os.path.dirname(HERE))
MISSIONS = os.path.join(MAP, "sandbox-gog", "main", "app", "miss16")
GAME_DIRS = [r"C:\Users\james\i76-uncap-lab\game", r"C:\Users\james\i76-bisect\game", os.path.join(MAP, "sandbox-gog"),
             os.path.expanduser(r"~\Downloads")]


def refuse_game_path(p):
    ap = os.path.abspath(p).lower()
    for g in GAME_DIRS:
        if ap.startswith(os.path.abspath(g).lower()):
            raise SystemExit("REFUSE: %s is inside a game folder (%s); write to data/out" % (p, g))


def fsm_chunk(doc):
    hits = bwd2x.chunks(doc, "FSM", "ADEF")
    if not hits:
        raise SystemExit("no ADEF/FSM chunk")
    return hits[0]


def dis(path):
    doc = bwd2x.decode(open(path, "rb").read(), os.path.splitext(path)[1])
    _, c, info = fsm_chunk(doc)
    return fsm.disassemble(info.value, os.path.basename(path))


def asm(text_path, msn_in, msn_out):
    refuse_game_path(msn_out)
    data = open(msn_in, "rb").read()
    doc = bwd2x.decode(data, os.path.splitext(msn_in)[1])
    _, c, info = fsm_chunk(doc)
    info.value = fsm.assemble(open(text_path, encoding="latin1").read())
    out = bwd2x.encode(doc)
    os.makedirs(os.path.dirname(os.path.abspath(msn_out)), exist_ok=True)
    open(msn_out, "wb").write(out)
    back = open(msn_out, "rb").read()
    assert back == out, "readback mismatch"
    doc2 = bwd2x.decode(back, ".msn")
    assert fsm.serialise(fsm_chunk(doc2)[2].value) == fsm.serialise(info.value)
    return len(out)


def main(argv):
    if len(argv) >= 2 and argv[1] == "dis":
        t = dis(argv[2])
        if len(argv) > 3:
            refuse_game_path(argv[3]); open(argv[3], "w", encoding="latin1").write(t)
        else:
            sys.stdout.write(t)
    elif len(argv) >= 5 and argv[1] == "asm":
        n = asm(argv[2], argv[3], argv[4]); print("wrote %s (%d bytes, read back ok)" % (argv[4], n))
    elif len(argv) >= 2 and argv[1] == "dumpall":
        out = argv[argv.index("--out") + 1] if "--out" in argv else os.path.join(MAP, "data", "out", "fsm")
        os.makedirs(out, exist_ok=True)
        n = 0
        for p in sorted(glob.glob(os.path.join(MISSIONS, "*.MSN"))):
            t = dis(p)
            open(os.path.join(out, os.path.splitext(os.path.basename(p))[0].lower() + ".fsm"), "w", encoding="latin1", newline="\n").write(t)
            n += 1
        print("dumped %d mission scripts to %s" % (n, out))
    else:
        print(__doc__); return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
