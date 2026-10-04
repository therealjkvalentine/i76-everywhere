"""t5b_port.py - Task 5b: turn Version Tracking results + Roanish's nitro items + That Tony's CD-era FSM addresses
into `proposed` rows of symbols/ported.tsv (gate P). Never touches functions.tsv / globals.tsv.

Inputs (all under C:/Users/james/i76-map):
  status/vt-nitro.json, status/vt-cd1997.json      RunVT_T5b.java output (accepted matches, per correlator)
  status/t5b/roanish-items.tsv                     t5b_roanish_parse.py output (nitro VAs + names)
  foldin/community/roanish-port-table.tsv          the earlier masked-signature route nitro->i76 (independent route)
  symbols/functions.tsv, symbols/globals.tsv       the current map (to report the name already at the target, gate N)
Output: symbols/ported.tsv, status/t5b/port-summary.json
Address classes: i76 (ref) VA: text 0x401000-0x4bbe55, rdata 0x4bc000-0x4c1788, init 0x4c2000-0x501800, bss 0x501800-0x669ef8.
"""
import json, io, csv, os, sys
ROOT = "C:/Users/james/i76-map"
REF_MD5 = "9a232dcc2c164648cff20c414c1f9698"
def i76cls(va):
    if 0x401000 <= va < 0x4bbe55: return "text"
    if 0x4bc000 <= va < 0x4c1788: return "rdata"
    if 0x4c2000 <= va < 0x501800: return "init"
    if 0x501800 <= va < 0x669ef8: return "bss"
    return "outside"

def load_vt(path):
    """returns dict dst_va -> (src_va, correlator, sim, conf, type) for accepted rows; plus per-correlator stats"""
    j = json.load(io.open(path, encoding="utf-8"))
    acc = {}; stats = []
    for c in j["correlators"]:
        stats.append({k: c[k] for k in ("correlator", "matches", "accepted", "below_threshold", "related_accepted_skipped", "not_applicable", "seconds")})
        for r in c["rows"]:
            if r["verdict"] == "accepted":
                acc[int(r["dst"], 16)] = (int(r["src"], 16), c["correlator"], r["similarity"], r["confidence"], r["type"], r.get("src_name", ""))
    return j, acc, stats

def load_tsv(path):
    rows = []
    with io.open(path, encoding="utf-8") as f:
        hdr = None
        for line in f:
            if line.startswith("#") or not line.strip(): continue
            cells = line.rstrip("\n").split("\t")
            if hdr is None: hdr = cells; continue
            rows.append(dict(zip(hdr, cells)))
    return rows

def main():
    out_rows = []
    summary = {"ref_md5": REF_MD5}
    existing_f = {int(r["addr"], 16): r for r in load_tsv(ROOT + "/symbols/functions.tsv")}
    existing_g = {int(r["addr"], 16): r for r in load_tsv(ROOT + "/symbols/globals.tsv")}
    sig = {}
    for r in load_tsv(ROOT + "/foldin/community/roanish-port-table.tsv"):
        if r["status"] == "unique" and r["i76_va_text"]: sig[int(r["nitro_va"], 16)] = int(r["i76_va_text"], 16)

    # ---- Roanish (nitro) ----
    jn, accN, statsN = load_vt(ROOT + "/status/vt-nitro.json")
    summary["vt_nitro"] = {"stats": statsN, "accepted_function": jn["accepted_function_associations"], "accepted_data": jn["accepted_data_associations"],
                           "src_functions": jn["source_functions"], "dst_functions": jn["destination_functions"]}
    items = load_tsv(ROOT + "/status/t5b/roanish-items.tsv")
    n_named = n_vt = n_sig = n_agree = n_disagree = n_vt_only = n_sig_only = n_none = 0
    for it in items:
        if not it["name"] or it["kind"] == "global": continue  # globals are handled by the operand-alignment block below
        nva = int(it["nitro_va"], 16)
        n_named += 1
        vt = accN.get(nva); s = sig.get(nva)
        if vt: n_vt += 1
        if s: n_sig += 1
        if vt and s:
            if vt[0] == s: n_agree += 1
            else: n_disagree += 1
        elif vt: n_vt_only += 1
        elif s: n_sig_only += 1
        else: n_none += 1
        if vt:
            src, corr, sim, conf, typ, srcname = vt
            ex = existing_f.get(src) if it["kind"] == "function" else existing_g.get(src)
            out_rows.append({
                "addr": "0x%06x" % src, "class": i76cls(src), "kind": it["kind"], "name": it["name"], "status": "proposed",
                "source_instance": "roanish:nitro_28b8ae27:0x%06x" % nva, "source_status": it["roanish_status"],
                "vt_session": "vt-nitro", "vt_correlator": corr, "vt_similarity": "%.4f" % sim, "vt_confidence": "%.3f" % conf,
                "sig_route": ("agree" if s == src else ("disagree:0x%06x" % s)) if s else "none",
                "existing_name": (ex["name"] if ex else ""), "existing_status": (ex["status"] if ex else ""),
                "note": "doc_line=%s" % it["doc_line"]})
        elif s:
            out_rows.append({
                "addr": "0x%06x" % s, "class": i76cls(s), "kind": it["kind"], "name": it["name"], "status": "proposed",
                "source_instance": "roanish:nitro_28b8ae27:0x%06x" % nva, "source_status": it["roanish_status"],
                "vt_session": "vt-nitro", "vt_correlator": "none", "vt_similarity": "", "vt_confidence": "",
                "sig_route": "sig-only", "existing_name": (existing_f.get(s, {}).get("name", "")), "existing_status": (existing_f.get(s, {}).get("status", "")),
                "note": "signature route only (foldin/community/roanish-port-table.tsv); no VT match; doc_line=%s" % it["doc_line"]})
        else:
            out_rows.append({
                "addr": "", "class": "", "kind": it["kind"], "name": it["name"], "status": "unported",
                "source_instance": "roanish:nitro_28b8ae27:0x%06x" % nva, "source_status": it["roanish_status"],
                "vt_session": "vt-nitro", "vt_correlator": "none", "vt_similarity": "", "vt_confidence": "",
                "sig_route": "none", "existing_name": "", "existing_status": "", "note": "no VT match and no signature match; doc_line=%s" % it["doc_line"]})
    summary["roanish"] = {"named_items": n_named, "vt_matched": n_vt, "sig_matched": n_sig, "both_agree": n_agree, "both_disagree": n_disagree,
                          "vt_only": n_vt_only, "sig_only": n_sig_only, "neither": n_none}

    # ---- Roanish globals by operand alignment (tools/t5b_globals.py) ----
    gp = ROOT + "/status/t5b/globals-port.tsv"
    ng = ng_ported = 0
    if os.path.exists(gp):
        for r in load_tsv(gp):
            ng += 1
            nva = int(r["nitro_va"], 16)
            if r["ref_va"]:
                tgt = int(r["ref_va"], 16); ex = existing_g.get(tgt); ng_ported += 1
                out_rows.append({"addr": "0x%06x" % tgt, "class": i76cls(tgt), "kind": "global", "name": r["name"], "status": "proposed",
                    "source_instance": "roanish:nitro_28b8ae27:0x%06x" % nva, "source_status": "",
                    "vt_session": "vt-nitro", "vt_correlator": "operand-alignment", "vt_similarity": "", "vt_confidence": "",
                    "sig_route": "n_sites=%s;n_funcs=%s" % (r["n_sites"], r["n_funcs"]), "existing_name": ex["name"] if ex else "", "existing_status": ex["status"] if ex else "",
                    "note": r["method"]})
            else:
                out_rows.append({"addr": "", "class": "", "kind": "global", "name": r["name"], "status": "unported",
                    "source_instance": "roanish:nitro_28b8ae27:0x%06x" % nva, "source_status": "", "vt_session": "vt-nitro", "vt_correlator": "none",
                    "vt_similarity": "", "vt_confidence": "", "sig_route": r["candidates"], "existing_name": "", "existing_status": "", "note": r["method"]})
    summary["roanish_globals"] = {"items": ng, "ported": ng_ported}

    # ---- That Tony (CD 1997) ----
    jc, accC, statsC = load_vt(ROOT + "/status/vt-cd1997.json")
    summary["vt_cd1997"] = {"stats": statsC, "accepted_function": jc["accepted_function_associations"], "accepted_data": jc["accepted_data_associations"],
                            "src_functions": jc["source_functions"], "dst_functions": jc["destination_functions"]}
    tony = [(0x40EBB0, "fsm_opcode_switch", "string 'Unknown fsm assembler instuction' referenced at cd1997 0x40ec06; GOG by string xref: 0x414670"),
            (0x40D0D0, "fsm_action_dispatch", "string 'Uknown fsm prototype - %s' at cd1997 0x40d0fa after the 96-case switch; GOG by string xref: 0x412ce0"),
            (0x40BF40, "match_prototype", "string 'Uknown FSM prototype in match_prototype: %s' at cd1997 0x40c85d; GOG by string xref: 0x410a10")]
    string_route = {0x40EBB0: 0x414670, 0x40D0D0: 0x412ce0, 0x40BF40: 0x410a10}
    tony_rows = []
    for cva, name, note in tony:
        vt = accC.get(cva)
        tgt = vt[0] if vt else string_route[cva]
        ex = existing_f.get(tgt)
        row = {"addr": "0x%06x" % tgt, "class": i76cls(tgt), "kind": "function", "name": name, "status": "proposed",
               "source_instance": "thattony:cd1997_6cc509ad:0x%06X" % cva, "source_status": "published",
               "vt_session": "vt-cd1997", "vt_correlator": vt[1] if vt else "none", "vt_similarity": ("%.4f" % vt[2]) if vt else "", "vt_confidence": ("%.3f" % vt[3]) if vt else "",
               "sig_route": ("string-xref:agree" if (vt and vt[0] == string_route[cva]) else ("string-xref:disagree:0x%06x" % string_route[cva] if vt else "string-xref-only")),
               "existing_name": ex["name"] if ex else "", "existing_status": ex["status"] if ex else "", "note": note}
        out_rows.append(row); tony_rows.append(row)
    summary["thattony"] = tony_rows

    cols = ["addr", "class", "kind", "name", "status", "source_instance", "source_status", "vt_session", "vt_correlator", "vt_similarity", "vt_confidence", "sig_route", "existing_name", "existing_status", "note"]
    path = ROOT + "/symbols/ported.tsv"
    with io.open(path + ".tmp", "w", encoding="utf-8", newline="\n") as f:
        f.write("# ported.tsv - gate P: names ported from other people's work enter as `proposed` with source_instance and a Version Tracking score; never copied into functions.tsv/globals.tsv by this file.\n")
        f.write("# addr = i76 reference VA (md5 %s); class per section (text/rdata/init/bss). vt_* from status/vt-<name>.json (RunVT_T5b.java: exact bytes/instructions/mnemonics accept all 1:1; reference correlators accept similarity>=0.95 & confidence>=10; no implied matches).\n" % REF_MD5)
        f.write("# sig_route = agreement with the independent masked-prologue signature route (foldin/community/roanish-port-table.tsv) or, for That Tony, with the GOG string-xref route. status=unported rows have no target here and are kept so the miss is on record.\n")
        f.write("\t".join(cols) + "\n")
        for r in out_rows: f.write("\t".join(r.get(c, "") for c in cols) + "\n")
    os.replace(path + ".tmp", path)
    back = load_tsv(path)
    assert len(back) == len(out_rows), (len(back), len(out_rows))
    summary["ported_rows"] = len(out_rows)
    summary["ported_proposed"] = sum(1 for r in out_rows if r["status"] == "proposed")
    json.dump(summary, io.open(ROOT + "/status/t5b/port-summary.json", "w", encoding="utf-8"), indent=1)
    print(json.dumps({k: v for k, v in summary.items() if k not in ("vt_nitro", "vt_cd1997")}, indent=1))
    print("wrote", path, "rows", len(out_rows), "(read back", len(back), ")")

if __name__ == "__main__":
    main()
