# What "stock" means for Interstate '76 (2026-10-13)

The owner asked: "Didn't the stock game run at different fps depending on hardware? Why 24 fps in particular (20 was said
to be right at some point; we used 19.x to get jumps working)? How do we know what stock behaviour is at all, since our
hardware is so different from the 1997 target?"

Full write-up, sources and data: lab `docs/AI-COMBAT-PARITY-2026-10-13.md` (sections 1-3 and 6). This page is the summary.

## Short answers

1. **Different fps on different hardware: yes.**
   - The engine has no frame cap. WinMain renders as fast as it can, and the whole simulation runs off one clock read per
     frame: `GetTickCount`, the Windows millisecond counter.
   - So the 1997 game ran at whatever the machine managed. Every cap anybody uses (20, 24, 25, 30) was added later, by the
     community or by us.
2. **Why 24.** It is not a 1997 number. It comes from this PC's clock.
   - On Windows 10, GetTickCount only moves in steps of 15.625 ms.
   - Capped at 20 fps (what we played under GOG's I76PATCH.DLL until 2026-10-03), each 50 ms frame reads as 46.9 or 62.5 ms.
     The engine cuts frames into physics steps of at most 50 ms. Measured 2026-09-27 (i76-map capture 014), that comes to
     **24 physics steps a second**, averaging 41.7 ms.
   - That is why `I76_FIXED_STEP=24` matches the jumps and the chassis feel of "stock 20". The first try, 40 steps a
     second, landed jumps short.
3. **"stock24" and "stock20" are two names for nearly the same physics.**
   - Later lab work used `stock24` (no switches, a 24 fps cap) as "the 1997 game as played". That name was wrong: nothing
     ties 24 fps to 1997.
   - On this clock, a 24 fps cap gives the **same physics step stream** as a 20 fps cap: 46.9 / 31.25 ms steps in the same
     2:1 mix.
   - What differs is what runs once per FRAME. At 24 fps the AI makes 24 decisions a second, at 20 fps it makes 20, and the
     frame-to-frame clock pattern the AI steers by is different.
   - The lab now uses **stock20** (the capped game we actually played) as the reference.
   - `stock24` stays as a bracketing profile. The measured difference between the two is in the lab doc, section 6.
4. **19.2 fps** came from the Mac build (DxWnd, 52 ms frame delay), where it cleared the Mission 5 canyon jump.
   - On Windows, the dgVoodoo `FPSLimit 19.2` was found to do nothing. I76PATCH was the real cap, and the lab cleared the
     same jump at 60 fps.
   - The jump turned out to depend on the physics **step size**, which is what `I76_FIXED_STEP=24` fixes.
5. **What the 1997 machines really did is not measured.**
   - No period benchmark of this game was found.
   - Anecdotes suggest a Pentium 166 with a Voodoo 1 was "playable with slowdowns" (roughly 15-25 fps, varying by scene),
     and software rendering was slower.
   - Windows 95's GetTickCount is believed to tick at about **55 ms** (the PC's 18.2 Hz timer), but that is not confirmed.
     Windows 98 may tick at 10 ms or at 55 ms. NT ticks at 10 or 15.6 ms.
   - With a 55 ms tick, a 20 fps game reads most frames as 55 ms and some as 0 ms (which the engine turns into 1 ms). That
     is a very different clock from ours.

## Reference profiles the lab can now reproduce on this PC

`I76_FPS_CAP` sets the frame rate. The new lab switch `I76_TICK_MS` sets the clock tick: the proxy rounds the sim clock
down to that tick in place of GetTickCount.

| profile | switches | what it stands for |
|---|---|---|
| **stock20** (the reference) | `I76_FPS_CAP=20` | stock exe, Windows 10 clock, 20 fps: GOG's I76PATCH as James played it to 2026-10-03 |
| stock24 | `I76_FPS_CAP=24` | same clock at 24 fps (lab convention 10-08..10-13) |
| R-1997a | `I76_FPS_CAP=20` + `I76_TICK_MS=55` | Windows 95 clock (if 55 ms), ~20 fps (P166 + Voodoo 1 class) |
| R-1997b | `I76_FPS_CAP=30` + `I76_TICK_MS=55` | Windows 95 clock, ~30 fps (faster 3D card) |
| R-1997c | `I76_FPS_CAP=30` + `I76_TICK_MS=10` | Windows 98 / NT 10 ms clock, ~30 fps |
| control | `I76_FPS_CAP=20` + `I76_TICK_MS=15.625` | must behave as stock20 (checks the emulation) |

## What the measurements say (lab twin, n = 5-9 per condition)

- **The emulation works.** The control profile behaves as the real clock does.
- **stock24 vs stock20:**
  - T04 racers are 0.7-1.8 s a lap slower at 24 fps;
  - the t13 attacker stays about 190 m farther away;
  - the AI makes 24 fire decisions a second instead of 20.
  The choice of reference matters.
- **Windows 95 clock (55 ms), measured on this PC:**
  - **R-1997a** (55 ms tick at 20 fps): racers lap 8 s slower, and the AI steering wobbles about 4x as much.
  - **R-1997b** (55 ms tick at 30 fps): racers barely finish a lap in 150 s. Combat AI drives at two thirds of the speed
    and hardly fires. Every second frame reads 0 ms, and the AI's one-frame steering then saturates.
  - **Conclusion:** if 1997 machines had that clock and ran above about 18 fps, the AI would have been visibly broken.
    Reviews do not describe that, so either the clock was finer or the machines ran slower. Either way, the 55 ms profiles
    are not a target.
- **R-1997c** (10 ms tick at 30 fps) is close to stock20, apart from its 30 decisions a second.
- **Decision.** **"Stock" for parity work = stock20.** The AI clock emulation (`I76_AI_STOCK_CLOCK`) now emulates the
  15.625 ms tick at 20 fps (`I76_AI_STOCK_CLOCK_FPS=20`). With it, the T04 racers lap within 0.7 s of stock20; the 24 fps
  version of this morning was 1.3-1.9 s slower.
- **The AI combat parity set** (owner test 40, `TEST-combat-parity.bat` in the lab copy) brings the AI's per-second
  decision rates back to stock20's: hazard checks, handbrake turns (whose handbrake now reaches the car), throttle ease and
  route search.
