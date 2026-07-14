# Interstate '76 (GOG Gold) - Apple Silicon

Status: **Playable on the free stack** (Sikarugir Wine 10, wow64) — fullscreen-4:3 window,
in-mission music, clean quit, built-in 20 FPS physics limiter, all verified in play. Not a Steam
title - GOG release, so no SteamCMD: you supply the game files yourself (see
[game-data/](game-data/)). **New here? Read [docs/README.md](docs/README.md)** (the doc map —
working vs. parked dead-ends) **and [docs/VERIFIED-FIXES.md](docs/VERIFIED-FIXES.md)** (every
symptom→cause→fix in one table).

## The launchers

Built/installed by [`build-launchers.sh`](build-launchers.sh) into `~/Applications/Sikarugir/`:

| App | What it is |
|---|---|
| **`Interstate 76 - Software (DxWnd).app`** | **The Mac build.** DxWnd wraps the software renderer into a big screen-filling 4:3 window (black bars, title bar, draggable). Double-click → straight into the game (`dxwnd.exe /R:1`, headless). Instant start, zero shader compile. Quitting (in-game EXIT, closing the window, *or* cmd-Q on the app) tears down *everything* — no leftover black window. |
| **`Interstate 76 - DxWnd Settings.app`** | The DxWnd GUI for tweaking the profile (select the "Interstate 76" row → Edit; settings map in [docs/DXWND-TUNING.md](docs/DXWND-TUNING.md)). Changes save to the live `dxwnd.ini`. |

> **The "Voodoo" Glide→Metal mode is parked.** It worked and looked great (bright 3dfx gamma, MSAA,
> higher res) but has one unfixable-from-here showstopper: MoltenVK can't persist compiled Metal
> pipelines, so every launch re-pays a shader compile. Full ledger + the exact announcement that
> un-parks it (one-line rebuild): **[docs/VOODOO-PARKED.md](docs/VOODOO-PARKED.md)**. The pretty
> Glide path lives happily on the **[Steam Deck](docs/STEAMDECK.md)** (native Vulkan, no MoltenVK).

One-time setup: [`setup-dxwnd.sh`](setup-dxwnd.sh) (installs DxWnd + our
[profile](interstate-76.dxw)), [`setup-music.sh`](setup-music.sh) (in-mission music, see below),
[`fix-arrows-for-mac.sh`](fix-arrows-for-mac.sh) (steering on Mac arrow keys).

First launch, macOS asks for **microphone** access — that's Wine's CoreAudio driver opening the
default *input* device during audio init. Harmless; **Deny is fine** (output is unaffected).

The launch stubs ([main](i76-launch-stub.swift) / [voodoo](i76-voodoo-stub.swift) /
[settings](i76-settings-stub.swift)) exist because the stock Sikarugir launcher injects a GL flag
and a wrong CWD that break the renderers, misses the GStreamer env (freezes + silent music — see
VERIFIED-FIXES), and LaunchServices won't run script bundle executables - so each is a small
Mach-O (original launcher kept as `Sikarugir.orig`). They also fix "quit doesn't really quit":
the stub waits for **`i76.exe`** to exit (the DxWnd host outlives the game), then reaps the whole
Wine session and sweeps survivors.

## In-mission music (fixed)

Mission music is CD redbook audio; GOG ships it as `music/N.mp3` + an empty `tracklen.nfo`, so
under Wine missions were silent (cutscene audio is separate and always worked).
[`setup-music.sh`](setup-music.sh) wires GOG's files into DxWnd's **virtual CD audio** emulation
(hard-links to its `TrackNN.mp3` naming, clears the broken `tracklen.nfo`; the profile's
VIRTUALCDAUDIO flag does the rest). MP3 decode needs the GStreamer env the stubs set.
**Confirmed playing in missions.** (No in-game radio/track controls exist — verified by dumping
the exe's action tokens: no radio/music/cd actions, only `track_*` camera-tracking ones. Music is
mission-scripted; the one knob is the music volume slider in Options.)

**Disk use (~1.4 GB after slimming; ~3.9 GB stock):** the **game itself is 477 MB**; the rest is
~850 MB of irreducible Windows/Wine runtime a self-contained no-dependencies `.app` must carry
(Wine engine 324 MB + `C:\windows` system DLLs 323 MB + GStreamer-for-music & libs ~200 MB). Stock,
the Steam-game-cloned wrapper also hauls ~2.5 GB I76 never touches: the whole **Steam client**
(~1.9 GB - I76 is GOG, launched directly), **wine-mono** (~230 MB .NET), **wine-gecko** (~207 MB
browser), and the **Voodoo GPU stack** (~140 MB renderer backends + MoltenVK - the software
renderer is CPU→DirectDraw→OpenGL, no Metal). [`slim-wrapper.sh`](slim-wrapper.sh) removes all of it
(quarantine → confirm → commit; boot+render verified), taking 3.9 GB → **1.4 GB**. 300 MB isn't
reachable without depending on a system-wide Wine.

Engine: 1997, 32-bit. Renderer tokens baked into the exe: `glide` (ZGLIDE -> bundled OpenGLide ->
OpenGL), `d3d`, `redline` (software), `powervr`, and an undocumented **`gdi`** (windowed software
blit - added/fixed by the AiO patch). No DirectX 11 anywhere - D3DMetal is irrelevant (set
`D3DMETAL=0`).

## DxWnd: the default (big fullscreen-4:3 window)

DxWnd wraps the game's DirectDraw output so the software render (set the in-game resolution to
its 1024x768 max — that IS the engine ceiling, see VERIFIED-FIXES) is scaled into a big window.
Setup once with [`setup-dxwnd.sh`](setup-dxwnd.sh) (downloads DxWnd, installs our profile). The
profile ([interstate-76.dxw](interstate-76.dxw)) is frozen at:

- **Main tab:** Run in Window, Early hook, `Terminate on window close` (closing the window = quit;
  the stub then reaps everything), **Position = Desktop** (`coord0=3`) + **Keep aspect ratio** →
  fills the screen as letterboxed 4:3. `Adaptive ratio` OFF (that one stretches).
- **Hook tab:** `Injection = Inject DLL` (the mouse is correct at this setting; the research's
  "SetWindowsHook causes mouse offset -> use Inject suspended" note does NOT apply here).
- **Video tab:** thick frame (gives the title bar + handles), Floating, SD 4:3, **Hide desktop**
  (black backdrop behind the letterbox).
- **DirectX tab:** `Renderer = primary surface` (avoids black menus/cutscenes). Caveat: DxWnd's
  author flags this renderer as leaking GDI handles over long sessions - watch for gradual
  slowdown on marathon runs; restart the game if it creeps.

**Headless launch:** `dxwnd.exe /R:1` (1-based index; the parser does `iProgIndex-1` so `/R:1`
= ini target 0 - this is why an earlier `/r:0` only opened the GUI; and do NOT add `/q`, it
*suppresses* the launch). To change settings, use `Interstate 76 - DxWnd Settings.app`
(select the "Interstate 76" row -> Edit; double-clicking the row *runs* the game).

*Note on quitting: if quitting a mission ever kills the whole game instead of returning to the
menu, that's `Terminate on window close` reacting to the game recreating its window — uncheck it
in Settings and quit via the in-game EXIT instead (the stub reaps either way).*

**Emergency fallback** (if DxWnd ever breaks): the exe's own windowed software renderer,
`i76.exe -gdi` - a normal but fixed 640x480 window, immune to every launcher quirk (reads no INI).

**Colors:** the software renderer lacks the 3dfx gamma lift, so it runs darker than the
Glide/Windows look - the game's own brightness setting (Options -> Graphic Detail) compensates.

## The Voodoo (Glide→Metal) mode — parked

The dgVoodoo path (`i76.exe -glide` → dgVoodoo 2.78.2 → DXVK → MoltenVK → Metal) got fully working
and looked great — bright 3dfx gamma, 4× MSAA, 32-bit, higher internal res — but every launch
re-pays a MoltenVK shader compile that **cannot be persisted** across runs, so it's parked in favor
of the instant-start software renderer. The complete ledger (how far we got, the exact blocker, the
one MoltenVK announcement that un-parks it, and the un-park playbook) is in
**[docs/VOODOO-PARKED.md](docs/VOODOO-PARKED.md)**. The battle log / root causes (the
three-condition dgVoodoo-under-Wine recipe, the Sikarugir launcher's Glide-fatal
`CX_FWD_COMPAT_GL_CTX=1`, the visual wins) live in
[docs/DXGI-DGVOODOO-RESEARCH.md](docs/DXGI-DGVOODOO-RESEARCH.md) +
[docs/VISUAL-QUALITY-MAC.md](docs/VISUAL-QUALITY-MAC.md). The pretty Glide path runs great on the
**[Steam Deck](docs/STEAMDECK.md)** (native Vulkan, no MoltenVK tax).

Sources: [Wine fullscreen focus-loss behavior](https://forum.winehq.org/viewtopic.php?t=20646),
[SDL issue on the broken restore](https://github.com/libsdl-org/SDL/issues/5320),
[winemac virtual-desktop limitation](https://forum.winehq.org/viewtopic.php?t=40541).

## Discovery: the GOG 2019 build IS the AiO patch (limiter included)

The GOG Gold `i76.exe` (2019-09-01, MD5 `60abf7bc...`) is **byte-identical** to UCyborg's
AiO Unofficial Patch final build (09/01/2019), and the install ships `I76PATCH.DLL` - the AiO's
**built-in frame limiter, hardcoded to 20 FPS** (QueryPerformanceCounter + Sleep, no config file).
So the physics-correct cap is already inside this exe on every platform. The Windows-side notes
("no cap configured") predate this discovery; the dgVoodoo `FPSLimit = 20` there was belt+braces.
(The exe contains a `toggle_framerate` KEYBOARD.MAP action string, but binding it - tried with
`Zero` - produced no visible effect, and if it does anything it more likely toggles the *limiter*
than a counter. Don't bind it. For an FPS readout in `-glide` mode use the DXVK HUD instead:
`dxvk.conf` next to the exe with `dxvk.hud = fps,compiler` - `compiler` also visualizes the
per-launch async-shader warmup, see quirks.)

## The working recipe (what got it this far)

1. Clone any Sikarugir Wine-10 wrapper (APFS `cp -c`), gut the old game from the prefix.
2. Unzip the GOG install to `drive_c/GOG Games/Interstate 76/` (the zip's backslash paths
   convert cleanly; `unzip` exits 1 with a warning - harmless).
3. `Info.plist`: `Program Name and Path` = `C:\GOG Games\Interstate 76\i76.exe`,
   `Program Flags` = `-gdi` (NOT `-glide` - see the saga above), `D3DMETAL` = `0`.
   *(Historical: the launch stubs now bypass the stock launcher entirely, so `Info.plist`
   program/flags are inert - launch args live in the stub sources.)*
4. Registry (per-app): `HKCU\Software\Wine\AppDefaults\i76.exe` -> `Version` = `win98`.
5. **Registry: a Wine virtual desktop is REQUIRED** - without it the game page-faults at
   `01B82C26` (it calls `NtUserChangeDisplaySettings`, macOS refuses exclusive 640x480, the game
   dereferences null): `HKCU\Software\Wine\AppDefaults\i76.exe\Explorer` -> `Desktop` = `i76`
   and `HKCU\Software\Wine\Explorer\Desktops` -> `i76` = `1280x960`.
6. **Registry: `HKCU\Software\Wine\Mac Driver` -> `WindowsFloatWhenInactive` = `all`.** Without
   it, the moment another app takes focus (especially a fullscreen app on its own Space), winemac
   treats the desktop window - which exactly equals Wine's virtual screen - as a fullscreen window
   and MINIMIZES it (parks it at -16000,-16000). Symptom: the game window appears, draws once,
   and vanishes within a few hundred ms. This key makes it float like a normal window.
7. Launch via the wrapper (`open .../Interstate 76 - Software (DxWnd).app`).

Do NOT force `renderer=gdi` for ddraw - the shell creates a Direct3D device and crashes at the
same address if refused. The default wined3d GL path works (one harmless
`GL_INVALID_FRAMEBUFFER_OPERATION` at startup).

Quirks seen on Mac so far:

- The **sim pauses when the app loses focus**; menus, cinematics, and the pause menu keep
  rendering and keep accepting input (even input posted directly to the process). Fine for
  play; matters for automation.
- Mouse hit-testing is offset in the scaled virtual desktop (the known 640x480 internal-coords
  quirk) - navigate menus by keyboard: arrows + Enter, numbers pick menu items.
- Do not maximize/zoom the virtual-desktop window; dragging it is fine. (The
  flash-and-vanish-on-refocus bug is fixed by `WindowsFloatWhenInactive` - step 6.)
- **CLI launches must set `WINEMSYNC=1` alongside `WINEESYNC=1`** (the wrapper's launcher sets
  both; msync wins). esync-only sends every Wine process (explorer, 2x winedevice, the game) into
  a 100%-CPU busy-spin on macOS. With msync, all of them idle at ~0-4%.
- Never kill the prefix's `explorer.exe` while playing - it's the Wine session shell/clipboard
  manager; the game exits shortly after it dies.
- `wow64_NtSetLdtEntries` stub warning at startup is harmless (unlike MW4, nothing depends on it).
- Wine-level FPS measurement: relaunch from CLI with `WINEDEBUG=-plugplay,+fps,+timestamp` and
  watch `wglSwapBuffers` lines. The 2D shell/menus tick at ~14-15 fps by design (the AiO limiter
  also throttles menus/cutscenes to save CPU).
- **`-glide` warmup: the first ~2 minutes of each session run at a slideshow pace** while
  DXVK-async + MoltenVK compile the sim's shaders (this MoltenVK has no persistent shader cache,
  so the Metal-side compile repeats per launch; the `i76.dxvk-cache` next to the exe shortens it
  as it grows). Brief hitches on first-seen effects (first explosion, first smoke) are the same
  thing and stop recurring within the session. Let it warm up in the menu/first mission start.

## THE ONE RULE: cap the game at ~20 FPS or the physics break

I76 ties physics/AI/scripted events to the render framerate (fixed-timestep assumption from 1997;
confirmed by the reverse-engineering community - no 60fps patch exists). Above ~30 FPS: cars flip,
Mission 5's ramp jump becomes impossible, the flamethrower/mortar break, AI caps at 35 mph.
Community consensus cap = **20 FPS** (24-25 ok, 30 = loose ceiling).

- On Windows this was fixed with dgVoodoo2 `FPSLimit = 20` - verified across ~40 min of melee +
  campaign play, zero crashes. Config in [docs/WHAT-THIS-IS-dgvoodoo.txt](docs/WHAT-THIS-IS-dgvoodoo.txt).
- On macOS **no external limiter is needed**: the GOG exe's own `I76PATCH.DLL` cap holds under
  Wine. **Confirmed in-sim (2026-07-04): ~20.66 FPS measured from the session log, physics limiter
  working** - this is what closed out "the challenge of the port." The cap is inside the exe on
  every platform (see the discovery section above), and `-gdi` inherits it for free.

Still: don't campaign uncapped if you swap renderers. The cap is verified for the shipping `-gdi`
mode; re-check it (checklist below) if you switch to a Glide path or a different build.

## The paths (from the handoff research)

- **Path A - Wine wrapper** (this repo's stack; trying first). 32-bit exe under Wine 10,
  `i76.exe -glide` through the bundled OpenGLide (Glide -> OpenGL). Cap candidates, in order:
  the **AiO Unofficial Patch** (PCGW Community file #1349 - built-in 20 FPS limiter + crash/audio
  fixes; compat with the 2019 GOG exe unverified - back up first), or **nGlide + DXVK** with
  `DXVK_FRAME_RATE=20` (coherent but untested chain).
- **Path B - 86Box** (physics-correct by construction): Pentium 200 MMX + Voodoo 1 (2MB+2MB) +
  Win95 OSR2, install from the CD ISO. Era-accurate speed can't break the physics; save states.
  Needs a Win95 license; the one recent report used software rendering at 5-10 fps - the
  Voodoo/Glide config should be much better but is untested.
- **Path C - stream from the Windows box** (zero-risk fallback, already fully working there):
  Sunshine host + Moonlight client, Ethernet. A 20fps game makes stream latency irrelevant.

Full handoff brief: [docs/MAC-SETUP.md](docs/MAC-SETUP.md). Deep research with sources:
[docs/i76-research-full.txt](docs/i76-research-full.txt). Windows-side notes:
[docs/MODERN-SETUP.md](docs/MODERN-SETUP.md).

## Controls: mouse driving + Xbox controller (native!)

The engine natively supports **mouse driving** (analog `mouse Left/Right` steer, `Down/Up`
throttle, three buttons) and **winmm joysticks** — no mapper software needed.
[`setup-mouse-and-pad.sh`](setup-mouse-and-pad.sh) patches the active `input.map`: mouse
steer/throttle + MB1/MB2/MB3 → weapons 1/2/3 (only three mouse-button tokens exist in the
engine; weapon 4 stays on the `4` key), and fixes GOG's phantom `joystick5` bindings to
`joystick1` with left-stick driving, A-button fire, hat glances. Keyboard bindings all stay —
everything works at once. **Connect the controller before launching** (1997 games enumerate
joysticks only at startup); verify Wine sees it with `wine control joy.cpl`. Never rebind via
the in-game Control Configuration menu — it's community-confirmed buggy (appends chords,
wrong stick numbers, crashes); edit `input.map` instead. Facts + citations in
[docs/VERIFIED-FIXES.md](docs/VERIFIED-FIXES.md).

## The Windows box

Setting the game up on real Windows (max graphics via dgVoodoo, force feedback, frame
interpolation, ALIVE multiplayer community)? The cited to-do list is
[docs/WINDOWS-PLAYBOOK.md](docs/WINDOWS-PLAYBOOK.md), automated by
[setup-windows.ps1](setup-windows.ps1). The full July 2026 findings report — verified
dgVoodoo recipe, the first documented I76+LSFG frame-generation result, the **cracked
.M16 hardware-texture format**, and the first working vehicle-texture replacement
pipeline — is **[docs/FINDINGS-2026-07-WINDOWS-AND-TEXTURES.md](docs/FINDINGS-2026-07-WINDOWS-AND-TEXTURES.md)**.

## Controls: Mac arrow keys (required fix)

winemac delivers Mac arrow keys as the game's `Grey*` (numpad-cluster) codes; the stock
`KEYBOARD.MAP` binds those to glance/track camera and puts **driving** on the plain arrow names
Mac arrows never produce - so arrows look around instead of steering. Run
[`fix-arrows-for-mac.sh`](fix-arrows-for-mac.sh) on the `KEYBOARD.MAP` in your game folder
(it swaps the four arrow tokens; backup written beside it; restart the game). Glance/track land
on the numpad - still reachable on a full-size external keyboard.

## Controls: the MW5-style laptop layout

[`KEYBOARD.MAP.mw5`](KEYBOARD.MAP.mw5) - drop-in replacement for the game's `KEYBOARD.MAP`
(back up the original first). W/S notched throttle, A/D steer, Space fire, Tab weapon cycle,
X reverse, C handbrake, I ignition, arrows glance. Not yet play-tested - verify in Instant Melee.
Quirk: bare Shift can't be a primary key (the parser treats it as a modifier).

## Force feedback (wheel/joystick)

Real, and in this GOG build (Nitro Pack) - but dormant by default, and **there is no macOS path**
(Wine's only FFB backend is Linux evdev). On a **Windows box**: run
[`enable-force-feedback.bat`](enable-force-feedback.bat) as Administrator and your FFB wheel
works like the Sidewinder did. Full analysis:
[docs/FORCE-FEEDBACK-AND-VISUALS.md](docs/FORCE-FEEDBACK-AND-VISUALS.md). (FFB **does** work on the
Steam Deck with a docked wheel — Linux has the evdev backend.)

## Steam Deck / Linux

The Deck may be the **best** way to play this: native Vulkan means the dgVoodoo→DXVK chain runs
without MoltenVK, so the shader-warmup stutter largely disappears — and force feedback works. Our
[`dgVoodoo.conf`](dgVoodoo.conf) and input bindings transfer directly. Full recipe (Heroic + Proton
+ dgVoodoo, controls, 20 FPS cap, FFB, open items): [docs/STEAMDECK.md](docs/STEAMDECK.md) +
[`setup-steamdeck.sh`](setup-steamdeck.sh).

## Verify-the-cap checklist (any path)

1. Instant Melee (MELEE -> AUTO MELEE -> INSTANT MELEE -> ENTER AREA): no flips on bumps, car
   settles after banking, AI cars can exceed 35 mph.
2. Game speed sane (cutscenes not fast-forwarded, no Benny-Hill effect).
3. The canonical full test: Mission 5's ramp jump.

## Hard-won facts (from the Windows sessions)

- **i76fix (github immi101) does NOT fit this 2019 GOG exe** - it blind-patches offsets for the
  2017 build (MD5 `9a232dcc...`) and would corrupt this one (`60abf7bc...`).
- Boot takes 60-75s of "PLEASE STAND BY" + intro; ESC (sometimes twice) skips.
- Throttle is NOTCHED (set-and-hold, like a mech) - tap W, don't hold.
- Menus hit-test the mouse in internal 640x480 coords offset from the window origin, unscaled;
  the in-sim pause menu is keyboard-only under wrappers (arrows + Enter).
- Known cosmetic jank under Wine (AppDB): garbled menu on first launch, menu bar turning black
  after missions - navigate by keyboard.
- Deep-campaign bugs (fixed by the AiO patch): mission 12->13 transition crash; restart the game
  around missions 14-15 on long sessions.
- Campaign mission 1 = "Follow Taurus to Seagraves": tight follow leash (~40-60s separation =
  fail); the road from the diner is one long gentle LEFT arc.
- interstate76.com forums are dead (2026) - source patches from PCGW Community #1349, VOGONS
  t=68384, or archive.org.

## Get the game

Buy [Interstate '76 on GOG](https://www.gog.com/game/interstate_76) (I76 Gold includes the Nitro
Pack). Then see [game-data/README.md](game-data/README.md) for what to place where - the repo
contains no game files.
