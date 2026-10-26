r"""step_count: the frame's physics dt -> number of player-vehicle substeps, per the run's step mode (physics.md, framerate.md).

Spec:
  physics.md: entity_TickVehicle 0x463800 splits each frame's dt into substeps with the stepper at entity+0x444
  (simclock_StepperBegin 0x49cc20, rate 20, so max 50 ms).
  framerate.md "Step rate is the physics' real clock": the GetTickCount frame dts are split by the stepper's floor(dt x 20) + 1.
  framerate.md: I76_FIXED_STEP=<rate> replaces that with an accumulator (I76_FIXED_STEP=24 reproduces stock 20 fps).
Mode comes from the run's manifest.json env_switches: I76_FIXED_STEP present -> fixed accumulator at that rate (stateful,
reset per run: acc += dt; n = floor(acc x rate); acc -= n / rate), else stock floor(dt x 20) + 1.
Telemetry fields (i76tel.h): sim_dt = simclock_sim_dt 0x4fe420, the frame's physics dt (equal to dt = 0x4fe428 on
every frame of the drive runs); step_count = substeps the player's tick ran this frame (-1 unknown). LAG 0.
"""

INPUTS = ["sim_dt"]
OUTPUTS = ["step_count"]
LAG = 0
KIND = "pass"

STOCK_RATE = 20.0           # physics.md: simclock_StepperBegin rate 20; framerate.md floor(dt x 20) + 1

MODE = "stock"
FIXED_RATE = None
_acc = 0.0

CONSTANTS = {
    "20": "stepper rate (physics.md entity_TickVehicle / simclock_StepperBegin 0x49cc20; framerate.md floor(dt x 20) + 1)",
}
GAPS = [
    "INSTRUMENT, not game (found by the poke runner 2026-10-02): in stock mode the proxy does not count substeps, it "
    "computes step_count = floor(sim_dt x 20) + 1 itself (music-fix/strlkproxy.c:2011); only under I76_FIXED_STEP is the "
    "field the accumulator's real count (g_step_acc). So on stock20 / stock60 runs this oracle checks the proxy's formula "
    "against the same formula: a tautology, and its PASS says nothing about entity_TickVehicle. Setting the 0.05 s substep "
    "immediate to 0.025 live left step_count on the stock formula. The game-side observable is a per-frame count of "
    "physics_StepVehicle calls (the census's per_substep series does exactly that: 1 and 2 steps per frame at stock20).",
    "i76tel.h says the stock count is 'capped at 20'; neither physics.md nor framerate.md names the cap, so it is not "
    "applied here. It cannot matter on these runs (the clamped dt tops out at 0.2 s -> 5 steps).",
    "The fixed-step accumulator's exact rule (carry, rounding) is not written in framerate.md; the accumulator here is "
    "the plain reading. No drive run uses I76_FIXED_STEP, so that branch is untested.",
    "Which dt the stepper sees (sim_dt 0x4fe420 vs dt 0x4fe428) cannot be told apart on these runs: the two columns are "
    "equal on every frame.",
]
CAVEAT = """On stock-mode runs (every run so far) a PASS here is a tautology: the proxy's step_count IS floor(sim_dt x 20) + 1
(strlkproxy.c:2011), so the oracle confirms only that the telemetry's sim_dt and step_count columns are consistent with
each other. The stepper rule itself is supported by the census, not by this oracle: physics_StepVehicle and the
per-substep functions read 1 or 2 calls per vehicle per frame at stock20 in proportion to this very formula (README
'Per-substep multipliers'). A fixed-step run (I76_FIXED_STEP) would make the field a real count and this oracle a test.
It does not test the 20-step cap or non-player vehicles."""
CLAIMS = [
    ("step_count telemetry field (stock mode)", "consistent with sim_dt under floor(sim_dt x 20) + 1 - the proxy's own formula, not a count (tautology; see GAPS)"),
    ("simclock_sim_dt 0x4fe420", "the dt the proxy's formula uses (indistinguishable from 0x4fe428 here)"),
]


def configure(manifest):
    global MODE, FIXED_RATE
    env = (manifest or {}).get("env_switches", {}) or {}
    if "I76_FIXED_STEP" in env:
        MODE = "fixed"
        try:
            FIXED_RATE = float(env["I76_FIXED_STEP"])
        except (TypeError, ValueError):
            FIXED_RATE = 24.0
    else:
        MODE = "stock"
        FIXED_RATE = None


def reset():
    global _acc
    _acc = 0.0


def skip(inputs, row):
    if int(row.get("step_count", -1)) < 0:
        return "step_count unknown (-1)"
    return None


def step(inputs):
    global _acc
    import math
    dt = float(inputs["sim_dt"])
    if MODE == "fixed" and FIXED_RATE:
        _acc += dt
        n = int(math.floor(_acc * FIXED_RATE))
        _acc -= n / FIXED_RATE
        return {"step_count": n}
    return {"step_count": int(math.floor(dt * STOCK_RATE)) + 1}
