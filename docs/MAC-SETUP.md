# Interstate '76 on macOS — handoff package & context brief
*(Prepared 2026-07-04 on the Windows box. This doc is self-contained context for a fresh
Claude session on the Mac — read top to bottom before doing anything.)*

## What's in this package
- `i76-stable-gog.zip` — pristine GOG install of I76 Gold (i76.exe 2019-09-01, MD5
  60abf7bc699da72476128ddce991a3d1, renders via bundled OpenGLide). Portable folder;
  config is file-based (no registry needed in practice).
- `I76_CD1.ISO` — original CD image (373MB). REQUIRED for the 86Box path (the GOG
  installer won't run inside Win95). Owner: James Valentine (owns GOG copy + original CD).
- `KEYBOARD.MAP.mw5` — proposed MW5-style laptop bindings (drop-in replacement for the
  game's KEYBOARD.MAP; back up the original first). NOT yet play-tested.
- `MODERN-SETUP.md`, `WHAT-THIS-IS-dgvoodoo.txt` — the Windows-side docs (reference).
- `i76-research-full.txt` — full multi-agent research report w/ sources (Windows+Mac+
  emulation+frame-gen; adversarially verified July 2026).

## THE ONE RULE (why any of this is complicated)
I76 ties physics/AI/scripted events to the RENDER framerate (per-frame numerical bugs;
no clean dt — confirmed by the reverse-engineering community; no 60fps patch exists).
**Above ~30fps: cars flip, Mission 5's jump is impossible, flamethrower/mortar break,
AI caps at 35mph.** Community consensus cap = **20 FPS** (24–25 ok, 30 = loose ceiling).
On Windows we fixed this with dgVoodoo2 `FPSLimit = 20` — VERIFIED WORKING (melee +
campaign mission 1 tested extensively, zero crashes across ~40min and 9 mission restarts).
On macOS there is NO verified equivalent limiter — that's the entire challenge.

## Path A — CrossOver (try first; ~1 evening)
1. Install CrossOver 26+ (14-day trial exists). i76.exe is 32-bit → runs via wine32on64.
   (CrossOver 27 drops Intel Macs; Whisky is dead since Apr 2025 — don't bother.)
2. New bottle: **Windows XP 32-bit**, then in winecfg set version to **Windows 98**
   (CodeWeavers' own tip page recipe + WineHQ AppDB both say Win98).
3. Unzip `i76-stable-gog.zip` into the bottle's `drive_c/GOG Games/Interstate 76/`.
   (Alternative: download the GOG offline installer on the Mac and install into the
   bottle — James owns the game on GOG.)
4. Run `i76.exe -glide` (the bundled OpenGLide translates Glide→OpenGL under Wine).
   Known cosmetic jank from AppDB: garbled menu on first launch, menu bar turning black
   after missions (navigate by keyboard: arrows+Enter; ESC skips cutscenes).
5. **THE CAP (unsolved on Mac — experiments in order of promise):**
   a. **AiO Unofficial Patch** (PCGW Community file #1349, "Interstate '76 + Nitro Pack
      AiO Patch" v1.0.5) — installs a built-in 20 FPS limiter + crash/audio fixes.
      Run its installer inside the bottle. Compat with this 2019 GOG exe is UNVERIFIED —
      keep the zip as backup, diff what it changes.
   b. **nGlide + DXVK experiment**: swap OpenGLide for nGlide (Glide→D3D9), enable DXVK
      in the bottle, then set env `DXVK_FRAME_RATE=20`. Chain is coherent but UNTESTED
      for I76 — would be a first if it works.
   c. If neither caps it: the game will RUN but physics will be wrong — do not campaign
      like that. Fall back to Path B.
6. Verify the cap before starting the campaign: game speed should feel normal (not
   Benny-Hill fast); AI cars should exceed 35mph; the world shouldn't strobe.

## Path B — 86Box (physics-correct BY CONSTRUCTION; ~1 weekend)
Era-accurate emulation: the whole machine is too slow to break physics. Save states =
campaign insurance. Works fully offline on Apple Silicon.
- 86Box config (VOGONS consensus): Socket 7, **Pentium 200 MMX**, 32MB RAM, S3 Trio64
  video + **Voodoo 1 (2MB framebuffer + 2MB texture)** — I76's Glide backend "is only
  really made for 2MB tmem'd voodoo cards". SB16 audio. Win95 OSR2 guest.
  Recompiler ON, 2 render threads.
- Install the game from `I76_CD1.ISO` (mount in 86Box), patch to v1.083 if the CD is
  older (patch is on archive.org / interstate76.com mirrors — see research file).
- Honest caveat: the one recent I76-in-86Box report (VOGONS 2025, UCyborg) used the
  SOFTWARE renderer and got 5–10 fps in-game. The Voodoo/Glide config should be much
  better but is untested — needs a strong single-core host (M2+ fine on paper).
- Host needs: 86Box.app (universal binary), a Win95 OSR2 ISO + license, patience.

## Path C — accepted-fallback: stream from the Windows box
Already fully working there (dgVoodoo build, 20fps, 1280x960+8xMSAA). Moonlight client
(free, Apple Silicon) + Sunshine host. 20fps game = stream latency irrelevant. Use
Ethernet (macOS AWDL wifi stalls). This is the zero-risk option when back in range.

## Controls (the MW5-style laptop scheme, agreed 2026-07-04)
See `KEYBOARD.MAP.mw5`. Summary: W/S=throttle(notched!) A/D=steer Space=fire
**Tab=weapon cycle** F=weapon link **X=reverse** **C=handbrake** **I=ignition**
Q=target-front T=nearest-enemy U=untarget R=radar-range H=lights B=binocs G=horn
V=view M=map N=notepad Arrows=glance(side windows! guns still fire forward) P=poetry.
Caveats: bare Shift can't be a primary key (parser treats it as modifier); glance
actions were on numpad ("Grey") keys by default. NOT yet play-tested — test in melee.

## Key facts a fresh session needs (learned the hard way)
- The game's menus hit-test the mouse in INTERNAL 640x480 coords offset from the window
  origin, unscaled — relevant if automating. Pause menu is keyboard-only under wrappers.
- Throttle is NOTCHED (set-and-hold like a mech) — tap W, don't hold.
- Boot takes 60-75s of "PLEASE STAND BY" + intro; ESC (sometimes twice) skips.
- Campaign mission 1 = "Follow Taurus to Seagraves" — tight follow leash (~40-60s
  separation = fail); road from the diner is one long gentle LEFT arc.
- i76fix (github immi101) DOES NOT fit this 2019 exe (targets 2017 MD5 9a232dcc,
  blind-patches offsets → corrupts). AiO patch compat also unverified — backup first.
- Known deep-campaign bugs (fixed by AiO): mission 12→13 transition crash; restart the
  game around missions 14-15 on long sessions.
- interstate76.com forums are DEAD (2026); source patches from PCGW Community #1349,
  VOGONS t=68384, or archive.org.

## Verify-the-cap checklist (any path)
1. Instant Melee (MELEE → AUTO MELEE → INSTANT MELEE → ENTER AREA), drive: no flips on
   bumps, car settles after banking.
2. Game speed sane (cutscenes not fast-forwarded).
3. Later: Mission 5's ramp jump is the canonical full test.
