#!/usr/bin/env python3
"""migrate_tune.py - move tools/ffb/FfbMixer.ps1's tune table into tools/haptics effect and rig files, and prove it.

No number is retyped by hand: the values are parsed out of Mix-DefaultTune in FfbMixer.ps1 itself and written to
the JSON pointers named in schema/legacy-tunemap.json. The skeletons below hold only the non-numeric structure
(model, routing shape, references, notes); the tune values are filled in from the parse.

  python design/migrate_tune.py --diff            # per-key: FfbMixer.ps1 value vs the value at its pointer; exit 1 on any mismatch
  python design/migrate_tune.py --write           # create missing files from the skeletons, update ONLY the mapped
                                                  # pointers in existing files (hand edits elsewhere survive)
  python design/migrate_tune.py --diff --overlay ../../tools/ffb/ffb-tune.json
                                                  # also report a saved panel tune (ffb-tune.json) against the defaults

Rule from memory (diff-the-table-after-a-bulk-merge): run --diff after every --write; it checks every key landed in
exactly one place with exactly the value FfbMixer.ps1 has, and that no two keys share a pointer.
"""
import argparse, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                       # tools/haptics
REPO = os.path.dirname(os.path.dirname(ROOT))
MIXER = os.path.join(REPO, "tools", "ffb", "FfbMixer.ps1")
TUNEMAP = os.path.join(ROOT, "schema", "legacy-tunemap.json")
EFFECTS = os.path.join(ROOT, "effects")
RIGS = os.path.join(ROOT, "rigs")
DEFAULT_RIG = "desk-t300-evo4"


def parse_default_tune(path=MIXER):
    """Mix-DefaultTune's hashtable -> {key: float | [floats]}. Handles `Key = 1.0  # comment` and @( ... ) over lines."""
    text = open(path, encoding="utf-8").read()
    m = re.search(r"function Mix-DefaultTune \{\s*return @\{(.*?)\n    \}\s*\n\}", text, re.S)
    if not m:
        raise SystemExit("cannot find Mix-DefaultTune in " + path)
    body = m.group(1)
    body = re.sub(r"#[^\n]*", "", body)            # comments (no '#' inside values in this table)
    out = {}
    for km in re.finditer(r"(?m)^\s*([A-Za-z][A-Za-z0-9]*)\s*=\s*", body):
        key, start = km.group(1), km.end()
        if body.startswith("@(", start):
            end = body.index(")", start)
            out[key] = [float(x) for x in body[start + 2:end].replace("\n", " ").split(",")]
        else:
            vm = re.match(r"[-+]?[0-9.]+(?:[eE][-+]?\d+)?", body[start:])
            out[key] = float(vm.group(0))
    return out


def get_ptr(doc, ptr):
    cur = doc
    for part in ptr.strip("/").split("/"):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            raise KeyError(ptr)
    return cur


def set_ptr(doc, ptr, value):
    parts = ptr.strip("/").split("/")
    cur = doc
    for part in parts[:-1]:
        cur = cur.setdefault(part, {})
    cur[parts[-1]] = value


def tap(motor, gain, frm="level"):
    return {"motor": motor, "gain": gain, "from": frm}


# ----------------------------------------------------------------------------------------------------------------
# Skeletons. None = filled from the tune via the tunemap. Every legacy effect names the reference-model channel that
# implements it ("model": "legacy.<channel>"); chain effects are interpreted generically by Core/EffectEngine.cs.
# ----------------------------------------------------------------------------------------------------------------
LEGACY_NOTE = ("Implemented by the reference model (Core/ReferenceMixer.cs = tools/ffb/FfbMixer.ps1). The numbers here "
               "ARE that model's tune: edit them here, not in FfbMixer.ps1. Design rationale: FfbMixer.ps1 comments.")

SKELETONS = {
    "global.mixer": {
        "kind": "global", "model": "legacy.global",
        "mix": {"master": None, "ramp_ms": None, "idle_fade_after_s": None, "idle_fade_over_s": None,
                "wheel_continuous_budget": 0.70},
        "notes": "Global scale, fade-in, thermal idle guard (Thrustmaster KB 1744). The pad's max/sum mode is a device fact: "
                 "rigs/*.json outputs.pad.mode. " + LEGACY_NOTE,
    },
    "steer.center": {
        "kind": "continuous", "model": "legacy.center",
        "source": {"channel": "steer", "speed_ref": None, "speed_floor": None},
        "routing": {"wheel": {"gain": None, "sign": "oppose_steer"},
                    "pad": [tap("L", 0.25, "bus.steady")], "lfe": None, "motion": None},
        "mix": {"group": "steady", "priority": 40},
        "reference": {"stock": "stock-ffb-reference.json#vehicle.centering", "sounds": []},
        "notes": "Self-aligning torque. The pad tap degrades the whole signed steady sum to unsigned weight on the heavy motor (Mix-RenderPad). " + LEGACY_NOTE,
    },
    "steer.corner": {
        "kind": "continuous", "model": "legacy.corner",
        "source": {"channel": "lat_g", "ref": None},
        "routing": {"wheel": {"gain": None, "sign": "oppose_yaw"}, "pad": [], "lfe": None, "motion": None},
        "mix": {"group": "steady", "priority": 40},
        "reference": {"stock": "stock-ffb-reference.json#vehicle.force", "sounds": []},
        "notes": "Cornering load; collinear with steer.center in this engine (no tyre model). " + LEGACY_NOTE,
    },
    "grip.loss": {
        "kind": "continuous", "model": "legacy.grip",
        "source": {"channel": "max(understeer, oversteer)"},
        "routing": {"wheel": {"attenuate_steady": None}, "pad": [], "lfe": None, "motion": None},
        "mix": {"group": "steady", "priority": 60},
        "reference": {"stock": None, "sounds": []},
        "notes": "Losing the car makes the wheel go LIGHT: attenuates center+corner. " + LEGACY_NOTE,
    },
    "slip.oversteer": {
        "kind": "continuous", "model": "legacy.oversteer",
        "source": {"channel": "oversteer"},
        "routing": {"wheel": {"gain": None, "sign": "with_yaw"}, "pad": [], "lfe": None, "motion": None},
        "mix": {"group": "steady", "priority": 60},
        "reference": {"stock": None, "sounds": ["tskid1", "tskid2", "tskid3", "tskid4"]},
        "notes": "Counter-steer push toward the correction. " + LEGACY_NOTE,
    },
    "slip.scrub": {
        "kind": "continuous", "model": "legacy.scrub",
        "source": {"channel": "max(understeer, oversteer)", "threshold": 0.15},
        "routing": {"wheel": {"gain": None, "hz": None},
                    "pad": [tap("R", 1.0, "tactile.scrub")],
                    "lfe": {"amp": None, "hz": None}, "motion": None},
        "mix": {"group": "slip", "priority": 60},
        "reference": {"stock": "stock-ffb-reference.json#tyre.skid", "sounds": ["tskid1", "tskid2", "tskid3", "tskid4", "tturn1", "tturn2"],
                      "analysis": "analysis/tskid1.json"},
        "notes": "Tyre-scrub buzz on a spin; on the shaker a rough-amplitude tone. " + LEGACY_NOTE,
    },
    "road.texture": {
        "kind": "continuous", "model": "legacy.texture",
        "source": {"channel": "uncommanded acceleration residual", "speed_ref": None, "rough_ref": None},
        "response": {"min_force": None},
        "routing": {"wheel": {"gain": None, "hz": None, "bump_gain": None},
                    "pad": [tap("L", 0.6, "lfe.road_amp"), tap("R", 0.5, "tactile.texture")],
                    "lfe": {"amp": None, "hz_lo": None, "hz_hi": None}, "motion": None},
        "mix": {"group": "road", "priority": 20},
        "reference": {"stock": "stock-ffb-reference.json#terrain.rumble", "sounds": ["vcddirt", "vcdsand", "vcdgrav"],
                      "analysis": "analysis/vcddirt.json"},
        "notes": "Road texture: oscillator on the wheel (11 Hz, under the 62 Hz loop's Nyquist), noise bed on the shaker. " + LEGACY_NOTE,
    },
    "brake.weight": {
        "kind": "continuous", "model": "legacy.brake",
        "source": {"channel": "-long_g", "ref": None},
        "routing": {"wheel": {"gain": None, "sign": "with_steer_opposed"}, "pad": [], "lfe": None, "motion": None},
        "mix": {"group": "steady", "priority": 40},
        "reference": {"stock": None, "sounds": []},
        "notes": LEGACY_NOTE,
    },
    "brake.judder": {
        "kind": "continuous", "model": "legacy.judder",
        "source": {"channel": "-long_g", "threshold": 0.45},
        "routing": {"wheel": {"gain": None, "hz": None}, "pad": [tap("R", 1.0, "tactile.judder")], "lfe": None, "motion": None},
        "mix": {"group": "brake", "priority": 70},
        "reference": {"stock": None, "sounds": ["fdmg1"]},
        "notes": "Lockup shimmy under heavy braking (no ABS in 1997). " + LEGACY_NOTE,
    },
    "impact.collision": {
        "kind": "transient", "model": "legacy.impact",
        "source": {"channel": "jolt", "ref": None, "trigger_fraction": 0.08},
        "envelope": {"attack_ms": "12% of decay", "hold_ms": 0, "decay_ms": None, "retrigger": "add"},
        "routing": {"wheel": {"gain": None, "shape": "jolt", "direction": "from_yaw"},
                    "pad": [tap("L", 1.0, "transient.impact")],
                    "lfe": {"amp": None, "hz": None}, "motion": None},
        "mix": {"group": "impact", "priority": 90},
        "reference": {"stock": "stock-ffb-reference.json#impact.collision", "sounds": ["vvch2", "vvcre2", "vvcbb3", "vnvcs1", "vnvcs3", "vnvcs5", "vnvco3"],
                      "analysis": "analysis/vvch2.json"},
        "notes": "stock: (55 + 0.5625*dmg)*100 DI units, decays by dt to -1500. " + LEGACY_NOTE,
    },
    "impact.kerb": {
        "kind": "transient", "model": "legacy.unused", "enabled": False,
        "routing": {"wheel": {"gain": None}, "pad": [], "lfe": None, "motion": None},
        "mix": {"group": "impact", "priority": 50},
        "reference": {"stock": None, "sounds": []},
        "notes": "KerbGain is defined in Mix-DefaultTune but NO code reads it (FfbMixer.ps1 at 560dcd2). Kept so the "
                 "migration is complete; a kerb effect should be a chain effect on wheel susp_offset edges (HAPTICS-ARCHITECTURE 6.8).",
    },
    "gear.shift": {
        "kind": "transient", "model": "legacy.shift",
        "source": {"event": "GEAR"},
        "envelope": {"attack_ms": "12% of decay", "hold_ms": 0, "decay_ms": None, "retrigger": "add"},
        "routing": {"wheel": {"gain": None, "shape": "jolt", "down_scale": None},
                    "pad": [tap("R", 0.6, "transient.shift")],
                    "lfe": {"via": "impact.collision"}, "motion": None},
        "mix": {"group": "shift", "priority": 50},
        "reference": {"stock": "stock-ffb-reference.json#engine.gear_changed", "sounds": ["vshif1a"], "analysis": "analysis/vshif1a.json"},
        "notes": "One short firm hit. The LFE impulse source carries impact + shift together (Mix-Update ImpulseAmp). The pad tap is new "
                 "(Mix-RenderPad had no shift); it only exists in pad_mode 'max'. " + LEGACY_NOTE,
    },
    "weapon.fire": {
        "kind": "transient", "model": "legacy.weapon",
        "source": {"event": "SHOT", "mag_ref": None, "mag_scale_max": None,
                   "shot_mag": "10", "shot_mag_note": "i76tel SHOT carries damage-per-hit, not the hardpoint FFB gain (+0x14, observed 5/10/60) the reference model was tuned on; nominal 10 until a live capture maps one to the other"},
        "envelope": {"decay_ms": None, "blank_ms": None, "retrigger": "rising_edge"},
        "routing": {"wheel": {"gain": None, "hz": None, "shape": "buzz"},
                    "pad": [tap("R", 1.0, "transient.weapon")],
                    "lfe": {"amp": None, "hz": None}, "motion": None},
        "mix": {"group": "weapon", "priority": 80},
        "reference": {"stock": "stock-ffb-reference.json#weapon.hardpoint", "sounds": ["wlmgun", "wmmgun", "whmgun", "wlcan", "wmcan", "whcan", "wrock", "wmiss"],
                      "analysis": "analysis/wmmgun.json"},
        "notes": "Decaying buzz scaled by sqrt(engine magnitude). " + LEGACY_NOTE,
    },
    "engine.vibration": {
        "kind": "continuous", "model": "legacy.engine",
        "source": {"channel": "rpm (speed fallback)", "rpm_idle": None, "rpm_max": None, "speed_ref": None},
        "carrier": {"base_hz": None, "high_hz": None, "jitter": None},
        "routing": {"wheel": None, "pad": [tap("L", 0.5, "lfe.engine_amp")], "lfe": {"amp": None}, "motion": None},
        "mix": {"group": "engine", "priority": 10},
        "reference": {"stock": "stock-ffb-reference.json#engine.vibration", "sounds": ["eishp", "eshp1", "esshp1", "eimarx", "eitank"],
                      "analysis": "analysis/eshp1.json"},
        "notes": "The one always-on source: smallest budget. " + LEGACY_NOTE,
    },
    "explosion.blast": {
        "kind": "transient", "model": "legacy.blast",
        "source": {"event": "EXPLOSION", "mag_threshold": None, "reach_m": 100.0,
                   "reach_note": "[proposed] blast level = clamp(1 - distance/reach_m); the engine's own concussion range is unknown (backlog P4-20, console test 6). 100 m = the sound's 3D min distance for vexplode"},
        "envelope": {"decay": "x0.90 per update", "retrigger": "max"},
        "routing": {"wheel": None, "pad": [], "lfe": {"amp": None, "hz": None}, "motion": None},
        "mix": {"group": "explosion", "priority": 95, "duck": {"groups": ["engine", "road", "slip"], "depth": None}},
        "reference": {"stock": "stock-ffb-reference.json#impact.concussion", "sounds": ["vexplode", "xcar", "xbuild"], "analysis": "analysis/vexplode.json"},
        "notes": "Deepest, longest event; ducks the beds instead of out-shouting them. " + LEGACY_NOTE,
    },
    "body.heave": {
        "kind": "continuous", "model": "legacy.heave",
        "source": {"channel": "|d(vy)/dt|", "ref": None},
        "carrier": {"base_hz": None, "modulation": "AM"},
        "routing": {"wheel": None, "pad": [], "lfe": {"amp": None}, "motion": None},
        "mix": {"group": "heave", "priority": 30},
        "reference": {"stock": None, "sounds": []},
        "notes": "Sub-shaker heave rendered as AM of a carrier at the rig peak. " + LEGACY_NOTE,
    },
}

RIG_SKELETON = {
    "name": DEFAULT_RIG,
    "description": "the developer's desk: Thrustmaster T300RS (belt), Audient EVO 4 -> Aura AST-2B shaker, an XInput pad. "
                   "Every output names the renderer that serves it; the host instantiates exactly the outputs listed here.",
    "outputs": {
        "wheel": {"renderer": "Wheel.DirectInput", "device_match": "T300", "min_force": None, "min_force_gate": None,
                  "clamp": None, "slew_max": None, "update_only_on_change": True},
        "pad": {"renderer": "Pad.XInput", "slot": 0, "deadzone": 0.30, "min_pulse_ms": 40, "mode": "max",
                "silence_below": 0.02},
        "lfe": {"renderer": "Lfe.Synth", "device_name_match": "EVO4", "rate": 16000, "hp_hz": 11.0, "lp_hz": 85.0,
                "drive": 1.5, "master": 0.9, "resp_hz": None, "resp_rel": None, "comp_max": None, "channels": 1,
                "max_voices": 3,
                "hp_lp_note": "11/85 Hz are what ffb-lfe-live.ps1 / ffb-lfe-probe.ps1 ship (the LP corner is raised x1.35 inside LfeCore); HAPTICS-ARCHITECTURE's 'HP 22 / LP 90' describes intent, not the shipped constants",
                "resp_source": "ffb-lfe-sweep.ps1, 21 steps, perceived by body, n = 1 rater (2026-08)"},
        "loopback": {"renderer": "Lfe.Loopback", "enabled": False, "gain": 0.25, "hp_hz": 22.0, "lp_hz": 90.0,
                     "duck_on_transient": 0.6, "gate": "player_present", "endpoint": "default-render"},
        "motion": {"renderer": "Motion.FileSink", "enabled": False,
                   "note": "Plug-in point only. Motion cueing, washout and packet formats are a separate workstream: docs/engine/MOTION-OUTPUT.md"},
    },
}


def load_tunemap():
    return json.load(open(TUNEMAP, encoding="utf-8"))["keys"]


def target_path(tid, rig=DEFAULT_RIG):
    if tid == "rig":
        return os.path.join(RIGS, rig + ".json")
    return os.path.join(EFFECTS, tid + ".json")


def write(tune, tmap, rig=DEFAULT_RIG):
    docs = {}
    for key, where in tmap.items():
        tid, ptr = where.split("#", 1)
        if tid not in docs:
            p = target_path(tid, rig)
            if os.path.exists(p):
                docs[tid] = json.load(open(p, encoding="utf-8"))
            else:
                skel = RIG_SKELETON if tid == "rig" else dict({"id": tid}, **SKELETONS[tid])
                docs[tid] = json.loads(json.dumps(skel))
        set_ptr(docs[tid], ptr, tune[key])
    for tid in SKELETONS:                          # skeletons with no tune key at all still get a file
        if tid not in docs and not os.path.exists(target_path(tid)):
            docs[tid] = dict({"id": tid}, **SKELETONS[tid])
    for tid, doc in docs.items():
        p = target_path(tid, rig)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            json.dump(doc, f, indent=2)
            f.write("\n")
        print("wrote", os.path.relpath(p, ROOT))


def diff(tune, tmap, rig=DEFAULT_RIG, overlay=None):
    bad = 0
    seen_ptrs = {}
    cache = {}
    print("%-16s %-48s %-14s %-14s %s" % ("key", "lands in", "FfbMixer.ps1", "file", "ok"))
    for key in sorted(set(tune) | set(tmap)):
        if key not in tmap:
            print("%-16s %-48s %-14s %-14s MISSING FROM TUNEMAP" % (key, "-", tune[key], "-")); bad += 1; continue
        if key not in tune:
            print("%-16s %-48s %-14s %-14s NOT IN FfbMixer.ps1" % (key, tmap[key], "-", "-")); bad += 1; continue
        where = tmap[key]
        if where in seen_ptrs:
            print("%-16s %-48s shares a pointer with %s" % (key, where, seen_ptrs[where])); bad += 1
        seen_ptrs[where] = key
        tid, ptr = where.split("#", 1)
        p = target_path(tid, rig)
        if p not in cache:
            cache[p] = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None
        try:
            v = get_ptr(cache[p], ptr) if cache[p] is not None else "<no file>"
        except KeyError:
            v = "<absent>"
        ok = v == tune[key]
        bad += 0 if ok else 1
        show = lambda x: ("[%d values]" % len(x)) if isinstance(x, list) else str(x)
        print("%-16s %-48s %-14s %-14s %s" % (key, where, show(tune[key]), show(v), "ok" if ok else "MISMATCH"))
    print("%d keys in FfbMixer.ps1, %d in the tunemap, %d distinct pointers, %d problems" % (len(tune), len(tmap), len(seen_ptrs), bad))
    if overlay and os.path.exists(overlay):
        ov = json.load(open(overlay, encoding="utf-8-sig"))
        print("\noverlay %s (a saved panel tune; NOT migrated - report only):" % overlay)
        for k in sorted(ov):
            if k not in tune:
                print("  %-16s %s  (no such key in the current model)" % (k, ov[k]))
            elif ov[k] != tune[k] and not (isinstance(ov[k], float) and abs(ov[k] - tune[k]) < 1e-9):
                print("  %-16s overlay %-10s default %s" % (k, ov[k], tune[k]))
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--diff", action="store_true")
    ap.add_argument("--rig", default=DEFAULT_RIG)
    ap.add_argument("--overlay", default="")
    a = ap.parse_args()
    tune = parse_default_tune()
    tmap = load_tunemap()
    if a.write:
        write(tune, tmap, a.rig)
    if a.diff or not a.write:
        return 1 if diff(tune, tmap, a.rig, a.overlay) else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
