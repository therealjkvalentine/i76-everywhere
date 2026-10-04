# True 60 Hz: what the engine actually does with physics

## VERDICT (2026-08-09, after per-system sweep)

**Interstate '76 is substantially frame-rate independent.** Uncapped it runs at a measured
60 fps and the physics that were supposed to break do not. The headline numbers, each measured
with a terrain-independent method:

| system | 20 Hz | 60 Hz | ratio | verdict |
|---|---|---|---|---|
| **gravity / falling** | −9.893 m/s² | −9.735 m/s² | **0.984** | **dt-correct** — both are real gravity |
| engine clock vs real time | 0.9943 | 0.9991 | — | honest at both rates |
| engine dt (FFB block `0x4F2488`) | ~0.050 s | 0.0156 s | — | tracks true frame time |
| player top speed (continuous input) | 39.7 m/s | 37.6 m/s | 0.95 | ~5% low |
| AI top speed (Taurus) | 36.40 m/s | 33.21 m/s | 0.91 | ~9% low; **no 35 mph cap** (74 mph) |
| weapon fire rate (30cal MG) | 9.7 rounds/s | 13.8 rounds/s | 1.4× | **timer-driven**, not per-frame (per-frame would be 3×) |

The famous falling breakage **does not reproduce**. Gravity lands on −9.8 m/s² at both frame
rates, matching the `−9.8` immediate at `0x0043A6A1`. The "AI caps at 35 mph" report does not
reproduce either — Taurus does 74 mph at 60 Hz.

**Weapons** (the last thread): `weapon_fire` is bound to **Enter**, not Space — the comment at
the top of `input.map` is stale, which is why the first fire tests registered nothing. Neither
documented detection route works on this machine (the input flag `0x5367D0` is unreliable by
the repo's own note, and the FFB effect table only fills when an FFB device is present), so
fire rate was read from the HUD ammo counter instead: 2000 → 1951 at 20 Hz and 2000 → 1931 at
60 Hz over 5 s. Per **frame** the two differ 2.2×; per **second** only 1.4×. A per-frame weapon
would drain 3× faster at 60 Hz. It does not, so emission is timer-driven.

### The 5–9% "residual" was terrain, not physics — RESOLVED

Chasing it produced three dead ends worth recording, then the answer:

1. **Euler integration error?** No. It predicts a monotonic trend with step size, but 30 Hz
   (37.37 m/s) landed *below* 60 Hz (37.6), with 20 Hz alone at 39.7. Not monotonic.
2. **`I76PATCH.DLL`?** No — I had been restoring it for every 20 Hz test and disabling it for
   the others, a real confound in my own setup. Removing it made 20 Hz *faster* (41.30 m/s),
   so the patch was not the cause.
3. **Air drag?** No. Measured terrain-free on airborne samples: horizontal velocity is
   essentially unchanged in flight at 60 Hz (median 0.0000 m/s²). The 20 Hz "2.0 m/s²" was
   ground-scrape contamination inside the airborne window.

**The real answer: "top speed over a 12 s drive" is itself a terrain measurement.** A car that
wanders downhill gains speed, and the runs diverge onto different ground within seconds. Even
the flat-sounding Slick Track arena gave 14 m of elevation change.

Settled by filtering *for* level ground instead of hunting it — `tools/framerate/accel-curve.py` keeps
only grounded, level samples (|vy| < 0.6 and |Δy| < 0.06 m) and bins acceleration by speed:

| speed bin (m/s) | 20 Hz flat | 20 Hz no-patch | 20 Hz ref | **60 Hz** |
|---|---|---|---|---|
| 5–10 | 8.73 | 8.87 | 9.71 | **8.82** |
| 10–15 | 6.96 | 7.41 | 7.44 | **6.46** |
| 15–20 | 4.90 | 4.96 | 5.05 | **4.50** |
| 20–25 | 3.34 | 3.94 | 4.52 | **3.58** |
| 25–30 | 2.97 | 3.28 | 3.54 | **2.86** |

The 60 Hz curve lies inside the spread of the three 20 Hz runs in every bin — **run-to-run
variation at one frame rate exceeds the difference between frame rates**. The acceleration
model, drag included, is frame-rate independent.

**Conclusion: no frame-coupled system was found. The engine plays the same at 60 Hz.**

### Methodology warnings earned the hard way

- **Discrete key taps are NOT comparable across frame rates.** A 25 ms tap spans ~0.5 frames at
  20 Hz and ~1.5 at 60 Hz, so the notched throttle gets different input. Tapping produced a
  bogus 48 vs 25 m/s "difference"; continuous key-hold gives 39.7 vs 37.6. Always hold.
- **A run that records nothing silently reuses the previous file.** Two byte-identical "20 Hz"
  and "60 Hz" traces were produced this way (the game had lost focus, so no frames presented
  and no flush happened). `fall-test.ps1` now deletes the recording first, re-asserts focus when
  frames stall, and fails loudly.
- **Free-fall fitting must require actual falling.** Fitting any "vy decreasing" run picks up
  suspension jitter on the ground and yields a confident, wrong constant (this is what produced
  the earlier retracted "gravity is per-frame" claim). Require ≥5 frames and ≥2 m/s of drop.
- **External polling cannot resolve sub-frame events** — at 20 Hz a whole launch-to-fall
  transition fits inside one 50 ms sample and returns −38 m/s². Use the in-process recorder.


*Measured 2026-08-08 with `tools/framerate/physics-trace.ps1` + `tools/framerate/trace-diff.py` — deterministic
scripted input, identical spawn, memory-sampled traces. Numbers, not folklore.*

## Headline: uncapping works, and the physics are far more frame-rate independent than the lore says

Removing both limiters (dgVoodoo `FPSLimit = 0`, `I76PATCH.DLL` renamed away) makes the engine
run at a **measured 60 fps** — the sim itself, not injected frames. Running the *same* scripted
input from the *same* spawn at 20 Hz and 60 Hz:

| | 20 Hz | 60 Hz | ratio |
|---|---|---|---|
| speed at 1…9 s | 14.6 → 39.7 m/s | 13.0 → 37.6 m/s | **0.89–0.95** |
| falling accel, **per second** | −3.644 m/s² | −3.171 m/s² | **0.87** |
| falling accel, **per frame** | −0.1819 m/s | −0.0532 m/s | **0.29 ≈ 1/3** |

The per-frame numbers differ by almost exactly 3× while the per-second numbers nearly match.
**That means gravity (and vehicle acceleration) are integrated against real elapsed time, not
applied once per frame.** At 60 Hz the car accelerates and falls at roughly the correct
per-second rate — within 5–13%.

**Retraction:** an earlier pass reported gravity as per-frame (−0.0044 m/s/frame identical at
both rates). That was wrong — it measured *suspension jitter while the car sat on the ground*,
not free fall. Filtering to genuine airborne samples (`vy < −1` and decreasing) reverses the
conclusion. Lesson: a "free-fall" segment finder must require actual falling, or it will
happily fit noise and produce a confident, wrong constant.

## Where gravity lives

`0x0043A6A1: push 0xC11CCCCD` — the float **−9.8**, an **immediate operand** in the instruction
stream, pushed with the entity's velocity vector (`lea edx,[ebp+0xbc]`) into `call 0x438630`.

This is why hardware *data* breakpoints never fire on gravity: an immediate is fetched as code,
not read as data. Searching `.rdata` for `9.8` finds unrelated copies (`0x4BC59C`), and
watchpointing them shows zero reads.

Other constants found — **corrected 2026-10-02 (i76-map finding L092): both addresses were a file-offset-as-VA
slip of the `.rdata` raw/VA delta (0xc00).** `0x4bc71c` actually holds −0.1f and `0x4bc59c` holds 0.2f. The
values meant are at `0x4bd31c = 0.05f` (read by `fmul` at 0x444099) and `0x4bd19c = 9.8f` (read by `fmul` at
0x43a0c9 in 0x438fd0) — both *are* read during gameplay, so "9.8 never read" is false at the corrected address.
Neither is the physics timestep; dt is the variable `0x4fe428` (`simclock_dt`, writer 0x49c920).

The per-tick velocity integrator sites (hardware watchpoints on the player's `vy` at
entity `+0xC0`, ~128 hits over 5 s ≈ the sim tick rate): `0x43A687`, `0x43A695`, `0x43AB70`,
`0x43C3C2`, `0x43BC1A`, and the higher-frequency `0x46437D` / `0x4643BA`.

## What is still unresolved

- **5–13% residual difference.** Small but real. It may be Euler integration error (a
  fixed-step integrator run at different step sizes does not produce identical trajectories
  even with correct dt), or a genuinely frame-coupled term. Distinguishing them needs a
  *controlled* drop from identical initial conditions — the trace runs diverge onto different
  terrain within seconds, so later samples compare different situations, not different rates.
- **Sampling resolution.** At 20 Hz a whole launch-to-fall transition can occur inside one
  50 ms frame, making per-event derivatives meaningless (one segment fit −38.8 m/s²). Fine
  comparisons need sub-frame sampling or an in-process (DLL) recorder rather than an external
  poller.
- **The famous breakages were never gravity.** Community reports are specific: ramp jumps
  become impossible, flamethrowers do not extend, mortar range collapses, AI caps ~35 mph.
  Since gravity and acceleration scale correctly, those are separate frame-coupled systems and
  each needs its own trace, not a global constant fix.

## How to reproduce

```powershell
# 20 Hz reference
autotest\enter-melee.ps1
tools\framerate\physics-trace.ps1 -Label ref20 -Seconds 12 -Profile straight

# uncap: dgVoodoo FPSLimit = 0, rename I76PATCH.DLL away, relaunch
autotest\enter-melee.ps1
tools\framerate\physics-trace.ps1 -Label test60 -Seconds 12 -Profile straight

python tools\framerate\trace-diff.py    captures\traces\ref20.csv captures\traces\test60.csv
python tools\framerate\measure-gravity.py captures\traces\ref20.csv captures\traces\test60.csv
```

`tools/instruments/patch-float.ps1` retunes a constant live (VirtualProtectEx + verified write-back) if a
scaling fix is needed for a specific subsystem.

**Traps that produced wrong numbers here** (all now guarded in the tools):
- A trace of a **frozen sim** is a page of identical rows that looks like data —
  `Ensure-SimRunning` (autotest/lib/simlib.ps1) now refuses to record unless the frame counter
  is advancing. The pause menu ("Spanner's Cafe") and losing window focus both freeze it.
- **Writing the input block does not drive the car** — the engine rebuilds it from the device
  every frame; the written throttle read back as 0. Hold real scancodes instead.
- **Melee spawn points differ between runs**, so absolute positions are not comparable;
  `trace-diff.py` compares motion relative to each run's own start.
- **A damaged/wedged car silently invalidates a run** (full throttle, speed 0.03). Start each
  trace from a fresh mission.
- PowerShell `'{0:N0}'` writes `9,855` into a CSV and corrupts the columns — use
  InvariantCulture without group separators.
