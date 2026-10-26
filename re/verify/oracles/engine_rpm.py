r"""engine_rpm: gear + speed -> rpm on grounded, geared, engine-running frames (subsystems/engine.md, Model).

Spec (engine.md "Model", static reading of md5 9a232dcc, physics_UpdateEngine 0x46a320):
  rpm (geared, engine running, not skidding, not airborne) = 850 + 126.81 x R[g] x v, v in m/s,
  R = {3.0 reverse, -, 1.67, 0.96, 0.67} at 0x4f8640 indexed by gear g = eng+0x08 (0 reverse, 1 idle, 2/3/4 = 1st/2nd/3rd),
  idle / neutral (g = 1): 1050.
The free-rev branch (skidding flag 0x2, airborne flag 0x4, lever P/N) eases the rpm toward 1050 + 4950 x throttle at
2 x dt per call and is path-dependent, so those frames are skipped and counted, not predicted. Engine-off (flag 0x1
clear), starting (0x8) and destroyed (0x20) frames are skipped for the same reason: the spec gives no rpm for them.

Telemetry fields (tools/telemetry/i76tel.h): gear = eng+0x08, speed = ent+0xac |velocity| m/s, rpm = eng+0x1c,
flags = ent+0x454, gear_lever = ent+0x104 (0 P, 1 R, 2 N, 3 D, 4 "2", 5 "1").
LAG 0: physics_UpdateEngine is the last stage of the substep (physics.md "One substep"), so the rpm it writes uses the
speed the same substep integrated; both are read at the end of the frame.
"""

INPUTS = ["gear", "speed", "flags", "gear_lever"]
OUTPUTS = ["rpm"]
LAG = 0
KIND = "pass"

RPM_BASE = 850.0            # engine.md: rpm = 850 + ...
RPM_PER_MS = 126.81         # engine.md: 126.81 x R[g] x v
RATIOS = {0: 3.0, 2: 1.67, 3: 0.96, 4: 0.67}   # 0x4f8640; index 1 (idle) has no ratio
IDLE_RPM = 1050.0           # engine.md: idle / neutral 1050

CONSTANTS = {
    "850": "rpm offset (engine.md Model)",
    "126.81": "rpm per m/s per unit ratio (engine.md Model)",
    "R": "{3.0 reverse, -, 1.67, 0.96, 0.67} at 0x4f8640 (engine.md Model)",
    "1050": "idle / neutral rpm (engine.md Model)",
    "flags 0x1 / 0x2 / 0x4 / 0x8 / 0x20": "engine running / skid / airborne / starting / destroyed (i76tel.h, ent+0x454) - used only to skip free-rev frames",
}
GAPS = [
    "engine.md gives no rpm for an engine that is off, starting or destroyed; those frames are skipped, not predicted.",
    "The free-rev branch (skid / airborne / P-N) is path-dependent (eases at 2 x dt toward 1050 + 4950 x throttle, cap "
    "6000) and is not modelled here; a stateful oracle over consecutive free-rev frames would need the per-substep dt.",
]
CAVEAT = """A PASS supports the geared rpm equation and the ratio table on the frames the drive runs reach (reverse,
1st, 2nd, 3rd, idle; speeds 0..45 m/s). It does not test the free-rev branch, the engine-off value or the gear
decision itself (engine_gear does that). The idle 1050 is tested only as a constant on gear-1 frames."""
CLAIMS = [
    ("physics_UpdateEngine 0x46a320", "geared rpm equation 850 + 126.81 x R[g] x v and idle 1050 reproduce eng+0x1c on every grounded geared frame"),
    ("0x4f8640 gear ratio table", "R = 3.0 / 1.67 / 0.96 / 0.67 for gears 0 / 2 / 3 / 4"),
    ("eng+0x1c rpm, eng+0x08 gear, ent+0xac speed", "the three telemetry fields are the quantities the equation relates (same-frame)"),
    ("ent+0x454 bits 0x2 / 0x4", "skid / airborne frames are exactly the ones that leave the equation (skipped here, visible in engine_gear's variants)"),
]


def skip(inputs, row):
    f = int(inputs["flags"])
    if not f & 0x1:
        return "engine off (flag 0x1 clear)"
    if f & 0x8:
        return "engine starting (flag 0x8)"
    if f & 0x20:
        return "destroyed (flag 0x20)"
    if f & 0x4:
        return "airborne (flag 0x4): free-rev branch"
    if f & 0x2:
        return "skidding (flag 0x2): free-rev branch"
    if int(inputs["gear_lever"]) in (0, 2):
        return "lever P/N: free-rev branch"
    return None


def step(inputs):
    g = int(inputs["gear"])
    v = float(inputs["speed"])
    if g == 1:
        return {"rpm": IDLE_RPM}
    return {"rpm": RPM_BASE + RPM_PER_MS * RATIOS[g] * v}
