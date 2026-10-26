#!/usr/bin/env python3
"""Gate P (ported names; method doc 4.3; FOLDIN-REPORT section 3 fast path). Any name, type or address from Roanish,
That Tony, Peelar, VOGONS, i76fix, UCyborg or the user's earlier notes enters as `proposed` with `source_instance`
and counts as one instance under H6; it reaches `supported` only with a GOG-side anchor (string xref, unique
constant, table entry, capture, a Version Tracking match with a stated score and no implied-match propagation, or
the `ported-static` fast path below).

Fast path `ported-static` (FOLDIN-REPORT section 3): a ported static claim whose quoted bytes match the pristine
file (merge.gate_p_static: bytes_at at `addr` for init/text, or the referencing instruction at `site` for bss) is
`supported` on entry for the ADDRESS; semantics stay proposed (the evidence carries `semantics: proposed`).
Inside an aio-60abf7bc .text patch cluster (merge.PATCH_CLUSTERS + binaries\\diff-9a232dcc-vs-60abf7bc.tsv) the
item is tagged `build_shifted`; an instruction-level row (kind `site`) inside a cluster does not get the fast path.

G-BUILD-TAG: every ported / ported-static evidence item and every `ported` batch row carries `build_tag` from
merge.BUILD_TAGS. G0: ported evidence carries the source's own row text verbatim as `quote` (data, never a reason).

Checks (batch or map): every `ported` evidence item carries source_instance, source, quote and build_tag; a row
whose only evidence is ported (or ported + vt-match without score) stays `proposed`; a `vt-match` item carries
`score` and `implied: false`; foldin\\*.md claims referenced by evidence exist; every `ported-static` item passes
the byte match. Map audit additionally checks symbols\\ported.tsv rows with `ledger=` notes carry `build=`.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import make, Reject

GOG_ANCHORS = {"string-xref", "constant-anchor", "table-entry", "dynamic-capture", "import-callee", "import-thunk",
               "import-wrapper", "emulated-io", "callback-pointer", "pe-entry", "ported-static"}


def check_row(ctx, r, evs, clusters, row_kind):
    from merge import gate_p_static, gate_build_tag
    ported = [e for e in evs if e.get("kind") == "ported"]
    vt = [e for e in evs if e.get("kind") == "vt-match"]
    static = [e for e in evs if e.get("kind") == "ported-static"]
    if not ported and not vt and not static:
        return False
    for e in ported:
        if not e.get("source_instance") or not e.get("source"):
            raise Reject("ported evidence without source_instance/source")
        if not e.get("quote"):
            raise Reject("ported evidence without the source's verbatim row text (`quote`, G0)")
        gate_build_tag(e, "ported evidence")
        fi = e.get("foldin")
        if fi and not os.path.exists(ctx.path("foldin", fi)):
            raise Reject("ported evidence cites foldin/%s which does not exist" % fi)
    for e in vt:
        if e.get("score") is None or e.get("implied", True) is not False:
            raise Reject("vt-match needs score and implied: false (no implied-match propagation)")
    for e in static:
        gate_p_static(ctx.img, ctx.dis, dict(e), clusters, row_kind)  # re-verify on a copy: the gate never writes
        if e.get("semantics", "proposed") != "proposed":
            raise Reject("ported-static anchors the address only; semantics must stay proposed")
    anchors = {e["kind"] for e in evs if e.get("kind") in GOG_ANCHORS and not (e["kind"] == "constant-anchor" and not e.get("unique"))}
    if r.get("status") not in ("proposed", "auto", "finding", "request", "note") and not anchors:
        raise Reject("status %s with only ported/vt evidence and no GOG-side anchor" % r.get("status"))
    return True


def main():
    ctx, args = make("gateP", __doc__)
    from merge import load_patch_clusters, PORTED_COLS, read_tsv
    clusters = load_patch_clusters(ctx.M)
    n = 0
    rows = (ctx.batch_rows("functions") + ctx.batch_rows("globals")) if ctx.batch else (ctx.functions + ctx.globals)
    for r in rows:
        try:
            if check_row(ctx, r, ctx.row_evidence(r), clusters, "function" if "class" not in r else "global"):
                n += 1
        except Reject as ex:
            ctx.fail("%s %s: %s" % (r.get("addr"), r.get("name"), ex))
        except Exception as ex:
            ctx.fail("%s %s: %s" % (r.get("addr"), r.get("name"), ex))
    # the `ported` batch section (merge.apply_ported): rows that enter symbols\ported.tsv, never functions/globals directly
    np_ = 0
    for r in ctx.batch_rows("ported") if ctx.batch else []:
        np_ += 1
        try:
            from merge import gate_build_tag
            gate_build_tag(r, "ported row %s" % r.get("ledger_id"))
            if not r.get("quote"):
                raise Reject("ported row without verbatim quote (G0)")
            if r.get("entry") not in ("ported-static", "proposed", "finding", "build-shifted", "request", "note"):
                raise Reject("ported row entry %r not in the gate-P vocabulary" % r.get("entry"))
            rr = dict(r); rr["status"] = "supported" if r.get("entry") == "ported-static" else "proposed"
            check_row(ctx, rr, r.get("evidence", []), clusters, r.get("kind", "function"))
            if r.get("entry") == "ported-static" and not any(e.get("kind") == "ported-static" for e in r.get("evidence", [])):
                raise Reject("entry ported-static without a ported-static evidence item")
        except Reject as ex:
            ctx.fail("ported %s %s: %s" % (r.get("ledger_id"), r.get("addr"), ex))
        except Exception as ex:
            ctx.fail("ported %s %s: %s" % (r.get("ledger_id"), r.get("addr"), ex))
    if not ctx.batch:
        _, prow = read_tsv(ctx.path("symbols", "ported.tsv"), PORTED_COLS)
        miss = [p for p in prow if "ledger=" in (p.get("note") or "") and "build=" not in p["note"]]
        for p in miss:
            ctx.fail("ported.tsv %s %s: ledger row without build= tag (G-BUILD-TAG)" % (p.get("addr"), p.get("name")))
        ctx.note("ported.tsv: %d rows, %d ledger rows" % (len(prow), sum(1 for p in prow if "ledger=" in (p.get("note") or ""))))
    ctx.note("checked %d rows carrying ported / vt-match / ported-static evidence, %d ported batch rows, %d patch clusters" % (n, np_, len(clusters)))
    return ctx.finish()


if __name__ == "__main__":
    sys.exit(main())
