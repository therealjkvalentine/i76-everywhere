# Everything this repo adds to Interstate '76

One catalogue of every enhancement in this repository, written 2026-10-03. It is not only frame rate and graphics:
controls, the AutoHotkey layers, force feedback and head tracking are as much of the project as the 120 fps work.

**How to read the tables.** Each row is one enhancement: what the player gets, how to turn it on, how far it has
been proven, and where the detail lives. The **evidence status** column is copied from the linked document (or from
the session record [STATUS-2026-10-02.md](records/STATUS-2026-10-02.md), which runs to 2026-10-03); it is not a new
judgement. Where no document records a status the cell says *status not recorded*.

Words used in the status column, as the project's own documents use them:

| word | meaning |
|---|---|
| console-verified / played / field-confirmed | a person played it and reported the result |
| measured | a number was taken, with the run count where the source gives one |
| sandbox | on the test copy of the game, not the install the owner plays on |
| built, untested / not measured | the code exists and applies; nobody has confirmed the effect |
| design / research | a document only |
| retired / parked | tried, then withdrawn; kept so nobody repeats it |

**You need your own copy of the game** (the GOG release is the tested one). See
[What this repo does not ship](#what-this-repo-does-not-ship).

**Multiplayer is untested** with anything in this catalogue that changes timing (every preset other than `stock`).
Two copies can run on one PC with `I76_MULTI_INSTANCE=1` (section 8), but no session between them was achieved.

Contents: [Controls](#1-controls) · [Force feedback and haptics](#2-force-feedback-and-haptics) ·
[Head tracking and camera](#3-head-tracking-and-camera) · [Frame rate and simulation fixes](#4-frame-rate-and-simulation-fixes) ·
[Graphics](#5-graphics) · [Audio](#6-audio) · [Bug fixes](#7-bug-fixes) ·
[Trainer, save editor, modding and RE tools](#8-trainer-save-editor-modding-and-re-tools) ·
[Platforms and packaging](#9-platforms-and-packaging) · [How the engine works](#how-the-engine-works-what-we-learned) ·
[What this repo does not ship](#what-this-repo-does-not-ship)

---

## 1. Controls

The one rule behind all of it: the engine reads `input.map` and nothing else, and the in-game Control Configuration
menu corrupts that file ([AGENTS.md](../AGENTS.md), [CONTROL-DOCTRINE.md](CONTROL-DOCTRINE.md)). The layouts are drawn
from the live configs in the [README](../README.md#the-gamepad-layout).

**To sit down and play, read [CONTROLS.md](CONTROLS.md)**: the four control setups (all keyboard, keyboard and mouse,
gamepad, wheel and stick), the keys they share, and the common faults, on one page. On paper:
[Interstate76-Controls-Quick-Reference.pdf](Interstate76-Controls-Quick-Reference.pdf). Since 2026-10-03 the Windows installer writes this project's own WASD-style map
([`controls/input.map`](../controls/input.map)), not the 1997 layout; `-Controls stock` keeps the original keys.

| enhancement | what the player gets | how to turn it on | evidence status | doc |
|---|---|---|---|---|
| Native gamepad (baseline tier) | Any Xbox pad drives the game through the engine's own joystick bindings: analog steer and throttle, fire, cycle weapon, handbrake, a special, camera glance. No Steam Input, no emulation | Windows: `setup-windows.ps1 -Controls stock` (the default map, `-Controls i76e`, binds only the two analog axes natively and leaves every button to the AutoHotkey layer). Mac: [`setup-mouse-and-pad.sh`](../setup-mouse-and-pad.sh). Connect the pad before launching | Field-tested 2026-07-14: `joystick1` token confirmed, button A=1 confirmed. X=3 is **unconfirmed**: its confirmation was retracted 2026-07-18 (made on the dead bare `Joystick` token); "still to confirm: buttons B=2 / Y=4 and 5-10" | [GAMEPAD-PC-MAC.md](GAMEPAD-PC-MAC.md), [CONTROL-DOCTRINE.md](CONTROL-DOCTRINE.md) |
| AutoHotkey controller layer | On top of the baseline: an LB shift layer, look-back fire, independent triggers and a rumble mixer; mouse button 4 becomes special 1 (the nitrous slot) and button 5 hardpoint 3 | [`i76-remap.ahk`](../i76-remap.ahk). Mac / Deck: [`setup-input-remapper.sh`](../setup-input-remapper.sh) installs AutoHotkey inside the prefix. Windows: [`PLAY-i76.ps1`](../PLAY-i76.ps1) starts it, or [`i76-with-remap.bat`](../i76-with-remap.bat) | "deployed, verified on Mac/Windows" (RELEASE-PLAN section 1). Mouse button 5 fires nitrous: confirmed in-game 2026-07-14 | [INPUT-REMAPPER.md](INPUT-REMAPPER.md), [README layout](../README.md#the-gamepad-layout) |
| Printable quick reference | Four Letter pages (keyboard and mouse, gamepad, wheel and stick, 1997 keys vs ours), generated from the shipped map and the layer scripts; the build fails when they disagree | [`tools/controls-sheet/build.ps1`](../tools/controls-sheet/README.md); output [Interstate76-Controls-Quick-Reference.pdf](Interstate76-Controls-Quick-Reference.pdf) | Generated and checked offline 2026-10-03 (`tests/test_controls.py`); four pad controls send keys the map does not bind, listed on the sheet | [CONTROLS.md](CONTROLS.md) |
| Layout diagrams from the live config | The two controller pictures in the README, and an interactive page with the mouse and keyboard tables, regenerated from the real bindings (a Mac game folder's map; for Windows use the quick reference above) | [`tools/pad-diagram.py`](../tools/pad-diagram.py), [`open-pad-diagram.command`](../open-pad-diagram.command) | status not recorded | [README layout](../README.md#the-gamepad-layout) |
| CH Fighterstick layer | A flight stick on a driving game: the grip follows F-16 HOTAS convention (trigger, hats for hardpoints, targeting, displays), and stick deflection is the gearbox and handbrake | [`i76-ch-fighterstick.ahk`](../i76-ch-fighterstick.ahk); `PLAY-i76.ps1` starts it unless `-NoStick`. `-whatif` names each action without sending keys, `-map` prints the card | "Confirmed in the game, 2026-08-08, control by control" (trigger, three hats, special, glance, stick axes, horn); buttons 17-19 and the mode-switch renumbering do not exist | [FIGHTERSTICK.md](FIGHTERSTICK.md) |
| Thrustmaster T300RS wheel | Analog steering, analog accelerator and brake, all 13 buttons with a shift layer (about 27 actions) | Install the Thrustmaster driver, set pedals to COMBINED, keep the `steer` / `throttle` blocks in `input.map`; buttons come from `i76-remap.ahk` | "STATUS 2026-08-01: WORKING AND PLAYED", confirmed in-sim | [WHEEL-T300.md](WHEEL-T300.md) |
| Mouse wheel as keys | Wheel up cycles the weapon, wheel down fires the dropper (the engine has no wheel input at all) | [`tools/i76wheel.c`](../tools/i76wheel.c) (`i76wheel.exe`); `PLAY-i76.ps1` starts it, `-WheelUp` / `-WheelDown` choose the keys | status not recorded for the helper itself (the launcher that starts it is listed "deployed, verified" in RELEASE-PLAN section 1) | [RELEASE-PLAN.md](RELEASE-PLAN.md) |
| Mouse-button weapons | Windows (the shipped map): left = fire the selected weapon, right = hardpoint 2, middle = look left. Mouse **steering** is not offered (owner decision 2026-10-03). The Mac script still writes its own set (mouse steering; left = fire, right = all guns, middle = dropper): see "Mac: converge later" in CONTROLS.md | `setup-windows.ps1` ([`controls/input.map`](../controls/input.map)); Mac: [`setup-mouse-and-pad.sh`](../setup-mouse-and-pad.sh) | Windows: the owner's daily-driver map. Mac: mouse steering "SOLVED 2026-07-13"; right-click broadside "confirmed in-game 2026-07-14" | [CONTROLS.md](CONTROLS.md), [VERIFIED-FIXES.md](VERIFIED-FIXES.md) |
| `input.map` lint | Catches the silent killers before a launch is wasted: tokens the engine does not know, accidental chords, two analog sources in one block, a file rewritten by the in-game menu | `python3 tools/lint-input-map.py <game dir>` ([source](../tools/lint-input-map.py)) | status not recorded | [AGENTS.md](../AGENTS.md) |
| Menu and save-screen pointer mapping (`u32x`) | Clicks land where the pointer is in the menus, garage and save screen when the picture is scaled | [`u32x/deploy-u32x.ps1`](../u32x/deploy-u32x.ps1); `setup-windows.ps1` and the portable zip deploy it | Sandbox, 2026-10-02: bookmark route 2/2, save screen after 10 s idle (row click, SAVE twice, overwrite prompt). "Not yet done for this build: a run on the daily driver, and a fresh-install run". The 2026-10-03 daily driver runs the full build (md5 `054fb411`, gated: leg-b 3/3, trip route 120 fps, save screen, Esc-menu Exit, melee); since 2026-10-03 its source and binary are here (`u32x/u32x_full.c`, `u32x/u32x_full.dll`; a rebuild matches apart from 4 link-time bytes) and `setup-windows.ps1` installs it by default. The portable zip and `Make-Daily-Driver.ps1` still default to the minimal build | [u32x/README.md](../u32x/README.md), [SAVE-FREEZE-ROOT-CAUSE.md](SAVE-FREEZE-ROOT-CAUSE.md) |
| Cursor overlay | A pointer the game cannot hide (the OS pointer is invisible over the game window, so a waiting prompt looks like a freeze) | [`i76-cursor-overlay.ahk`](../i76-cursor-overlay.ahk); started by `PLAY-i76.ps1` unless `-NoCursorOverlay`; Ctrl+Alt+C toggles | "mitigated (overlay), cause open" | [MENU-USABILITY-PLAN.md](records/MENU-USABILITY-PLAN.md) |
| Cursor mode switch | Choose whether dgVoodoo or `u32x` maps the pointer, so the two do not both do it | [`tools/cursor-mode.ps1`](../tools/cursor-mode.ps1); also in `LAUNCHER.ps1` | status not recorded | [u32x/README.md](../u32x/README.md) |
| Steam Deck controller layout | A full Steam Input layout: sticks, triggers, back grips and a trackpad radial menu for the rarely used keys, with labels | [`deck/controller_neptune_i76.vdf`](../deck/controller_neptune_i76.vdf), applied from Controller Settings > Templates; the Deck installer pre-applies it | "INSTALLED on this user's Deck (2026-07-11) ... all verified"; left for the user: launch once and apply the controller config | [DECK-CONTROLS.md](DECK-CONTROLS.md), [STEAMDECK-INPUT-MODES.md](STEAMDECK-INPUT-MODES.md), [DECK-INPUT-SCIENCE.md](records/DECK-INPUT-SCIENCE.md) |
| Steam Deck baseline tier | The same AutoHotkey pad layer (shift layer, rumble) inside the Proton prefix, for parity with Mac and Windows | [`deck/setup-deck-baseline.sh`](../deck/setup-deck-baseline.sh), [`deck/i76-deck-launch.sh`](../deck/i76-deck-launch.sh) | "STATUS 2026-08-01: DEPLOYABLE, NOT YET RUN ON DECK HARDWARE"; rumble on this path is "unverified" | [DECK-BASELINE.md](records/DECK-BASELINE.md) |
| Mac arrow keys | Arrow keys steer instead of glancing the camera | [`fix-arrows-for-mac.sh`](../fix-arrows-for-mac.sh) | Listed in VERIFIED-FIXES ("hit, diagnosed, and fixed on this port"); no date given | [VERIFIED-FIXES.md](VERIFIED-FIXES.md) |

## 2. Force feedback and haptics

Two stacks exist: a Windows wheel and bass-shaker rig that runs outside the game, and a Mac shim inside it. They
"have never been run together" ([FFB-STACKS.md](FFB-STACKS.md): read it before running force feedback anywhere).

| enhancement | what the player gets | how to turn it on | evidence status | doc |
|---|---|---|---|---|
| The game's own force feedback on a modern wheel | The 1997 authored effects (weapon kick, impacts) on a current wheel | Nothing to switch on: force-feedback start-up is unconditional on the Gold exe (WHEEL-T300, from disassembly). [`enable-force-feedback.bat`](../enable-force-feedback.bat) is not needed per that disassembly and is harmless; nobody has re-tested a wheel on a PC where it was never run. Close the wheel's control panel before launching; remove extra or virtual joysticks | "verified in-sim" on a T300RS ("WORKING AND PLAYED" 2026-08-01). 2026-10-03 daily driver: "Not verified: force feedback (module loads; no wheel was attached during the gate)" | [WHEEL-T300.md](WHEEL-T300.md), [FFB-LAPTOP-RECON.md](records/FFB-LAPTOP-RECON.md) |
| Custom wheel force feedback | Forces the engine never had: self-aligning weight, cornering load, the wheel going light on understeer, oversteer catch, braking, road texture, impacts. Eight channels, live panel, solo and mute | `PLAY-i76.ps1 -Ffb` (opt-in), or `tools\ffb\ffb-interposer.ps1`; run `tools\ffb\ffb-calibrate.ps1` first (`FFB-PANEL.bat`, `FFB-CALIBRATE.bat`) | Output, telemetry, force model ("28 assertions passing"), interposer and calibration: "working". "Feel tuning: not started - needs a drive; nothing here has been judged by hand yet" | [tools/ffb/README.md](../tools/ffb/README.md), [FFB-DESIGN-LIBRARY.md](FFB-DESIGN-LIBRARY.md) |
| Bass shaker channel | Engine, road and impact content rendered as low-frequency audio for a tactile transducer | `tools\ffb\ffb-lfe.ps1` (and the `ffb-lfe-*.ps1` scripts beside it) | "built ... feel tuning not started" (RELEASE-PLAN section 1); wheel, shakers and pad "have never run together" | [tools/ffb/README.md](../tools/ffb/README.md), [FFB-STACKS.md](FFB-STACKS.md) |
| Motion rig and SimHub feed | LFS OutSim / OutGauge UDP that SimTools, SimHub and similar receivers already listen for | `tools\ffb\ffb-telemetry-udp.ps1 -Targets simhub` | Layout: "21 layout assertions". Rig: "nothing here is hardware-verified yet" (2026-07-19) | [MOTION-SIM.md](records/MOTION-SIM.md), [tools/ffb/README.md](../tools/ffb/README.md) |
| Pad rumble from the game's force stream (shim) | Gamepad rumble led by real wheel slip, surface, impacts and weapons, with no DirectInput device; this is what makes force feedback work on a Mac | [`ffb-shim/build.sh`](../ffb-shim/build.sh), [`ffb-shim/install.sh`](../ffb-shim/install.sh) (the DLL is built locally, not committed) | "field-run and tuned on the Mac over 2026-07-19/20"; "it has only ever run on the Mac" | [ffb-shim/README.md](../ffb-shim/README.md), [FFB-DEEP-DIVE.md](records/FFB-DEEP-DIVE.md), [FFB-MORNING-TEST.md](records/FFB-MORNING-TEST.md) |
| Pad rumble mixer in the AutoHotkey layer | Two-motor rumble (heavy / buzz) from the controller layer | [`i76-remap.ahk`](../i76-remap.ahk) | "field-confirmed 2026-07-18" on Mac (note in `enable-force-feedback.bat`); controller layer "deployed, verified on Mac/Windows" | [SIM-RUMBLE-RESEARCH.md](records/SIM-RUMBLE-RESEARCH.md), [INPUT-REMAPPER.md](INPUT-REMAPPER.md) |
| Rumble from the sounds the game plays | A backup path: rumble follows the actual audio, including sounds the physics stream does not model | [`sound-rumble/build.sh`](../sound-rumble/build.sh), [`sound-rumble/install.sh`](../sound-rumble/install.sh); not installed by default | "EXPERIMENTAL, not verified in-game" | [sound-rumble/README.md](../sound-rumble/README.md) |
| Telemetry feed | The player's state once per frame plus shot, impact and explosion events, over UDP and shared memory, so force feedback, motion and logging tools do not have to scan memory | `I76_TELEMETRY=1` (preset `lab-all`); watch with `python tools\telemetry\i76tel.py` | "Verified live 2026-10-01 (sandbox, i76.exe, t01): 1,067 of 1,067 frames decoded" | [tools/telemetry/README.md](../tools/telemetry/README.md), [FFB-DATA-AUDIT.md](records/FFB-DATA-AUDIT.md) |

## 3. Head tracking and camera

| enhancement | what the player gets | how to turn it on | evidence status | doc |
|---|---|---|---|---|
| Head tracking, digital mode | Turn your head, the view turns: head angle past a threshold holds the glance key. Works in every view | opentrack with output "freetrack 2.0 Enhanced", then [`i76-opentrack-headlook.ahk`](../i76-opentrack-headlook.ahk); `PLAY-i76.ps1 -OpenTrack <path>` starts both | "Working and field-confirmed" on the GOG Gold build. Carried into the 2026-10-03 daily driver; untested at 120 fps | [HEAD-TRACKING.md](HEAD-TRACKING.md) |
| Head tracking, analog mode | Proportional yaw in the cockpit view; live sensitivity keys | Ctrl+Alt+H toggles digital / analog; Ctrl+Alt+[ ] and - = adjust | Yaw range "field-confirmed". "Pitch injection does not work on this build"; pitch uses the glance key. Untested at 120 fps | [HEAD-TRACKING.md](HEAD-TRACKING.md) |
| opentrack auto-start | Tracking starts with the game, without touching the mouse | [`i76-opentrack-autostart.ahk`](../i76-opentrack-autostart.ahk), run by `PLAY-i76.ps1` | Listed with head tracking as "verified" in RELEASE-PLAN section 1; no separate record | [HEAD-TRACKING.md](HEAD-TRACKING.md) |
| Head-look test harness | Checks the tracking script without the game | [`i76-opentrack-headlook-test.ahk`](../i76-opentrack-headlook-test.ahk) | status not recorded | [HEAD-TRACKING.md](HEAD-TRACKING.md) |
| Camera address sweeper | A diagnostic that finds which memory address really drives the view (it settled the analog target) | [`i76-camsweep.ahk`](../i76-camsweep.ahk), Ctrl+Alt+1..6 in a mission | status not recorded | [HEAD-TRACKING.md](HEAD-TRACKING.md) |

## 4. Frame rate and simulation fixes

The game ships at 20 fps. The music-fix proxy (`music-fix/Strlkup.dll`) carries opt-in `I76_*` switches that let it
run at 60 or 120 with the physics, AI and effects behaving as they do at 20. Each switch is off unless set, and
every patched site's bytes are checked first. Two things must be true for any of them to act: the game folder's
`Strlkup.dll` is the current build, and GOG's `I76PATCH.DLL` (the 20 fps cap) is renamed out of the way.

| enhancement | what the player gets | how to turn it on | evidence status | doc |
|---|---|---|---|---|
| Presets | A named switch set handed to the game process only | `PLAY-i76.ps1 -Preset <name>` (`-Preset ?` lists, `-DryRun` shows); files in [`presets/`](../presets/); `LAUNCHER.ps1` has the same drop-down | Per preset, in each `.psd1` header | [README](../README.md#playing-at-60--120-fps), [music-fix/README.md](../music-fix/README.md) |
| Smooth 60 fps | 60 fps with stock-feeling physics | Preset `smooth-60` | "[measured, sandbox] capture 014; [console-verified 2026-10-02, sandbox] n = 1" | [music-fix/README.md](../music-fix/README.md), [PLAYTEST-2026-10-02.md](records/PLAYTEST-2026-10-02.md) |
| 120 fps | 120 fps; physics, AI and input run exactly as at 60, four frames in five are interpolated | `I76_GLIDE_REFRESH=120`: preset [`best-120`](../presets/best-120.psd1) or `smooth-120`. Needs a display above 60 Hz and a dgVoodoo conf that dgVoodoo accepts | Measured 120.1 fps (frame time 8.34 ms, sd 0.06) and played by the owner. 120 is the ceiling: no renderer tested exceeds it | [FPS-120.md](records/FPS-120.md), [RENDERER-ALTERNATIVES.md](records/RENDERER-ALTERNATIVES.md) |
| Fixed physics step | Jumps, body roll and suspension as tuned at 20 fps, at any frame rate (the Mission 5 canyon jump clears) | `I76_FIXED_STEP=24` (in every smooth preset) | Owner playtest 2026-10-02, sandbox, n = 1: Mission 5 jump with no nitrous, out-of-gas jumps, body roll all "good" | [PLAYTEST-2026-10-02.md](records/PLAYTEST-2026-10-02.md) |
| Exact frame clock | Removes the 15.6 ms timer jitter from the simulation clock | `I76_HIRES_CLOCK=1` | "dt exact (50.00 ms at 20 fps, 16/17 ms at 60 fps)" | [music-fix/README.md](../music-fix/README.md) |
| Render interpolation | Removes the judder the fixed step leaves: cars and camera are drawn between physics poses | `I76_RENDER_INTERP=1` | "31-33% of frames without motion -> 0%, roughness 1.00 -> 0.04-0.06 (n = 2 missions)" | [music-fix/README.md](../music-fix/README.md) |
| Engine model step | Engine RPM and torque smoothing counted per substep as at 20 fps | `I76_ENGINE_DT_FIX=1` | "static; consistent with the fixed step" | [music-fix/README.md](../music-fix/README.md) |
| Per-frame effects held to the 20 Hz grid | Sky drift, free-look and zoom keys, keyboard throttle ramp, lock tones, radar ping, vehicle sounds, AI throttle / steering / fire decisions, flamers, smoke, missile trails behave as at 20 fps | `I76_FRAMERATE_FIXES=1` | Clouds "0.0300 /s at 60 fps = 20 fps (stock 0.0899)"; sky and free-look "confirmed in play"; flamer and AI behaviour "good" in the 2026-10-02 playtest (n = 1); HUD ammo-digit roll "not measured" | [music-fix/README.md](../music-fix/README.md), [FRAMERATE-COVERAGE-2026-10-02.md](records/FRAMERATE-COVERAGE-2026-10-02.md) |
| Oil slick and fire patch at high fps | Hazards hurt and sound as at 20 fps instead of once per rendered frame | Part of `I76_FRAMERATE_FIXES=1` | Measured: 20 contacts per second at 20, 60 and 120 fps (9 of 10 runs; one staging miss) | [PER-FRAME-AUDIT-2026-10-03.md](records/PER-FRAME-AUDIT-2026-10-03.md), [STATUS-2026-10-02.md](records/STATUS-2026-10-02.md) |
| Dead-weapon click | The click of a destroyed weapon with fire held plays at the 20 fps cadence | Part of `I76_FRAMERATE_FIXES=1` | Measured: 20 per second at 20, 60 and 120 fps (2 runs each) | [PER-FRAME-AUDIT-2026-10-03.md](records/PER-FRAME-AUDIT-2026-10-03.md) |
| Radar missile turn rate | Radar-guided missiles turn at the 20 fps rate | Part of `I76_FRAMERATE_FIXES=1` | Not measured | [PER-FRAME-AUDIT-2026-10-03.md](records/PER-FRAME-AUDIT-2026-10-03.md) |
| Collision repeat dedupe | One impact is applied once, not once per rendered frame under the fixed step | `I76_COLL_DEDUPE` (with `I76_FIXED_STEP`) | No data: the acceptance test ran on 2026-10-03 but "the ram test could not stage rams". `best-120` sets it to `0`: count only, behaviour as played on 2026-10-02 | [PER-FRAME-AUDIT-2026-10-03.md](records/PER-FRAME-AUDIT-2026-10-03.md), [best-120.psd1](../presets/best-120.psd1) |
| AI skid and horn roll hold | AI skid-turn and horn decisions rolled at the 20 fps rate | `I76_AI_ROLL_HOLD` | No data: the acceptance test ran on 2026-10-03 but no AI car entered the behaviour. `best-120` sets it to `0`: count only | [PER-FRAME-AUDIT-2026-10-03.md](records/PER-FRAME-AUDIT-2026-10-03.md), [best-120.psd1](../presets/best-120.psd1) |
| AI dodge rate | AI checks for incoming projectiles as often as at 20 fps, not three to six times as often | `I76_AI_FIXES=1` | "[measured, sandbox]": 2.87 checks/s at 20 fps, 8.90 at 60 unheld, 3.17 at 60 with the switch, 17.19 at 120 unheld (n = 2). The avoidance-prediction part has no recorded measurement | [FRAMERATE-COVERAGE-2026-10-02.md](records/FRAMERATE-COVERAGE-2026-10-02.md) |
| Rear mirror cadence | The mirror redraws 10 times a second as stock, instead of a full extra scene every frame | `I76_MIRROR_RATE=1` | "[measured, sandbox]": 10 redraws/s with the switch; sky drift unchanged (coarse) | [FRAMERATE-COVERAGE-2026-10-02.md](records/FRAMERATE-COVERAGE-2026-10-02.md) |
| Collision sweep window | The collision sweep covers the whole physics step at 60 and 120 fps | `I76_COLL_WINDOW=1` | "[built, untested]" | [FRAMERATE-COVERAGE-2026-10-02.md](records/FRAMERATE-COVERAGE-2026-10-02.md) |
| Far-vehicle engine step | Distant AI cars accelerate as at 20 fps | `I76_FAR_ENGINE_DT=1` | "[built, untested]" | [FRAMERATE-COVERAGE-2026-10-02.md](records/FRAMERATE-COVERAGE-2026-10-02.md) |
| Precise frame cap | An exact cap from the proxy (the source's "dgVoodoo's `FPSLimit` did not cap this build" is void: it was measured while dgVoodoo was rejecting the sandbox conf; not re-measured) | `I76_FPS_CAP=<n>` | "held 20.0 fps exactly". A cap above about 64 fps delivered about 62 until the proxy requested 1 ms timer resolution; no measurement recorded after that change | [music-fix/README.md](../music-fix/README.md), [RENDERER-ALTERNATIVES.md](records/RENDERER-ALTERNATIVES.md) |
| Stock 20 fps pacing | The original physics rate for stock play (Mac: DxWnd limiter; Windows: GOG's `I76PATCH.DLL`) | Mac: the DxWnd profile [`interstate-76.dxw`](../interstate-76.dxw). Windows: preset `stock` | Mac: "all verified in play". GOG's limiter "measured ~20.66 FPS in-sim" | [VERIFIED-FIXES.md](VERIFIED-FIXES.md), [MAC-BUILD.md](MAC-BUILD.md) |

## 5. Graphics

| enhancement | what the player gets | how to turn it on | evidence status | doc |
|---|---|---|---|---|
| Glide through dgVoodoo (Windows) | The hardware renderer at high resolution with 3dfx gamma, antialiasing and 32-bit colour, in place of GOG's bundled wrapper | `setup-windows.ps1` with a dgVoodoo folder you downloaded; conf [`dgVoodoo.windows.conf`](../dgVoodoo.windows.conf) | "verified (dgVoodoo recipe ...)" in the 2026-07-09 findings | [WINDOWS-PLAYBOOK.md](WINDOWS-PLAYBOOK.md), [FINDINGS-2026-07-WINDOWS-AND-TEXTURES.md](records/FINDINGS-2026-07-WINDOWS-AND-TEXTURES.md) |
| 2x supersampling + 4x MSAA at 120 fps | Smooth edges and more texture and distance detail, with the frame rate held | [`dgVoodoo.daily-driver-2026-10-03.conf`](../dgVoodoo.daily-driver-2026-10-03.conf) as the game folder's `dgVoodoo.conf` | Measured 2026-10-03, n = 1 each: 2x internal + 4x MSAA 120.1 fps at 28-37 % of a GTX 1080 Ti; 2x + 8x MSAA and 3x + 4x MSAA drop to about 90. The conf itself: "twin-verified: 16:10 picture, 120.2 fps" (commit `013a8fd`). "Not yet judged by eye in motion" | [GRAPHICS-ENHANCEMENT.md](records/GRAPHICS-ENHANCEMENT.md) |
| Draw distance | Landscape drawn to 1800 m instead of 600 m | `I76_FAR_CLIP=1800` (presets `best-120`, `lab-all`); the proxy refuses values above 2500 | Owner 2026-10-02: hood view and binoculars at 1800 m "good". Soak: trip missions t01-t17 clean (t14 inconclusive); melee / arena missions untested at 1800 m | [DRAW-DISTANCE.md](DRAW-DISTANCE.md), [FARCLIP-CAMERA-CRASH.md](records/FARCLIP-CAMERA-CRASH.md) |
| Frame generation | Interpolated display frames from Lossless Scaling (a commercial app you own); physics unchanged | [`Setup-FrameGen.ps1`](../Setup-FrameGen.ps1) writes the profile; `PLAY-i76.ps1 -LosslessScaling <path>` starts and stops it | "verified 2026-08-01 (no Steam dependency)"; 20 to 40 fps verified in the 2026-07 findings. Carried into the 2026-10-03 daily driver; untested at 120 fps | [WINDOWS-PLAYBOOK.md](WINDOWS-PLAYBOOK.md), [RENDERER-ALTERNATIVES.md](records/RENDERER-ALTERNATIVES.md) |
| Other renderers, measured | An answer to "would another wrapper be better": none passes 120 fps | Nothing to turn on; dgVoodoo stays the renderer | Measured 2026-10-03, n = 1 each: nGlide Direct3D 9 62.6 / 124.9 fps, nGlide Vulkan and DXVK did not open a window, ReShade (CAS + SMAA) and DDrawCompat 120.1; ReShade's effect "not judged by eye yet" | [RENDERER-ALTERNATIVES.md](records/RENDERER-ALTERNATIVES.md) |
| Menu HD art pipeline | Offline 2x / 3x versions of the menu backgrounds, sprites and fonts from your own `DATABASE.MW2`, and a cleaned 8-bit repack | `python tools\menu-hd\build_hd.py check` / `build` ([source](../tools/menu-hd/build_hd.py)); output stays local | "[measured]" offline, one run each; "Not installed anywhere and untested in play" | [MENU-HD-ART.md](records/MENU-HD-ART.md) |
| Menu rebuild and one-pointer mode | One visible pointer that lands where it points in every menu; later, HD menu art drawn in place | Not shipped. One-pointer mode (`I76_U32X_VPTR`) exists only in the lab build | Design study ("[proposed]"); one-pointer mode experimental | [MENU-REBUILD-DESIGN.md](records/MENU-REBUILD-DESIGN.md), [MENU-USABILITY-PLAN.md](records/MENU-USABILITY-PLAN.md) |
| Enhanced texture pipeline | Tools that decode, edit and re-encode the game's textures (the `.M16` hardware format round-trips) | [`texture-lab/`](../texture-lab/README.md), [`tools/i76img.py`](../tools/i76img.py) | "RETIRED (2026-07-27)": marginal in-game gain, palette tiles broke on night missions; the format work is kept | [HD-TEXTURES-RESEARCH.md](HD-TEXTURES-RESEARCH.md) |
| OpenGLide-HD patch series | Hash-based texture dump and replace at any resolution, as patches to an open-source Glide wrapper | [`tools/openglide-hd/`](../tools/openglide-hd/README.md) | "Status 2026-07-10: builds, boots, stays alive; dump/replace loop not verified in game" | [FINDINGS-2026-07-WINDOWS-AND-TEXTURES.md](records/FINDINGS-2026-07-WINDOWS-AND-TEXTURES.md) |

## 6. Audio

| enhancement | what the player gets | how to turn it on | evidence status | doc |
|---|---|---|---|---|
| In-mission soundtrack restored | The CD soundtrack plays in missions from GOG's own MP3 files, sequenced by the engine as from the disc; tracks follow on instead of one song looping | `music-fix/Strlkup.dll`, deployed by `setup-windows.ps1` (always on once deployed) | "Confirmed in a mission 2026-08-08". Track run: "verified in the sandbox 2026-10-01"; owner 2026-10-02: "music adjustment is huge" | [MUSIC.md](MUSIC.md), [music-fix/README.md](../music-fix/README.md), [MUSIC-TRACK-MAP.md](MUSIC-TRACK-MAP.md) |
| In-game music slider works | The Options music level controls the soundtrack volume, and holds across tracks | Same proxy | Sandbox 2026-10-01: slider level 3 gives volume 300/1000; owner 2026-10-02: "slider works" | [music-fix/README.md](../music-fix/README.md) |
| Cutscene music fix | The mission track no longer plays over a movie's own score (a GOG bug) | [`smack-music-fix/`](../smack-music-fix/README.md); Mac: [`setup-cutscene-music-fix.sh`](../setup-cutscene-music-fix.sh); Windows / Deck: rename and copy by hand (README) | "Mac: verified by ear 2026-07-14. Windows: built; not on the daily driver" | [VERIFIED-FIXES.md](VERIFIED-FIXES.md) |
| Mission music on the Mac | Mission music through DxWnd's virtual CD | [`setup-music.sh`](../setup-music.sh) | "Confirmed in-mission" | [VERIFIED-FIXES.md](VERIFIED-FIXES.md) |
| External soundtrack player (stopgap) | Plays the MP3s beside the game when the proxy is not deployed | [`tools/i76-music.ps1`](../tools/i76-music.ps1); `PLAY-i76.ps1 -MusicVolume`, `-NoMusic` | status not recorded (the release plan marks it for retirement) | [RELEASE-PLAN.md](RELEASE-PLAN.md) |
| winmm CD-audio proxy (superseded) | An earlier attempt at the soundtrack fix; its emulation detail fed the working proxy | Not deployable; its build outputs are not committed | "works standalone (15 self-test assertions) ... BLOCKED for the game"; "Do not deploy it" | [MUSIC.md](MUSIC.md) |

## 7. Bug fixes

Fixes to faults in the game itself or in how it meets a modern machine. The Mac port's own crash, window and launch
fixes are a table of their own: [VERIFIED-FIXES.md](VERIFIED-FIXES.md).

| enhancement | what the player gets | how to turn it on | evidence status | doc |
|---|---|---|---|---|
| Target health bar | The enemy health bar shrinks and changes colour in step with damage (stock reads a scratched car as nearly dead) | `I76_FIX_HEALTH_PCT=1` (presets `smooth-60-bugfixes`, `best-120`) | "verified live 2026-10-02": stock 0.99 / old fix 99.0 / new fix 49.6 on a 30 % armour car with a 99 % engine | [HEALTH-BAR-COLOUR.md](records/HEALTH-BAR-COLOUR.md) |
| Object label table | Very large custom missions no longer corrupt the label table when it grows | `I76_FIX_LABEL_TABLE=1` | "T01 with capacity 16: grew to 272, all 88 labels kept, game ran" | [music-fix/README.md](../music-fix/README.md) |
| Far-clip crash ceiling | Long draw distances without the hood-view / binoculars crash: the cause is found and the switch refuses unsafe values | `I76_FAR_CLIP` at or below 2500 | Sandbox 2026-10-02: crash between 2500 and 2750 m reproduced and explained; 1800 m soaked (see Graphics) | [FARCLIP-CAMERA-CRASH.md](records/FARCLIP-CAMERA-CRASH.md) |
| Save Bookmark screen: freeze and dead mouse | Saving no longer freezes, and the mouse works on the save screen after it sits idle | `u32x.dll` ([`u32x/deploy-u32x.ps1`](../u32x/deploy-u32x.ps1)) | Keyboard save with no freeze "confirmed by the owner in play 2026-10-02". Mouse: sandbox 2026-10-02 (10 s idle, row click, SAVE twice, overwrite prompt). 2026-10-03 gate on the lab twin: NO writes nothing, YES writes only the picked bookmark | [SAVE-FREEZE-ROOT-CAUSE.md](SAVE-FREEZE-ROOT-CAUSE.md), [u32x/README.md](../u32x/README.md) |
| Save-name typing | Typing a bookmark name works (a widely circulated patched shell DLL broke it) | [`tools/fix-shell-textentry.ps1`](../tools/fix-shell-textentry.ps1) | "deployed and verified in play" (docs/README.md) | [SHELL-MENU-AND-SAVE-FREEZE.md](records/SHELL-MENU-AND-SAVE-FREEZE.md) |
| Fullscreen Esc-menu Exit | The mouse can reach Exit in the in-mission menu | A newer `u32x` build than the one committed here; the committed `u32x/u32x.dll` does not include it ("use the keyboard there") | Withdrawn 2026-10-02 22:30, restored 23:30 with a rebuilt DLL gated on the sandbox; passed the 2026-10-03 daily-driver gate on the lab twin | [STATUS-2026-10-02.md](records/STATUS-2026-10-02.md), [PLAYTEST-2026-10-02.md](records/PLAYTEST-2026-10-02.md) |
| Working-directory fix | The game finds its data however it is started (a bare double-click or a launcher that sets no working directory) | Always on in the proxy; `I76_CWD_FIX=0` disables | Sandbox 2026-10-02: launched from `C:\Windows`, "with the cwd fix the data resolves" | [STATUS-2026-10-02.md](records/STATUS-2026-10-02.md), [music-fix/README.md](../music-fix/README.md) |
| "Insert CD 2" prompt | The prompt on unpatched executables is explained and can be answered by the proxy | `I76_CD_FAKE=1` (opt-in) | "[measured, sandbox]"; "opt-in for now; candidate for default-on" | [STATUS-2026-10-02.md](records/STATUS-2026-10-02.md) |
| Save index handling | Launchers, installers and the editor read `savegame.dir` as the game writes it (earlier tools misread every scene by one record) | Built into `PLAY-i76.ps1`, the installers and the save editor | "sandbox-verified 2026-10-01" | [VERIFIED-FIXES.md](VERIFIED-FIXES.md), [SAVES-STATE-AND-TEST-PLAN.md](records/SAVES-STATE-AND-TEST-PLAN.md) |
| No crash on the first shot with custom force feedback | Firing while the custom wheel layer holds the device no longer faults the game | Applied by `tools\ffb` when it takes the wheel | "Fixed" (one 4-byte write, no code patched) per the tools/ffb README; no date or run count given | [tools/ffb/README.md](../tools/ffb/README.md) |

## 8. Trainer, save editor, modding and RE tools

| enhancement | what the player gets | how to turn it on | evidence status | doc |
|---|---|---|---|---|
| Trainer window | God mode, unlimited ammo, no flats, repair, teleport, stop, forced Play Options, held on the game's own thread | [`tools/trainer/TRAINER.bat`](../tools/trainer/TRAINER.bat) (Python 3, nothing to install); refuses anything but the test copy unless told otherwise | "[measured, sandbox]": `trainer_live_test.py` 13/13 on 2026-10-02 (a 40 m drop costs 156 hp without god mode, 0 with) | [tools/trainer/README-GUI.md](../tools/trainer/README-GUI.md) |
| Trainer command line | Status, flags, repair, ammo, teleport from a terminal; every write read back | `python tools\trainer\i76trainer.py` | "sandbox; addresses from i76-map cheats.md" | [RELEASE-PLAN.md](RELEASE-PLAN.md), [MODDING-GUIDE.md](MODDING-GUIDE.md) |
| Live tuner | Change physics, weapon, AI, camera and sound constants in a running game from a catalogue | `python tools\trainer\i76tune.py list` | status not recorded | [tools/trainer/TUNING.md](../tools/trainer/TUNING.md) |
| Save editor | Edit equipped parts, armour, part state and condition, scene, slots; in a browser with nothing installed, as a terminal tool, or on a Mac with write-back and backups | [`i76-save-editor.html`](../i76-save-editor.html) ([hosted](https://therealjkvalentine.github.io/i76-everywhere/i76-save-editor.html)), [`i76-save-editor.py`](../i76-save-editor.py), [`i76-save-editor.command`](../i76-save-editor.command) | Byte-exact round trips on 46 saves, HTML == Python (`python -m pytest tests/` on 2026-10-03: 156 passed with the lab saves folder present, 133 on the repo samples alone; the 172 and 132 written on 2026-10-02 were the same suite over different save sets). Seven in-game probes answered in the sandbox 2026-10-02. Not tested: Radar Jammer effect, state-1 LOAD of a next-scene label | [SAVE-EDITOR-STATUS-2026-10-02.md](records/SAVE-EDITOR-STATUS-2026-10-02.md), [SAVE-FORMAT-GAPS.md](SAVE-FORMAT-GAPS.md) |
| Save probes (the game as oracle) | Generated saves that ask the game one question each, so the editor's model is checked against the garage screen | [`i76-calibration-saves.py`](../i76-calibration-saves.py) into a staging folder | Probes 1-7 answered in the sandbox 2026-10-02 | [EDITOR-FIELD-TESTS.md](EDITOR-FIELD-TESTS.md) |
| Two copies on one PC | A second copy of the game starts instead of exiting at once (for local multiplayer tests) | `I76_MULTI_INSTANCE=1` in each copy's environment; each copy in its own folder | 2026-10-03: two lab copies ran side by side, both responding. A multiplayer session between them was **not** achieved: both copies need UDP port 21157, and the internet transport wants a game server | [music-fix/README.md](../music-fix/README.md) |
| Terrain detail distance (experiment) | The ground refines farther from the camera, so its reshaping happens farther away | `I76_TERRAIN_LOD=<1..16>` | 2026-10-03, sandbox: runs at 120 fps at x2 / x4 / x8 on t01; visual gain not judged, not soaked with the far clip; in no preset | [music-fix/README.md](../music-fix/README.md) |
| Mount rules | Why an edited weapon stays mounted or silently vanishes (name matching, the 11-record garage list, the turret rule) | Reading only | "static, consistent with the probe result" | [MOUNT-VALIDATION.md](records/MOUNT-VALIDATION.md) |
| Bookmark saves | Start from a given scene on a fresh install | [`saves/`](../saves/README.md), `saves/Install-Saves.ps1` | status not recorded | [saves/README.md](../saves/README.md) |
| Memory tools (AutoHotkey, 2026-07) | Debug menu with live edit and freeze, repair + rearm, all-vehicle list, overlay scanner | `tools/i76-debugmenu.ahk`, `i76-rearm.ahk`, `i76-worldscan.ahk`, `i76-trainer.ahk` (launch: `tools/debugmenu.sh`) | Repair + rearm and vehicle enumeration "field-tested"; debug menu: field-test sheet, run 2 on 2026-07-19 | [docs/README.md](README.md), [DEBUG-MENU-FIELD-TEST.md](records/DEBUG-MENU-FIELD-TEST.md), [MEMORY-MAP-INDEX.md](MEMORY-MAP-INDEX.md) |
| Format tools | Extract the game archive, decode and re-encode its images, list every object in a level | [`tools/zfs_extract.py`](../tools/zfs_extract.py), [`tools/i76img.py`](../tools/i76img.py), [`tools/level-objects.py`](../tools/level-objects.py) | Formats "verified against game data" (tool docstrings); level format "decoded live" from a community map | [HD-TEXTURES-RESEARCH.md](HD-TEXTURES-RESEARCH.md), [LEVEL-FORMAT.md](LEVEL-FORMAT.md) |
| Disassembly helpers and address map | Scripts that disassemble and cross-reference your own executable; a machine-readable address list | [`tools/exe-disasm.py`](../tools/exe-disasm.py), [`tools/exe-xref.py`](../tools/exe-xref.py), [`tools/i76-addresses.json`](../tools/i76-addresses.json) | status not recorded | [RE-METHODOLOGY.md](RE-METHODOLOGY.md) |
| Modding guide | Which lever changes what (data files, proxy switches, trainer, code patches) and the traps | Reading only; the data-file mod tool it names lives in a sibling repository, not here | Written 2026-09-27 from the specs; that mod tool: "built; in-game effect pending" | [MODDING-GUIDE.md](MODDING-GUIDE.md) |
| Weapon table | Rate of fire, range, speed, weight, ammo and damage for every weapon, mirrored locally | Reading only | Ammo figures "matched the values read out of the live game eight for eight" (AGENTS.md) | [WEAPON-STATS.md](WEAPON-STATS.md), [COMMUNITY-RESOURCES.md](COMMUNITY-RESOURCES.md) |

## 9. Platforms and packaging

| enhancement | what the player gets | how to turn it on | evidence status | doc |
|---|---|---|---|---|
| Windows install from your GOG backup | One double-click from the GOG offline installer to a configured game | [`INSTALL.bat`](../INSTALL.bat) -> [`Setup-From-GOG.ps1`](../Setup-From-GOG.ps1) | "verified on this machine (INSTALL.md)" | [INSTALL.md](../INSTALL.md) |
| Windows launcher and settings panel | Starts the game with the control layers, overlay, head tracking and frame generation, and stops them after; a panel for the common settings and health checks | [`PLAY-i76.ps1`](../PLAY-i76.ps1), [`LAUNCHER.ps1`](../LAUNCHER.ps1) | Launcher "deployed, verified"; panel "deployed" | [RELEASE-PLAN.md](RELEASE-PLAN.md) |
| Boot straight into a mission | Skip the title, menus and mission select | `PLAY-i76.ps1 -Mission t01.msn` (`I76_MISSION`) | "Working 2026-08-08"; "in the mission 10 seconds after launch" | [MISSION-LAUNCH.md](MISSION-LAUNCH.md) |
| Portable zip | Carry your configured install to another of your own PCs; unzip and play | [`MAKE-PORTABLE.bat`](../MAKE-PORTABLE.bat) -> [`Make-Portable-Zip.ps1`](../Make-Portable-Zip.ps1). It contains your game files: not for sharing | "verified (the daily driver is one)" | [INSTALL.md](../INSTALL.md), [THIRD-PARTY.md](../THIRD-PARTY.md) |
| Daily-driver builder | Assembles a new self-contained game folder from an existing one plus the current proxy, pointer DLL, conf, launcher and presets, with a manifest of hashes and an untouched golden copy | [`tools/Make-Daily-Driver.ps1`](../tools/Make-Daily-Driver.ps1) (`-Plan` writes nothing) | 2026-10-03: a driver built with it was gated on a lab twin (bookmark route 3/3, trip route at 120 fps 2/2, save screen, Esc-menu Exit, melee, lint, saves byte-identical). "Not verified: force feedback ..., the real folder itself has not been launched, multiplayer". The built folders: `C:\Users\james\Games\Interstate76-2026-10-03` and the golden copy `...\Interstate76-golden-2026-10-03` | [NEW-DAILY-DRIVER-RECIPE.md](records/NEW-DAILY-DRIVER-RECIPE.md), [STATUS-2026-10-02.md](records/STATUS-2026-10-02.md) |
| Apple Silicon Mac build | The game in a self-contained Wine wrapper: instant start, big 4:3 window, in-mission music, clean quit, 20 fps | [`build-launchers.sh`](../build-launchers.sh), `setup-*.sh`; [`mac-install.command`](../mac-install.command) runs them in one step | "Playable on the free stack ... all verified in play". `mac-install.command`: "BETA / not yet tested on a clean machine". The 60 / 120 switches are "untested under Wine" | [MAC-BUILD.md](MAC-BUILD.md), [VERIFIED-FIXES.md](VERIFIED-FIXES.md) |
| Glide on the Mac | The hardware renderer through Metal | Not shipped | "PARKED" (the graphics layer cannot keep compiled shaders between launches) | [VOODOO-PARKED.md](VOODOO-PARKED.md) |
| Steam Deck | Guided install from your GOG installer; the Glide path through dgVoodoo and Vulkan, library artwork, controller layout | [`deck/Install-I76.desktop`](../deck/Install-I76.desktop) or [`deck/deck-install.sh`](../deck/deck-install.sh) (marked BETA) | "INSTALLED on this user's Deck (2026-07-11)"; "verified installed 2026-07-11 (Glide path + FFB)"; the proxy switches are "untested under Proton" | [STEAMDECK.md](STEAMDECK.md) |
| Nitro Pack | The same Windows recipe applied to the Nitro Pack executable | `install.ps1` detects it (`setup-windows.ps1 -Exe nitro.exe`) | status not recorded | [CHANGELOG.md](../CHANGELOG.md) |
| Phones | A route for Android (the Deck recipe again) and iPhone (streaming or a VM) | Reading only | "Research/untested" | [PHONE-PORTS.md](records/PHONE-PORTS.md) |

---

## How the engine works (what we learned)

The enhancements above rest on reverse-engineering notes kept in this folder. Start with
[docs/README.md](README.md), which says which documents are current and which are parked dead ends.

**Memory and structure**
- [MEMORY-MAP-INDEX.md](MEMORY-MAP-INDEX.md): the current pointer chains (player, inventory, every vehicle), with a dead-ends list.
- [GHIDRA-MEMORY-MAP.md](records/GHIDRA-MEMORY-MAP.md) and [STATIC-RE-FABLE.md](records/STATIC-RE-FABLE.md): raw session logs behind the index; they contain claims later corrected.
- [MW2-I76-STRUCTS.md](records/MW2-I76-STRUCTS.md): struct and encoding shapes from the file formats.
- [FRESH-START-2026-09-04.md](records/FRESH-START-2026-09-04.md) and [FRESH-START-METHOD.md](records/FRESH-START-METHOD.md): the restart of the executable survey and its method.

**Simulation, timing and handling**
- [HANDLING-MODEL.md](HANDLING-MODEL.md): how the car actually drives, measured from the live process.
- [FRAMERATE-UNCAP-RESEARCH.md](records/FRAMERATE-UNCAP-RESEARCH.md), [FPS-120.md](records/FPS-120.md), [FRAMERATE-COVERAGE-2026-10-02.md](records/FRAMERATE-COVERAGE-2026-10-02.md), [PER-FRAME-AUDIT-2026-10-03.md](records/PER-FRAME-AUDIT-2026-10-03.md): what in the engine depends on frame count, and what was done about each item.
- [HEALTH-BAR-COLOUR.md](records/HEALTH-BAR-COLOUR.md): how vehicle health is computed and drawn.
- [I76-GAMEPLAY-REFERENCE.md](I76-GAMEPLAY-REFERENCE.md) and [WEAPON-STATS.md](WEAPON-STATS.md): controls, hardpoints, specials, weapon numbers.

**Rendering**
- [DRAW-DISTANCE.md](DRAW-DISTANCE.md) and [FARCLIP-CAMERA-CRASH.md](records/FARCLIP-CAMERA-CRASH.md): the far clip chain and its three ceilings.
- [HD-TEXTURES-RESEARCH.md](HD-TEXTURES-RESEARCH.md): the archive and texture formats (ZFS, VQM, M16).
- [GRAPHICS-ENHANCEMENT.md](records/GRAPHICS-ENHANCEMENT.md), [RENDERER-ALTERNATIVES.md](records/RENDERER-ALTERNATIVES.md), [DXGI-DGVOODOO-RESEARCH.md](DXGI-DGVOODOO-RESEARCH.md), [DXWND-TUNING.md](DXWND-TUNING.md): how the Glide and software paths reach a modern display.

**Menus, saves and file formats**
- [SHELL-MENU-AND-SAVE-FREEZE.md](records/SHELL-MENU-AND-SAVE-FREEZE.md), [SAVE-FREEZE-ROOT-CAUSE.md](SAVE-FREEZE-ROOT-CAUSE.md), [MENU-USABILITY-PLAN.md](records/MENU-USABILITY-PLAN.md), [MENU-REBUILD-DESIGN.md](records/MENU-REBUILD-DESIGN.md): the menu shell, its pointer handling and the save freeze.
- [SAVE-FORMAT-GAPS.md](SAVE-FORMAT-GAPS.md), [SAVES-STATE-AND-TEST-PLAN.md](records/SAVES-STATE-AND-TEST-PLAN.md), [MOUNT-VALIDATION.md](records/MOUNT-VALIDATION.md): the save format and what the game does with it on load.
- [LEVEL-FORMAT.md](LEVEL-FORMAT.md) and [ASSET-BIBLE.md](ASSET-BIBLE.md): level chunks and the object class list.
- [MISSION-LAUNCH.md](MISSION-LAUNCH.md): how the game reaches a mission, and the direct-boot patch.

**Sound, music and force feedback**
- [MUSIC.md](MUSIC.md) and [MUSIC-TRACK-MAP.md](MUSIC-TRACK-MAP.md): why there was no music, and which track each mission asks for.
- [SOUND-INTERPOSER-REVIEW.md](records/SOUND-INTERPOSER-REVIEW.md): the sound proxies checked against the sound spec.
- [FFB-DEEP-DIVE.md](records/FFB-DEEP-DIVE.md), [FFB-STACKS.md](FFB-STACKS.md), [FFB-DATA-AUDIT.md](records/FFB-DATA-AUDIT.md): the force-feedback plugin interface and the data it carries.
- [HEAD-TRACKING.md](HEAD-TRACKING.md) ("What the camera actually is"): the camera inputs and outputs.

**Method**
- [RE-METHODOLOGY.md](RE-METHODOLOGY.md), [RE-FIELD-GUIDE.md](RE-FIELD-GUIDE.md), [FIND-WHAT-WRITES.md](FIND-WHAT-WRITES.md), [RE-RESOURCES.md](RE-RESOURCES.md): how values were found and the traps that gave wrong answers.
- [COMMUNITY-RESOURCES.md](COMMUNITY-RESOURCES.md) and [COMMUNITY-SITEMAP.md](COMMUNITY-SITEMAP.md): the published community work, indexed by the problem it solves.
- [MODDING-GUIDE.md](MODDING-GUIDE.md): the levers for changing the game.

## What this repo does not ship

This section reports what [THIRD-PARTY.md](../THIRD-PARTY.md) and [LICENSE](../LICENSE) say. It is a description
of the repository, not legal advice.

- **The game.** THIRD-PARTY.md: the repository "ships no copyrighted game files"; the executables, archives,
  textures, audio, movies and missions are Activision's (rights now with Microsoft), and "you must own a legitimate
  copy". The GOG release is the tested source. Game material you download stays in a local, gitignored `game-data/`
  folder.
- **Game art and audio, original or upscaled.** The texture and menu-art tools work on your own install and write
  their output to folders that are not committed ([MENU-HD-ART.md](records/MENU-HD-ART.md) section 9: "Upscaled derivatives
  of the game's art are game data"; [texture-lab/README.md](../texture-lab/README.md) states the same rule).
- **Bulk decompiled listings.** THIRD-PARTY.md: decompiler output "is Activision's code in another form and is
  never committed here". The documents in this folder describe addresses, structures and behaviour.
- **Third-party binaries.** THIRD-PARTY.md: "no third-party binaries". dgVoodoo, DxWnd, AutoHotkey, opentrack,
  Lossless Scaling, DXVK, Proton and the rest are fetched from their own sources at install time or copied from
  your own installation; each keeps its own licence. Lossless Scaling is commercial and is never fetched or shipped.

What it does ship: scripts, source, configuration and documentation, plus three prebuilt binaries of this
project's own code, each beside its source (`music-fix/Strlkup.dll`, `u32x/u32x.dll`, `tools/i76wheel.exe`), and a
set of bookmark saves ([saves/](../saves/README.md)). Per LICENSE, the MIT licence covers the original work here and
does not cover the game or the third-party tools.

The tools work on **your own install**. The portable zip and the daily-driver builder copy your game files for your
own machines; THIRD-PARTY.md says the zip "is not a distribution format and must not be shared".
