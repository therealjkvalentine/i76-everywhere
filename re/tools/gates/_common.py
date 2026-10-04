"""Shared loader for the gate executables in tools\\gates\\ (Task 8).

Every gate is `python tools\\gates\\gateX.py [--map M] [--batch b.json] [--json]` and exits 0 (pass) or 1 (fail, with
one message per failing row on stdout, prefixed `FAIL <gate>`), 2 on a usage/IO error. With --batch the gate
checks the rows of that merge batch (tools\\merge.py format) against the map; without it the gate audits what is
already in the map (symbols\\*.tsv, evidence\\E*.json, types\\i76.h, status\\*.json). Gates never write.
"""
import os, sys, json, glob, argparse

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
DEFAULT_MAP = os.path.dirname(TOOLS)

from merge import read_tsv, FUNC_COLS, GLOB_COLS, PRISTINE_MD5, parse_addr, Reject  # noqa: E402
from gen_tables import Image, hx  # noqa: E402

TABLE_COLS = ["name", "base", "class", "end", "count", "stride", "ptr_off", "kind", "method", "source_sites", "targets", "note"]
IMPORT_COLS = ["iat_slot", "dll", "name", "call_sites", "load_sites", "ghidra_refs", "functions", "jmp_sites", "jmp_site_list",
               "thunk_caller_sites", "thunk_caller_functions", "ghidra_total_call_sites", "ghidra_functions", "call_site_list",
               "load_site_list", "gap_sites"]
REGION_COLS = ["start", "end", "size", "kind", "name"]


class Ctx:
    def __init__(self, gate, args):
        self.gate = gate
        self.M = args.map
        self.batch = json.load(open(args.batch, encoding="utf-8")) if args.batch else None
        self.batch_path = args.batch
        self.json_out = args.json
        self.fails = []
        self.notes = []
        self._img = None
        self._dis = None
        self._funcs = None
        self._globs = None
        self._evidence = None

    def fail(self, msg):
        self.fails.append(msg)

    def note(self, msg):
        self.notes.append(msg)

    def path(self, *p):
        return os.path.join(self.M, *p)

    @property
    def img(self):
        if self._img is None:
            exe = self.path("ghidra", "i76_ref.exe")
            self._img = Image(exe)
            if self._img.md5 != PRISTINE_MD5:
                raise SystemExit("REFUSE: %s md5 %s is not the pristine %s (H0)" % (exe, self._img.md5, PRISTINE_MD5))
        return self._img

    @property
    def dis(self):
        if self._dis is None:
            from merge import Disasm
            self._dis = Disasm(self.img)
        return self._dis

    @property
    def functions(self):
        if self._funcs is None:
            self._funcs = read_tsv(self.path("symbols", "functions.tsv"), FUNC_COLS)[1]
        return self._funcs

    @property
    def globals(self):
        if self._globs is None:
            self._globs = read_tsv(self.path("symbols", "globals.tsv"), GLOB_COLS)[1]
        return self._globs

    def tsv(self, name, cols):
        return read_tsv(self.path("symbols", name), cols)[1]

    @property
    def evidence(self):
        """{id: dict} for every evidence\\E*.json."""
        if self._evidence is None:
            self._evidence = {}
            for p in glob.glob(self.path("evidence", "E*.json")):
                try:
                    e = json.load(open(p, encoding="utf-8"))
                    self._evidence[e.get("id") or os.path.basename(p)[:-5]] = e
                except Exception as ex:
                    self.fail("evidence file %s does not parse: %s" % (p, ex))
        return self._evidence

    def row_evidence(self, row):
        """Evidence dicts for a TSV row (from evidence_ids) or a batch row (inline)."""
        if "evidence" in row:
            return row["evidence"]
        ids = [x for x in (row.get("evidence_ids") or "").split(";") if x]
        return [self.evidence[i] for i in ids if i in self.evidence]

    def batch_rows(self, kind):
        return list((self.batch or {}).get(kind, []))

    def finish(self):
        out = {"gate": self.gate, "map": self.M, "batch": self.batch_path, "fails": self.fails, "notes": self.notes,
               "verdict": "PASS" if not self.fails else "FAIL"}
        if self.json_out:
            print(json.dumps(out, indent=1))
        else:
            for n in self.notes:
                print("note %s: %s" % (self.gate, n))
            for f in self.fails:
                print("FAIL %s: %s" % (self.gate, f))
            print("%s %s (%d failures, %d notes)" % (self.gate, out["verdict"], len(self.fails), len(self.notes)))
        return 0 if not self.fails else 1


def make(gate, doc=None, extra=None):
    ap = argparse.ArgumentParser(description=doc)
    ap.add_argument("--map", default=DEFAULT_MAP)
    ap.add_argument("--batch", default=None, help="merge batch JSON to check (default: audit the map)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    if extra:
        extra(ap)
    args = ap.parse_args()
    return Ctx(gate, args), args
