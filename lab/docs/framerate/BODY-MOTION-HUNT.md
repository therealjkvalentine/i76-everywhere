# Body-motion (chassis buzz) hunt — mechanism map & state

**Symptom (user, firsthand + measured):** at 60 fps the car body oscillates at ~1.6x the
frequency of 20 fps with smaller amplitude on rough ground, and carries a constant micro-wobble
on smooth road where 20 fps sits still. Airborne roll rate 1.24x. Car 5-9% slower at 60 fps.

## What is proven (2026-08-30/31)

1. **Not the global clock.** The frame clock module is `0x49C7C0–0x49CBA0`. The per-frame
   updater `0x49C8D0` computes `dt = now - prev` and stores: `0x5A7E78 = now`, **`0x5A7E7C = dt`**
   (forced to 0 on frame 1 via the `0x5A7E80` first-frame flag). `0x49C8C0` = `fld [0x5A7E74]; ret`
   is the "current time" accessor. Every clock global is consumed ONLY inside this module; dt is
   handed to physics as a pushed argument, not read globally. So a global dt clamp would just put
   physics in slow motion — the wrong fix. The frame-loop 1 Hz throttle (`0x403A3D fsub [0x504A28]`,
   clamp vs 1.0 at `0x4BC48C`) is unrelated (once-per-second task gate).

2. **The main integrator is dt-correct.** `integrate(dst,src,accel,dt)` at `0x438630` does
   `pos += vel*dt; vel += accel*dt`. Gravity (−9.8 immediate, `0x43A6A1`), acceleration, and the
   summed suspension force are all dt-scaled — confirmed by measurement (gravity ratio 0.984) and
   by the force-integration site `0x43B184..0x43B1A1` which does `fmul [esp+0x1B4]` (the dt arg).

3. **The four-wheel suspension path is mapped:**
   - Caller `0x43B090`: **4× unrolled** call to the per-wheel routine, wheel objects at
     `entity+0x3A8 / +0x3AC / +0x3B8 / +0x3BC` (live: 4 distinct heap pointers; NOT on the logic
     object). Then sums forces and integrates with dt at `0x43B184+`.
   - Per-wheel routine **`0x43C960`** (0x498 bytes): loads previous-frame state as **doubles**
     `fld qword [esi+0x40]`, `fld qword [esi+0x50]`; builds contact geometry, normalizes
     (`fsqrt`/`fdivp`), multiplies a coefficient `[ebp+0xC]` (ebp = sub-object at `[esi+0x70]`),
     calls transform `0x43A320` (pure 3x3 matrix mul, no dt) and `0x493CA0`.
   - Wheel-struct live layout (probe, `tools/wip/suspension/wheel-probe.ps1`): `+0x4C` is the
     active DYNAMIC field (compression/spring-length, ~1.66, visibly changing, differs per wheel);
     `+0x40`/`+0x50` are **doubles** (prev-frame state — the probe's float view showed -2/1.80969);
     `+0x108 = -0.21875`, `+0x138 = -0.738`, `+0x13C = -0.328` are static candidates.

## The hypothesis (research-backed)

Per the GTA V wheel-physics analysis (danielgp.com, FiveM #4059) and Open76's own `RaySusp.cs`,
the classic bug is a **damper term using a per-frame position delta without dividing by dt**:
damper force = c·(x_now − x_prev). At 60 fps the per-frame Δx is ⅓, so estimated wheel velocity is
⅓, damper force ⅓, then ×dt (⅓) per frame ×3 frames/‑20fps‑interval = **net damping ≈ ⅓** →
3× under-damped → higher-frequency, lightly-damped oscillation. Predicted frequency ratio √3 ≈
**1.73**; measured **1.6**. Independent 1990s corroboration: Local Ditch's uncapped-I'76 symptom
list includes "enemy cars constantly brake and flutter their front wheels."

The doubles at wheel `+0x40`/`+0x50` are the stored "previous state" this delta is computed
against. The fix pattern (GTA V #2): rescale the stored previous value so the delta matches the
dt the formula divides by — or, simplest given our precedent, dt-scale the damper coefficient by
(fps/20), exactly as the death-camera constant was scaled.

## Still open (the win condition)

> **Closed 2026-09-27 (annotated 2026-10-02; backlog P2-12).** There is no single damper coefficient to catch. The
> step dependence is `physics_ResolveGroundContact` 0x437230's projection/rest cycle — the body is moved up along
> the surface normal by the deepest wheel penetration in one go per step, roll and pitch rates are eased toward
> fixed targets at 2/s and set to exactly 0 when the velocity-against-normal test passes — a discrete contact model
> tuned for the stock ~42 ms step (`../i76-map/subsystems/framerate.md:73-85`, "Where the step dependence lives";
> capture 014: at rest on 62 % of frames with 25 ms steps, 11-40 % with 16.7 ms, 65 % again with a fixed 25 ms step
> at 60 fps). The fix is the fixed step (`I76_FIXED_STEP=24`) plus `I76_RENDER_INTERP`; body roll was judged good in
> the owner's 2026-10-02 playtest. The parameter sweep and in-process logger plans below are superseded.

- **The exact damper coefficient.** Not an inline `.rdata` constant in `0x43C960` (those are
  geometry: `1e-08` epsilons). Likely from the **WDF wheel-def file** (Open76: floats at
  +0x14=160,+0x18=100,+0x1C=70,+0x20=30,+0x2C=10) loaded into the wheel struct, OR a per-
  SuspensionType table in `.data` indexed by the `.vcf` field at VCFC-payload +0x2E.
- **Confirmation experiment (ready):** drive the desert at 60 fps and poke each static wheel-
  struct float ×3, watching roll-activity (`sweep-suspension.ps1` pattern + `wheel-probe.ps1`
  field list). The field whose ×3 restores 20fps-like settling is the damper. Requires the focus
  guard (`Ensure-GameFocus`, added to focuslib after synthetic keys were silently going to the
  desktop for two sessions).

## Anchors
- frame clock updater `0x49C8D0`; dt = `0x5A7E7C`; time accessor `0x49C8C0`→`[0x5A7E74]`
- integrator `0x438630`; gravity caller `0x43A650`; force-integrate `0x43B184` (`fmul [esp+0x1B4]`=dt)
- 4-wheel dispatch `0x43B090`; per-wheel `0x43C960`; wheel transform `0x43A320`
- wheel objs `entity+0x3A8/+0x3AC/+0x3B8/+0x3BC`; VCFC parser `0x4ADB90`, SuspensionType payload+0x2E
- immi i76fix frame hook `0x4039B8` (cross-ref); Local Ditch flutter symptom; GTA V danielgp analysis


## Honest status (2026-08-31, end of overnight push)

**Cornered, not caught.** The mechanism is well-established (above); the exact frame-coupled
constant is NOT, and my dynamic oracle proved unable to resolve it.

**What is SOLID:**
- The bug is real and frame-coupled — from the FIRST motion A/B (speed-governed, both surfaces,
  fps verified): 60fps desert roll reversals 15.2/s vs 20fps 9.7/s; smooth road a constant
  micro-wobble at 60 where 20 is still. Ratio ~1.6 (theory √3≈1.73 for per-frame spring impulse).
- Master clock decoded (0x49C8D0, dt=0x5A7E7C, consumed only in-module, handed to physics as an
  arg) → a global dt clamp would cause slow-motion, so the fix is a per-subsystem dt correction.
- Main integrator 0x438630 and the summed suspension force ARE dt-correct.
- Suspension path mapped: dispatch 0x43B090 → per-wheel 0x43C960 → transform 0x43A320; wheel
  objects at entity+0x3A8/+0x3AC/+0x3B8/+0x3BC; wheel-struct +0x4C = live compression, +0x40/+0x50
  = prev-frame doubles, +0x138/+0x13C = per-wheel static params.

**What is NOT established (and why):**
- WHICH constant is the frame-coupled damper. The live poke sweeps (`wheel-field-sweep.ps1`,
  `susp-verify.ps1`) are **inconclusive** — a noise-floor control (60fps stock measured twice)
  gave 0.729 vs 1.291 reversals/m, a 77% spread on an unchanged condition. Every A/B delta I saw
  (including a striking +0x13C ×3→18x in one early run) sits within that noise. I over-read that
  single uncontrolled A/B; with the control run it does not survive.
- **Root cause of the bad oracle:** PowerShell polling at ~8 ms with heavy per-sample RPM reads
  cannot cleanly sample a 15-22 Hz oscillation — under-resolved and jitter-dominated by
  construction. Also the 20fps arm repeatedly failed to drive under the harness (dist=5 m),
  so there was often no valid baseline.

*(superseded — see the closed note under "Still open")* **The correct next approach (do this instead of more PowerShell polling):**
1. **In-process per-frame logger.** A tiny injected routine (or a hook in the frame loop at the
   known clock site) records roll/pitch or wheel-compression (+0x4C) into a ring buffer every
   frame, dumped afterward. That samples at the true frame rate with no polling jitter, giving a
   clean signal to FFT / zero-cross for the natural FREQUENCY — which is excitation-amplitude
   independent, so it sidesteps the terrain/speed confound entirely.
2. Measure that frequency at 20 vs 60 fps (should differ ~1.6x — reproduces the known-good
   result cleanly), then sweep the wheel-struct params and watch which one, scaled, brings the
   60fps frequency onto the 20fps value. Frequency, measured in-process, is the oracle this hunt
   needs; roll-amplitude polled from PowerShell is not.
3. Then trace that param to its load source (WDF wheel-def file, or a SuspensionType table) to
   build a deployable patch.

**Lesson banked:** [[same-rate-control-run]] — I ran five elaborate A/B sweeps before once
measuring the same condition twice; the control run then invalidated all of them in one shot.
Run the control FIRST next time. And match the instrument's sample rate to the signal.
