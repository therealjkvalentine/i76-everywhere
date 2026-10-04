# The 60 Hz patch — design

**Goal:** render at 60 FPS while the simulation stays at its native ~20 Hz, so no
physics, AI, scripted-stunt or audio timing changes. 3 rendered frames per sim tick.

**Chosen architecture: additive extra frames at the present hook (D2DX model), NOT
sim-gating.** The engine keeps running exactly as it does today (sim+render locked, capped
to 20 by the AiO/dgVoodoo limiter). We hook the present pointer and, after each *real*
frame, synthesize 2 *extra* frames by re-rendering the scene with transforms nudged forward
along their velocities, then restore the true transforms. The engine's frame clock
(`0x49C920`/GetTickCount) is never touched by the extra frames, so the sim's sense of time —
and therefore its speed — is unchanged. This is strictly safer than gating the sim step,
which would require identifying and re-timing every frame-coupled subsystem (the Bloodborne
tar-pit).

## Why this engine allows it

- The present is a **function pointer** `[0x5DD2C0]` (and `[0x5DD2BC]` = BeginFrame). We swap
  the pointer to our thunk and chain to the original — **no code-byte patching of i76.exe**,
  so nothing is fragile against the exe and it composes with dgVoodoo/DDraw underneath.
- `render_scene` is a **plain callable** `call 0x4621E0` taking the camera struct
  (`0x4C2730`). We can invoke BeginFrame → render_scene → Flip ourselves for the extra frames.
- Sim state we need to interpolate is **all in memory at known-ish offsets**: camera angles
  `0x4C2964..74` and camera position (in the `0x4C2908..` struct), plus per-entity velocity
  `+0xBC` / angular velocity `+0xC8` on `[[[0x54A264]]+0x70]` and the whole entity table
  (`0x507DA0`). The one missing piece is the entity **position/orientation** offset —
  `tools/framerate/probe-loop.ps1 -FindPos` is built to pin it.

## The present thunk (per real frame N)

```
present_thunk(surface):
    real_Flip(surface)                      # show the true frame N first (zero added latency to it)
    save = snapshot_transforms()            # camera + every visible entity: pos, orientation
    for k in 1..2:                          # two extra frames → 3x
        alpha = k / 3.0                     # 1/3, 2/3 of a tick ahead
        for each entity e:                  # extrapolate along known velocity
            e.pos        = save[e].pos + e.velocity     * (alpha * SIM_DT)
            e.orientation= save[e].orientation ⊕ e.angvel * (alpha * SIM_DT)
        camera.pos/ang = extrapolate(camera, alpha)     # from camera deltas frame-to-frame
        BeginFrame(surface); render_scene(camera@0x4C2730); real_Flip(surface)
    restore_transforms(save)                # CRUCIAL: engine's next sim step must integrate from truth
```

- **Extrapolate, don't interpolate** (D2DX's choice): no need to hold a previous frame or add
  a frame of latency. A 1-tick misprediction (e.g. a car that just braked) self-corrects at
  the next real frame — visually a tiny hitch, not a divergence.
- `SIM_DT` = the engine's own per-frame dt (the value at `0x504A28` / the frame clock, ~1/20 s
  once the cap is on). Read it live rather than hard-coding, so it stays correct if the cap
  changes.
- **restore_transforms is load-bearing.** The extra frames mutate entity memory; if we don't
  put the true values back before the engine's next update, the integrator accumulates our
  extrapolation as real motion and the sim drifts/speeds up. Snapshot→render→restore keeps the
  sim byte-identical to unpatched.

## Milestones (each independently testable at the console)

1. **Measure & confirm (no patch).** `probe-loop.ps1 -Fps` → confirm ~20 and that `0x5A7E1C`
   is the frame counter. `-Coupling` → confirm sim==render. *(Runnable now; needs the game up.)*
2. **Present hook, passthrough.** Swap `[0x5DD2C0]` to a thunk that just calls the original.
   Prove we can intercept present without breaking rendering. FPS unchanged.
3. **Camera-only 3×.** Extra frames re-render with only the camera extrapolated (all offsets
   already known). In cockpit view the world already flows 3× smoother; other cars judder.
   This is the first real visible 60 Hz win and needs **no** new offsets — a genuine MVP.
4. **Entity extrapolation.** Once `-FindPos` pins the position/orientation offset, extend the
   snapshot/extrapolate/restore to every entity in the table. Full 60 Hz.
5. **Discontinuity guards.** Skip extrapolation for an entity on the frame it respawns,
   teleports (checkpoint), or its velocity sign flips hard (collision) — the sm64ex
   `gGlobalTimer == prev+1` idea. Prevents smeared cars on hard events.

## Delivery vehicle

No C compiler is present in this environment (i76fix/smackproxy were built with mingw
elsewhere). Two options, both matching proven repo practice:

- **Live injector (fast iteration, no build):** a PowerShell/AHK tool that WriteProcessMemory's
  a small code cave + swaps the present pointer at runtime — the same RPM/WPM route the repo's
  trainer already uses. Best for milestones 2–3 while iterating at the console.
- **Proxy DLL (shippable):** once the thunk is proven, port it to a `ddraw.dll`/renderer proxy
  built with mingw (the smackproxy pattern), so it loads automatically with the game. This is
  the form a real release would take (offsets + a tiny DLL, no game code — within the repo's
  scope rules).

## Risks / open questions

- **render_scene re-entrancy.** Does calling `0x4621E0` a second time within one frame have
  side effects on game state (advancing an animation clock, consuming a render-frame counter)?
  Must verify live — watch for state writes during the extra renders. If it does, snapshot must
  cover those too.
- **Backend sharing.** Confirm `[0x5DD2BC]/[0x5DD2C0]` are the same pointers under software /
  Glide (ZGLIDE) / D3D (ZDX5DRAW). The loop is backend-agnostic, so they should be, but the
  cost of an extra `render_scene` differs a lot by backend.
- **HUD/cockpit double-draw.** The overlay calls (`0x49B430`/`0x49BEE0`) sit between
  render_scene and Flip. For extra frames we can skip them (HUD at 20 Hz is fine) or redraw
  them — skipping is cheaper and avoids animating HUD elements 3×.
- **dgVoodoo FPS limiter interaction.** With the extra frames the app now presents 60×/s;
  dgVoodoo's `FPSLimit=20` must be OFF or it will throttle our extra frames. The engine's own
  20 Hz pacing (GetTickCount Sleep) stays as the sim pacer.
