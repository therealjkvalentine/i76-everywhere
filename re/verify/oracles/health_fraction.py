r"""health_fraction: armour, chassis and core components -> object_HealthFraction, compared with the telemetry's health_pct (damage.md).

Spec (damage.md "Damage smoke", object_HealthFraction 0x40b450 for a vehicle at 0x40b4e8):
  engine +0x3c4, suspension +0x3c8, brakes +0x3cc ratios hp/max:
    all three >= 0.9999: value = 28 + 72 x r, r = min over the 4 sides of min(armour +0x138 / max +0x158,
                         chassis +0x148 / max +0x168), clamped to 0..1 (floats 72 / -28 at 0x4bc630 / 0x4bc634);
    any of the three < 0.9999: value = the smallest live component ratio, unscaled (0..1; the stock bug);
                         all three dead (< 0.02 each): 100.
  I76_FIX_HEALTH_PCT=1 (i76-everywhere music-fix, off by default) multiplies the unscaled branch by 100.
Observable: telemetry v2 `health_pct` = object_HealthFraction(obj) called by the proxy on the game thread every frame
(i76tel.h), so both branches are compared value-for-value. v1 runs (no health_pct column) are INCONCLUSIVE here; the
smoke bit is damage_smoke's business now.
Telemetry fields: armour_0..3 / armour_max_0..3 = ent+0x138 / +0x158, chassis_0..3 / chassis_max_0..3 = ent+0x148 / +0x168,
engine_hp/_max = eng+0x00/+0x04, susp_hp/_max, brake_hp/_max, health_pct. LAG 0 (same-frame read of the same fields).
"""

INPUTS = (["armour_%d" % i for i in range(4)] + ["armour_max_%d" % i for i in range(4)]
          + ["chassis_%d" % i for i in range(4)] + ["chassis_max_%d" % i for i in range(4)]
          + ["engine_hp", "engine_hp_max", "susp_hp", "susp_hp_max", "brake_hp", "brake_hp_max"])
OUTPUTS = ["health_pct"]
REQUIRED_COLUMNS = ["flags"]
LAG = 0
KIND = "pass"

CORE_INTACT = 0.9999        # damage.md: all three >= 0.9999 -> scaled branch
SCALE_OFFSET = 28.0         # damage.md: 28 + 72 x r (0x4bc634 holds -28)
SCALE_SPAN = 72.0           # 0x4bc630
ALL_DEAD = 0.02             # damage.md: all three < 0.02 -> 100
ALL_DEAD_VALUE = 100.0
FIX_X100 = False            # I76_FIX_HEALTH_PCT: the unscaled branch x 100 (set from the manifest env; VARIANT forces it)
CLAMP_LO, CLAMP_HI = 0.0, 100.0   # 0x4bc61c / 0x4bc620: the final clamp at 0x40b6f0 (not in damage.md; see GAPS)

CONSTANTS = {
    "0.9999": "core-component intact test (damage.md Damage smoke, 0x4bc62c)",
    "28 / 72": "scaled branch 28 + 72 x r, 0x4bc634 / 0x4bc630 (damage.md)",
    "0.02 / 100": "all-three-dead return (damage.md, 0x4bc624)",
    "100": "the x100 of the unscaled branch under I76_FIX_HEALTH_PCT (damage.md Opt-in fix)",
}
GAPS = [
    "damage.md does not mention the final clamp: whatever the branch, the return is clamped to [0, 100] at "
    "0x40b6f0..0x40b714 (fcom 0x4bc620 = 100.0, fcom 0x4bc61c = 0.0). Found live by verify/poke.py: with the offset "
    "poked from -28 to -40 (28 + 72 x 1 -> 112) health_pct stayed at 100. The oracle applies the clamp; it is a code "
    "constant the spec should name (it also caps the 'all three dead -> 100' return and any mod that raises the span).",
    "damage.md does not say what HealthFraction returns while a core component sits between 0.02 and 0.9999 with the "
    "others intact beyond 'the smallest live component ratio'; the oracle takes min over the three ratios, which the "
    "take-damage run (engine 600/1200 -> 0.5) confirms for one point.",
    "The all-three-dead branch (100) is not exercised: no run destroys engine, suspension and brakes together.",
    "Whether the unscaled branch's 'live' qualifier drops dead components (< 0.02) from the min is untested (none died).",
]
CAVEAT = """A PASS supports the two branches the runs reach: the scaled 28 + 72 x r value (drive runs: chassis wear;
take-damage: armour side 0 poked to 80/800 -> 35.2) and the unscaled stock value once a core component is below 99.99%
(take-damage: engine 600/1200 -> 0.5, with I76_FIX_HEALTH_PCT off). It does not test the x100 fix (no run has it on),
the all-dead return, or the clamp of r below 0 (a side at 0 hp was not reached). The variant 'x100 fix reading' is
expected to FAIL on a stock run exactly on the unscaled-branch frames: that failure is what shows the stock bug is live."""
CLAIMS = [
    ("object_HealthFraction 0x40b450", "28 + 72 x min side ratio while engine / suspension / brakes are intact; the unscaled 0..1 component ratio (stock bug) once one is below 0.9999, value-for-value against health_pct"),
    ("0x4bc630 / 0x4bc634 = 72 / -28", "the scaled branch's span and offset reproduce health_pct on every intact-core frame"),
    ("0x4bc62c = 0.9999", "the branch switch: engine 600/1200 (take-damage) moves health_pct from the 28 + 72 x r value to 0.5"),
    ("health_pct telemetry field (v2)", "the proxy's game-thread object_HealthFraction call reads the same fields the spec names"),
]


def configure(manifest):
    global FIX_X100
    env = (manifest or {}).get("env", {}) or {}
    FIX_X100 = str(env.get("I76_FIX_HEALTH_PCT", "")).strip() not in ("", "0")


def _value(inputs):
    cores = []
    for a, b in (("engine_hp", "engine_hp_max"), ("susp_hp", "susp_hp_max"), ("brake_hp", "brake_hp_max")):
        mx = float(inputs[b])
        cores.append(float(inputs[a]) / mx if mx else 0.0)
    if all(c >= CORE_INTACT for c in cores):
        r = 1.0
        for i in range(4):
            am = float(inputs["armour_max_%d" % i])
            cm = float(inputs["chassis_max_%d" % i])
            ar = float(inputs["armour_%d" % i]) / am if am else 0.0
            cr = float(inputs["chassis_%d" % i]) / cm if cm else 0.0
            r = min(r, ar, cr)
        r = min(1.0, max(0.0, r))
        return SCALE_OFFSET + SCALE_SPAN * r
    if all(c < ALL_DEAD for c in cores):
        return ALL_DEAD_VALUE
    v = min(c for c in cores)         # unscaled: 0..1 (the stock bug)
    return v * 100.0 if FIX_X100 else v


def _clamped(inputs):
    # 0x40b6f0..0x40b714: the return is clamped to [0, 100] (0x4bc620 = 100.0, 0x4bc61c = 0.0) whatever branch produced it.
    # damage.md does not state this; the poke runner found it (health_frac_offset -40 gave 100, not 112).
    return min(CLAMP_HI, max(CLAMP_LO, _value(inputs)))


def step(inputs):
    return {"health_pct": _clamped(inputs)}


def summary(rows):
    live = [r for r in rows if r.get("player_present")]
    if not live:
        return {}
    vals = [_value(r) for r in live]
    unscaled = [r for r in live if _value(r) <= 1.0 and not FIX_X100]
    return {"predicted min": round(min(vals), 2), "predicted max": round(max(vals), 2),
            "observed health_pct min": min(float(r["health_pct"]) for r in live),
            "observed health_pct max": max(float(r["health_pct"]) for r in live),
            "frames in the scaled branch": sum(1 for r in live if _value(r) > 1.0 or FIX_X100),
            "frames in the unscaled branch": len(unscaled),
            "frames with health_pct < 75": sum(1 for r in live if float(r["health_pct"]) < 75.0),
            "I76_FIX_HEALTH_PCT": FIX_X100}


VARIANTS = [
    ("x100 fix reading", {"FIX_X100": True}),
]
