# Era envelope: stock = what stays the same across 1997 machines (2026-10-15)

This replaces the single W95-18 reference ([W95-18-BASELINE.md](W95-18-BASELINE.md), superseded).
- **Where:** everything was measured on the lab twin. The daily driver and golden were not touched.
- **Full write-up:** lab `docs\ERA-ENVELOPE-2026-10-15.md`.
- **Raw data:** lab `captures\envelope-20261015\`.

## Definition
- **Owner's ruling:** stock = behaviour that is invariant across valid era configs.
- **The configs:** the unmodified exe on Windows 95's measured **1 ms** GetTickCount at the 86Box software-renderer frame
  rates:
  - E13 = 13.3 fps, the P166's default-detail rate; E10 = 10 fps, below it;
  - E25, E29 (29.5) and E33 = 25-33 fps, around the P166 low-detail reference (29-34 fps).
- The Glide/Voodoo emulator numbers are not used.
- **Stepper rule:** one physics step per frame from 25 fps up (40 / 34 / 30 ms); 2 × 37.6 ms at E13; 2-3 steps at E10.
- **Check:** every run's frame log was read back. The fps held to ±0.01, sim dt came in whole ms, and the step pattern was
  the expected one.

## Result (n = 5 boots per condition, A/A twin E29aa; T04 n = 2-3, cut by the owner's playtest)

| behaviour | across E10-E33 | class | best-wide / TEST-next | candidate |
|---|---|---|---|---|
| gravity | 9.800 everywhere | invariant | inside | inside |
| steady handling (yaw) | 0.799-0.808 rad/s | invariant | 0.792 / 0.86 ±0.22 | 0.90 ±0.19 (next-based outliers, open) |
| acceleration 0-30 m/s | 5.50-5.70 s, quicker at lower fps | weak artefact (3.5 %) | inside | inside (e33 end) |
| T06 ramp: clears / distance / apex | 96-100 % / 73-80 m / 29.2-29.6 m | invariant | inside | inside |
| T05 canyon: clears on the centre line | 95-100 % | invariant | inside | inside |
| T05 canyon: jump distance | 197-249 m | artefact (step) | 254 m (at the top) / 248 | 210 m |
| **T05 canyon: car turned over after landing (descents)** | E33 0/15, E29 1/30, E10 2/15, E13 2/13, **E25 7/11** | **artefact (step)** | **9/10 / 7/10, car lost 4/5 boots: outside** | **0/24** |
| roll wobble on flat road | calm (≤0.8 reversals/s; 0 at 2-3 substeps) | invariant | 12 /s limit cycle in some boots: outside | calm |
| barricades knocked (T05, 10 bars) | 7.8 in every profile | invariant | 6.6: outside | 6.6 (the box switch) |
| T04 race laps | Patriot 44.2-45.6 s, Knight 46.3-47.6 s | invariant within resolution | inside | inside |

## The landing bug
- **What kills the car (static: `physics_CheckImpact` 0x436ff0 → `object_Destroy` 0x4652b0).** The car is not killed by
  damage. It is killed by the stock **at-rest rollover rule**: an inverted car whose pitch and roll rates have dropped below π/5
  is destroyed. Health is never read, which is why the god flag does not help.
- **How the car turns over.** It bounces after the 60 m/s canyon landing. While flag 0x200 ("just landed") is held by the high
  rates, the attitude solver eases it toward its hanging wheels instead of snapping it to the ground, so the car rolls over.
- **The cause is the physics step size, not the 120 fps cadence or any proxy switch:**
  - best-wide capped at 24 fps, one 41.7 ms step on every frame, still dies;
  - 27.5 / 30 / 33 ms steps give 0/9 each.
- **The turn-over rate grows with the step.** Inside the envelope it runs from 0 % (30 ms, a P166 at low detail) to 64 %
  (40 ms, E25). best-wide's 41.7 ms is past the worst era machine.

## Candidate
- **Re-baselined on retail (2026-10-17, [ENVELOPE-RETAIL-REBASE.md](ENVELOPE-RETAIL-REBASE.md)): unchanged.**
  - "30 ms = a P166 at low detail" came from the Gold exe. Retail 1.0's median step there is 27 ms in melee and
    32-35 ms in missions. Retail's step follows the scene; ours does not.
  - A retail step list (side build, `I76_STEP_SEQ`) matches the step rows of its own context (5 / 5). But it turned the
    car over on the placed T05 landing 6 / 25 times, against 0 / 33 at 30 ms.
  - A fixed 32 ms with the frame-rate fixes hit the ramp lip 7 / 27 times.
  - So 30 ms stays, now as "the step at which the fix set lands T05 cleanly". It is 3 % short on take-off speed against
    retail (50.1 vs 51.6 m/s, n 33 vs 7).
  - The handling rows (accel, yaw, ramp foot speed) fail the same in every profile. That is the lab car, not the pacing.
- **Launcher:** lab twin `TEST-envelope-candidate.bat` (owner test 42).
- **What it is:** TEST-next with
  - `I76_FIXED_STEP=33.3333` (30 ms: the P166 low-detail end of the envelope);
  - `I76_REF_FPS=30`;
  - `I76_AI_STOCK_CLOCK=1.5` with `I76_AI_STOCK_CLOCK_FPS=30` (1.5 ms is the proxy's minimum tick).
- **Measured:**
  - no descent turned over (0/24);
  - calm body;
  - every other row inside the envelope.
- **Open:**
  - barricades 6.6, from `I76_BREAKABLE_BOX`: a check without the switch was queued and not run;
  - the next-based yaw outliers;
  - T04 rounds 3-5;
  - combat.
