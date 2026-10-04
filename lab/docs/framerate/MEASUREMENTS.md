# Frame rate - every measured result

*Companion to [README.md](README.md), which carries the story and how to enable it, and
[DEAD-ENDS.md](DEAD-ENDS.md), which records what was tried and did not work.*

**This file holds numbers, not narrative.** Every table below came from a run repeatable with
the scripts in `tools/framerate/`. Retracted numbers are not quietly deleted - the retraction
lives in [DEAD-ENDS.md](DEAD-ENDS.md), because which measurements failed is worth as much as
which held.

---

## 3. What is NOT frame-rate dependent (measured)

Terrain-independent methods; see [../PHYSICS-60HZ.md](../PHYSICS-60HZ.md) for the full working.

| system | 20 Hz | 60 Hz | verdict |
|---|---|---|---|
| **gravity / falling** | −9.893 m/s² | −9.735 m/s² | dt-correct (ratio 0.984) — both are real gravity |
| acceleration curve a(v) | — | — | indistinguishable; the 60 Hz curve sits **inside** the spread of three separate 20 Hz runs |
| engine clock vs real time | 0.9943 | 0.9991 | honest at both rates |
| engine dt (FFB block `0x4F2488`) | ~0.050 s | 0.0156 s | tracks true frame time |
| weapon fire rate (30cal MG) | 9.7 rds/s | 13.8 rds/s | timer-driven (per-frame would be 3×) |
| AI top speed (Taurus) | 36.4 m/s | 33.2 m/s | no "35 mph cap" — 74 mph at 60 Hz |
| **Mission 5 canyon jump** | clears | **clears** | confirmed by play, 2026-08-09 |

Gravity is an **immediate operand** — `push 0xC11CCCCD` (−9.8f) at `0x0043A6A1`, pushed with
the velocity vector into `call 0x438630`. That is why data watchpoints never catch it.

## 4. What IS still frame-rate dependent — the fix list

Four behaviours reported from play at 60 fps (2026-08-09). All four are real as *observations*;
what has changed since is where the cause can be. Status as of the 2026-08-09 measurement pass:

1. **Post-death rotating camera spins too fast.** — ✅ **CONFIRMED FRAME-COUPLED AND FIXED
   (2026-08-10).** The first of the four bugs actually repaired. Full write-up below
   ("The death camera: confirmed, diagnosed and fixed").
2. **Chassis roll is too fast.** — **MEASURED 2026-08-17: the user's perception is real, and
   it is FREQUENCY, not amplitude.** Body-attitude traces over the same ground at matched speed
   (`body-motion.ps1` + `analyze-motion.py`, 2 reps/rate, fps verified 20.0/60.0):

   | rate | surface | v | body activity deg/s (roll/pitch) | roll direction changes /s |
   |---|---|---|---|---|
   | 20 | desert | 17.2 | 18.0 / 18.7 | 9.7 |
   | 60 | desert | 17.7 | 11.8 / 13.2 | **15.2** |
   | 20 | road | 4.2 | ~0 (dead still) | 4.5 |
   | 60 | road | 4.5 | 0.6 (constant small wobble) | **21.6** |

   At 60 fps each bump event is SMALLER but the body reverses direction ~1.6x more often on
   rough ground, and on smooth road it carries a constant fast micro-wobble where 20 fps is
   motionless. Chunky ~10 Hz rocking becomes 15-22 Hz buzz — which the eye reads as "the car
   animation is too fast". Signature of per-frame suspension stepping (each frame contributes
   a jitter quantum; 3x frames = 3x the frequency). This measurement supersedes the earlier
   partial result (a steering step on smooth ground rolls the same at both rates - still true,
   but it tested the wrong path). Caveat: the road-surface crossing counts partly reflect more
   samples crossing near zero; the desert numbers and the road activity level (0.6 vs 0.1
   deg/s) are the robust part. Fix target: the suspension update's per-frame constants
   (spring/damper step) - same class as the death-camera fix (scale by 20/actual-fps).

3. **Over-rotates in mid-air** — died on the bridge after rotating too far. *The integrator is
   NOT the cause* (measured: gain 0.85, not 3.0). But at 20 Hz three of four jumps left the
   ground with essentially **zero** spin while at 60 Hz all four had 0.17–0.79 rad/s, so the spin
   is *acquired* differently. Prime suspect: **contact/suspension impulses applied per frame**,
   which get 3× the kick over the same time on the ground. Still the best candidate for the real
   canyon-jump bug — the jump never failed because the car fell short (gravity is dt-correct, §3)
   but because it leaves the ramp rotating.
   *(2026-10-02: i76-map reads the contact model as running once per substep from `physics_StepVehicle` (0x43a104)
   and once per frame through `physics_SnapToGround` 0x43d070 (`../i76-map/subsystems/framerate.md:75-85`), so the
   per-frame kick is the SnapToGround pass and the fixed step is the principled fix. Not yet re-measured under
   `I76_FIXED_STEP=24` — backlog P2-04: `tools/framerate/airborne-test.ps1` + `analyse-airborne.py`, stock 20 vs
   fixed 60, A/A first; angular velocity at lift-off should match 20 fps.)*
4. **The sky moves too fast.** *(closed 2026-09-27: render-side constant at 0x405200 / 0x405455, fixed by `I76_FRAMERATE_FIXES`; see the note at the top of "The sky" section)* — *render-computed, not freezable via data (2026-08-10)* — and
   now instrumented (2026-08-17): `sky-motion.ps1` measures cloud scroll in px/s from screenshots
   (2-D shift search over the sky band; no human watcher). First finding: **with the car parked
   at 60 fps the sky translates ~0-0.8 px/s over 5 s gaps — essentially still.** So the
   too-fast effect is probably tied to DRIVING (the sky's response to camera/car motion being
   frame-coupled), not an autonomous scroll. Next measurement: sky-band tracking while the
   pursuit harness holds a straight line at fixed speed, 20 vs 60. (Protocol notes: measure
   only after control is acquired and the car re-stopped - the intro fly-through's camera cuts
   read as huge false shifts; and give the wrapper the mission-entry retries, the 20 fps arm
   was lost to one flake.)
5. **Collisions pass through objects — MEASURED 2026-08-17, and it is NOT frame-rate
   dependent.** The hypothesis (worse at high fps) is REFUTED. Automated A/B on the training
   cactus field (`cactus-ab.ps1`: pure-pursuit weave through fresh saguaros with exact ODEF
   coordinates, hit = v_min < 0.6·v_before within 1.8 m of the trunk):

   | rate | speed | valid approaches | hit rate |
   |---|---|---|---|
   | 20 fps | 15 m/s | 10 | 70% |
   | 60 fps | 15 m/s | 12 | 67% |
   | 20 fps | 21 m/s | 5 | 20% |

   At matched 15 m/s the two rates are statistically identical (7/10 vs 8/12 — not significant,
   and the trivial difference runs OPPOSITE to the predicted "60 fps tunnels more"). The variable
   that actually governs pass-through is **speed**: the collision test samples proximity per tick
   against a ~0.45 m trunk, so faster travel skips over it more often — ~1/3 miss at 15 m/s rising
   to ~4/5 miss at 21 m/s, at EITHER frame rate. So the user-reported "~2/3 pass-through at 60 fps"
   is real but speed-driven (they play at speed), not a 60 fps regression; it is a pre-existing
   1997-era engine bug. **Conclusion: collision comes OFF the 60 fps blocker list.** Fixing it at
   all would mean a swept/continuous collision test (a general enhancement, unrelated to frame
   rate). Raw data: `captures/cactus/*.csv`; method and the several harness bugs found the hard
   way are in the commit log (reverse-gear steer inversion, intro-autopilot throttle hold, etc.).

## The sky: why freeze-hunting failed, and where to look next (2026-08-10)

> **Closed 2026-09-27 (pointer added 2026-10-02).** The cloud scroll is `u = fmod(u - 1/(1001 - s), 1)` (and `v`
> alike) once per call with no dt, at 0x405200 and 0x405455..0x4054a9 (s = 0x504c30 = 0.0078):
> `../i76-map/subsystems/framerate.md:36` row 4. The proxy's `I76_FRAMERATE_FIXES` puts it on the 20 Hz grid —
> measured 0.0300 /s at 60 fps = stock 20 fps (stock 60 fps: 0.0899) — and "sky confirmed in play"
> (`../i76-everywhere/music-fix/README.md` switch table). No render-path anchor is needed; the section below is
> the record of why the data-side hunt could not find it.

Spent a long session trying to find and freeze the sky's scroll value with a human watching.
It did not yield a fix, but it ruled out enough to point the next attempt the right way. Recorded
so nobody repeats the freeze grind.

**What was ruled out:**

- **Not a static per-frame value.** The `find-perframe.ps1` values (`0x501858`, `0x501918`,
  `0x644334`, `0x59BCD4`, `0x4F70F8`, `0x524550`) were each frozen with a human watching — none
  stopped the sky.
- **Not a frame-linear float in the heap.** `sky-hunt.py` snapshots all writable memory three
  times and keeps float32 values advancing linearly with the frame count. Freezing **all 652** of
  them at once did not stop the sky.
- **Not a frame-linear int either (as far as could be tested).** Adding integer scrollers to the
  scan gave ~950 more candidates, but freezing them all crashed the game — some frozen counter in
  the exe's data is load-bearing. Restricting to heap-only still crashed on a heap range
  (`0x4C2F0B4..0x4DD39DC`), and every crash reallocates the heap, forcing a rescan. Group-by-group
  freezing (crash-safe, ≤120 at a time) is the method that survives, but it never reached a group
  that stopped the sky before the session ended.
- **The frame counter's readers are a clock subsystem, not the sky.** `0x5A7E1C` is read from five
  sites, all in `0x49C7xx`–`0x49CCxx`: a getter (`0x49C7D0`), the per-frame `inc` (`0x49C921`),
  the reset, and two table lookups that use `0x5A7E1C` as an array base. None touch the sky.

**The conclusion:** the sky scroll is almost certainly **computed at render time** (e.g. a UV or
rotation offset derived from a time/frame value each frame) rather than stored-and-advanced —
which is exactly why no stored value freezes it. The one-time "sky stopped" on a 60-value group
early on never reproduced and was most likely coincidence with a heap that then reallocated.

**Where the next attempt should start:** get a DATA ANCHOR in the render path, not another memory
sweep. Find the sky's texture or mesh handle (it has a name — cross-reference the asset bible /
`geo_cache_acquire` by name), then hardware-watchpoint the matrix/UV it feeds and trace the
per-frame write back to its constant, the same shape as the death-camera fix. The tooling is all
in place (`tools/framerate/sky-hunt.py`, `sky-bisect.ps1` crash-safe group mode); what was missing
is the anchor.

**Cost/benefit note:** the sky is cosmetic. The death camera (a comparable per-frame animation)
was fixed in one pass because its value sat at a *static* address that xref'd directly; the sky's
does not, which turns it into an open-ended render-path hunt. Worth doing, but not a quick win.

The useful summary: **the physics integrator is dt-correct on every axis** (linear, yaw, roll,
pitch — see §"State of the roll/pitch hunt"). Two of the four reports are pure animation, and the
other two now point at the contact solver rather than at integration.

## The death camera: confirmed, diagnosed and fixed (2026-08-10)

**The first frame-coupled bug repaired end to end.** Worth reading as a template — measure, find
the variable live, xref the code, patch the constant, re-measure.

### Dying on demand

Melee AI cannot kill the player (400 s of deliberate ramming left the entity untouched), which
blocked this for weeks. The unlock was a community find: **`CTRL+ALT+X` detonates the player's
car**, and it can be sent from a script — `Send-SelfDestruct` in `autotest/lib/cheatlib.ps1`.
Deaths are now automated; no human needed.

**Timing gotcha:** the orbit window is only ~5 s, because the mission then ends into the
STANDINGS screen where the frame counter `0x5A7E1C` stops advancing. A fixed 8 s capture measured
*0.0 fps and 0 degrees of orbit* — all standings screen. `tools/framerate/death-orbit.ps1`
samples from the instant of detonation and stops when the counter stalls.

### The measurement

| | deg/s | deg/frame |
|---|---|---|
| 20 Hz | −143.3 | −7.06 |
| 60 Hz | −475.1 | −7.87 |
| ratio | **3.32** | **1.12** |

deg/s scales with frame rate, deg/frame does not → **frame-coupled**.

**The rate is not constant, and averaging the whole window hides it.** The orbit eases in over
~0.6 s (≈5 → 8 deg/frame) and the 20 Hz run decays late; whole-window means gave a nonsensical
deg/frame ratio of 1.28 and a first quick estimate was off by 25% (166 vs 143 deg/s). Use the
**median of per-frame steps after the ramp-in**.

### The cause

Found by scanning the camera region live *during* an orbit (`find-camera-angle.ps1`) — the
constant could not be identified statically, because the measured 8.0 deg/frame matches **45
different float32 `8.0` literals** in the exe. The scan gave `0x4C291C`, advancing 0.14098
rad/frame = 8.08 deg/frame. That is a *static* address, so its writer xrefs directly:

```
0x00405C16  fild  dword [0x53679C]   ; yaw step - an INTEGER NUMBER OF DEGREES
0x00405C1C  fmul  dword [0x4BC528]   ; * -0.017453292  (= -1 degree in radians)
0x00405C22  fsubr dword [0x4C291C]   ; angle - that
0x00405C28  fst   dword [0x4C291C]   ; store back
```

`angle -= degrees × DEG2RAD`, **once per frame, with no frame delta-time anywhere.** Pitch gets
the same treatment via `0x536794`/`0x4C2918`, and the whole routine is inlined twice (identical
copies at `0x405BC0` and `0x4061D0`) — which is why `0x4BC528` has exactly four references.

### The fix

Those four references are its **only** ones in the binary, so the constant is camera-private and
safe to scale. (Its sibling `+1 degree` at `0x4BC52C` has **11** references spread across the
exe — do **not** touch that one.) Scaling it by 20/target makes a frame's step equal what 20 Hz
used to give:

```
0x4BC528 (file offset 0x0BB928):  -0.017453292  ->  -0.005817764   (-1.0 deg -> -0.3333 deg)
```

A pure **data** patch — no code moved, nothing relocated. `tools/framerate/patch-camera-rate.ps1`
(`-TargetFps`, `-Restore`, `-Status`; keeps `i76.exe.camorig`).

### Verified

| | deg/s | deg/frame |
|---|---|---|
| 20 Hz original | −143.3 | −7.06 |
| 60 Hz broken | −475.1 | −7.87 |
| **60 Hz patched** | **−144.4** | **−2.39** |

−144.4 against the original −143.3 — a ratio of **1.008**. The death camera now orbits at its
intended speed at 60 fps.

**Caveat, stated plainly:** this tunes the camera for *one* frame rate rather than making it
truly dt-correct. Real dt-scaling needs a code cave to multiply by the frame time. For the
fixed-60 build this project settled on, the constant is the right trade — and `-TargetFps`
retunes it if anyone later breaks the 60 fps ceiling. It also corrects **all** camera rotation,
not just the death orbit, since every camera axis runs through this one constant.

### Where the bug is NOT: yaw is fine (measured)

`tools/framerate/angular-test.ps1` + `analyse-angular.py` measured steering rotation with **matched
input** (applied steer `+1.000` at both rates, verified from the engine's own `+0xE0`):

| | 20 Hz | 60 Hz |
|---|---|---|
| actual rotation d(heading)/dt | 0.953 rad/s | 1.054 rad/s |

**Yaw is frame-rate independent** (~10%, the same spread as every linear quantity). Driving
confirms it: the car is described from play as "mostly fine and drivable" at 60.

*(A first attempt at this test tapped the steering key instead of holding it and produced yaw
rates 15× apart — meaningless. Hold input, and prove comparability from the applied-steer value
before believing any angular number.)*

### So the bug is not the driving integrator

None of the four reports are yaw. When this was written the reasoning went: the remaining
suspects must be **the roll/pitch axes** — which steering does not drive, so they never entered
the yaw measurement — or **visual animation systems** advanced per frame.

Half of that held. Roll and pitch have since been measured directly and are **also dt-correct**,
so the split is now: two visual animation systems (death camera, sky), and a contact/suspension
path that changes how much spin a car carries off a ramp. The integrator is exonerated on all
four axes.

### State of the roll/pitch hunt (2026-08-09) — the blocker is cleared, and roll/pitch are FINE

**Orientation is readable, and it was in the eye transform the whole time.** `0x5FCDC4` is not
just "position + a matrix"; read as ONE atomic block its layout is

| floats | meaning |
|---|---|
| `[0..2]` | world position |
| `[3..5]` | **right** vector |
| `[6..8]` | **forward** vector |
| `[9..11]` | **up** vector |
| `[12..14]` | scale (`1, 1, 0.8`) |

Roll is the tilt of `up` about `forward`, measured against world-up projected perpendicular to
`forward`. `Mem-EyeAngles` in `autotest/lib/memlib.ps1` returns pitch/yaw/roll from it.

**Two earlier claims in this section were wrong and are retracted:**

- *"The cockpit camera decouples from the chassis in flight — exactly 0.000 rad/s at both frame
  rates."* It does not. Measured properly it tracks pitch and roll in the air all the way through
  a jump. A reading of exactly 0.000 was the instrument, not the engine.
- *"Chassis orientation is not stored as a matrix; find this first, everything is blocked on it."*
  Nothing was blocked on it. The chassis world matrix is indeed **not** in the entity struct — a
  scan of the first 0x2000 bytes finds only *local part* transforms (four wheels at stride `0x54`,
  plus a steering matrix at `+0x91C` showing the front wheels' 5° deflection) — but the eye
  transform carries the attitude, so the entity's own matrix was never needed.

**Read matrices in a single `ReadProcessMemory` call.** Reading 12 floats one at a time spreads
the read over several milliseconds; a moving camera updates midway and the "matrix" comes back
non-orthonormal (rows dotting to 0.97 instead of 0). That torn read is almost certainly what
produced the retracted claims above. `Mem-Floats` exists for this.

#### Roll under a steer step is dt-correct (measured)

`tools/framerate/roll-test.ps1` + `tools/framerate/analyse-roll.py`. Flat arena, zero AI, throttle held to a steady
~25 m/s, then full lock held; roll angle logged against wall-clock.

| roll reached | 20 Hz | 60 Hz | time ratio | frame ratio |
|---|---|---|---|---|
| 1° | 0.067 s / 2 f | 0.112 s / 7 f | 0.60 | 3.50 |
| 2° | 0.127 s / 3 f | 0.160 s / 9 f | 0.80 | 3.00 |
| 3° | 0.183 s / 4 f | 0.205 s / 12 f | 0.89 | 3.00 |
| 5° | 0.322 s / 7 f | 0.483 s / 29 f | 0.67 | 4.14 |

Entry speeds matched (24.8 vs 24.3 m/s), exit speeds matched (34.4 vs 34.9), peak roll 5.9° vs
5.2°. Same angle in the same **seconds**, taking 3× the **frames** — dt-correct.

#### Mid-air pitch and roll are also dt-correct (measured)

`tools/framerate/airborne-test.ps1` + `tools/framerate/analyse-airborne.py`, Dunes, zero AI, throttle held, 30 s.

The comparison is made dimensionless so that jumps of different sizes on different terrain can
be compared at all: **gain = degrees actually turned ÷ (stored angular velocity × seconds)**.
A dt-correct integrator gives 1.0 for any jump; a per-frame integrator gives 3× more at 60 Hz.

| | 20 Hz | 60 Hz | B/A |
|---|---|---|---|
| gain | 0.894 | 0.764 | **0.85** |
| deg/s airborne | 17.7 | 21.9 | 1.24 |
| deg/frame | 0.886 | 0.366 | 0.41 |

0.85, not 3.0. **The orientation integrator uses dt on every axis** — linear, yaw, roll, pitch.

Two filters were needed before this number meant anything, and both changed the answer:

- **Dedupe samples by frame.** The sampler polls faster than the game draws, so at 20 Hz several
  rows share a frame and carry identical `vy`; a strictly-decreasing free-fall test then breaks on
  every duplicate and reports "no airborne segments" for a run full of jumps.
- **Never express a threshold in frames.** "At least 5 frames of airtime" is 0.25 s at 20 Hz but
  0.083 s at 60 Hz, so the fast run qualifies on hops the slow run never sees. Use seconds.

A third filter is worth keeping: require the segment's vertical acceleration to be near −9.8 m/s².
Falling is not flying — a car settling on its springs also loses vertical speed, and those frames
carry suspension torques. Including them produced angular-velocity "decay" of **+7.6 /s**, i.e.
spin appearing from nowhere in what was supposed to be free flight.

#### What this leaves

The integrator is exonerated on all four axes. But the raw data still shows something real:
at 20 Hz, three of four jumps had **essentially zero** angular velocity, while at 60 Hz all four
had 0.17–0.79 rad/s. Spin is *acquired* differently. That points at the contact/suspension
impulse — the solver runs 3× as often, and if each contact frame applies a fixed impulse rather
than a dt-scaled one, the car gets kicked 3× harder over the same time on the ground. **That is
the next hypothesis to test, and it is not the integrator.**

#### The frame delta-time is not a static global

Worth knowing before anyone else hunts for it. `tools/framerate/snap-static.ps1` + `tools/framerate/find-dt.py` take
five snapshots of `0x400000`–`0x900000` at each rate and keep only dwords sitting within ±12% of
1/rate in *every* snapshot at *both* rates. Result: **zero addresses**. dt is computed per frame
and passed on the stack/FPU, so there is no single global to scale.

`tools/framerate/ratio-scan.py` (values 3× smaller at 60 Hz) found 7 candidates in `0x6543F8`–`0x6547CC`.
All 7 are false: sampled 14,000 times each, every one is **constant within a run** (min == max)
and takes an arbitrary different value — including sign flips — in the next run. Seven
coincidences out of 1.3M dwords is what chance predicts. Sample before believing a scan.


### ~~The car IS measurably slower at 60 Hz — about 5–9%~~ (2026-08-09, n=5 per rate) — RETRACTED: this measured terrain, not physics

> **Retracted (lab commit `62e0332`; annotated 2026-10-02).** Whole-run speed comparisons measure the terrain the car
> wandered over, not the physics — trap 1 in the "traps" list below (`:396-398`). Level-ground filtering dissolved
> the shortfall. The tables are kept as the record of a wrong result and how it was caught; do not cite them.

*(retracted — see above)* This was read as the one place the game does **not** play the same. Dunes, zero AI, throttle held 25 s:

| | 20 Hz (n=5) | 60 Hz (n=5) | Δ |
|---|---|---|---|
| ground path length | 944.1 ± 12.3 m | 856.9 ± 29.3 m | **−9.2%** |
| mean speed | 38.34 ± 0.48 m/s | 34.94 ± 0.97 m/s | **−8.9%** |
| top speed | 55.21 ± 0.66 m/s | 50.61 ± 1.12 m/s | **−8.3%** |

No overlap on any of the three. Three spawns were drawn at both rates, and every matched pair
points the same way: 929.9→823.2 m, 946.1→895.7 m, 930.0→876.4 m.

Acceleration from the standing spawn shows the same deficit and rules out a startup artefact —
the time-to-speed gap **grows** with speed instead of staying constant:

| reach | 5 m/s | 10 | 15 | 20 | 25 | 30 |
|---|---|---|---|---|---|---|
| 60 Hz minus 20 Hz | +0.087 s | +0.098 | +0.145 | +0.198 | +0.207 | +0.312 |

So the longitudinal path (traction / drag / engine force) carries a per-frame dependency of
roughly 5%, on top of which rough terrain costs more. Small enough to be invisible while driving —
matching the report that 60 fps feels "mostly fine and drivable" — but real.

**Where the loss happens is NOT localised.** On-ground-only speed is also lower (30.63 ± 0.38 vs
28.63 ± 1.25 m/s), but that reasoning is circular: a faster car covers more ground and meets
different terrain. A per-landing energy-loss metric (`tools/framerate/analyse-contact.py`) was attempted and
is **not trustworthy** — it reports *negative* loss (the car accelerates downhill through the
measurement window) with a standard deviation larger than its mean. Treat that script as a
starting point, not a result.


## 8. How any of this gets measured

`autotest/README.md` is the harness cookbook. The frame-rate-specific tools:

| tool | what it does |
|---|---|
| `tools/framerate/fall-test.ps1` + `analyse-fall.py` | terrain-free gravity: per-frame in-process recording, free-fall segments only |
| `tools/framerate/accel-curve.py` | acceleration vs speed using **level-ground samples only** — the only sound way to compare speeds |
| `tools/framerate/physics-trace.ps1` + `trace-diff.py` | deterministic scripted-input traces, checkpoint diff |
| `tools/framerate/clock-rate-test.ps1` | is the engine's clock honest at this frame rate? |
| `tools/framerate/coast-test.ps1`, `ai-speed-test.ps1`, `weapon-test.ps1` | drag, AI speed, fire rate |

**Four traps that produced confidently wrong answers here** (full list in
`autotest/README.md` §5):

1. **Whole-run speed comparisons measure terrain, not physics.** A car that wanders downhill
   gains speed. This faked a "5–9% shortfall" that survived three wrong explanations before
   level-ground filtering dissolved it.
2. **Free-fall fitting must require real falling** (≥5 frames, ≥2 m/s drop) or it fits
   suspension jitter on the ground and yields a confident, wrong gravity constant. This produced
   a fully retracted "gravity is per-frame" claim.
3. **Discrete key taps are not comparable across frame rates** — a 25 ms tap spans ~0.5 frames
   at 20 Hz and ~1.5 at 60 Hz, so the notched throttle receives different input. Hold keys.
4. **A run that records nothing silently reuses the previous file** — two byte-identical
   "20 Hz" and "60 Hz" traces were produced this way. Delete before writing; fail loudly.
