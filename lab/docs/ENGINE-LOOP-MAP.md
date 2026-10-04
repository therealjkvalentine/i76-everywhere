# Autonomous harness — launching, menus, input, observation

> **Corrections from `../i76-map/status/findings.md` (2026-09-05, propagated 2026-10-02).**
> - **L006** — instruction addresses inside the sim-clock cluster 0x49c7f0-0x49cbd6 do **not** transfer between
>   builds: the AiO entry of 0x49c920 starts `51 ff 05 1c 7e 5a 00` where pristine starts `83 ec 08 ff 05 1c 7e
>   5a 00`. The function address holds; every instruction site quoted inside it is build-shifted.
> - **L009** — `0x504A28` (`:45`, `:47`, `:80`) is not the physics dt. It is a 1 Hz gate in WinMain 0x402b30
>   (`fsub [0x504a28]` at 0x403a3d, `fcomp` against 1.0f at 0x4bc48c); it lies above 0x501800 so it is bss, not
>   data-init. The dt is `0x4fe428` (`simclock_dt`), written by 0x49c920 and clamped to [0.001, 0.2]
>   (0x4be9ac / 0x4be9b0).
> - **L010** — `0x49C8D0` (`:79`) does not compute dt: it is a net time-offset helper (`call 0x454e00; push eax;
>   call 0x454bc0; fadd [esp+8]`, stores to 0x5a7e78 / 0x5a7e7c). dt is produced in 0x49c920 and read back through
>   `simclock_GetDt` 0x49c8b0; 0x5a7e70 / 0x5a7e78 are sim time / net offset.

*Added 2026-08-08. The game crashes easily during RE and its menus need a DirectInput cursor,
so unattended iteration needs a scripted way in. All of this is in `tools/`.*

- **Focus** (`focuslib.ps1` `Force-Foreground`): a background process can't `SetForegroundWindow`
  normally; defeat the lock via AttachThreadInput + `SPI_SETFOREGROUNDLOCKTIMEOUT=0` + an ALT tap.
  **Required before every screenshot** — dgVoodoo/Glide only presents a live image to the desktop
  while focused; unfocused, `CopyFromScreen` returns a stale frame (this wasted hours).
- **Mouse mapping** (`maplib.ps1`): the menu cursor lives in the game's internal space anchored to
  the screen's **upper-left**, NOT 1:1 with the 3440x1440 display. Calibrated:
  `screen_x = 3.98*OS_x + 393`, `screen_y = 2.77*OS_y + 120`. So the active region is ~709x454 in
  the top-left. `Click-Screen sx sy` converts and clicks. Menu items don't respond to hover-move
  visually but DO highlight (brighten) when the cursor is over them - `sweep-menu.ps1` +
  `analyze-sweep.py` find any item's hover point by brightness.
- **Keyboard** (`inputlib.ps1`): `keybd_event` with **scan codes** (DirectInput ignores posted
  WM_KEY). The main menu ignores keyboard; forms ignore ENTER too - it's a mouse UI.
- **Enter a mission** (`enter-melee.ps1`): launch -> skip intro -> MELEE(OS 450,300) ->
  AUTO MELEE(490,360) -> INSTANT MELEE(535,375) -> ENTER AREA(screen 1648,1385). Verified into the
  Tombstone arena. In-mission is detected from memory (player entity `[[[0x54a264]]+0x70]` != 0).
  Default setup: ABX Leprechaun, 1 AI car (Torque Daisy). Set A.I. DRIVERS to 0 for an empty arena.

# The gameplay frame loop — static map of the Gold i76.exe

*All addresses are our sandbox `game/i76.exe`, **MD5 `60ABF7BC699DA72476128DDCE991A3D1`**
(2019 GOG Gold / AiO lineage), loaded at 0x400000, no ASLR. Derived by static
disassembly (`tools/instruments/disasm.py` from the parent repo) — **not yet live-verified**.
The single most important result: the i76fix frame-loop hook offset `0x4039B8` lands
exactly on a `call` in this exe too, so the community's proven injection point
**transfers to our Gold build** despite the different MD5.*

## The one-screen picture

```
Fun_Real_Entry ... gameplay hot loop (one iteration = one rendered frame):

  0x4039B8  call 0x49C920     ; frame_clock_update()  ← i76fix hooks HERE (Sleep before this = FPS cap)
                              ;   - inc [0x5A7E1C]     = FRAME COUNTER (++ once per frame)
                              ;   - call [0x4BC100]    = GetTickCount import  ← the engine's pacing clock
                              ;   - store ms→seconds into the frame clock
  0x4039BD  call 0x44D9E0     ; (message pump / per-frame housekeeping)
  0x4039C2  call 0x49AEB0     ; returns eax; ==0 → quit path (0x4040BD)
  ...
  0x403A38  call 0x49C8C0     ; get_frame_time()  → fld [0x5A7E74]  (current time, seconds)
  0x403A3D  fsub [0x504A28]   ; dt = now - last   (frame delta)
  0x403A43  fcomp[0x4BC48C]   ; clamp dt (spiral-of-death guard)
  0x403A5A  fstp [0x504A28]   ; last = now
  ...       ------------------ SIM / INPUT / AI / PHYSICS UPDATE region -------------
  0x403A98  call 0x457530     ; world_ctx = [0x54A264]   (the world-context root)
  0x403DD5  call 0x461D50     ; ┐
  0x403DDF  call 0x40A320     ; │ world/AI/physics advance cluster
  0x403DE7  call 0x462A90     ; │ (one of these is the sim step; exact split = live watchpoint)
  0x403DEC  call 0x4A0410     ; │
  0x403DF6  call 0x4A4130     ; │
  0x403DFB  call 0x44AF80     ; ┘
  ...       ------------------ RENDER / PRESENT block (gated on gamestate 0x4FE534) --
  0x403E78  cmp [0x4FE534], ebp
  0x403E7E  jne 0x403EBA       ; skip render unless in the right gamestate
  0x403E80  push 0x5DCEC0
  0x403E85  call [0x5DD2BC]    ; BeginFrame(surface=0x5DCEC0)      renderer fn-ptr
  0x403E8E  push 0x4C2730
  0x403E93  call 0x4621E0      ; render_scene(camera=0x4C2730)     ← draws the world
  0x403E9B  call 0x49B430      ; (HUD / cockpit overlay)
  0x403EA0  call 0x49BEE0      ; (   ''   )
  0x403EA5  push 0x5DCEC0
  0x403EAA  call [0x5DD2C0]    ; Flip(surface)  = PRESENT           renderer fn-ptr
  ...
  (loop back-edge → next frame)
```

## The addresses that matter for 60 Hz

| What | VA | How found | Confidence |
|---|---|---|---|
| **Frame counter** (++ per rendered frame) | `0x5A7E1C` | `inc` at top of 0x49C920 | static, strong |
| **Frame-clock update fn** (reads GetTickCount) | `0x49C920` | i76fix-hooked call target | static, strong |
| GetTickCount import ptr | `0x4BC100` | i76fix delay.c names it; matches `call [0x4BC100]` | confirmed (i76fix) |
| **get_frame_time()** → current time (s) | `0x49C8C0` | `fld [0x5A7E74]; ret` | static, strong |
| Frame clock: current / prev / dt (float, s) | `0x5A7E74` / `0x5A7E70` / `0x5A7E78` | operands around 0x49C8D0 | static, medium |
| Per-frame **dt** + last-time (physics-side) | `0x504A28` | `fsub/fstp` in the loop | static, strong |
| dt clamp constant | `0x4BC48C` (.rdata) | `fcomp` guard | static |
| **i76fix hook site** (Sleep-before-clock) | `0x4039B8` | matches patch.s PATCH5; lands on a `call` here too | verified transfers |
| CPU-measurement no-op (i76fix PATCH1) | `0x499B25` | patch.s | needs re-check on this exe |
| **render_scene(camera)** | `0x4621E0` | `push 0x4C2730; call` | static, strong |
| **BeginFrame fn-ptr** | `[0x5DD2BC]` | `push surf; call [ptr]` | static, strong |
| **Flip / Present fn-ptr** | `[0x5DD2C0]` | `push surf; call [ptr]` | static, strong |
| Render surface struct | `0x5DCEC0` | pushed to Begin/Flip | static |
| Camera struct (arg to render_scene) | `0x4C2730` | pushed to render_scene | static; camera angles at 0x4C2964.. (parent repo) |
| Gamestate / render-gate flags | `0x4FE534` | `cmp/test` gates | static |

## WORLD POSITION TABLE — FOUND, 2026-08-08 (the blocker is cleared)

**`0x0054E11C`, static, stride `0x20`, in i76.exe `.data`** (containing region base `0x541000`).
Found by a whole-heap differential scan (`tools/instruments/scan-heap.ps1`): three snapshots of all 976
writable regions (160 MB) while driving, keeping only float3s whose *both* deltas matched
velocity x dt. 11 survivors, all resolving to this one table plus its copies.

```
record (stride 0x20), position at the VA below:
  +0x00  float x   world position
  +0x04  float y   height
  +0x08  float z
  +0x0C  float     bounding radius (player 2.759, AI cars 1.950)
```

| idx | VA | live sample (x,y,z) | radius | what |
|---|---|---|---|---|
| 0 | `0x54E11C` | 1409.51, 28.73, 49603.19 | 2.759 | **player** - moved 12.44 m in 0.869 s at 15 m/s |
| 1 | `0x54E13C` | 1603.79, 25.88, 49533.45 | 1.950 | AI car (moved -4.06 X while player moved +12.43) |
| 2..4 | `+0x20` each | ~1523-1680, ~26, ~49533-49680 | 1.950 | AI cars |
| 5..6 | `0x54E1BC/DC` | y~108-110, z~50370 | 1.950 | elevated/distant objects |
| 7+ | | all zero | 0 | empty slots |

Also found, and directly useful:
- **`0x005443B0` / `0x005443BC`** - the player's AABB **min / max** corners (float3 each, 0xC
  apart; ~6.5 m x 5.6 m apart = car-sized). Both track the player.
- Heap mirrors of the player transform at `0x02FF7D70`, `0x02FF7DB0`, `0x02FF7EB4`, `0x02FF7EF4`,
  `0x03030818`, `0x03030858`, `0x030308FC`, `0x0303093C` - all carrying identical values, i.e. the
  per-node scene copies. **Which of these the renderer actually consumes is still unverified** and
  decides where interpolated values must be written (see PATCH-DESIGN risks).

**Why every earlier scan missed it:** it is not in the player entity struct. The entity
(`[[[0x54a264]]+0x70]`) holds velocity/speed/controls/wheel-contacts but *no* world position -
its allocation ends at `+0x6000` and no triple inside it tracks the velocity vector (verified
with a 14-snapshot turning series). Position lives in this separate static table. This also
explains the repo's long-standing "translation reads origin-small" note in
MEMORY-MAP-INDEX.md - the transform block's translation is not the world position.

**Measurement caveat that invalidated three earlier attempts:** I'76 **freezes its simulation
when the window loses focus** while the renderer keeps running (frame counter advances, sim
state bit-identical). Any capture taken while the game is not focused is stale. All capture
tools now wait for a *changing* value, not merely a non-zero one; `autotest/diagnose/check-sim.ps1`
reports the state directly.

### Which copy the RENDERER reads — settled by hardware watchpoints (2026-08-08)

Screenshot A/B could not attribute anything (ambient AI/car motion swamped the effect, and
moving player copies doesn't change the cockpit view — the player's own car isn't drawn there).
So `src/find-reads.c` (a hardware-data-breakpoint debugger, `DebugActiveProcess` + Dr0-3
read/write breakpoints, MSVC 32-bit) logged the exact instruction that reads each copy. 6 s,
3582 hits:

| copy | read by | verdict |
|---|---|---|
| `0x54E11C` (culling table) | **exe only**: `0x469958/0x469976/0x46989E/0x4685F4/0x4224B1` | AI/radar/collision - **NOT rendered** (matches the poke test) |
| `0x02F892A0` (heap scene node) | **renderer DLL** `0x6BF782E2` (1109), `0x6BF76705` (1080), `0x6BF76FFB` | **render transform**, read per-draw (~18x/frame) |
| `0x02F8A830` (heap scene node) | **renderer DLL** `0x6BF770C3` | render transform |
| `0x5FCDC4` (static pos+matrix) | **both**: renderer `0x6BF76012/0x6BF70C03` + exe `0x421967/0x4224B1` | render-consumed static transform |

The `0x6BF7xxxx` reader is the loaded Glide/dgVoodoo **renderer DLL** (non-ASLR base ~0x6B000000).
**Conclusion: interpolation must write the heap scene nodes (and/or `0x5FCDC4`), never the culling
table.** The scene node layout (from the dump) is `[pos float3][3x3 rotation matrix][flags/ptrs]` -
a full pose, so extrapolation can nudge position and leave rotation, or slerp both.

**WARNING — `find-reads.c` crashed the game on detach** (crash dump `i76.exe.14016.dmp`). The
histogram it printed before the crash is valid, but the attach/detach is not yet safe to leave
running unattended. Prefer short windows and expect a relaunch.

### What the position table is NOT (write-tested 2026-08-08, sandbox)

`tools/instruments/poke-pos.ps1` offset the player's Y in the table by +40 m for 4 s on the sandbox
instance, with before/after screenshots. **The picture did not move.** `tools/instruments/verify-write.ps1`
then proved this is not a failed write:

```
addr 0x54E120  original = 26.552
WriteProcessMemory -> ok=True bytesWritten=4
immediate read-back = 66.552   (wanted 66.552)
after 120 ms        = 66.552
after 620 ms        = 66.552      <- the engine did not even overwrite it
```

So `0x54E11C` **is** the world position (it tracks driving exactly) but it is a
**derived/cached list** - radar, AI targeting, audio or collision broadphase - and the
renderer does not draw from it. It is excellent for READING (telemetry, radar, minimap,
mission logic); it is useless as a write target for interpolation.

### The camera struct holds no per-frame position

Checked `0x4C2700..0x4C2A80` across the driving snapshots: **not one float changed** while
the car moved. The engine therefore computes the view transform per frame from the car's
state instead of storing it. That is consistent with head-tracking working by writing camera
*angles* (`0x4C2964/70`, read fresh each frame) while there is no camera *position* to move.

**Consequence for the patch:** the transform the renderer consumes is neither the static
table nor the camera struct - it is the per-entity scene node on the heap (the copies seen at
`0x02FF7D70`/`0x03030818` in one session). Heap addresses are per-session, so they must be
re-found in the live process and poke-tested in the same session. The decisive tool is
write -> screenshot -> compare -> restore, which identifies render-consumed addresses directly
without having to trace the data flow.

## Present hook — live-confirmed target (2026-08-08)

Reading the pointers out of the running process (`readptr`, read-only) resolved them
**inside i76.exe**, not into a Glide/DDraw DLL — they are the engine's own present wrappers:

| loop fn-ptr | resolves to | what it is |
|---|---|---|
| `[0x5DD2BC]` BeginFrame | `0x434340` | begin-frame wrapper → `call 0x42DD30(surface)` into the backend |
| `[0x5DD2C0]` Flip | `0x4343D0` | present wrapper: if flag `[0x5280CC]` set → `call [0x608BCC]` (real backend present), else `call 0x431C70`; returns 1 |

So the backend present is the fn-pointer **`[0x608BCC]`**, gated by render-active flag
**`[0x5280CC]`**. Two equivalent hook points, both stable and in-exe:
- **Preferred:** swap the loop pointer `[0x5DD2C0]` → our thunk → chain to `0x4343D0`
  (the thunk owns the whole present, so it can re-run BeginFrame/render_scene/Flip for extra
  frames). No code-byte patch of i76.exe.
- Alt: swap `[0x608BCC]` (the backend present) if we want to sit below the wrapper.

This confirms PATCH-DESIGN milestone 2 has a concrete, low-risk target.

## What this settles

- **The Roanish `world_tick(in, dt)` fixed-step + interpolation is his REWRITE, not the
  original.** His `src/engine/loop.c` header says *"We reproduce that shape"* and hard-codes
  `FIXED_STEP = 1.0/60.0`; the original binary just does **time-delta → update → render once
  per frame** (the map above). So the repo's central contradiction is resolved in favour of
  every field test: **sim == render, one sim step per rendered frame, no interpolation exists
  yet.** That is exactly the condition the 60 Hz plan is built for.
- **The engine's pacing clock is `GetTickCount`** (via `[0x4BC100]`), read once per frame in
  0x49C920. i76fix caps FPS by `Sleep()`-ing before that call. Our extra render frames must
  **not** touch 0x49C920 or the frame clock, or they would be counted as engine frames and the
  sim would speed up.
- **The present is a fn-pointer (`[0x5DD2C0]`)** — hookable without patching the exe's code
  bytes (swap the pointer, chain to the original). That is the clean insertion point for extra
  frames (see PATCH-DESIGN.md).

## Still unknown (the live-only gaps)

- **Entity world-position and orientation offsets.** render_scene (0x4621E0) reaches them
  through matrix builders (0x474D40 / 0x46FFC0 / 0x474C60) several calls deep — not cheap to
  resolve statically. The parent repo left this OPEN ("needs drive-correlation or a render
  watchpoint"). Velocity (+0xBC), speed (+0xAC), angular velocity (+0xC8) on the player entity
  `[[[0x54A264]]+0x70]` are already verified — position is almost certainly adjacent. **This is
  the one blocker for entity interpolation** and the target of `tools/framerate/probe-loop.ps1 -FindPos`.
- Which call in the 0x403DD5–0x403E00 cluster is the physics step vs. AI vs. prep (only matters
  if we gate the sim rather than add extra frames — the current plan does not).
- Whether `[0x5DD2BC]/[0x5DD2C0]` resolve into ZGLIDE/ZDX5DRAW/DDraw and whether all three
  render backends share this pointer pair (they should — the loop is backend-agnostic here).
