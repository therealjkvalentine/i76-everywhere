# Raising the REAL frame rate — research verdict and the go/no-go checklist

*Research pass 2026-08-08: 9-agent sweep (4 over this repo's RE docs, 4 over the web, 1
adversarial synthesis). **Nothing in this doc is field-tested** — it is a map of what is
known, what is folklore, and what to measure next. Confidence tags: **[verified]** =
repo field test or fetched primary source; **[probable]** = consistent secondary
evidence; **[folklore]** = repeated claim nobody has measured.*

**The question:** can the engine's real frame rate be doubled/tripled (20 → 40–60) by
scaling the physics so it doesn't break? Frame generation (LSFG x2, see
[Setup-FrameGen.ps1](../Setup-FrameGen.ps1)) already fakes 40 at the display; this is
about real frames.

## Verdict

**Plausible — but only by inverting the question.** Don't scale the physics; leave the
20 Hz sim untouched and make the *renderer* run 2–3x per sim tick with
interpolated/extrapolated transforms (the D2DX / SM64-60fps / Ship of Harkinian shape).
Every field-verified fact says the engine advances physics, AI, script VM, and even
weapon audio **once per rendered frame with per-frame-tuned constants**, so raising the
actual tick rate inherits an unbounded tail of per-subsystem breakage and can never be
faithful to era-tuned stunts (the Mission 5 jump). Render decoupling has genuine
closed-binary precedent and no evidence against it — but it is blocked today by two
concrete unknowns: **entity position/orientation offsets** (still OPEN in
[GHIDRA-MEMORY-MAP.md](GHIDRA-MEMORY-MAP.md)) and **the Gold exe's main-loop/render
seam** (no Gold VA exists for the loop). The first five checklist items below convert
"plausible" to go/no-go with tooling the repo already has.

## The premise inversion — what the engine actually does

- **The shipped engine has NO frame limiter and NO sim/render separation.** It runs the
  main loop as fast as the machine allows; the 20 FPS "lock" is imposed from outside
  (UCyborg's I76PATCH.DLL, dgVoodoo `FPSLimit`, i76fix's injected Sleep — every known
  community fix is a limiter). [verified — repo field tests + Peelar's blog]
- **Sim advances once per rendered frame.** DxWnd throttling the ddraw Flip throttles
  physics; qemu-3dfx runs the game fast regardless of limiter. [verified]
- **The coupling is not one clean dt.** UCyborg: it "isn't intentionally tied to
  frame-rate" — scattered per-frame constants and integer accumulation. Symptom
  direction proves it: jump distance *shrinks* as FPS rises, i.e. per-frame impulses
  don't rescale with time. Degradation is continuous/monotonic, not thresholded —
  exact-multiple rates (40) buy nothing. [probable — multiple independent sources]
- **But a wall-clock dt exists somewhere:** the FFB param block holds a live, varying
  dt float at `0x4f2488` (block +0x160; observed 0.047–0.063 s). Only proven to reach
  the FFB builder; nobody has traced its writer or other readers. The repo's single
  pinned timing value. [verified — live memory]
- **Known breakage ladder (folklore, never measured per-mechanic):** MG audio breaks at
  ~24; flamethrower extension, mortar range, AI top speed (~35 mph cap + brake
  flutter), scripted-event timing, and jump ballistics degrade above ~20. The Mission 5
  jump fails even at the AiO limiter's own measured 20.66 FPS — which is why this
  repo's wrapper caps sit at-or-under 20 (`FPSLimit=20` / 19.2).

## The four routes, ranked

### 1. Render-decoupled interpolation/extrapolation — the plan of record

Keep the 20 Hz tick (retain the limiter as sim pacer). Find the main-loop seam between
sim-step and render call; run the render path 2–3x per tick with interpolated
(prev+current state, sm64ex-style, discontinuity guards for respawns) or extrapolated
(pos + velocity·elapsed, D2DX-style) entity + camera transforms. Velocity (+0xbc),
angular velocity (+0xc8) and camera floats (`0x4c2964/70`) are already mapped and
writable; extrapolation is the cheaper variant (no prev-state capture; 1-tick
mispredictions self-correct — D2DX's documented behavior). Delivery: in-exe injection
at the frame loop (i76fix proves the pattern on this exe family) or a proxy DLL
scheduler (proven build chain: [smack-music-fix](../smack-music-fix/),
winmm-cdaudio). HUD/cockpit/audio stay 20 Hz — acceptable. FFB/telemetry unaffected
(sim tick never changes).

*Blocked by:* position/orientation offsets unfound; unknown whether the renderer reads
entity structs directly vs a snapshot/scene list; unknown whether the draw path can run
twice per tick without advancing game state; three render backends may not share one
submission point.

### 2. True dt rescale — run as one-day reconnaissance, not the plan

Find-what-writes on `0x4f2488` (native x32dbg/Cheat Engine on the Windows box —
strictly easier than the documented Mac winedbg route). Learn who computes dt, from
which clock, who reads it. All evidence says a full rescale fails (Quake 3 / DSfix /
Bloodborne: even engines *with* a dt break at other rates), but the tracing output is
required by routes 1 and 3 anyway — and the observed ~30% dt spread (47–63 ms) means
*something* already tolerates variable dt; a modest 25–30 Hz raise has never been
costed honestly.

### 3. Raise the tick, repair each subsystem (anpage/Bloodborne pattern) — follow-on only

anpage proved the shape works in this exact engine lineage (MW2 jump-jet
integer-quantization: per-frame tick delta ÷ 4 floors to 0 above 45.5 FPS; fixed with a
cross-frame tick accumulator injected into null padding). But for I76 the repair list
is unbounded (physics, AI FSM, script VM, audio retrigger, suspected ram-to-heal
accumulator), and even "fixed," integration error changes — era-tuned stunts need
per-stunt retuning. Result is a variant game. Bloodborne's 60fps took a world-class RE
months on a better-instrumented engine.

### 4. Time-source dilation hooking — REFUTED as a solution; diagnostic only

Warping timeGetTime/QPC (Cheat Engine speedhack, DxWnd Time Stretch) changes **game
speed, not smoothness** — tick scheduler and per-tick step read the same lied-to clock.
Zero counterexamples exist anywhere. Budget one day with a winmm proxy (from the
[tools/winmm-cdaudio](../tools/winmm-cdaudio/) pattern) purely to learn which clock, if
any, paces the sim. Note: the 2017 Galaxy exe imports **no winmm at all**; only the
2019 lineage imports timeGetTime.

## What to learn next — ordered, cheapest and most decisive first

1. **Pin the exe lineage (30 min; blocks everything).** i76fix targets MD5
   `9a232dcc2c164648cff20c414c1f9698` — repo-verified as the **2017 Galaxy** exe, *not*
   the 2019 Gold/AiO `60abf7bc…` the memory map targets. MD5 the local exes; if
   josecoelho's i76_24fps.exe is around, diff it (~136 changed bytes = the community's
   proven loop hook, free).
2. **Settle the architecture contradiction.**
   [MW2-I76-STRUCTS.md](MW2-I76-STRUCTS.md) claims (via Roanish) a fixed-step
   `world_tick(in, dt)` with render interpolation *already exists*; every field test
   says sim==render with no dt. Under a 20 cap the two are **observationally
   identical** — all our 20 Hz measurements were taken under a cap and prove nothing
   about coupling. Read Roanish's REVERSING.md: is that his rewrite's design or a
   decompiled finding? This decides whether route 1 is a graft or a restructure.
3. **The uncap experiment (one session, definitive).** Raise/remove FPSLimit with the
   memory harness polling speed (+0xac) and the +0x0D8 per-tick region at high
   frequency. Sim tick tracking render rate 1:1 proves sim==render directly. Record
   `0x4f2488` uncapped too.
4. **Re-anchor the main loop into the exe we'd patch.** Disassemble around i76fix's
   frame-loop hook (`0x4039B8` i76.exe / `0x432805` nitro.exe; CPU-measure no-op at
   `0x499b25` / `0x49AE45`) with [tools/exe-xref.py](../tools/exe-xref.py) + the
   capstone disasm tooling; re-anchor the `while(g_gamestate==5)` hot loop
   (g_gamestate @ Nitro `0x4f30cc`) via string xrefs. Deliverable: Gold VAs for the
   sim-update call and the render/present call — **the seam every route needs**.
5. **Find-what-writes on the dt float `0x4f2488`** (see route 2).
6. **Xref timeGetTime's import (2019 exe) to call sites** — loop pacing vs MCI music vs
   joystick. With item 5, answers "does the sim path read a wall clock at all." The
   winmm-proxy warp is the dynamic version if static tracing is ambiguous.
7. **Hunt entity world-position + orientation offsets — the blocking data gap.**
   Live-test Roanish's +0x84..+0xab transform block on the Gold player entity; drive
   straight at known speed and scan for floats stepping v·0.05 per tick; watchpoint the
   velocity writer (the integrator writes position nearby). AI entities via the entity
   table (`0x507da0`/`0x51f5d0`).
8. **Find the renderer's transform read site** (hardware read-watchpoint on position
   once found): direct struct read vs snapshot vs scene list, and whether
   software/Glide/D3D share one choke point. Decides if route 1 has one seam or three.
9. **Reverse I76PATCH.DLL** (present in the Mac GOG install per
   [MAC-BUILD.md](MAC-BUILD.md); absent from both Windows installs — presence varies by
   install). What does its QPC+Sleep trampoline hook, and why does it overshoot to
   20.66? Its insertion point is a field-proven host for a scheduler.
10. **Build the per-mechanic breakage ladder nobody has:** 22/25/30/40 FPS with the
    memory harness measuring Mission 5 jump distance, flamethrower reach, mortar range,
    AI top speed, MG audio. Converts the folklore thresholds (20.66 vs 24 vs ~25 vs
    ~30 — the docs disagree) into data; bounds route 3's repair scope.
11. **Trace the `toggle_framerate` action string** to its handler via the input-action
    table — whatever it toggles is engine framerate machinery, found from a string
    anchor.
12. **Scan .data for a 20 Hz tick-counter global and 0.05f / 1/20f constants.** Nobody
    has looked; a tick counter anchors script-VM timer analysis (frames vs ms), which
    route 1 needs to rule out render-frame-counter consumers.

## Prior art — what each piece actually proves

| Prior art | What it proves |
|---|---|
| **[D2DX motion prediction](https://github.com/bolrog/d2dx/wiki/Motion-Prediction)** | **The strongest precedent, exact shape of route 1**: Glide wrapper for closed-source Diablo II (25 Hz logic) rendering 60+ real fps by extrapolating unit/missile/weather positions between ticks. No source, zero added lag, self-correcting mispredictions. Open source — its state-access mechanism is the implementation blueprint (nobody has read the code yet). |
| **Kaze Emanuar SM64 60fps (2018) + [sm64ex 60fps patch](https://github.com/sm64pc/sm64ex/blob/nightly/enhancements/60fps_ex.patch)** | Kaze's hack predates the SM64 decomp — interpolation retrofits at the binary level. sm64ex documents exactly what state to capture: prev transform + timestamp per object, camera prev-state, `gGlobalTimer == prev+1` guards so teleports skip interpolation. |
| **Ship of Harkinian / Doom ports / KEX** | The 20 Hz-logic + interpolated-render model is fully sound (SoH keeps OoT logic at exactly 20 Hz — same rate as I76). They had source/decomp; they prove the model, D2DX/Kaze prove binary-only delivery. |
| **[i76fix](https://github.com/immi101/i76fix) (immi101)** | The map into this exe family's timing code: frame-loop hook addresses (above), GetTickCount+Sleep injected into the draw loop, CPU-measurement disable. Proves in-exe injection works here. Targets the **2017 Galaxy** exe. |
| **[anpage's MW2 jump-jet patch](https://gist.github.com/anpage/9b5ec3d72200117e224b2e696e8b4280)** | Per-subsystem framerate-independence repair works in this engine lineage. Also the lineage's timebase heritage: 182 Hz AIL/Miles timer; Win95 builds paced by winmm timeSetEvent via wail32 (why checklist 5/6 target winmm). |
| **[mw2hook](https://codeberg.org/retropc/mw2hook) (retropc)** | Detours-based DLL interposition fixing framerate bugs in the Win95 sibling builds — the delivery-vehicle template. Practical note: its limiter busy-waits on timeGetTime ("sleeping here screws up windows"). |
| **Bloodborne 60fps / DSfix / Quake 3 pmove / FramerateVigilante / dethrace** | The cost model and warning for routes 2/3: naive unlocks run fast-forward; dt-aware ports still need hand-patching (cloth, elevators, AI pathing); dt-unlocked games break era-tuned content (DSfix shorter jumps, ladder fall-throughs; Q3 jump height varies with FPS — id's fix was to **re-lock** the timestep); 1997 engines bake the step into constants (dethrace made `physics_step_time` configurable). |
| **[Cheat Engine speedhack](https://wiki.cheatengine.org/index.php?title=Cheat_Engine:Internals) / DxWnd Time Stretch** | Route 4 refuted: uniform time-lying changes gameplay speed, never smoothness. Retained value: the hook set (GetTickCount/timeGetTime/QPC) is the menu of clocks a 90s game can pace with. |
| **[Shane Peelar's RE blog](https://inbetweennames.net/blog/2021-05-04-interstate-76-reverse-engineering-efforts-the-story-so-far/) + UCyborg (VOGONS)** | The authoritative history: the 30→24→20 limiter ladder, physics AND AI framerate-dependent, MG audio at 24, "isn't intentionally tied to frame-rate." No memory maps published — there is no external shortcut to the timing internals. |
| **Lossless Scaling LSFG (field-verified 20→40) + ReShade's refusal** | The zero-RE baseline any real patch must beat: display-only interpolation, physics correct, latency stays ~20fps. ReShade cannot add frames; OptiScaler-class FG needs motion vectors a 1997 engine can't supply. |
| **Roanish/i76 decompile ("Vigilante 76", Nitro exe)** | Source of the WinMain/state-machine map and `g_gamestate` anchor. Vehicle physics/collision/damage: "Not started." Its `world_tick` fixed-step description is suspect (likely rewrite architecture, not recovered original) — checklist item 2. |
| **30 years of MW2/I76 community work** | **Nobody has ever attempted decoupling or a rescale in this engine family.** Every shipped fix is a cap. Open field: no roadmap, no known blocker. |

## Web claims the repo's field tests overrule

- PCGamingWiki's "24 FPS is fine / breakage starts above 30" — the Mission 5 jump
  fails at the AiO limiter's own **20.66** measured FPS. Caps stay at-or-under 20.
- GOG-forum claim of stable physics at 200+ FPS after the Feb 2021 update —
  contradicts live 20 Hz memory measurements and every other source. Discounted.
- "The GOG 2019 exe universally ships I76PATCH.DLL" — presence varies by install
  (absent from both Windows installs here, present on the Mac one).
- "Nitro's engine handles frames differently" (AiO reportedly caps Nitro at 24 vs 20) —
  unverified folklore; but if true, the two exes differ somewhere in timing code, a
  valuable diff target.

## True unknowns — what no research stream answered

- Where the physics integrator lives and whether ANY dt feeds it (the decisive
  question; public decompile coverage of vehicle physics is "Not started").
- Strict sim-per-frame vs latent tick structure (all 20 Hz measurements were taken
  under a 20 cap — observationally identical; needs the uncap experiment).
- Entity position/orientation offsets (the +0x08 "rotation matrix" was wheel contact
  points; orthonormality scan found no matrix in the first 0x200 bytes).
- Renderer read path (direct/snapshot/scene-list; one seam or three backends).
- Script-VM timer semantics: frames or milliseconds?
- I76PATCH.DLL internals (never disassembled by anyone; the 20.66 overshoot).
- D2DX's exact state-access mechanism (in its source; unread).
- Whether the sim already tolerates the observed 47–63 ms dt variance — if yes, a
  modest 25–30 Hz raise may be far cheaper than assumed.

## Sources that stayed dark (don't re-chase blind)

VOGONS t=40829 replies (UCyborg may have posted disassembly detail); PCGW AiO file
page (403 — main page worked via the MediaWiki API); interstate76.com forums (DNS-dead
/ fetcher banned); replaying.de (expired TLS); Dev Game Club ep 427 (Vesce/Norman
interview, untranscribed — possible dev statement on timing); GTAForums/libertycity
FramerateVigilante bug catalogs (403); web.archive.org (blocked in the research
environment).
