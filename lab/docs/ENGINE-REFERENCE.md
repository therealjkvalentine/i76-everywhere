# Interstate '76 engine reference

**A working map of the 1997 Interstate '76 engine: where its state lives in memory, how its
frame loop and physics behave, and how to drive it from a script.** Everything here was
measured against a live process, not inferred — each claim carries how it was established and
how confident it is.

Written for: reverse engineers, the *Time Vigilantes* spiritual-successor effort, trainer and
mod authors, and anyone capturing telemetry for force feedback or motion simulators.

**Target binary:** GOG "Gold"/AiO `i76.exe`, MD5 `60ABF7BC699DA72476128DDCE991A3D1`, 1,051,648
bytes. PE image base `0x400000`, **no ASLR**, so every static VA below is also a live process
address. A different build (e.g. the 2017 Galaxy exe, MD5 `9a232dcc…`) will have different
addresses — re-anchor before trusting anything here.

> **Corrections from `../i76-map/status/findings.md` (batch 2026-09-05, propagated 2026-10-02).**
> - **L001** — 60abf7bc is the *same* 1998-02-19 link as the 2017 Galaxy exe 9a232dcc: `.text` differs in 2,459
>   bytes over 45 clusters (`binaries/diff-9a232dcc-vs-60abf7bc.tsv`) and every address outside those clusters
>   decodes identically in both files. Re-anchor only inside the listed clusters, not "everything".
> - **L024** — `0x5FCDC4` (row below) is the `DS3DLISTENER` block at 0x5fcdc0, written by `fstp [0x5fcdc4]` at
>   0x4224ab inside the function that pushes 0x5fcdc0 to DirectSound (0x42252f); the "poking it moves the camera"
>   observation had no A/A control. Re-test is backlog P4-21 (poke twice with no change, then change). The same
>   claim is in `docs/RESULTS.md:36,44` and `docs/framerate/MEASUREMENTS.md:253-265`.

Confidence tags: **[live]** verified against the running game · **[disasm]** read from
disassembly · **[inferred]** consistent with evidence but not directly proven.

---

## 1. Architecture in one page

I'76 is a modified **MechWarrior 2** engine. Four facts shape everything:

1. **The simulation advances once per rendered frame** — there is no separate fixed-rate tick.
   Verified [live]: sampling per frame shows the sim state changing on *every* frame at both
   20 Hz and 60 Hz (0% unchanged frames in 1561 samples).
2. **But the physics are integrated against real elapsed time**, not per-frame constants. This
   contradicts long-standing community lore. See §5 — gravity measures −9.89 m/s² at 20 Hz and
   −9.74 m/s² at 60 Hz.
3. **Gameplay objects are heap-allocated and relocate** per mission/load. Flat value scans miss
   them; use the static root and pointer chains in §3.
4. **A vehicle is split** into a transform/dynamics entity (velocity, controls, wheel contacts)
   and a separate vehicle-**logic** object (weapons, components) reached by accessor.
   Different objects, different roots.

The renderer is a swappable back end (`ZGLIDE`, `ZDX5DRAW`, `ZREDLINE` — Glide, DirectDraw,
software) reached through function pointers, so the frame loop is back-end agnostic.

---

## 2. The frame loop

One iteration of the gameplay hot loop = one rendered frame:

```
0x4039B8  call 0x49C920     frame_clock_update()
                              inc [0x5A7E1C]        <- FRAME COUNTER (++ per rendered frame)
                              call [0x4BC100]       <- GetTickCount import: the engine's clock
                              (ms * 0.001 -> seconds, constant 0.001 at 0x4BE994)
0x4039BD  call 0x44D9E0     message pump / housekeeping
0x403A38  call 0x49C8C0     get_frame_time() -> fld [0x5A7E74]   (current time, seconds)
0x403A3D  fsub [0x504A28]   dt = now - last
0x403A43  fcomp [0x4BC48C]  clamp dt (spiral-of-death guard)
0x403A5A  fstp [0x504A28]   last = now
          ...               input / AI / physics / script VM
0x403A98  call 0x457530     world_ctx = [0x54A264]
0x403DD5..0x403E00          world/AI/physics advance cluster
                            (0x461D50, 0x40A320, 0x462A90, 0x4A0410, 0x4A4130, 0x44AF80)
0x403E78  cmp [0x4FE534]    render gate (gamestate flags)
0x403E85  call [0x5DD2BC]   BeginFrame(surface 0x5DCEC0)   -> engine wrapper 0x434340
0x403E93  call 0x4621E0     render_scene(camera 0x4C2730)
0x403E9B  call 0x49B430     HUD / cockpit overlay
0x403EA0  call 0x49BEE0        ''
0x403EAA  call [0x5DD2C0]   Flip / present(surface)         -> engine wrapper 0x4343D0
                              wrapper gates on [0x5280CC], calls backend via [0x608BCC]
```

**Hooking the present** is the cleanest injection point: `[0x5DD2C0]` is a *function pointer in
.data*, so you can swap it and chain to `0x4343D0` without patching code bytes. [live]

The community frame limiter (immi101's `i76fix`) hooks the same loop at `0x4039B8` — that
address is from the 2017 Galaxy exe but lands on a `call` in the Gold exe too. [live]

**Frame-rate limiters, in order of precedence:** `I76PATCH.DLL` (the AiO patch's
QueryPerformanceCounter+Sleep limiter, ~20.66 fps), dgVoodoo's `FPSLimit` in `dgVoodoo.conf`,
and any wrapper cap. Both are read **once at startup** — to change frame rate at runtime, limit
inside your own present hook instead (see §7).

---

## 3. Memory map

### 3.1 Static globals (no pointer chain — always valid)

| VA | type | meaning | conf |
|---|---|---|---|
| `0x54A264` | ptr | **world-context root**; `0x457530` returns it | [live] |
| `0x5A7E1C` | int | **frame counter**, ++ per rendered frame — measure real FPS from this | [live] |
| `0x5A7E74` | float | engine clock, seconds (GetTickCount×0.001) | [live] |
| `0x504A28` | float | previous frame time (dt = `0x5A7E74` − this) | [disasm] |
| `0x4BE994` | float | `0.001` — ms→s conversion | [live] |
| `0x4BC100` | import | `GetTickCount` — the engine's only time source | [disasm] |
| `0x54E11C` | table | **world position table** — see §3.2 | [live] |
| `0x5FCDC4` | float3+matrix | **DS3DLISTENER block** (0x5fcdc0; L024). The earlier "eye/view transform; poking it moves the camera" reading had no A/A control — re-test scheduled (backlog P4-21) | [live, contested] |
| `0x5443B0` / `0x5443BC` | float3 | player AABB min / max corners | [live] |
| `0x5DD2BC` / `0x5DD2C0` | fn-ptr | BeginFrame / Flip (→ `0x434340` / `0x4343D0`) | [live] |
| `0x608BCC` | fn-ptr | real backend present (called by the Flip wrapper) | [disasm] |
| `0x5280CC` | int | render-active flag gating the Flip wrapper | [disasm] |
| `0x5DCEC0` | struct | render surface (argument to BeginFrame/Flip) | [disasm] |
| `0x4C2730` | struct | camera (argument to `render_scene`) | [disasm] |
| `0x4C2964/6C/70/74` | float | **live camera Euler angles** — head-tracking write targets | [live] |
| `0x4C2728` | int | camera view mode (F1..F11) | [disasm] |
| `0x4FE534` | flags | gamestate / render gate | [disasm] |
| `0x536770/78/80` | int | pilot yaw / pitch / roll look input | [live] |
| `0x5367CC` / `0x5367D4` | int | **throttle / steer input** | [live] |
| `0x5367D0` | int | weapon-fire flag (unreliable for detection — see §8) | [live] |
| `0x52BBD0` / `0x52BBCC` | int/ptr | FFB present flag / object pointer | [live] |
| `0x52BBE4` | fn-ptr | `I7FF_SIM_Effect` — the single force-feedback event funnel | [disasm] |
| `0x4F2328` | 364 B | **FFB effect parameter block** — see §6 | [live] |
| `0x524674` | int | music-active flag (nonzero = playing) | [disasm] |
| `0x507DA0` / `0x51F5D0` | table | entity wrapper pointer arrays / group counts (8 groups, stride 0x100) | [live] |

### 3.2 The world position table — `0x54E11C`, stride `0x20`

**Every vehicle's world position, in one static array. No pointer chase.** [live]

```
record:  +0x00 float x
         +0x04 float y      (height)
         +0x08 float z
         +0x0C float radius (player 2.759, AI cars ~1.95-3.2)
```

Slot 0 is the player; the rest are AI cars and objects. Occupied slots have non-zero x or z;
~16–18 slots seen populated. Identify a specific car **by behaviour** — e.g. in Trip mission 1,
Taurus is the slot that moves 110 m while everything else stays parked (slot 2).

**Important: this table is a *derived copy*.** Hardware watchpoints show it is read only by exe
code (`0x469958`, `0x469976`, `0x46989E`, `0x4685F4`, `0x4224B1` — AI/radar/collision) and
**never by the renderer**. Writing it changes nothing on screen: a +40 m poke landed, persisted
620 ms untouched, and the picture did not move. [live]

*Excellent for reading* (radar, minimap, telemetry, mission logic, AI analysis).
*Useless for writing* if you want to move something visually.

### 3.3 The player entity (pointer chain)

```
world  = [0x54A264]
sub    = [world]
entity = [sub + 0x70]          ; = [[[0x54A264]] + 0x70]
```

| offset | type | meaning | conf |
|---|---|---|---|
| `+0x04..0x30` | 4× float3 | wheel contact points, **local** space (wheelbase 4.662 m, track 1.976 m) | [live] |
| `+0xAC` | float | speed = ‖velocity‖ | [live] |
| `+0xBC` | float3 | **velocity, world space** — `+0xC0` is vertical = **fall speed** | [live] |
| `+0xC8` | float3 | angular velocity; yaw rate at `+0xCC` | [live] |
| `+0xD4` | float3 | acceleration / accumulated force | [inferred] |
| `+0xE0` / `+0xE4` | float | applied steer / throttle (−1..1; negative throttle = brake) | [live] |
| `+0x108` | ptr | → vehicle-**logic** object (weapons, components, damage) | [live] |

**There is no world position in this struct.** Its allocation ends at `+0x6000` and no float3
inside it tracks the velocity vector (checked with a 14-snapshot turning series). Position lives
in the table (§3.2) and in per-entity scene nodes on the heap. This surprised us and cost real
time — the old note claiming a transform at `+0x08` was wrong; that region is wheel contacts.

Units are **metres and m/s** throughout (confirmed by the wheelbase measurement).

### 3.4 Render-consumed transforms (heap)

The renderer draws from **per-entity scene nodes**, not from the table:

```
node:  +0x00 float3 position
       +0x0C 3x3 rotation matrix (orthonormal)
       ...   flags / mesh + parent pointers before the position
```

Hardware watchpoints confirm the Glide renderer DLL (`~0x6BF7xxxx`) reads these ~18×/frame.
Addresses are **heap and per-session** — find them at runtime by scanning committed memory for
float3s matching a known entity position from the table, then verifying they move with it.
`i76uncap.dll`'s `rescan()` does exactly this and tags each copy with its owning slot.

The static eye transform `0x5FCDC4` (position + matrix) *is* render-consumed — poking it visibly
moves the view (~26% of the viewport changed). [live]

### 3.5 Vehicle logic object

```
logic = [entity + 0x108]
  -> 16 component records, stride 0x90 (engine/suspension/brakes/tyres/armor)
     armor and chassis are integer TENTHS (91.0 -> 910)
  -> weapon container -> weapon pointer array -> weapon -> ammo (int32 countdown)
  AI aggression at logic + 0xA818 (int 0..4)
```

Exact per-field offsets inside the 0x90 component record still need a watchpoint; the
`+0xa71c` / `+0xa738` weapon-array offsets from older notes did **not** resolve on this build.

---

## 4. Physics: what is and isn't frame-rate dependent

> **See [framerate/README.md](framerate/README.md)** for the full frame-rate story: how to run at 60, the
> measurements, the two confirmed frame-coupled bugs (both rotational), and the open questions.

Measured with deterministic scripted input and per-frame in-process recording, comparing
20 Hz against 60 Hz:

| quantity | 20 Hz | 60 Hz | ratio | verdict |
|---|---|---|---|---|
| **gravity (free fall)** | −9.893 m/s² | −9.735 m/s² | 0.984 | **dt-correct**, both are real gravity |
| engine clock vs real time | 0.9943 | 0.9991 | — | honest |
| engine dt (FFB block `+0x160`) | ~0.050 s | 0.0156 s | — | tracks true frame time |
| acceleration curve a(v), level ground | see below | | | **indistinguishable** |
| AI top speed (Taurus) | 36.40 m/s | 33.21 m/s | 0.91 | no 35 mph cap (74 mph observed) |
| MG fire rate | 9.7 rds/s | 13.8 rds/s | 1.4× | **timer-driven** (per-frame would be 3×) |

Acceleration, level grounded samples only, median dv/dt (m/s²) by speed bin:

| bin (m/s) | 20 Hz #1 | 20 Hz #2 | 20 Hz #3 | 60 Hz |
|---|---|---|---|---|
| 5–10 | 8.73 | 8.87 | 9.71 | 8.82 |
| 10–15 | 6.96 | 7.41 | 7.44 | 6.46 |
| 15–20 | 4.90 | 4.96 | 5.05 | 4.50 |
| 20–25 | 3.34 | 3.94 | 4.52 | 3.58 |
| 25–30 | 2.97 | 3.28 | 3.54 | 2.86 |

The 60 Hz curve lies **inside the spread of three separate 20 Hz runs** in every bin — run-to-run
variation at one frame rate exceeds the difference between frame rates.

**Conclusion: no frame-coupled system was found.** Uncapped, the engine runs at 60 fps and plays
the same. The long-standing "high FPS breaks I'76" lore did not reproduce for gravity, driving,
AI speed, or weapon cadence. Untested: the Mission 5 canyon jump (needs a human to line up the
approach), flamethrower, mortar/rocket projectile range.

**Gravity constant:** `0x0043A6A1: push 0xC11CCCCD` — the float **−9.8**, an **immediate
operand** pushed with the velocity vector into `call 0x438630`. Because it is an immediate, it
is fetched as *code*: hardware **data** breakpoints never fire on it, and the `9.8` copies in
`.rdata` (`0x4BC59C`) are never read. Per-tick velocity integrator sites: `0x43A687`, `0x43A695`,
`0x43AB70`, `0x43C3C2`, `0x43BC1A`, plus higher-frequency `0x46437D` / `0x4643BA`.

---

## 5. Force feedback and telemetry capture

`I7_SFRCE.DLL` exports three symbols and **every** force event the engine plays goes through
one funnel:

| VA | meaning |
|---|---|
| `0x52BBDC` / `0x52BBE0` / `0x52BBE4` | resolved `I7FF_InitSystem` / `ExitSystem` / **`I7FF_SIM_Effect`** |
| `0x4F2328` | **364-byte effect parameter block** (`0x16C`), the function's only argument |

Dispatcher at `0x446110` fills the block and calls through the pointer; it already tolerates a
null pointer, so zeroing `0x52BBE4` (not `0x52BBD0`) disables FFB safely while still letting the
block be populated.

Inside the block: effect slots from `+0x030`, **stride `0x1C`**, ≥6 slots —
`+0x00` active flag (0→1 *is* the event), `+0x0C` effect/weapon id, `+0x10` direction,
`+0x14` magnitude/duration, `+0x18` flag. `+0x0D8` onward updates continuously at the sim tick
rate. **`+0x160` is the sim delta-time** (0.0156 s at 60 Hz, ~0.05 s at 20 Hz) — a ready-made
frame-time source for motion-sim rigs.

Caveat for capture tools: the block is only filled when an FFB device is actually present, so
on a machine without one these slots stay zero.

**For motion sim / telemetry**, the cheapest useful set is: velocity `entity+0xBC` (heave from
`+0xC0`), speed `+0xAC`, yaw rate `+0xCC`, applied steer/throttle `+0xE0`/`+0xE4`, and the
position table for world context — all readable at any rate with `ReadProcessMemory`.

---

## 6. Handling model

Fitted from 1072 live samples:

```
yaw_rate = sign(steer) * min( (v / L) * tan(|steer| * lock),  a * |steer| / v )
    lock = 0.76 rad     a = 31.0 m/s^2     L = 4.662 m     crossover ~12 m/s
```

Geometry-limited at low speed, grip-limited at high speed. No tyre or suspension model beyond
the four contact points.

---

## 7. Driving the engine from a script

Full harness and cookbook: `../autotest/README.md`. The essentials:

- **Runtime frame-rate control** — limit inside your own present hook. `i76uncap.dll` takes
  `fpscap=N` and switches 60→20→30→60 live, no relaunch. This is the only practical way to A/B
  frame rates without changing spawn conditions.
- **Input replay** — `inputrec.exe rec|play` records real keyboard/mouse with timestamps
  (low-level hooks) and replays via SendInput. A 7 s recorded drive replayed to within 3% of the
  original distance. Use it for anything a human must line up.
- **Per-frame recording** — recording from inside the present hook gives one exact sample per
  frame. External polling cannot resolve events inside a 50 ms frame (a whole launch-to-fall
  transition once fitted −38 m/s² that way).
- **Menus are mouse-only and the cursor is mapped**, not 1:1 with the screen. Calibrated:
  `screen_x = 3.98·OS_x + 393`, `screen_y = 2.77·OS_y + 120`. Menu items highlight on hover, so
  an unknown control can be found by sweeping and watching brightness — that is how every
  coordinate here was obtained, including the weapon-slot control at OS x ≈ 260.

---

## 8. Traps that produce wrong data rather than errors

Every one of these cost real time here, and none of them announce themselves:

1. **Window focus: fixed by configuration, not code.** I'76 freezes its simulation when its
   window loses focus - unless `EnableInactiveAppState = true` is in the **[General]** section
   of `dgVoodoo.conf`. It is commonly placed in [Glide], where it does nothing. With it in
   [General] the sim keeps running in the background and screen captures stay live (verified
   2026-08-09). Without it, the frame counter stalls, every sim value is bit-identical, and any
   measurement taken then is meaningless - so verify a value is *changing*, not merely present.
2. **The in-mission pause menu ("Spanner's Cafe", ESC) also freezes the sim** — and entry
   scripts that spam ESC to skip cutscenes often open it by accident.
3. **A screenshot of an unfocused game returns the last focused frame.** dgVoodoo/Glide only
   presents live while foreground, so captures come back byte-identical and look like "nothing
   changed".
4. **`VirtualQueryEx` needs `PROCESS_QUERY_INFORMATION` (0x400).** With `VM_READ` alone it
   returns 0 and you enumerate *zero* regions — silently dumping empty files.
5. **NaN defeats range filters.** `if (x < lo || x > hi) skip` never skips NaN, so a float scan
   returns hundreds of thousands of garbage hits. Use `fabs(x - target) <= tol`.
6. **Free-fall fitting must require actual falling** (≥5 frames, ≥2 m/s drop) or it fits
   suspension jitter on the ground and yields a confident, wrong gravity constant.
7. **Whole-run speed comparisons measure terrain, not physics** — a car that wanders downhill
   gains speed. Filter for level ground, or compare acceleration curves.
8. **Discrete key taps are not comparable across frame rates** — a 25 ms tap spans ~0.5 frames
   at 20 Hz and ~1.5 at 60 Hz, so a notched throttle receives different input. Hold keys.
9. **The engine rebuilds the input block from the device every frame**, so writing throttle/steer
   there is overwritten before physics sees it. Send real key state instead.
10. **A run that records nothing silently reuses the previous file.** Delete before writing, and
    fail loudly on an empty capture.
11. **The game locks its loaded DLL** — rebuilding an injected DLL fails with LNK1104 while the
    game runs, so you keep testing the old binary.
12. **PowerShell aliases shadow helper functions** (`ri` = Remove-Item) and `$pid` is reserved.
13. **Emulator-style save-states do not work here.** Restoring the process's private memory
    kills the game — the calling thread's own stack, then other threads racing restored heap,
    then still dying with all threads suspended. Heap metadata, CRT state and DirectDraw
    internals cannot be rolled back under a live Win32 process. Use the game's own bookmark
    saves (reproducible to 0.4 m) plus runtime `fpscap` instead.

---

## 9. Open questions

- ~~The **authoritative** position the physics integrator writes~~ — **closed**: the pose is the 0x40-byte
  transform at object+0x18 (3x3 float rotation, three position doubles), written by the physics directly; the
  table and scene nodes are consumers (`../i76-map/status/GOAL-COVERAGE.md:25`; the proxy's render interpolation
  swaps it in and out around the render call).
- ~~Projectile system: fired rockets do not appear in the position table~~ — **closed**: the projectile pool is
  specified in `../i76-map/subsystems/weapons.md:4-33`.
- ~~Exact field offsets inside the 0x90 component record~~ — **closed**: `components[24]`, health at +0x70
  (`../i76-map/types/i76_runtime.h:302`).
- ~~Script-VM timer semantics: frames or milliseconds?~~ — **closed**: seconds on the mission clock
  (`../i76-map/data/FSM.md:151`).
- Whether the three render back ends share the same `[0x5DD2BC]`/`[0x5DD2C0]` pointers (expected, untested —
  only Glide was exercised; the i76-map census never saw the D3D back ends run).
- `I76PATCH.DLL` internals: what it hooks, and why it overshoots to ~20.66 fps (`docs/framerate/README.md:33`;
  backlog P4-06: disassemble its trampoline for the Sleep granularity).
