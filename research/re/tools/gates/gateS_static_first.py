#!/usr/bin/env python3
"""Gate S (static-first requests; method doc 4.3). Every requests\\dynamic-*.yaml item is checked against the
export and the refute corpus before it may cost a console sitting.

Checks every item in requests\\dynamic-*.yaml (and every `dynamic_request` in a --batch row's evidence or a
proposal): the item carries `static_check:` naming the export files consulted and what they could not settle,
an `owner`, a `blocker` sentence (H7) and a canary; it is not about an already-settled fact:
  - the sim clock (0x49c7f0 / 0x49c920; dt = delta(GetTickCount) * 0.001 clamped [0.001, 0.2] in 0x4fe428),
  - the renderer slots 0x608ba4-0x608be4 (18 names),
  - the plugin ABI convention (cdecl),
  - the LZO identity (emulated, 5,623 entries).
"""
import os, sys, glob, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import make, parse_addr
import yaml

SETTLED = {
    "sim clock": [0x49c7f0, 0x49c920, 0x4fe428],
    "renderer slots": list(range(0x608ba4, 0x608be8, 4)),
    "LZO decoders": [0x4babd8, 0x4baa00, 0x4b9fc0],
}
SETTLED_WORDS = re.compile(r"\b(sim ?clock|GetTickCount delta|renderer slot|plugin ABI|plugin convention|LZO identity|lzo1[xy]_decompress)\b", re.I)


def check_item(ctx, it, where):
    if not isinstance(it, dict):
        ctx.fail("%s: item is not a mapping" % where); return
    for k in ("id", "what", "static_check", "owner", "blocker"):
        if not it.get(k):
            ctx.fail("%s: missing %s" % (where, k))
    sc = it.get("static_check") or {}
    if isinstance(sc, dict):
        if not sc.get("export_files") or not sc.get("unsettled"):
            ctx.fail("%s: static_check needs export_files (what was read) and unsettled (what static reading could not settle)" % where)
    elif isinstance(sc, str) and len(sc) < 20:
        ctx.fail("%s: static_check too short to name the export files consulted" % where)
    text = " ".join(str(it.get(k, "")) for k in ("what", "why", "break_on", "log"))
    if SETTLED_WORDS.search(text):
        ctx.fail("%s: asks about a settled fact (%s); gate S forbids it" % (where, SETTLED_WORDS.search(text).group(0)))
    for a in re.findall(r"0x[0-9a-fA-F]{5,8}", text):
        v = parse_addr(a)
        for name, addrs in SETTLED.items():
            if v in addrs:
                ctx.fail("%s: address %s belongs to the settled %s" % (where, a, name))
    if not it.get("canary"):
        ctx.note("%s: no canary named (H4 requires one per state)" % where)


def main():
    ctx, args = make("gateS", __doc__)
    n = 0
    for p in sorted(glob.glob(ctx.path("requests", "dynamic-*.yaml"))):
        try:
            d = yaml.safe_load(open(p, encoding="utf-8")) or {}
        except yaml.YAMLError as ex:
            ctx.fail("%s does not parse: %s" % (p, ex)); continue
        items = d.get("items") if isinstance(d, dict) else d
        for i, it in enumerate(items or []):
            n += 1
            check_item(ctx, it, "%s[%d]" % (os.path.basename(p), i))
    if ctx.batch:
        for r in ctx.batch_rows("functions"):
            dr = r.get("dynamic_request")
            if dr and dr != "~":
                n += 1
                check_item(ctx, dr if isinstance(dr, dict) else {"what": str(dr)}, "batch %s dynamic_request" % r.get("addr"))
    ctx.note("checked %d dynamic request items" % n)
    return ctx.finish()


if __name__ == "__main__":
    sys.exit(main())
