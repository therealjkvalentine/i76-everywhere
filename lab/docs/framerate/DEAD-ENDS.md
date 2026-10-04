# Frame rate - dead ends, retractions and test hygiene

*Companion to [README.md](README.md), which carries the story and how to enable it, and
[MEASUREMENTS.md](MEASUREMENTS.md), which holds the results that survived.*

**Read this before designing a frame-rate experiment.** Most wrong answers in this project were
not the engine misbehaving - they were the instrument: a torn memory read, a threshold expressed
in frames instead of seconds, an A/B with n=1, a scan hit never re-sampled. Each section records
what was tried, what it appeared to show, and why that was wrong.

---

### A general detector for per-frame systems — `tools/framerate/find-perframe.ps1`

Rather than hunt each reported bug by hand, this finds **every** value the engine advances per
frame at once. Park the car, let the same wall-clock time pass at 20 Hz and 60 Hz, and diff the
engine's static data: real-time-driven values change by the same amount; per-frame values change
**3× more** at 60 Hz.

It validates itself — the known frame counter `0x5A7E1C` comes out at exactly **3.00**.

Confirmed per-frame values (car parked, so these are animation/timers, not physics):

| address | Δ @20 Hz | Δ @60 Hz | ratio | writer code |
|---|---|---|---|---|
| `0x5A7E1C` | +120 | +360 | 3.00 | the frame counter (control) |
| `0x4F70F8` | +120 | +360 | 3.00 | `0x45AE88`, `0x45AE99` |
| `0x524550` | +120 | +360 | 3.00 | — |
| `0x644334` | −0.0024 | −0.0071 | 2.98 | `0x493002`, `0x49301B`, `0x493039`, `0x49303E` |
| `0x501858` | +15.22 | +54.37 | 3.57 | `0x494DBB`, `0x494E0C`, `0x401A85`, `0x401AE3` |
| `0x501918` | −15.22 | −56.67 | 3.72 | — |
| `0x59BCD4` | −6.95 | −22.56 | 3.25 | `0x48D1D9`, `0x48D1F7`, `0x48D2B9`, `0x48D2D4` (very hot, ~480/s) |

**These are the raw material for fixing the sky and death-camera bugs** — one of them is almost
certainly the sky. Scaling the writer's increment by dt is the fix.

**Identifying which is the sky is NOT done, and the pixel method is a dead end.** Four attempts,
each removing one suspected confound, and the baseline never moved:

| attempt | setup | baseline noise | result |
|---|---|---|---|
| 1 | melee, wide band | 19.4 | every candidate *noisier* (25–38) |
| 2 | TRIP mission 5, narrow band between ridges | 33.1 | 26–48, nothing stops |
| 3 | **training mission**, car braked to 0.6 m/s, wide clean sky | 37–40 | 23–40, nothing stops |
| 4 | as 3 but **`Dithering = appdriven`** (suspecting per-frame dither noise) | 37–41 | 25–40, nothing stops |

So the sky band changes by ~40 per sample *no matter what*, which is larger than any effect a
frozen candidate produces. Dithering was not the cause; neither was car motion or the band
choice. **Do not spend more time on pixel-diffing the sky.**

The likely explanation: **the sky animation is not in the static range that was scanned.**
`find-perframe.ps1` only covers `0x4C0000`–`0x700000`. Widen it to the heap (the game's private
committed regions, as `dump-memory.ps1` enumerates) and re-run the 20 vs 60 Hz comparison — the
sky's driver is probably a per-frame value there. That is the concrete next step.

Alternative that needs a human for ten seconds: `tools/framerate/freeze-candidate.ps1 -Addr <a>` holds one
value while a person watches the screen and says whether the sky stopped. Human eyes are not
fooled by the noise floor that defeated the metric.


### Do not compare trajectories across launches — it is not a controlled experiment

The tempting whole-system test is: same spawn, same held throttle, compare where the car ends up.
It produced a confident, wrong result — 926.6 m at 20 Hz vs 822.4 m at 60 Hz, "11% slower", with
the 20 Hz car faster at every sample. Repeat runs at the **same** frame rate then diverged by
150 m (60 vs 60 Hz) and 285 m (20 vs 20 Hz) — the terrain makes the path chaotic, so per-timestep
position comparison carries no signal at all.

Path length looked more robust (929.9 and 930.0 m at 20 Hz — "the 20 Hz sim is deterministic")
until the flat-arena control was run: top speed came out 44.9 / 35.1 m/s at 20 Hz against
45.9 / 46.8 at 60 Hz — the opposite ordering, and one 20 Hz run covered only 210 m because the car
hit something. So the single-pair version of this test was rightly thrown away.

**Repeated to n=5 per rate, though, the effect is real** — see below. The pair was not wrong
because the metric is bad; it was wrong because n=2 cannot see a ±12 m spread. And the "20 Hz is
deterministic" reading was luck: **Dunes draws a random spawn from several**, and those two runs
were different spawns that matched by coincidence. Same-spawn repeats really are deterministic
(823.2 and 822.7 m).

**Do not use SlickTrack or AirBase as the flat control.** Neither is a flat plain: SlickTrack is a
walled circuit where "hold W" drives into barriers (path 328–669 m, sd ±127 m at a single rate),
and AirBase produced a 210 m run against a 962 m one at the same rate.

What reliably works is a test that normalises itself before measuring: reach a steady state first,
then apply a step input, and compare the response in seconds vs frames. That is what
`roll-test.ps1` does, and why its answer held up.


### Camera code, for whoever gets a death on the clock

- Camera FSM state: `0x4C2728` (compared against 2 at `0x405941`, reset to 0 at `0x405A49`).
- Camera state block: `0x4C2730`, **616 bytes** (`0x9A` dwords), `rep movsd`-copied from a preset
  table at `0x5DBB20` indexed by camera number.
- Euler/limit fields zeroed together at `0x405A53`-`0x405A7B`: `0x4C2964`, `0x4C2968`, `0x4C296C`,
  `0x4C2970`, `0x4C2980`; constants `0x3F060A92` (0.524 ≈ 30°) into `0x4C2918`/`0x4C2928` and
  `0x40B00000` (5.5) into `0x4C2924`.

A static xref reaches the *initialiser* only — the per-frame camera update addresses this block
through a register base, so the rotation constant is not statically visible. It has to be caught
live, which means the player has to die on the clock.

**Dying autonomously did not work. Seven runs, ~40 minutes; do not repeat these.**

| attempt | result |
|---|---|
| Crater melee (AI kept), fixed 4 s left/right weave, 150 s | alive |
| TRIP mission 5, same weave, 300 s | alive — car circled a **342 × 95 m** box; it never went looking for anyone |
| mission 5, steer at *nearest* entity, 300 s | alive — nearest entity is slot 1 at 79 m, i.e. **Taurus, the mission escort**. 300 s spent chasing a teammate |
| mission 5, steer at nearest entity **beyond 400 m**, 420 s | alive — and **stuck**: mean speed 0.95 m/s, 92% of frames under 1 m/s, jammed in a 34 × 96 m box. Mission 5 is the canyon; a distant target means driving into a wall |
| mission 5, + reverse-and-turn stuck recovery, 420 s | alive — mean speed only 2.29 m/s, still boxed in at 71 × 159 m |
| Crater melee, hunt anything past 20 m, 400 s | alive — ramming enemies at up to 55 m/s the whole time, player entity pointer never changed |

This matches [ARMOR-INVESTIGATION.md](../ARMOR-INVESTIGATION.md), where 35 s of AI fire produced no
armor change at all: **melee AI cannot realistically kill the player**, and 400 s does not change
that. The armor mirror it found is downstream and writing to it repairs nothing, so scripting a
death by zeroing health is not available either.

**What this needs:** a human dying once at each frame rate while `death-cam-test.ps1` logs (it
records the raw eye vectors, so the orbit rate falls straight out), or a damage source strong
enough to script — a very large fall, or a scripted mission whose opposition actually engages.

Two harness pieces came out of this and are worth keeping regardless:

- **Hunting**: steer toward a chosen entity using `Mem-Entities` plus the eye yaw. Set a minimum
  target distance or the car will faithfully chase its own escort.
- **Stuck recovery**: hold reverse and turn (alternating direction) when speed stays under
  1.5 m/s. Holding the throttle into a hillside otherwise does nothing forever.
- **Log every sample unconditionally.** Guarding the log on `if ($a)` from `Mem-EyeAngles`
  dropped exactly the frames of interest — the forward vector collapses at the moment of death,
  the helper returns null, and the run recorded **zero** post-death frames.

### Test hygiene for anything rotational

- **Set A.I. DRIVERS to 0** — AI cars collide with the player and corrupt rotation. The
  `enter-melee.ps1` AI-zero click was silently failing under the old cursor calibration; it now
  uses `Click-UI 159 295` and is **verified by entity count** (1 entity = clean).
- **Pick a hilly arena.** AirBase and SlickTrack are flat — a 30 s run there produced *zero*
  airborne samples. Dunes/Crater/Tombstone give airtime (`enter-melee.ps1 -Area Dunes`).
- **Hold input, never tap** (see above), and prove comparability from applied steer `+0xE0`.

*(Add further entries here as they turn up — that is the point of this list.)*

Untested, so treat as unknown rather than fine:

- **Flamethrower** — exists in save003/004 (`flm01`) but equipping needs the Build & Repair
  weapon-slot arrows, which do not respond to synthetic clicks; `CONFIGURE CHASSIS` is disabled
  in Instant Melee.
- **Mortar / rocket range** — fired projectiles do **not** appear in the world position table
  (18 slots, unchanged across shots), so they live in a separate system that has not been found.
- **Later-mission ramp and bridge gaps** — only Mission 5 has been played at 60.

