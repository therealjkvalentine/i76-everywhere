#!/usr/bin/env python3
"""stock_reference.py - what the stock force-feedback DLL (i7_sfrce.dll) did per event -> stock/stock-ffb-reference.json.

The behaviour comes from a hand-entered table citing docs/records/FFB-DEEP-DIVE.md section 3 (the DLL's six
SIM_Effect handlers, disassembled 2026-07-19) - formulas, gates, durations. The .frc compositions come from
tools/ffb/parse-frc.py run over the PRISTINE install's force\\*.FRC (read-only). Only effect TYPE NAMES and counts
go into the committed JSON; the raw .frc parameter blocks (undecoded, game data) go to design/out/ with --params.

  python design/stock_reference.py               # writes stock/stock-ffb-reference.json
  python design/stock_reference.py --params      # also design/out/stock-frc-params.json (raw blocks, gitignored)
"""
import importlib.util, json, os, sys

from common import ROOT, REPO, OUT, game_dir, write_json

DD = "docs/records/FFB-DEEP-DIVE.md section 3"
TABLE = {
    "impact.collision": {"family": "constant force, directional, decaying", "trigger": "impact-collision list node (block +0x15c), one active node per list",
                         "formula": "mag = (55.0 + 0.5625 * dmg) * 100 DI units; direction = node angle (deg) * 100",
                         "decay": "per tick by block +0x160 dt; stopped when mag < -1500", "frc": [], "evidence": DD + " impact event nodes (DIRECT); node floats live-confirmed 2026-07-20"},
    "impact.ordnance": {"family": "constant force, directional, decaying", "trigger": "ordnance-impact list node (block +0x150): weapon hits on the player",
                        "formula": "mag = (40.0 + 0.6667 * dmg) * 100", "decay": "as impact.collision", "frc": [], "evidence": DD},
    "impact.concussion": {"family": "EXPLOSN.FRC template, directional", "trigger": "concussion list node (block +0x154)",
                          "formula": "mag = (35.0 + 0.6667 * dmg) * 100", "decay": "as impact.collision", "frc": ["EXPLOSN.FRC"], "evidence": DD + "; fn 0x10001930"},
    "engine.vibration": {"family": "periodic (engine vibration)", "trigger": "block +0x10 engine running",
                         "formula": "gain = 0x14 - min(speed_mph / 2, 0x14) (loudest at idle); freq = 8 - round(pitch * k1 * k2), pitch = block +0x0c (ftol rpm)",
                         "decay": "continuous", "frc": [], "evidence": DD + " handler 0x10001d90"},
    "engine.start": {"family": "one-shot", "trigger": "block +0x14 engine starting (DLL clears it)", "formula": "authored ENGSTART.FRC", "decay": "authored",
                     "frc": ["ENGSTART.FRC"], "evidence": DD},
    "engine.gear_changed": {"family": "re-parameterise (not a felt effect)", "trigger": "block +0x18 = engine object changed (new car / engine), NOT a gear shift (FFB-DATA-AUDIT 2.3)",
                            "formula": "-", "decay": "-", "frc": [], "evidence": DD + "; label corrected by FFB-DATA-AUDIT 2.3"},
    "terrain.rumble": {"family": "periodic by surface", "trigger": "block +0x148 surface id + 1 (0 = stopped), with speed",
                       "formula": "table by surface: I7_DIRT_INTERSECTION, I7_PARKING_LOT, I7_ROCKY, I7_WASH_ROAD, I7_DIRT_ROAD, I7_PAVED_ROAD, I7_LIGHT_VEGETATION, I7_PACKED_DIRT, I7_STOPPED, I7_IN_AIR (id order = jump table, GUESS); gain scales with speed",
                       "decay": "continuous", "frc": [], "evidence": DD + " handler 0x10002f80"},
    "tyre.flat": {"family": "Sine + Constant + Superimpose (side kick with a shake)", "trigger": "tire status FL/FR/RL/RR (block +0x108..0x114) vs 3000",
                  "formula": "'Flat Tire: gain%d'", "decay": "while flat", "frc": ["TIREBLWL.FRC", "TIREBLWR.FRC"], "evidence": DD + " handler 0x100029e0"},
    "tyre.skid": {"family": "modifier", "trigger": "block +0x130 skidding (flags & 2)", "formula": "modifies the X/Y vehicle force", "decay": "while set", "frc": [], "evidence": DD},
    "tyre.sliding": {"family": "modifier", "trigger": "block +0x138 sliding (flags & 0x2000, grip limit)", "formula": "modifies the X/Y vehicle force", "decay": "while set", "frc": [], "evidence": DD},
    "vehicle.airborne": {"family": "modifier", "trigger": "block +0x128 airborne (flags & 4)", "formula": "forces released in the air", "decay": "while set", "frc": [], "evidence": DD},
    "vehicle.oil": {"family": "modifier", "trigger": "block +0x140 oil slick (flags & 0x400)", "formula": "-", "decay": "while set", "frc": [], "evidence": DD},
    "vehicle.force": {"family": "constant force X/Y from the body-frame acceleration", "trigger": "block +0xf0..+0xf8 every tick",
                      "formula": "ForceX = steering kick with a +-0x320 bias; ForceY mag = 2 * sqrt(x^2 + y^2) signed; +2500 lateral with block +0x1c (nitrous)",
                      "decay": "continuous", "frc": [], "evidence": DD + " handler 0x100027d0"},
    "vehicle.centering": {"family": "spring / friction (XSpring, XFriction)", "trigger": "speed (block +0x104, mph, clamp 165)",
                          "formula": "spring and friction coefficients scale with speed", "decay": "continuous", "frc": [], "evidence": DD},
    "weapon.hardpoint": {"family": "per-hardpoint periodic / authored", "trigger": "hardpoint record +0x00 firing (6 records at block +0x30, stride 0x1c)",
                         "formula": "gain = record +0x14 (observed 5 / 10 / 60); WpnId +0x0c picks the template (CANNON1-4 UserDefined, MISSILE2/5, MISSIL45); missiles get random direction jitter; +0x10 firing freq (or direction: open question, owner test C5)",
                         "decay": "while the trigger is held", "frc": ["CANNON1.FRC", "CANNON2.FRC", "CANNON3.FRC", "CANNON4.FRC", "MISSILE2.FRC", "MISSILE5.FRC", "MISSIL45.FRC"], "evidence": DD + " hardpoint records (DIRECT)"},
    "weapon.misfire": {"family": "one-shot", "trigger": "hardpoint +0x04 / +0x08 event flags", "formula": "'Misfire: Triggered'", "decay": "authored", "frc": [], "evidence": DD},
    "weapon.ui.cycle": {"family": "one-shot click", "trigger": "block +0x24 (DLL clears)", "formula": "authored", "decay": "authored", "frc": ["WPNCYCLE.FRC"], "evidence": DD},
    "weapon.ui.link": {"family": "one-shot click", "trigger": "block +0x28", "formula": "authored", "decay": "authored", "frc": ["WPNLINK.FRC"], "evidence": DD},
    "weapon.ui.unlink": {"family": "one-shot click", "trigger": "block +0x2c", "formula": "authored", "decay": "authored", "frc": ["WPNUNLNK.FRC"], "evidence": DD},
}


def load_parse_frc():
    p = os.path.join(REPO, "tools", "ffb", "parse-frc.py")
    spec = importlib.util.spec_from_file_location("parse_frc", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def frc_compositions(force_dir):
    pf = load_parse_frc()
    out = {}
    for fn in sorted(os.listdir(force_dir)):
        if not fn.lower().endswith(".frc"):
            continue
        buf = open(os.path.join(force_dir, fn), "rb").read()
        if buf[:4] != b"RIFF" or buf[8:12] != b"FORC":
            continue
        effects = [pf.parse_effect(buf, c[0], c[1]) for c in pf.find_data_chunks(buf) if c[0] != "trgt"]
        out[fn.upper()] = {"types": [e[1] for e in effects], "params": [e[4] for e in effects], "mid_kind": [e[3] for e in effects]}
    return out


def build(with_params=False):
    force = os.path.join(game_dir(), "force")
    comps = frc_compositions(force) if os.path.isdir(force) else {}
    ref = {"generated_by": "tools/haptics/design/stock_reference.py",
           "sources": [DD, "tools/ffb/parse-frc.py over the pristine force\\*.FRC (" + str(len(comps)) + " files)"],
           "note": "Stock = what i7_sfrce.dll did. The .frc parameter blocks are NOT decoded (parse-frc.py); only type names are listed.",
           "events": {}}
    for k, v in TABLE.items():
        e = dict(v)
        e["frc_composition"] = {f: comps.get(f, {}).get("types", "file not found") for f in v["frc"]}
        ref["events"][k] = e
    ref["frc_files"] = {f: c["types"] for f, c in comps.items()}
    write_json(os.path.join(ROOT, "stock", "stock-ffb-reference.json"), ref)
    if with_params:
        write_json(os.path.join(OUT, "stock-frc-params.json"), comps)
    return ref


if __name__ == "__main__":
    r = build("--params" in sys.argv)
    print("wrote stock/stock-ffb-reference.json: %d events, %d .frc files" % (len(r["events"]), len(r["frc_files"])))
