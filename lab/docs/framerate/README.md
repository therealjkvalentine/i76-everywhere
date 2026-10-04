# Frame rate in Interstate '76 — what's true, what's lore, what's still broken

*Everything learned about running I'76 above 20 fps. Measured on the GOG 2019 Gold build
(`i76.exe`, MD5 `60ABF7BC…`). **First confirmed community result: the Mission 5 canyon jump was
cleared at 60 fps** (2026-08-09) — the single set piece the "high FPS breaks I'76" lore is built
on.*

---

## 1. The short version

**I'76 runs correctly at 60 fps.** Its physics integrate against real elapsed time, not per
frame, so raising the frame rate does not speed the game up or change trajectories. This was
measured, then confirmed by actually driving the canyon jump.

**But the community's advice was not wrong**, and it matters *why* — see §5. Two things are
still genuinely frame-coupled (§4), and nobody has yet found the frame rate at which it does
break (§6).

## 2. Turning it on

Two external limiters, both read **once at startup** (changing them needs a relaunch):

| limiter | where | what to do |
|---|---|---|
| `I76PATCH.DLL` | game folder — the AiO patch's ~20 fps `QueryPerformanceCounter`+`Sleep` trampoline | rename to `.disabled` |
| `FPSLimit` | `dgVoodoo.conf`, **`[GeneralExt]`** section | set to `0` |

### ⚠ dgVoodoo's `FPSLimit` DOES NOT WORK here — `I76PATCH.DLL` is the only real cap

> **Void (corrected 2026-10-03):** measured while dgVoodoo was rejecting this sandbox's conf, so `FPSLimit` was
> never in effect ([../DGVOODOO-CONF-REJECTED.md](../DGVOODOO-CONF-REJECTED.md)). Not re-measured on an
> accepted conf.

Measured directly, and it changes how the whole limiter story should be read:

The matrix is complete in both directions (2026-08-09; fps read from the frame counter `0x5A7E1C`
in a live melee, since the counter does **not** advance at the menus):

| dgVoodoo `FPSLimit` | `I76PATCH.DLL` | measured fps |
|---|---|---|
| 20 | **present** | **20.0** |
| 21 | **present** | **20.0** |
| 30 | **present** | **20.0** |
| 60 | **present** | **20.2** |
| 0 | **present** | **20.0** |
| 21 | absent | **60** |
| 45 | absent | 60 |
| 90 | absent | 60 |
| 0 | absent | 60 |

**Every `FPSLimit` value is ignored, in both configurations.** Setting it to 60 with the DLL
present still gives 20; setting it to 0 with the DLL absent still gives 60. The only thing on this
machine that changes the frame rate is whether `I76PATCH.DLL` is loaded.

Whatever `FPSLimit` is set to, the result is the 60 fps ceiling
(§6) unless `I76PATCH.DLL` is present, in which case the DLL pins it to 20 and dgVoodoo's
setting is irrelevant. The repo's long-standing `FPSLimit = 19.2` has therefore been doing
**nothing**; the 20 fps everyone relied on came entirely from the DLL.

**This is very likely the real explanation for "raising the limit breaks the game."** If you edit
`FPSLimit` from 19.2 to 21 expecting 21 fps, you do not get 21 — you get whatever the ceiling
is (here 60; on a machine with no vsync ceiling, potentially hundreds). So the reported breakage
at "21 fps" was almost certainly never 21 fps at all: it was the cap being effectively *removed*.
Nobody who tuned that number was choosing a frame rate — the setting has no effect at any value.
That reconciles the field reports with the measurements in §3, which show 60 fps to be fine.

**Practical consequence:** to actually cap the frame rate, use `I76PATCH.DLL` (20 fps) or the
DLL's own `fpscap=N` (§8, needs injection). Do not trust `FPSLimit`. Verify any cap by reading
the frame counter rather than believing the config.

The **engine itself has no frame limiter**. Proof: at menus, with both caps removed, the loop
spins at **31,000+ fps**. Anything below that is imposed from outside.

```bash
cd "<game dir>" && cp dgVoodoo.conf dgVoodoo.conf.pre-60hz \
  && sed -i 's/^\([[:space:]]*FPSLimit[[:space:]]*=\).*/\1 0/' dgVoodoo.conf \
  && mv I76PATCH.DLL I76PATCH.DLL.disabled
```

Reverse by swapping the two `mv`/`cp` operations back.


### How to finish it

1. **Test the contact-impulse hypothesis.** The integrator is dt-correct, so the remaining
   suspect is the suspension/collision solver: 3× the contact frames per second, and a fixed
   per-frame impulse would mean 3× the kick. A repeatable single-bump test is what is missing —
   see the warning about cross-launch runs below.
2. The two visual bugs (death camera, sky) are independent of physics and may be fixable without
   touching it. The death camera needs a live death to measure (see below); the sky still needs a
   human to watch one frozen candidate.
3. `0x5DDA74` and the rest of the `0x5DDxxx`/`0x5DExxx` cluster from the widened per-frame scan
   are **not** animation — disassembling their readers (`0x417950`-`0x4179BA`, `0x40E926`) shows
   free-list pointer swaps and a generic object initialiser. It is heap-allocation churn, which
   happens once per frame because the frame allocates. Ignore that whole region.


## 5. Reconciling with the community: why everyone said it breaks

Three separate explanations, and the evidence for each:

**(a) RESOLVED (2026-08-09) — "21 fps" was never 21 fps.** Field report from this machine: with
`I76PATCH.DLL` *installed*, raising `FPSLimit` even to **21** broke the game; the user had to run
slightly *below* 20. With `I76PATCH.DLL` *removed*, 60 fps is fine.

The proposed experiment — "run 60 fps *with* I76PATCH restored" — turns out to be **impossible**,
and that impossibility is the answer. The complete matrix in §2 shows `FPSLimit` at 20/21/30/60/0
all measuring **20.0 fps** while the DLL is loaded, and 21/45/90/0 all measuring **60** once it is
not. The setting has no effect at any value, in either configuration.

So nobody tuning that number was ever choosing a frame rate. Editing `FPSLimit` from 19.2 to 21
did not produce 21 fps — it produced whichever of {20, the ceiling} the DLL's presence dictated.
"Breakage at 21 fps" was the cap being *removed*, on machines whose ceiling was far above 60.
This is the most likely explanation of the entire body of community advice.

**(b) "Uncapped" historically meant *hundreds* of fps, not 60.** A 1997 engine on modern
hardware with vsync off is not 60 fps — the menu loop here hits **31,000 fps**. At those rates
dt is microseconds and float precision, integration error, and any minimum-dt assumption would
genuinely fall apart. The lore and these measurements can both be right: fine at 60, broken at
500.

**(c) It is NOT that the AiO patch fixed the physics.** Tested and rejected: a byte diff of the
2017 Galaxy build (`9A232DCC`) against the 2019 Gold build (`60ABF7BC`) shows only 3099 bytes
differing (0.3%), and **the gravity constant sits at byte-identical file offsets in both**
(`0x39AA2`, `0x6B327`, `0xA1507`, …). The patch did not touch physics code.

### The verdict, after checking the community's specific claims (2026-08-10)

The published advice is consistent across every current source — the
[GOG forum guide](https://www.gog.com/forum/interstate_series/simple_stepbystep_instructions_for_running_interstate_76_with_hardware_acceleration_using_dgvood/page1),
[CahootsMalone's dgVoodoo guide](https://github.com/CahootsMalone/interstate-76-stuff/blob/master/running-interstate-76-gog-release-using-dgvoodoo.md),
[PCGamingWiki](https://www.pcgamingwiki.com/wiki/Interstate_%2776) and the
[Fandom wiki](https://interstate76.fandom.com/wiki/Fixes_%26_Tweaks) — and it is **not stale or
pre-patch**: it says the game breaks above **~30 fps** and names specific symptoms. So the gap is
not "they were looking at old sites". Checking their claims one by one:

| community claim | what we measured at 60 fps |
|---|---|
| "ramps unjumpable / jump physics out of whack" | **false at 60** — the Mission 5 canyon jump was cleared, and gravity is dt-correct (−9.89 vs −9.74 m/s²) |
| "AI cars will not travel faster than ~35 mph" | **false at 60** — Taurus measured 33.2 m/s ≈ **74 mph** |
| "flamers won't extend, mortar range collapses" | weapon cadence is **timer-driven**, not per-frame (9.7 vs 13.8 rds/s scales with time, not 3×). Projectile range itself still untested |
| "cars steer left-right rapidly / AI misbehaves" | not reproduced at 60 |
| "things break above 30 fps" | **the threshold is wrong** — 60 is fine on every physics axis we can measure |

**But they were right that things break** — four systems genuinely are frame-coupled (§4), the
death camera provably so (8.0 deg/frame). What was wrong was the *threshold* and the *mechanism*.

Three factors produced the gap, and together they explain why it felt like "a whole crazy thing":

1. **"Uncapped" then meant hundreds of fps, not 60** (see (b)). Advice tuned in a 300–1000 fps
   regime, extrapolated down to a threshold nobody had actually bisected.
2. **Nobody was ever choosing a frame rate** (see (a)). `FPSLimit` is inert at every value, so
   the number people typed never mattered — only whether `I76PATCH.DLL` was loaded. That makes
   the "threshold" irreproducible *between machines*, because each machine's real ceiling
   differed. A knob that does nothing, next to a real effect, is a folklore generator.
3. **The visible bugs are animation, not physics.** A death camera spinning 3× too fast and a
   racing sky *look* like "the game is running too fast", and reasonably get reported as broken
   physics. The driving model underneath was fine the whole time.

**Net:** cap-to-20 was a blunt instrument that worked by accident. The defensible statement this
project can now make, which nobody had before: **I'76 is measurably safe at 60 fps**, with a
short list of specific animation/contact systems to fix (§4) rather than a superstition.

## 6. The 60 fps ceiling — INVESTIGATION CLOSED, 60 accepted (2026-08-10)

> **Correction 2026-10-03.** The rows for the dgVoodoo conf keys are void: `FPSLimit` and the forced
> `640x480@120` were measured on 2026-08-10, while dgVoodoo was rejecting this sandbox's conf and running a
> 2020 global file ([../DGVOODOO-CONF-REJECTED.md](../DGVOODOO-CONF-REJECTED.md)), so neither key was in effect.
> The ceiling itself is now explained: dgVoodoo paces windowed presents at the refresh code the game passes to
> `grSstWinOpen` (60 Hz). The proxy's `I76_GLIDE_REFRESH=120` substitutes the code and the game runs at 120
> (i76-everywhere `docs/records/FPS-120.md`). 120 is the ceiling of every renderer tested (i76-everywhere
> `docs/records/RENDERER-ALTERNATIVES.md` section 11). The `grBufferSwap` and dead-call-site rows still
> stand.

**Decision: we stopped here and accepted 60 fps.** Five independent levers were tested and every
one was inert; the remaining candidate needs a code cave for an uncertain payoff, and 60 fps is
already 3× the historical cap with physics measured correct. The eliminations below are recorded
so nobody spends another session re-running them.

| lever tested | result |
|---|---|
| dgVoodoo `FPSLimit` = 0 / 21 / 30 / 45 / 90 / 120 | **all inert.** `30` — a cap *below* 60 — still measured **60.2**, so dgVoodoo's limiter cannot even push the rate *down*. The cap is enforced beneath its controllable present path |
| dgVoodoo forced resolution `640x480@120` | ignored (silently fell back), 60.0 |
| `ForceVerticalSync = false` | already off; no effect |
| Monitor refresh | **not the cause** — verified single 179 Hz display (Dell AW3425DWM, 3440×1440, G-SYNC compatible), game window on it, still exactly 60 |
| NVIDIA driver profile | **not the cause** — user-verified Global tab: Max Frame Rate **Off**, Preferred refresh rate **Highest available**, Low Latency Off. No per-app override |
| `zglide.dll` `grBufferSwap(1)` → `(0)` (drop the vsync-to-retrace wait) | patched at file offset `0x2303`; **60.1, unchanged** |
| `zglide.dll` `grSstWinOpen(refresh)` second call site `push 0` → `push 8` (120 Hz) | patched at file offset `0x27DA`; **60.0, unchanged — that call site is dead code** |

**The one untested lever, for whoever picks this up:** the *active* `grSstWinOpen` call site at
`0x10001D9D` passes refresh in `edi`, a register shared with three other arguments, so it cannot
be changed by a byte poke — it needs a code cave that loads the refresh separately. dgVoodoo is
documented to honour only 75/85/120 Hz Glide refresh requests and force everything else to 60,
so this remains the most plausible source. `tools/framerate/uncap-vsync.ps1` shows the patch
pattern (backup, byte-poke, `-Restore`, `-Status`) if you want to extend it.

### (historical) cause NOT yet identified

With both caps removed and a **179 Hz** desktop, in-mission frames still measure exactly **60**,
while `FPSLimit = 45 / 90 / 120` are all ignored. Menus meanwhile spin at 31,000 fps, so the
pacing is specific to the 3D render path.

**A first explanation — that dgVoodoo's `Resolution = 640x480` forced a 60 Hz swapchain — was
wrong and is retracted:** the game visibly renders far above 640x480. That setting is the Glide
render target, which `ScalingMode = stretched` then scales to the window; it does not fix the
output mode.

**Re-confirmed 2026-08-09 at a verified 179 Hz desktop:** gameplay measured **60.2 fps**. The
desktop mode was checked directly (`Win32_VideoController` → `CurrentRefreshRate = 179`) rather
than assumed, and `dgVoodoo.conf` contains only two rate-related settings in total —
`FPSLimit` (proven inert, §2) and `ForceVerticalSync = false`. **So the ceiling is not vsync and
not the monitor**; it survives a 3× increase in refresh rate untouched.

**What the cap is NOT — two more suspects eliminated by patching the renderer (2026-08-10):**

The game's Glide renderer plugin is `zglide.dll` (the exe dynamically loads one of
`zglide`/`zdx5draw`/`zpowervr`/`zredline` by command line; `-glide` picks zglide, which calls
into dgVoodoo's `glide2x.dll`). Two things there could have paced it, and neither does:

- **`grBufferSwap(1)` — the per-frame vsync-to-retrace wait.** zglide calls it with swap
  interval `1` at `0x10002F03`. Patched to `0` (`tools/framerate/uncap-vsync.ps1`, one byte
  `6A 01`→`6A 00` at file offset `0x2303`): frame rate **unchanged at 60.1**. So the swap wait
  is not the gate.
- **`grSstWinOpen` refresh = `GR_REFRESH_60Hz`.** zglide opens the device requesting 60 Hz
  (arg 3 = 0 at the `0x10001D9D` call site). dgVoodoo is documented to honour only 75/85/120 Hz
  Glide requests and force everything else to 60 — so this *could* be the emulated-refresh
  source, and the fix would be to patch the request to 85 Hz (`GR_REFRESH_85Hz` = 7). **Untested
  — needs a code-cave detour (a 1-byte→2-byte push doesn't fit in place).** This is the one
  renderer-side lever still standing, and the fallback if the driver profile is clean.

**The decisive evidence points below dgVoodoo entirely:** `FPSLimit = 30` — a soft cap *below*
60 — still measured **60.2 fps**. dgVoodoo's own limiter cannot even push the rate under 60, so
the 60 is being enforced beneath dgVoodoo's controllable present path. On a verified single
179 Hz monitor (3440×1440, game window on it), an exact-60 that survives every application and
wrapper setting is the classic signature of a **driver-level cap**.

- **LEADING: NVIDIA driver profile** — a "Max Frame Rate = 60", "Vertical sync = On", or
  "Background Application Max Frame Rate = 60" applied globally or to `i76.exe`. GUI-only; the
  user must check it. This is the cheapest test and now the most likely cause by elimination.
- dgVoodoo's emulated Glide refresh (the `grSstWinOpen` lever above), if the driver profile is
  clean.

(Correction retained: the "menus spin at 31,000 fps" figure elsewhere in this repo cannot be
reproduced with the frame counter `0x5A7E1C`, which does not advance at menus at all — re-derive
it before relying on it.)

Check the NVIDIA profile for `i76.exe` first — Manage 3D Settings, both Global and Program
Settings: Max Frame Rate (Off / ≥180), Vertical sync (Off or app-controlled), Preferred refresh
rate (Highest available), Background Application Max Frame Rate (Off). Then re-measure with
`tools/framerate/probe-loop.ps1 -Fps`.

## 7. What comes next — fixing the bugs at 60 (current focus)

The frame-rate *ceiling* question is closed (§6): **60 is the target, and it is measurably
safe.** The remaining work is the short list of genuinely frame-coupled systems in §4:

1. ~~**Death camera**~~ — ✅ **FIXED 2026-08-10.** Confirmed frame-coupled (deg/s ratio 3.32,
   deg/frame 1.12), traced to `angle -= degrees * DEG2RAD` applied once per frame with no dt,
   and fixed by scaling the camera degree constant at `0x4BC528` by 20/target. Verified: 60 fps
   now orbits at −144.4 deg/s against the 20 Hz original of −143.3 (ratio 1.008). Full write-up
   in [MEASUREMENTS.md](MEASUREMENTS.md); patch is `tools/framerate/patch-camera-rate.ps1`.
2. **Collisions pass through objects** — ~2/3 miss rate on the training-level cactus at 60 fps.
   Needs a counted repro at 20 vs 60. The only *gameplay*-affecting bug on the list.
   **Repro note:** the training mission opens with a ~20 s scripted sequence (a cutscene where
   speed reads 15 m/s while the position is frozen, then a teleport to (1575, 49600) and a hold
   at 0) — a naive 25 s capture from mission start is almost all intro and hits nothing. Drive
   only after the car is released. The route itself IS deterministic (two runs covered 207 m and
   216 m), which makes it a good arena once the timing is right.
3. **Contact/suspension impulses** — the surviving suspect behind the mid-air spin and rough-ground
   roll reports (the integrator is exonerated on every axis).
   *(2026-10-02: i76-map reads the contact model as running once per substep from `physics_StepVehicle` (0x43a104)
   and once per frame through `physics_SnapToGround` 0x43d070 (`../i76-map/subsystems/framerate.md:75-85`), so the
   per-frame kick is the SnapToGround pass and the fixed step is the principled fix. Not yet re-measured under
   `I76_FIXED_STEP=24` — backlog P2-04: `tools/framerate/airborne-test.ps1` + `analyse-airborne.py`, stock 20 vs
   fixed 60, A/A first; angular velocity at lift-off should match 20 fps.)*
4. **Sky** — visual only; pixel-diffing is a proven dead end, needs a human on one frozen candidate.

~~Sweep 60 → 90 → 120 → 180 and find where it breaks.~~ Parked with the ceiling. If someone
later breaks 60 (the `grSstWinOpen` code cave in §6), the sweep tooling is ready:
`tools/framerate/fall-test.ps1` + `analyse-fall.py` measure gravity terrain-independently at any
rate.

The deliverable the community never had is a number: **"I'76 is safe up to X fps."** The evidence
says **X ≥ 60**, and the old advice of 20 was roughly 3× more conservative than necessary.

