r"""damage_smoke: health_pct -> the damage-smoke emitter flag ent+0x454 bit 0x100 (damage.md, entity_UpdateDamageSmoke 0x466ca0).

Spec (damage.md "Damage smoke"):
  Input f = object_HealthFraction(obj) x 0.01 (0x463f53), the call made only when f < 1.0 (0x463f65).
  Smoke starts at f < 0.75 (0x466ca4, the dual-use float 0x4be1e8): the emitter is added once and sets +0x454 bit 0x100;
  level 0 rate 0 for f > 0.6, level 1 rate 0.5 for f > 0.4, level 2 rate 1.0 otherwise (0x4be22c / 0x4be230);
  f >= 0.75 removes the emitter (0x466dbe).
Reading used: the flag follows the same frame's health_pct. damage.md places the call in entity_DamageAndKill ("after a
hit"), but the census (runs/phase1-all-summary.json) classes entity_UpdateDamageSmoke `per_substep` (7,681 calls in the
drive / fire-each / mission-idle hooks, same cadence as entity_ApplyRandomDamage 0x4641e0), i.e. the damage path runs
every substep whether or not a hit landed, so no hit-frame bookkeeping is needed; the take-damage run bears this out
(the bit set on the armour-poke frame itself, no IMPACT event within 38 frames). The emitter's rate levels (0.6 / 0.4)
are not observable in the telemetry; only the bit is.
Telemetry fields: health_pct (v2), flags = ent+0x454. v1 runs are INCONCLUSIVE (no health_pct). LAG 0.
"""

INPUTS = ["health_pct"]
OUTPUTS = ["smoke"]
BOOL_OUTPUTS = ["smoke"]
REQUIRED_COLUMNS = ["flags"]
LAG = 0
KIND = "pass"

PERCENT = 0.01              # damage.md: f = value x 0.01
SMOKE_BELOW = 0.75          # damage.md: smoke starts at f < 0.75 (0x466ca4)
CALL_BELOW = 1.0            # damage.md: UpdateDamageSmoke is reached only when f < 1.0 (0x463f65)
SMOKE_FLAG = 0x100          # damage.md / i76tel.h: ent+0x454 bit 0x100

_state = False

CONSTANTS = {
    "0.01": "value -> f (damage.md, 0x463f53)",
    "0.75": "smoke threshold on f (damage.md, 0x466ca4 = 0x4be1e8)",
    "1.0": "the f < 1.0 gate on the UpdateDamageSmoke call (damage.md, 0x463f65)",
    "0x100": "smoke emitter flag bit (damage.md, i76tel.h)",
}
GAPS = [
    "damage.md says UpdateDamageSmoke is reached from entity_DamageAndKill 'after a hit'; the census shows it running "
    "every substep (entity_ApplyRandomDamage -> DamageAndKill with zero damage, presumably), which is what makes the flag "
    "same-frame with health_pct. The spec should say 'every substep while f < 1.0'.",
    "The emitter's rate levels (0.6 -> 0.5, 0.4 -> 1.0) and the back-panel position are not in the telemetry; the bit "
    "alone is graded.",
    "The remove path (f back above 0.75 -> emitter removed, 0x466dbe) is not exercised: no run repairs a smoking car.",
]
CAVEAT = """A PASS supports the 0.75 threshold on object_HealthFraction x 0.01 and the bit's same-frame behaviour over the
frames the runs reach: drive runs never cross it (one-sided), the take-damage run crosses it once (76.0 -> 35.2 at the
armour poke) and stays below through the unscaled-branch frames (0.5). It says nothing about the smoke rate levels or
the removal on repair."""
CLAIMS = [
    ("entity_UpdateDamageSmoke 0x466ca0", "sets ent+0x454 bit 0x100 on the frame object_HealthFraction x 0.01 drops below 0.75 and keeps it while below"),
    ("0x4be1e8 = 0.75 (dual use)", "the smoke threshold: 76.0 no smoke, 35.2 smoke (take-damage)"),
    ("ent+0x454 bit 0x100", "the bit is the emitter's presence; it follows health_pct within the same frame"),
]


def reset():
    global _state
    _state = False


def observed(row):
    return {"smoke": bool(int(row["flags"]) & SMOKE_FLAG)}


def step(inputs):
    global _state
    f = float(inputs["health_pct"]) * PERCENT
    if f < CALL_BELOW:                 # the update runs only while f < 1.0; at full health the bit keeps its state
        _state = f < SMOKE_BELOW
    return {"smoke": _state}


def summary(rows):
    live = [r for r in rows if r.get("player_present")]
    if not live:
        return {}
    flags = [bool(int(r["flags"]) & SMOKE_FLAG) for r in live]
    changes = [(live[i]["frame"], "set" if flags[i] else "clear", live[i]["health_pct"]) for i in range(1, len(live)) if flags[i] != flags[i - 1]]
    return {"frames with flag 0x100": sum(flags),
            "frames with health_pct x 0.01 < 0.75": sum(1 for r in live if float(r["health_pct"]) * PERCENT < SMOKE_BELOW),
            "flag transitions (frame, to, health_pct)": changes[:6],
            "health_pct min": min(float(r["health_pct"]) for r in live)}
