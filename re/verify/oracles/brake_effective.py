r"""brake_effective: brake hp and the vehicle mass -> brake+0x10 effective strength with the single-player 2300/m rule (engine.md, Brakes).

Spec (engine.md "Model", Brakes; physics.md constants table):
  brake+0x10 = max(hp/max, 0.2) x strength.
  In single player the BRAK strength is replaced by 2300 / m (physics_BrakeSetStrength 0x46a890, called with 2300/m by
  physics_InitEntity 0x438f7e; 0x4bd144 = 2300.0); network games and multi-melee multiply instead.
  engine.md's worked example: "Piranha, 1951 kg: 9.4 m/s^2" (= 2300/1951 x 8).
Telemetry v2 carries the mass (ent+0xa4, `mass`), so the prediction has no fitted constant: 2300 / mass x max(hp/max, 0.2).
Reading used: the hp factor is applied every frame (brake+0x10 is rewritten by the brake damage handler; no run damages
the brakes, so hp/max = 1 throughout and the two readings coincide). v1 runs (no mass column) are INCONCLUSIVE.
Telemetry fields: brake_hp / brake_hp_max = [[ent+0x3cc]+0x70]+0x04 / +0x08, mass = ent+0xa4, brake_effective = brake+0x10. LAG 0.
"""

INPUTS = ["brake_hp", "brake_hp_max", "mass"]
OUTPUTS = ["brake_effective"]
LAG = 0
KIND = "pass"

HP_FLOOR = 0.2              # engine.md: max(hp/max, 0.2)
SP_STRENGTH_NUM = 2300.0    # engine.md / physics.md 0x4bd144: single-player strength = 2300 / m

CONSTANTS = {
    "0.2": "brake hp floor (engine.md Brakes)",
    "2300": "single-player brake strength numerator, 0x4bd144 (engine.md Brakes, physics.md)",
}
GAPS = [
    "brake_hp stays at brake_hp_max in every run so far (the take-damage hits took chassis and armour only), so the "
    "max(hp/max, 0.2) factor and its floor are not exercised; only the 2300 / m point is. A run that damages the brakes "
    "(an AI's fire, or a trainer poke of brake hp followed by a brake hit) is needed.",
    "Whether brake+0x10 is rewritten on the brake damage event only (like eng+0x18) or on every frame cannot be told "
    "while hp never changes.",
    "The network / multi-melee branch (BRAK strength multiplied instead of replaced) is outside the sandbox scenarios.",
]
CAVEAT = """A PASS supports the single-player rule brake+0x10 = 2300 / m with m read from ent+0xa4 (1951 kg) on every frame of
the drive and take-damage runs: 1.17888 to the CSV's six digits, which a BRAK-file strength (1.0-2.0 stock) would not
give. It does not prove the hp factor or the 0.2 floor (brake hp never left its max)."""
CLAIMS = [
    ("physics_BrakeSetStrength 0x46a890 / 0x4bd144 = 2300", "offline brake+0x10 = 2300 / m with m = ent+0xa4 read live (1951 kg Piranha), no fit"),
    ("ent+0xa4 mass (v2)", "the telemetry field is the mass the brake rule divides by (and brake accel = brake+0x10 x throttle x 8)"),
    ("brake+0x10 brake_effective", "the effective strength; constant while brake hp is full"),
]


def step(inputs):
    hp, mx, m = float(inputs["brake_hp"]), float(inputs["brake_hp_max"]), float(inputs["mass"])
    ratio = hp / mx if mx else 0.0
    return {"brake_effective": max(ratio, HP_FLOOR) * (SP_STRENGTH_NUM / m if m else 0.0)}


def summary(rows):
    live = [r for r in rows if r.get("player_present")]
    if not live:
        return {}
    return {"mass values": sorted(set(r["mass"] for r in live)),
            "distinct brake_hp/max values seen": len(set((r["brake_hp"], r["brake_hp_max"]) for r in live)),
            "brake_effective values": sorted(set(r["brake_effective"] for r in live))[:4]}
