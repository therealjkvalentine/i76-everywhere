#!/usr/bin/env python3
"""Game-as-oracle calibration saves: bookmarks that make the game itself answer the save-format
questions the editor still cannot (docs/EDITOR-FIELD-TESTS.md). Built on i76-save-editor.py's
frame (PartNode + PartRec, section C rebuilt from the state-3 records), so every edit lands on
the record it names - the 2026-07 calibration saves wrote condition and location one record
late and their results are void.

Writes into a STAGING folder, never into the game directory:

  i76-calibration-saves.py --game GAMEDIR --staging OUTDIR [--base saveNNN] [--scene N]

  GAMEDIR   the save set to build on (read-only): savegame.dir + the base bookmark.
            Default base = save003 (the Leg-B-verified garage bookmark, scene 5 / state 8),
            else the first state-8 record.
  OUTDIR    receives saveNNN.cmp for every probe, a savegame.dir that is GAMEDIR's directory
            with the probe records appended (the game's records are copied byte for byte;
            never shorter), and CAL-MANIFEST.md: slot, LOAD-board row, what to screenshot,
            expected reading. The integrator copies OUTDIR\\* into the sandbox game folder and
            loads each probe with autotest\\saves\\leg-b.ps1 -WantFile saveNNN -WantRow k.

Probes (all are state-8 garage bookmarks of the base scene, so they open on the garage):
  CAL COLOR      seven turret-class guns (unmountable on the Piranha, so they stay (V)) in the
                 van at 10/25/40/55/70/85/100 % condition - the van pane's highlight per row
                 gives the colour thresholds (the shell grades cond/full in thirds:
                 PartNode_DamageLevel, fmul 1/3).
  CAL V VS S     a unique "Howitzer" at state 2 and a unique "HADES Turret" at state 4 -
                 which pane shows which pins state 2 = van (V), 4 = field salvage (S).
  CAL BENCH 15   fifteen parts queued for repair (state 3 + section C) - the bench's cap.
  CAL SUSP 4     four distinct suspensions in the van (Stock / Sway Bars / Coil Overs /
                 EtherX Rally) - does the van list all four?
  CAL PAINT BLUE vtf piranha1 -> piranha2.vtf - is the car blue/white? LOAD text unchanged?
  CAL JAMMER     Special 3 becomes "Radar Jammer" / spc01 (equipped name, mounted record and
                 Mr. Damage registry entry) - what does the HUD/panel call it, does it do anything?
  CAL LABEL 7 / CAL LABEL 7+1  two byte-identical copies of the base with blank names, scene 7,
                 state 8 and state 1 - the LOAD board's default "SCENE N." label vs the dword.
"""
import argparse, hashlib, importlib.util, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("i76_save_editor", os.path.join(HERE, "i76-save-editor.py"))
ed = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(ed)

TURRETS = [  # (name, cls, def, full, wt, pct) - full/wt from the game's own gdf files (offset 76 = maxHP)
    ("30cal Turret", "slg01", "tmlight.gdf",  200,  32.0,  10),
    ("50cal Turret", "slg02", "tmmedium.gdf", 400,  47.0,  25),
    ("7.62 Turret",  "slg03", "tmheavy.gdf",  600,  91.0,  40),
    ("20mm Turret",  "slg04", "tclight.gdf",  200,  69.0,  55),
    ("25mm Turret",  "slg05", "tcmedium.gdf", 400,  89.0,  70),
    ("30mm Turret",  "slg06", "tcheavy.gdf",  600, 150.0,  85),
    ("Pyro-Turret",  "flm04", "tfpyro.gdf",   600, 120.0, 100),
]
SUSP = [(n, c, d, du, w) for n, c, d, t, du, w in ed.SUSPENSIONS]

def md5(b): return hashlib.md5(b).hexdigest()

def pick(cmp, pred, n, exclude=()):
    """the first n section-A records matching pred (preds never select state-1 = mounted records)"""
    out = [p for p in cmp.a if pred(p) and p.state != 1 and p not in exclude]
    return out[:n]

def probe_color(base):
    c = ed.Cmp(base.to_bytes())
    guns = pick(c, lambda p: p.type in (7, 8) and p.state == 2, 7)
    guns += pick(c, lambda p: p.type in (7, 8) and p.state == 4, 7 - len(guns), exclude=guns)
    if len(guns) < 7: raise SystemExit(f"CAL COLOR needs 7 spare guns, found {len(guns)}")
    rows = []
    for p, (nm, cls, dfl, full, wt, pct) in zip(guns, TURRETS):
        p.set_identity(nm, 7, cls, dfl, full, wt); p.state = 2; p.cond = full * pct // 100
        rows.append((nm, pct, p.cond, full))
    c.sync_repair_queue()
    expect = "; ".join(f"**{nm}** {pct} % = {cond}/{full} ({'top third' if pct > 66 else 'middle third' if pct > 33 else 'bottom third'}{', full' if pct == 100 else ''})" for nm, pct, cond, full in rows)
    return c, ("Van pane of the Build & Repair Form. Screenshot the whole van list. Write down the highlight colour "
               "(none / green / yellow / red) next to each of the seven turrets. Reload the bookmark once and "
               "screenshot again: a colour that changes between loads is not stored state. Set: " + expect + ".")

def probe_v_vs_s(base):
    c = ed.Cmp(base.to_bytes())
    v = pick(c, lambda p: p.type in (7, 8) and p.state == 2, 1)
    s = pick(c, lambda p: p.type in (7, 8) and p.state == 4, 1, exclude=v)
    if not v or not s: raise SystemExit("CAL V VS S needs one spare gun in the van and one in salvage")
    v[0].set_identity("Howitzer", 7, "slg06", "tthowitz.gdf", 900, 170.0); v[0].cond = 900; v[0].state = 2
    s[0].set_identity("HADES Turret", 7, "slg07", "tchades.gdf", 600, 150.0); s[0].cond = 600; s[0].state = 4
    c.sync_repair_queue()
    return c, ("Garage: open the Build & Repair Form, then Field Salvage. Expected if state 2 = van and 4 = salvage: "
               "**Howitzer** listed in the van (V) pane and NOT in Field Salvage; **HADES Turret** in Field Salvage "
               "and NOT in the van. Also count the (C) rows: they must be exactly the 14 equipped names "
               "(state-1 records). Screenshot both panes.")

def probe_bench(base, target=15):
    c = ed.Cmp(base.to_bytes())
    have = sum(1 for p in c.a if p.state == 3)
    need = target - have
    cands = pick(c, lambda p: p.state == 4 and p.type != 13 and p.full and p.cond < p.full, need)
    cands += pick(c, lambda p: p.state == 2 and p.type != 13 and p.full and p.cond < p.full, need - len(cands),
                  exclude=cands)
    if len(cands) < need: raise SystemExit(f"CAL BENCH needs {need} more damaged spares, found {len(cands)}")
    for p in cands: p.state = 3
    c.sync_repair_queue()
    names = ", ".join(f"{p.name} {p.cond}/{p.full}" for p in c.a if p.state == 3)
    return c, (f"Build & Repair Form, repair order. The save queues **{target}** jobs (section C has {len(c.c)} "
               f"references). Count the bench rows the game lists and screenshot: 13, 14 or {target}? If fewer than "
               f"{target}, note which are missing. Queue: {names}.")

def probe_susp(base):
    c = ed.Cmp(base.to_bytes())
    sus = pick(c, lambda p: p.type == 3 and p.state in (2, 4), 4)
    if len(sus) < 4: raise SystemExit(f"CAL SUSP needs 4 spare suspensions, found {len(sus)}")
    for p, (n, cls, dfl, full, wt) in zip(sus, SUSP):
        p.set_identity(n, 3, cls, dfl, full, wt); p.cond = full; p.state = 2
    c.sync_repair_queue()
    return c, ("Van pane: four distinct suspensions are in the van (Stock, Sway Bars, Coil Overs, EtherX Rally) "
               "on top of the mounted one. Does the van list all four? Screenshot. If one is missing, which?")

def probe_paint(base):
    c = ed.Cmp(base.to_bytes())
    c.vtf = "piranha2.vtf"
    return c, ("LOAD board: does the row still read the variant text? Garage: is the Piranha painted the blue/white "
               "scheme (piranha2.vtf) instead of orange? Start the mission: paint in the hood view, damage decals "
               "OK? Screenshot garage + mission.")

def probe_jammer(base):
    c = ed.Cmp(base.to_bytes())
    slot = 13
    old = c.equipped[slot]
    if not old or old == "Empty": raise SystemExit("CAL JAMMER needs a special in Special 3")
    mounted = c.mounted().get(slot)
    if mounted is None: raise SystemExit(f"no mounted record for {old}")
    mounted.set_identity("Radar Jammer", 13, "", "spc01", 0, 0.0); mounted.cond = 0
    c.set_equipped(slot, "Radar Jammer")
    c.rename_registry(old, "Radar Jammer")
    return c, (f"Special 3 was {old}, now 'Radar Jammer' / spc01 (equipped name, mounted record, registry). Garage: "
               "what does the Spcl. row and the Mr. Damage panel call it? Mission: press the Special 3 key - HUD text, "
               "any effect (enemy missile lock / radar)? If the game ejected it to Empty, note that: spc01 is not a special.")

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--game", required=True, help="save set to build on (read-only)")
    ap.add_argument("--staging", required=True, help="output folder (created); must not be the game folder")
    ap.add_argument("--base", help="base bookmark, e.g. save003 (default: save003, else the first state-8 record)")
    ap.add_argument("--scene", type=int, help="scene dword for the probes (default: the base record's)")
    a = ap.parse_args()
    game = os.path.abspath(a.game); out = os.path.abspath(a.staging)
    if os.path.normcase(game) == os.path.normcase(out): raise SystemExit("staging must not be the game folder")
    sd = ed.SaveDir.load(os.path.join(game, "savegame.dir"))
    base_rec = sd.get(a.base) if a.base else (sd.get("save003") or next((r for r in sd.records if r.state == 8), None))
    if base_rec is None: raise SystemExit("no base bookmark (give --base)")
    base_path = os.path.join(game, base_rec.file + ".cmp")
    base = ed.Cmp.load(base_path)
    if base.check(): raise SystemExit(f"base {base_rec.file} fails the game invariants: {base.check()}")
    scene = a.scene if a.scene is not None else base_rec.scene
    os.makedirs(out, exist_ok=True)

    probes = [("CAL COLOR", probe_color), ("CAL V VS S", probe_v_vs_s), ("CAL BENCH 15", probe_bench),
              ("CAL SUSP 4", probe_susp), ("CAL PAINT BLUE", probe_paint), ("CAL JAMMER", probe_jammer)]
    rows = []
    n0 = len(sd.records)
    for name, fn in probes:
        cmp, what = fn(base)
        if cmp.check(): raise SystemExit(f"{name}: {cmp.check()}")
        slot = sd.free_slot()
        data = cmp.to_bytes()
        with open(os.path.join(out, slot + ".cmp"), "wb") as f: f.write(data)
        sd.add(slot, scene, name, state=8)
        rows.append((slot, name, len(sd.records) - 1, scene, 8, what, md5(data), len(data)))
    # LOAD-board label probes: byte-identical copies of the base, blank names, scene 7
    for name, state in (("CAL LABEL 7", 8), ("CAL LABEL 7+1", 1)):
        slot = sd.free_slot()
        data = base.to_bytes()
        with open(os.path.join(out, slot + ".cmp"), "wb") as f: f.write(data)
        sd.add(slot, 7, "", state=state)
        rows.append((slot, name, len(sd.records) - 1, 7, state,
                     f"Blank name, scene dword 7, state {state}. LOAD board: what label does this row print "
                     f"('SCENE 7.' or 'SCENE 8.')? Expected from the 2026-10-01 sandbox runs: state 8 prints and "
                     f"loads 7, state 1 prints and loads 8. Load it and note which mission starts.", md5(data), len(data)))
    dir_bytes = sd.to_bytes()
    # the game's records ride along byte for byte; only the count and the appended records differ
    assert dir_bytes[4:4 + 60 * n0] == ed.SaveDir.load(os.path.join(game, "savegame.dir")).to_bytes()[4:4 + 60 * n0]
    with open(os.path.join(out, "savegame.dir"), "wb") as f: f.write(dir_bytes)

    man = [f"# Calibration saves - staged {ed.stamp()}", "",
           f"Built from `{game}` ({base_rec.file}, scene {base_rec.scene}, state {base_rec.state}); base md5 {md5(base.to_bytes())}.",
           f"`savegame.dir` here = the game's {n0} records byte for byte + {len(rows)} probe records ({len(dir_bytes)} B = 4 + 60 x {len(sd.records)}).",
           "", "Install: with the game closed, back up the sandbox's save set, copy every file in this folder over it,",
           "then for each row run `leg-b.ps1 -WantFile <slot> -WantRow <row>` (row = record index on the LOAD board,",
           "0-based; RowUy = 193 + 23 x row for the first six rows - the board may scroll past that, check the shot).",
           f"This savegame.dir assumes the sandbox still holds exactly the {n0} records it was built from - if the set",
           "changed, re-run the script against the current folder. Never copy these into the daily-driver install.", "",
           "| slot | name | board row | scene/state | what to do and screenshot |", "|---|---|---|---|---|"]
    for slot, name, row, sc, st, what, h, n in rows:
        man.append(f"| {slot} | {name} | {row} | {sc}/{st} | {what} |")
    man += ["", "## Files", "", "| file | bytes | md5 |", "|---|---|---|"]
    for slot, name, row, sc, st, what, h, n in rows: man.append(f"| {slot}.cmp | {n} | {h} |")
    man.append(f"| savegame.dir | {len(dir_bytes)} | {md5(dir_bytes)} |")
    with open(os.path.join(out, "CAL-MANIFEST.md"), "w", encoding="utf-8") as f: f.write("\n".join(man) + "\n")
    for slot, name, row, sc, st, what, h, n in rows: print(f"{slot}  row {row:>2}  {name:16} {n:>6} B  {h}")
    print(f"savegame.dir  {len(dir_bytes)} B ({len(sd.records)} records)  ->  {out}")

if __name__ == "__main__":
    main()
