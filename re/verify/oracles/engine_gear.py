r"""engine_gear: previous gear + this frame's speed, throttle, direction, lever -> this frame's gear (engine.md, Automatic gearbox).

Spec (engine.md "Model", physics_UpdateEngine 0x46a320 upshift, physics_AutoDownshift 0x46a140; static reading of
md5 9a232dcc, live-checked 2026-09-27 at 0.3 s sampling):
  gear g = eng+0x08: 0 reverse, 1 idle/neutral, 2 / 3 / 4 = 1st / 2nd / 3rd.
  Reverse input -> g 0. Lever P or N -> g 1 (lever = ent+0x104: 0 P, 1 R, 2 N, 3 D).
  Idle -> 1st as soon as the throttle is above 0.002 (0x46a518); 1st -> idle only below 0.002 throttle at under 0.5 km/h (0x46a2f1).
  Full throttle: upshifts at 62 / 106 km/h, kickdown below 60 / 98.
  Closed throttle (< 0.0625): upshifts at 25 / 40, downshifts at 12 / 31.
  One gear per substep at most. The "interpolated" shift curves (physics_ShiftCurveTest 0x46a0c0) never pass.
Reading used for what the spec leaves open (each listed in GAPS and settled by VARIANTS in the report):
  - any throttle >= 0.0625 uses the full-throttle thresholds (the curve test never passes, so there is no third set);
  - in the free-rev branch (skid 0x2 / airborne 0x4) the gearbox does not run (gear holds);
  - leaving reverse (gear_dir back to +1) goes to idle (g 1) first;
  - a frame with step_count substeps may shift step_count times (same end-of-frame speed used for each).
Why LAG 0 with gear@prev: physics_UpdateEngine is the last stage of physics_StepVehicle (physics.md "One substep"), so
the gear it writes is decided from the speed that substep has just integrated and the throttle applied this frame; the
telemetry's speed / throttle / gear are all end-of-frame values. The literal "previous frame's speed and throttle"
reading is VARIANT "prev-frame speed/throttle"; "prev-frame throttle only" keeps this frame's speed. The data cannot
pick between the throttle readings: every residual mismatch is a frame on which the throttle crossed 0.0625 and the
live shift landed one frame before or after the prediction, i.e. where the key event fell relative to the tick inside
that frame (frame-level telemetry cannot see that). Both readings are reported.
Telemetry fields (i76tel.h): gear = eng+0x08, speed = ent+0xac m/s, throttle = ent+0xe4 (-1..1, braking < 0),
gear_dir = ent+0xe8 (+-1), gear_lever = ent+0x104, flags = ent+0x454, step_count (substeps this frame).
"""

INPUTS = ["gear@prev", "speed", "throttle", "gear_dir", "gear_lever", "flags", "step_count", "speed@prev", "throttle@prev"]
OUTPUTS = ["gear"]
LAG = 0
KIND = "pass"

# spec constants (engine.md Automatic gearbox / Model)
FULL_UP = {2: 62.0, 3: 106.0}        # km/h: 1st -> 2nd, 2nd -> 3rd at full throttle
FULL_DOWN = {3: 60.0, 4: 98.0}       # km/h: 2nd -> 1st, 3rd -> 2nd kickdown below
CLOSED_UP = {2: 25.0, 3: 40.0}
CLOSED_DOWN = {3: 12.0, 4: 31.0}
CLOSED_THROTTLE = 0.0625
IDLE_TO_FIRST_THROTTLE = 0.002       # idle -> 1st above this
FIRST_TO_IDLE_THROTTLE = 0.002       # 1st -> idle below this ...
FIRST_TO_IDLE_KMH = 0.5              # ... and under this speed
KMH = 3.6                            # unit conversion m/s -> km/h (not a spec constant)

# readings the spec leaves open; the report runs the alternatives as VARIANTS
HOLD_IN_FREE_REV = True
USE_PREV_INPUTS = False              # both speed and throttle from frame N-1 (the literal "previous frame" reading)
USE_PREV_THROTTLE = False            # speed from frame N, throttle from frame N-1 (input applied after the tick)
SHIFTS_PER_FRAME = None              # None = step_count; an int fixes it

CONSTANTS = {
    "62 / 106": "full-throttle upshift km/h (engine.md Automatic gearbox)",
    "60 / 98": "full-throttle kickdown km/h (engine.md)",
    "25 / 40": "closed-throttle upshift km/h (engine.md)",
    "12 / 31": "closed-throttle downshift km/h (engine.md)",
    "0.0625": "closed-throttle boundary (engine.md)",
    "0.002": "idle <-> 1st throttle test (engine.md, 0x46a518 / 0x46a2f1)",
    "0.5 km/h": "1st -> idle speed test (engine.md, 0x46a2f1)",
    "3.6": "m/s -> km/h unit conversion only",
}
GAPS = [
    "engine.md gives thresholds for full and closed throttle only; the oracle treats every throttle >= 0.0625 as the "
    "full set (the interpolated ShiftCurveTest never passes). Partial-throttle frames (0.0625..0.99) are 120-383 per run.",
    "engine.md does not say whether the gearbox runs in the free-rev branch (skid / airborne). Default here: it does "
    "not (gear holds); VARIANT 'gearbox runs while skidding' is the other reading. The data decides (see report).",
    "engine.md does not say what gear follows reverse when gear_dir returns to +1; assumed idle (g 1); the runs show "
    "0 -> 1 at 0-0.8 km/h, consistent.",
    "The 1st -> idle rule (throttle < 0.002 and v < 0.5 km/h) is only ever reached through the contact model's rest "
    "snap: braking from 4-5 km/h the velocity goes to exactly (0, 0, 0) in one frame and the gear drops to 1 on that "
    "frame (e.g. run 211111 idx 630 -> 631, run 212443 idx 1864 -> 1865). physics.md names no rest-snap speed; the "
    "snap happens from 1.1-1.5 m/s at both 20 and 60 fps. The 0.5 km/h figure itself is therefore untested.",
    "Which frame's throttle the gearbox sees at a 0.0625 crossing is undecidable from frame-level telemetry: the "
    "residual mismatches (3-9 per run under the default, 0-1 under 'prev-frame throttle only') are all such crossings "
    "and the live shift lands within one frame either way. A per-substep trace of ent+0xe4 would settle it.",
    "Two single-frame throttle blips to 0.085 / 0.096 in 3rd gear at 61 km/h (run 212443 idx 1246, run 212619 idx "
    "323) produced no kickdown under either reading, although the full-throttle set (kickdown below 98 km/h) applies "
    "above 0.0625 as the spec reads; a sustained 0.59 did kick down (run 212619). Either the kickdown's throttle test "
    "is higher than 0.0625 or it needs more than one substep; engine.md does not say.",
    "Frame 41 -> 42 of run 211111 shifts 2 -> 4 inside one step_count = 2 frame: two shifts in two substeps, as the "
    "'one gear per substep' rule allows; the 'one shift per frame' variant loses exactly those frames.",
    "Frame 1 of every run (sim_time 0.2, the clamped 0.2 s load frame, step_count 5, flag 0x20000 set only there) keeps "
    "gear 1 although throttle = 0.219 > 0.002 and frame 0 reports speed 0 while the car is already at 61 km/h: a "
    "load-frame artefact (frame 0's telemetry is stale), one frame per run, counted as a mismatch.",
]
CAVEAT = """A PASS supports the shift-threshold table on the throttle regimes the drive runs cover (full, closed, braking,
some partial) and the reverse / idle rules, within one frame: every residual mismatch is a 0.0625 crossing where the
live shift lands one frame off. Frames where the gear held because the car was skidding (the 1 -> 2 shift at 32 km/h
after a wheelspin start, which also explains engine.md's "unexplained 1 -> 2 at 28 km/h") are predicted by the hold
reading, which the spec does not state: the 7-17 point gap between the default and the 'gearbox runs while skidding'
variant is a finding about the engine's branch order, not a confirmation of spec text. The sub-frame order of two
shifts in one multi-substep frame is approximated with the end-of-frame speed."""
CLAIMS = [
    ("physics_UpdateEngine 0x46a320 (upshift)", "upshifts at 62 / 106 km/h full throttle, 25 / 40 closed; idle -> 1st above 0.002 throttle"),
    ("physics_AutoDownshift 0x46a140", "kickdown below 60 / 98 km/h full throttle, 12 / 31 closed"),
    ("0.0625 closed-throttle rule", "the two threshold sets switch at throttle 0.0625 (braking counts as closed)"),
    ("ent+0xe8 gear_dir, ent+0x104 gear_lever", "reverse direction forces gear 0; lever P/N forces gear 1"),
    ("ent+0xe4 throttle_applied, ent+0xac speed", "the inputs the gearbox reads, same frame"),
]


def _shift_once(g, v_kmh, thr, gear_dir, lever):
    if gear_dir < 0:
        return 0
    if lever in (0, 2):
        return 1
    if g == 0:
        return 1
    closed = thr < CLOSED_THROTTLE
    up = CLOSED_UP if closed else FULL_UP
    down = CLOSED_DOWN if closed else FULL_DOWN
    if g == 1:
        return 2 if thr > IDLE_TO_FIRST_THROTTLE else 1
    if g == 2:
        if thr < FIRST_TO_IDLE_THROTTLE and v_kmh < FIRST_TO_IDLE_KMH:
            return 1
        return 3 if v_kmh >= up[2] else 2
    if g == 3:
        if v_kmh < down[3]:
            return 2
        return 4 if v_kmh >= up[3] else 3
    if g == 4:
        return 3 if v_kmh < down[4] else 4
    return g


def step(inputs):
    g = int(inputs["gear@prev"])
    if USE_PREV_INPUTS:
        v = float(inputs["speed@prev"])
        thr = float(inputs["throttle@prev"])
    elif USE_PREV_THROTTLE:
        v = float(inputs["speed"])
        thr = float(inputs["throttle@prev"])
    else:
        v = float(inputs["speed"])
        thr = float(inputs["throttle"])
    gear_dir = float(inputs["gear_dir"])
    lever = int(inputs["gear_lever"])
    flags = int(inputs["flags"])
    if HOLD_IN_FREE_REV and flags & (0x2 | 0x4):
        return {"gear": g}
    n = SHIFTS_PER_FRAME if SHIFTS_PER_FRAME else max(1, int(inputs["step_count"]))
    for _ in range(n):
        g2 = _shift_once(g, v * KMH, thr, gear_dir, lever)
        if g2 == g:
            break
        g = g2
    return {"gear": g}


VARIANTS = [
    ("gearbox runs while skidding", {"HOLD_IN_FREE_REV": False}),
    ("prev-frame speed/throttle", {"USE_PREV_INPUTS": True}),
    ("prev-frame throttle only", {"USE_PREV_THROTTLE": True}),
    ("one shift per frame", {"SHIFTS_PER_FRAME": 1}),
]
