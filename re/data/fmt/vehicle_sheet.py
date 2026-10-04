#!/usr/bin/env python3
r"""vehicle_sheet.py - every vehicle variant's stats, resolved through the same chain the game loads.

    python data\fmt\vehicle_sheet.py  -> data\vehicles.csv

Mass follows the loaders exactly (VEHICLES.md section 3): VDFC mass (0x4adf0d) + ENGN/BRAK/SUSP mass of the chosen
components (0x4b0dea / 0x4b0e3f / 0x4b0d86) + 2 x WDFC mass per non-null wheel slot (0x4ae8ec) + GDFC mass of
every weapon whose hardpoint exists (0x4af1b7). Engine id -> component row through engsnd.dat (0x469f10).
"""
import os, sys, csv
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bwd2x  # noqa: E402

MAP = os.path.dirname(os.path.dirname(HERE))
Z = os.path.join(MAP, "recon-2026-09-04", "recon", "formats", "zfs_out")


def load(name):
    p = os.path.join(Z, name.lower())
    if not os.path.exists(p):
        return None
    return bwd2x.decode(open(p, "rb").read(), os.path.splitext(p)[1])


def first(doc, tag):
    h = bwd2x.chunks(doc, tag)
    return h[0][2].value if h else None


def all_(doc, tag):
    return [i.value for _, _, i in bwd2x.chunks(doc, tag)]


def engsnd():
    m = {}
    for ln in open(os.path.join(Z, "engsnd.dat"), encoding="latin1"):
        t = ln.split()
        if t and not t[0].startswith("#"):
            m[int(t[0])] = int(t[1])
    return m


def main():
    es = engsnd()
    cdf = load("compnent.cdf")
    engn, brak, susp = all_(cdf, "ENGN"), all_(cdf, "BRAK"), all_(cdf, "SUSP")
    ntbl = first(cdf, "NTBL")["names"]; btbl = first(cdf, "BTBL")["names"]; stbl = first(cdf, "STBL")["names"]
    rows = []
    for fn in sorted(f for f in os.listdir(Z) if f.endswith(".vcf")):
        d = load(fn)
        v = first(d, "VCFC")
        vdf = load(v["vdf"]) if str(v["vdf"]).lower() != "null" else None
        vd = first(vdf, "VDFC") if vdf else None
        hl = {h["index"] for h in all_(vdf, "HLOC")} if vdf else set()
        comp = es.get(v["engine_id"], -1)
        mass = float(vd["mass"]) if vd else 0.0
        notes = []
        if 0 <= comp < len(engn):
            mass += float(engn[comp]["mass"])
        else:
            notes.append("engine id %d not in engsnd.dat" % v["engine_id"])
        if v["brake_id"] < len(brak):
            mass += float(brak[v["brake_id"]]["mass"])
        if v["suspension_id"] < len(susp):
            mass += float(susp[v["suspension_id"]]["mass"])
        wheels = []
        for slot in ("wdf_front", "wdf_mid", "wdf_rear"):
            w = str(v[slot])
            if w.lower() != "null":
                wd = load(w)
                if wd:
                    mass += 2 * float(first(wd, "WDFC")["mass"])
                wheels.append(w)
        weps = []
        for wp in all_(d, "WEPN"):
            g = str(wp["gdf"])
            if g.lower() == "null":
                continue
            gd = load(g)
            gc = first(gd, "GDFC") if gd else None
            if wp["hardpoint"] in hl and gc:
                mass += float(gc["mass"])
                weps.append("%d:%s" % (wp["hardpoint"], gc["name"]))
            else:
                weps.append("%d:%s(unmounted)" % (wp["hardpoint"], g))
        specs = [str(s["special_id"]) for s in all_(d, "SPEC")]
        size = vd["size"] if vd else 0
        total = sum(v["armour"]) + sum(v["chassis"]) + v["spare"]
        rows.append({
            "file": fn, "variant": str(v["variant"]), "vehicle": str(vd["name"]) if vd else "", "vdf": str(v["vdf"]), "class": vd["class_id"] if vd else "",
            "size": size, "mass_total": round(mass, 1), "vdf_mass": float(vd["mass"]) if vd else "", "drag": float(vd["drag"]) if vd else "",
            "engine": str(ntbl[comp]) if 0 <= comp < 64 else "?", "engine_power": float(engn[comp]["power"]) if 0 <= comp < len(engn) else "",
            "brakes": str(btbl[v["brake_id"]]) if v["brake_id"] < 64 else "?", "suspension": str(stbl[v["suspension_id"]]) if v["suspension_id"] < 64 else "?",
            "armour_FLRB": "/".join(str(x) for x in v["armour"]), "chassis_FLRB": "/".join(str(x) for x in v["chassis"]), "spare": v["spare"],
            "points_total": total, "mp_legal_budget": "yes" if size and total == 1600 * {6: 10, 5: 4}.get(size, size) else "no",
            "hardpoints": vd["hardpoint_count"] if vd else "", "weapons": " ".join(weps), "specials": " ".join(specs), "wheels": " ".join(wheels),
            "notes": "; ".join(notes)})
    out = os.path.join(MAP, "data", "vehicles.csv")
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    print("wrote %s (%d variants)" % (out, len(rows)))


if __name__ == "__main__":
    main()
