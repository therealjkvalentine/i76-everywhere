r"""drive_power: rpm, ENGN power and the engine health factor -> eng+0x10 drive power (engine.md, Power).

Spec (engine.md "Model", Power, physics_UpdateEngine 0x46a320, every call):
  eng+0x10 = P x f x rpm x (7000 - rpm) / 3500^2
  P = ENGN power (eng+0x14; telemetry v2 `engine_power`); k = P / 3500^2 is set once at load (eng+0xc).
  f = engine health factor eng+0x18 = max(hp/max, floor), floor 0.4 for the offline player (0x469fb0, physics_EngineApplyDamage);
  it is written by the engine damage handler, i.e. recomputed when the engine takes damage, not every frame
  (tools/trainer/tunables.json engine_health_floor_player: "takes effect at the next engine damage event").
Reading used (default): f starts at max(hp/max, 0.4) on the run's first frame and is recomputed only on frames where
engine_hp decreased AND the frame carries a player IMPACT event (events.csv type 3, i_0 = 1) - an engine damage event.
A trainer poke of engine_hp (take-damage: 1200 -> 600 at frame 1067, no hit) therefore leaves f at 1.0 until the engine
is hit again, which is what the telemetry shows (drive_power stays on the f = 1 curve). VARIANT "f = hp/max every frame"
is the naive reading; its failure after the poke is the finding that eng+0x18 is event-driven.
Telemetry fields: rpm = eng+0x1c, engine_hp / engine_hp_max = eng+0x00 / +0x04, engine_power = eng+0x14 (v2),
drive_power = eng+0x10, proxy_frame (event stamps). v1 runs (no engine_power) are INCONCLUSIVE. LAG 0.
"""
import csv
import os

INPUTS = ["rpm", "engine_hp", "engine_hp_max", "engine_power", "proxy_frame"]
OUTPUTS = ["drive_power"]
LAG = 0
KIND = "pass"

RPM_ZERO = 7000.0           # engine.md: zero at 7000
RPM_PEAK = 3500.0           # engine.md: peak at 3500, divisor 3500^2
PLAYER_FLOOR = 0.4          # engine.md: health floor for the offline player (0x469fb0, 0x4be268)
F_EVERY_FRAME = False       # VARIANT: f = max(hp/max, 0.4) on every frame (ignores the event-driven eng+0x18)

_hits = set()
_f = None
_prev_hp = None

CONSTANTS = {
    "7000": "rpm at which power is zero (engine.md Power)",
    "3500": "peak rpm and the 3500^2 divisor (engine.md Power)",
    "0.4": "offline player health floor (engine.md Power, 0x469fb0 / 0x4be268)",
}
GAPS = [
    "engine.md states f = max(hp/max, floor) but not when it is recomputed; the catalogue (tunables.json) says 'at the "
    "next engine damage event' (eng+0x18 is written by physics_EngineApplyDamage 0x469fb0). The default reading takes "
    "an engine damage event as 'engine_hp decreased on a player IMPACT frame'; the take-damage run has no such event "
    "(the engine lost hp only through the trainer), so the floor 0.4 and the hp factor are still not exercised live.",
    "Frame 0 of every run (sim_time 0, stale load-frame telemetry) carries drive_power 43897.5 at rpm 1050, 0.444 x the "
    "curve (implied P x f = 86073): one mismatch per run; engine.md's 'first engine update' in physics_InitEntity may "
    "run before the ENGN power is set.",
    "Whether the engine damage handler also runs on surface (random) damage that hits the engine is untested: the "
    "take-damage run's surface ticks only took chassis.",
]
CAVEAT = """A PASS supports eng+0x10 = P x f x rpm x (7000 - rpm) / 3500^2 with P read from eng+0x14 (no fitted constant any
more: P = 193960 is the Piranha's ENGN power, data/VEHICLES.md) on every frame of the drive and take-damage runs, and
that f is event-driven (the poke left the curve unchanged). It does not prove the value of the floor 0.4 nor the hp
factor itself, since no engine damage event occurred in any run; a hit that damages the engine (or an AI's fire on
it) is still needed for those two constants."""
CLAIMS = [
    ("physics_UpdateEngine 0x46a320 (power curve)", "eng+0x10 = eng+0x14 x f x rpm x (7000 - rpm) / 3500^2 on every frame, P read live"),
    ("eng+0x14 engine_power", "the telemetry field is the P of the power curve (193960 = Piranha ENGN power, data/VEHICLES.md)"),
    ("eng+0x18 engine health factor", "event-driven: a trainer write of eng+0x00 to 50% did not change the curve (f stayed 1.0)"),
]


def configure(manifest):
    global _hits
    _hits = set()
    run_dir = (manifest or {}).get("_run_dir")
    p = os.path.join(run_dir, "events.csv") if run_dir else None
    if p and os.path.exists(p):
        with open(p, newline="") as fh:
            for e in csv.DictReader(fh):
                if e.get("type") == "3" and e.get("i_0") == "1":
                    _hits.add(int(e["frame"]))


def reset():
    global _f, _prev_hp
    _f = None
    _prev_hp = None


def _factor(hp, hp_max):
    return max(hp / hp_max, PLAYER_FLOOR) if hp_max else PLAYER_FLOOR


def step(inputs):
    global _f, _prev_hp
    hp, mx = float(inputs["engine_hp"]), float(inputs["engine_hp_max"])
    if F_EVERY_FRAME:
        f = _factor(hp, mx)
    else:
        if _f is None:
            _f = _factor(hp, mx)
        elif _prev_hp is not None and hp < _prev_hp and int(inputs["proxy_frame"]) in _hits:
            _f = _factor(hp, mx)              # an engine damage event: the handler rewrites eng+0x18
        f = _f
    _prev_hp = hp
    rpm = float(inputs["rpm"])
    return {"drive_power": float(inputs["engine_power"]) * f * rpm * (RPM_ZERO - rpm) / (RPM_PEAK * RPM_PEAK)}


def summary(rows):
    live = [r for r in rows if r.get("player_present")]
    if not live:
        return {}
    hp_changes = [(live[i]["frame"], live[i - 1]["engine_hp"], live[i]["engine_hp"], int(live[i]["proxy_frame"]) in _hits)
                  for i in range(1, len(live)) if live[i]["engine_hp"] != live[i - 1]["engine_hp"]]
    return {"engine_power (P) values": sorted(set(r["engine_power"] for r in live)),
            "engine_hp changes (frame, from, to, on a hit frame)": hp_changes[:6],
            "engine damage events (hp drop on a hit frame)": sum(1 for c in hp_changes if c[3] and float(c[2]) < float(c[1])),
            "player impact frames": len(_hits)}


VARIANTS = [
    ("f = hp/max every frame", {"F_EVERY_FRAME": True}),
]
