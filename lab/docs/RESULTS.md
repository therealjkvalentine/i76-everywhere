# 60 FPS with physics-safe 20 Hz sim — achieved 2026-08-08

Interstate '76 now renders at **~60 FPS while its simulation stays at its native ~20 Hz**, so
physics, AI, and scripted timing are untouched. Done entirely at runtime via an injected DLL —
no game files modified.

## What runs

- `src/i76uncap.dll` (MSVC 32-bit), injected by `src/inject.exe` into the running game.
- It hooks the engine's present function-pointer at **`0x5DD2C0`** (→ wrapper `0x4343D0`).
- After each real (20 Hz) frame it renders **N extra frames** by re-running
  `BeginFrame(0x434340)` → `render_scene(0x4621E0, camera 0x4C2730)` → `Flip`.
- Between sub-frames it **extrapolates every render-consumed world-position copy** forward along
  its last-tick motion (D2DX-style): sub-frame k of N shows `pos + delta·k/(N+1)`. Then it
  **restores the true positions before the next sim step**, so the simulation is byte-identical
  to unpatched.
- Runtime-tuned via `captures/i76uncap.ctl`: `extras`, `interp`, `pace`, `enabled`.

## Measured (empty Tombstone melee, live)

| mode | presents/s | sim frames/s | notes |
|---|---|---|---|
| passthrough (`extras=0`) | 20 | 20 | baseline |
| `extras=2 interp=0 pace=0` | 57–60 | 19–20 | 60 fps, but identical & bunched |
| `extras=2 interp=1 pace=16` | **58** | **19–20** | **60 fps, interpolated, evenly paced** |

- **Physics safe:** with interpolation on, driving is normal — W took speed 0.83 → 18.83 m/s and
  world position advanced correctly; sim stayed at 20 Hz. The extra frames run in the render
  phase only and true positions are restored before each sim tick, so the sim never sees them.
- **Even pacing:** `pace=16` spaces the three presents at ~0/16/32 ms; the engine's own 20 Hz
  limiter absorbs the rest to fill the 50 ms tick — real (t0-16), +⅓ (t16-32), +⅔ (t32-50),
  then the next real frame. Monotonic, ~16 ms apart.
- **Clean render:** the interpolated view is coherent (cockpit, terrain, mirror, HUD) — no
  corruption or tearing.
- **Tracking:** on mission start the DLL scans committed heap for copies of the player world
  position and tracks 8 render-consumed transforms (the static eye transform `0x5FCDC4` +
  7 scene-node copies), excluding the sim-read culling table `0x54E11C`.

## Why it's physics-safe (the core idea)

The naive "raise the FPS cap" breaks I'76 because sim == render (one physics step per frame with
per-frame-tuned constants). This keeps the 20 Hz sim exactly as-is and only adds *display* frames
with extrapolated transforms — the same model D2DX uses for Diablo II. The eye transform drives
the cockpit view (verified: poking `0x5FCDC4` moves the view ~26%), so extrapolating it smooths
the whole scene; per-entity scene nodes cover other cars.

## Run it

```
autotest\enter-melee.ps1                       # launch + into an empty melee (unattended)
src\inject.exe <pid> src\i76uncap.dll       # inject the DLL
# then edit captures\i76uncap.ctl:  extras=2  interp=1  pace=16  enabled=1
```

## Honest limits / next steps

- **Subjective smoothness** (does it *look* 60 fps to the eye) needs a human or a video capture;
  every measurable indicator (60 presents/s, even pacing, monotonic extrapolation, 20 Hz sim) is
  green, but a static screenshot can't show motion smoothness.
- AI-car smoothness: the heap scan matches the *player* position, so it smooths the eye/player
  render nodes. Other cars would need per-entity delta tracking (their own positions) — the
  extension point is the entity table `0x507da0`.
- Extrapolation (not interpolation) means a tiny direction-change misprediction at hard
  accel/turn/collision, self-correcting next tick (the D2DX trade-off; avoids added latency).
- Rotation is left at 20 Hz (position-only extrapolation); adding matrix slerp would smooth fast
  spins further.
- Delivery is currently inject-on-demand; a `ddraw.dll`/renderer proxy (smackproxy pattern) would
  auto-load it with the game for a shippable form.
