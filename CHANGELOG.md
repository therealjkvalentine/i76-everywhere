# Changelog

All notable milestones for **i76-everywhere**. Dates are ISO. This project follows
["bring your own game"](THIRD-PARTY.md) — it ships no copyrighted content.

## Unreleased

### 2026-10-03

- **New daily driver** built by `tools/Make-Daily-Driver.ps1` at `C:\Users\james\Games\Interstate76-2026-10-03`
  with a golden copy beside it; preset `best-120`, the repo's `Strlkup.dll`, u32x lab build `054fb411`,
  `dgVoodoo.daily-driver-2026-10-03.conf`. Gated on a lab twin
  ([docs/records/STATUS-2026-10-02.md](docs/records/STATUS-2026-10-02.md) last section).
- **dgVoodoo had been rejecting the lab sandbox's `dgVoodoo.conf`** and running a 2020 global `%APPDATA%` file.
  Every earlier "this dgVoodoo knob does nothing" finding (`FPSLimit`, `CaptureMouse`, `FreeMouse`, forced refresh,
  the 1920x1440 pointer box) is `[retracted]`. The owner's daily-driver conf was accepted.
  [docs/records/GRAPHICS-ENHANCEMENT.md](docs/records/GRAPHICS-ENHANCEMENT.md),
  [docs/records/RENDERER-ALTERNATIVES.md](docs/records/RENDERER-ALTERNATIVES.md) section 11.
- **120 fps** `[verified in play]`: 120.1 fps measured and owner-played; 120 is the ceiling of every renderer
  tested (nGlide, DXVK, ReShade, DDrawCompat).
- **Per-frame audit fixes** ([docs/records/PER-FRAME-AUDIT-2026-10-03.md](docs/records/PER-FRAME-AUDIT-2026-10-03.md)):
  oil-slick hazard contact `[measured, sandbox]` 20 contacts/s at 20 / 60 / 120 fps (9 of 10 runs, one staging
  miss); dead-weapon click `[measured, sandbox]` 20/s at 20 / 60 / 120 (2 runs each); collision dedupe and AI roll
  hold `[built, untested]` (the tests ran but produced no data; count-only in `best-120`); radar turn
  `[built, untested]`.
- **`I76_MULTI_INSTANCE=1`** `[measured, sandbox]`: two lab copies ran side by side. A multiplayer session
  between them was not achieved (both need UDP port 21157; the internet transport wants a game server).
- **u32x**: lab build `054fb411` added to `deploy-u32x.ps1`'s known-good list (gated 2026-10-02/03: leg-b 3/3,
  trip route 120 fps, save screen, Esc-menu Exit, melee). Its source is in the lab repo; `u32x/u32x.dll` here is
  still `a5927cea`.
- **u32x full build in this repo** (the binary is the one gated above; `[built, untested]` on a fresh GOG
  install): `u32x/u32x_full.c` + `u32x_full.def` (lab `src/u32x.c` at lab commit `68a8a39`) and the gated binary
  `u32x/u32x_full.dll` (`054fb411`). `u32x/build-full.ps1` rebuilds it: same size, 4 bytes differ, all link-time
  stamps. `setup-windows.ps1` now installs this build by default (`-U32xDll u32x\u32x.dll` for the minimal one).
- **Repo tidy** (docs/REPO-ORGANIZATION-PROPOSAL.md): lab residue moved to `lab-residue/`; the 48 dated records
  moved to `docs/records/`. No installer or launcher moved.
- Docs: stale statements corrected or annotated, `docs/README.md` rewritten as an index of every doc,
  `docs/REPO-ORGANIZATION-PROPOSAL.md` added; tracked `.pyc` files and `grep.exe.stackdump` removed.
- Save-editor tests re-run: 156 passed with the lab saves folder present, 133 on the repo samples alone.

### 2026-10-02 (commits `c9e2695..7c998bf` plus the release-hygiene pass)

Status words are the ones [docs/RELEASE-PLAN.md](docs/RELEASE-PLAN.md) section 6 asks for: `[verified in play]`,
`[measured, sandbox]`, `[built, untested]`, `[retracted]`. "Sandbox" is `..\i76-uncap-lab\game`; **nothing in
this block is deployed to the playable install.** Session record: [docs/records/STATUS-2026-10-02.md](docs/records/STATUS-2026-10-02.md),
owner's console run: [docs/records/PLAYTEST-2026-10-02.md](docs/records/PLAYTEST-2026-10-02.md), open work:
[docs/records/BACKLOG-2026-10-02.md](docs/records/BACKLOG-2026-10-02.md).

Binaries of our own code at the end of the day: `music-fix/Strlkup.dll` 172,032 B, md5
`cf7329ea89660faa0d9299c754463c7b` (commit `7c998bf`; MSVC 2019 x86, `cl /nologo /LD /MT /O2 /W3
/D_CRT_SECURE_NO_WARNINGS strlkproxy.c /link user32.lib` via `music-fix/build.ps1`); `u32x/u32x.dll` 75,264 B,
md5 `a5927cea02697657ce2102be766b5616` (`cl /nologo /O2 /LD u32x_min.c /link /DEF:u32x.def user32.lib`).

#### Added

- **The whole switch set played at the console** `[verified in play]` (sandbox, owner, n = 1): in-mission music,
  F6 hood view and B binoculars at `I76_FAR_CLIP=1800`, flamer, music slider, AI behaviour, the Mission 5 jump
  without nitrous, the out-of-gas jumps, body roll, keyboard save. Why the jumps and body roll work:
  `I76_FIXED_STEP=24` steps 41.67 ms, the measured mean step of stock play at 20 fps.
- **120 fps: `I76_GLIDE_REFRESH=<hz>`** `[measured, sandbox]`: the 60 fps ceiling was `ZGLIDE.DLL` asking
  dgVoodoo for `GR_REFRESH_60Hz` in `grSstWinOpen`; the proxy repoints that import (through a `LoadLibraryA`
  hook) and substitutes the refresh code. 120.1 fps, dt 8.34 ms sd 0.06, physics still 24 steps/s, hood view and
  binoculars fine at 1800 m; melee entries at 120 passed 10 of 10. Not played by a person at 120 *(superseded:
  the owner played it that evening, see 2026-10-03 above)*.
  [docs/records/FPS-120.md](docs/records/FPS-120.md).
- **Trainer**: `Local\I76Trainer` control block in the proxy (god mode, unlimited ammo, no flats, component
  hold, freeze, held on the game thread; repair / teleport / ammo / stop one-shots; forced Play Options bits) and
  `tools/trainer/i76trainer_gui.py` + `TRAINER.bat` `[measured, sandbox]`: `trainer_live_test.py` 13/13 (a 40 m
  drop costs 156 hp without god mode, 0 with); GUI attached to the live game, toggles reflected.
- **Four opt-in frame-rate coverage switches** (backlog P2-05,
  [docs/records/FRAMERATE-COVERAGE-2026-10-02.md](docs/records/FRAMERATE-COVERAGE-2026-10-02.md)); all four apply on the sandbox
  (coll-window 3/3 sites, ai-fixes 6/6, far-engine-dt 1/1, mirror-rate 2/2 on the AiO layout):
  - `I76_AI_FIXES` `[measured, sandbox]`: AI dodge gate 2.87 checks/s at 20 fps, 8.90 at 60 unheld, 3.17 at 60
    with the switch, 17.19 at 120 unheld (A/A first, n = 2).
  - `I76_MIRROR_RATE` `[measured, sandbox]`: 10 mirror redraws/s with the switch; on the sandbox exe (GOG's AiO
    layout) the mirror otherwise redraws every frame.
  - `I76_COLL_WINDOW` `[built, untested]`: applies; the cactus-gauntlet acceptance run aborts on the direct-boot
    arena and was not ported.
  - `I76_FAR_ENGINE_DT` `[built, untested]`: applies; no acceptance driver yet.
- **`I76_FRAMERATE_FIXES`: oil slick and fire patch contact effect held to the 20 Hz grid** `[built, untested]`
  (commit `7c998bf`): the impact template and its sound fired once per rendered frame in contact (field report
  at 120 fps: "the oil slick sound plays too fast"). Not yet measured live *(superseded 2026-10-03: measured,
  20 contacts/s at 20 / 60 / 120 fps)*.
- **"Insert CD 2" prompt explained and mitigated** (backlog P1-09) `[measured, sandbox]`: the prompt fires when
  `startup_IsMinimum` 0x4b2220 answers 1, which on the pristine exes happens because `RegCreateKeyExA(...,
  KEY_ALL_ACCESS)` on the existing HKLM key is denied to a non-elevated process (the 6-of-21 split was launcher
  elevation); GOG's AiO exes carry `xor eax,eax; ret` there. The proxy now sets the current directory to the game
  folder at load (always on; `I76_CWD_FIX=0` disables), and `I76_CD_FAKE=1` (opt-in) answers 0 when
  `<game>\miss8` is a directory. `I76_CD_LOG=1` (opt-in since the evening, see Retracted) logs the modal with its
  cause.
- **Far clip on a file-patched exe** `[measured, sandbox]`: the proxy recognises the file patch and takes over the
  read (`far-clip: exe is file-patched (1800 m, pools x16); read site repointed`). Soak at 1800 m (backlog
  P1-14): trip missions t01-t17 clean with hood view and binoculars (t14 inconclusive); melee/arena missions are
  not direct-bootable and remain untested at 1800 m.
- **`u32x/`: the USER32 proxy's source, build script, deploy script and verified binary are in this repo**
  (backlog P3-02). The binary is the lab's `u32x_min` build (the 2026-08-16 revision + the DWM ghosting call)
  `[measured, sandbox]`: bookmark route to DONE 2/2, `TEST-FRAMERATE` option 6 through the trip menus 2/2 at
  120.0 fps, option 5 1/1 at 60.0, Save Bookmark after 10 s idle (row click, SAVE twice, overwrite prompt).
  Provenance and md5 in [u32x/README.md](u32x/README.md); a rebuild from the committed source differs from the
  committed DLL in 6 bytes (link stamps).
- **A fresh install and the portable zip now get u32x** (backlog P3-03) `[built, untested]`: `setup-windows.ps1`
  step 5a3 and `Make-Portable-Zip.ps1` (staged copy only) call `u32x\deploy-u32x.ps1`, which refuses a DLL that
  is not a recorded verified build, checks that it exports every USER32 function `i76.exe` and `i76shell.dll`
  import before writing anything, keeps the originals and reads every write back (`-U32xDll`, `-NoU32x`). Run
  offline against scratch copies of the pristine GOG binaries only (10 bytes changed per file, `-Restore`
  returns the original md5); the fresh-install console run (RELEASE-PLAN section 7 item 3) is still owed.
- **Docs**: the prioritised backlog (76 rows, 28 stale-claim pairs), the session status, the playtest record,
  [docs/records/HEALTH-BAR-COLOUR.md](docs/records/HEALTH-BAR-COLOUR.md), [docs/records/MOUNT-VALIDATION.md](docs/records/MOUNT-VALIDATION.md)
  (static: no class check at load; the turret rule applies only on DONE),
  [docs/records/SAVE-EDITOR-STATUS-2026-10-02.md](docs/records/SAVE-EDITOR-STATUS-2026-10-02.md),
  [docs/EDITOR-FIELD-TESTS.md](docs/EDITOR-FIELD-TESTS.md).

#### Changed

- **`I76_FIX_HEALTH_PCT=1` is now `min(28 + 72 x side, 100 x core)`** `[measured, sandbox]`
  (`health_pct_live_test.py`: stock 0.99 / x100-only 99.0 / min 49.6 on a 30 % armour car with a 99 % engine).
  The x100-only reading made the enemy target bar rise and go green on scratched cars (owner's playtest);
  `=2` keeps it for comparison.
- **Save editor rewritten on the game's own record frame** (`.cmp` = PartNode 0x20 + PartRec 0x54; the old
  editors read every part 32 bytes late) `[measured, sandbox]`: 172 tests *(the count follows the save files found; 2026-10-03: 156 with the lab folder,
  133 on the repo samples)*, byte-exact round trips on 46 saves,
  HTML == Python, and seven in-game probes (condition colour thirds; state 2 = van, 4 = salvage; **the garage's
  weapon list holds 11 records, a mounted weapon past the 11th reads EMPTY**; bench has no cap; the van holds
  >= 5 suspensions; vtf repaint works; spc01 = "Radar Jammer"; the LOAD label is scene + (state == 1)).
- **No tool defaults to the playable install any more** (backlog P3-12) `[built, untested]`: `LAUNCHER.ps1` and
  `tools/cursor-mode.ps1` take `-GameDir`, else `I76_GAME_DIR`, else an install beside the script, else the lab
  sandbox, else stop (LAUNCHER's title bar names the folder); `music-fix/build.ps1 -Install` lost the daily
  driver and `C:\Games\Interstate 76` from its fallback list. **If you started `LAUNCHER.ps1` with no arguments
  to configure the daily driver, pass `-GameDir` or set `I76_GAME_DIR` now.** Parse-checked, and `cursor-mode.ps1
  -Show` run read-only against the sandbox; the LAUNCHER window itself was not opened.
- **`music-fix/build.ps1` builds under a captured stderr** `[measured]` (no game involved): the MSVC branch
  aborted under `ErrorActionPreference Stop` because the in-`cmd` redirect covered `cl` but not `vcvars32.bat`'s
  "vswhere is not recognized" line. The chain is parenthesised, `-Msvc` forces the branch, `build-msvc.ps1` is
  now a wrapper for it, and the dead `$fwd` list is gone. `build-msvc.ps1` run from a captured-stderr shell:
  172,032 B, x86, exit 0 (the test build was discarded; the committed DLL is unchanged).
- **`tools/check-ffb.ps1` names** (backlog P3-18, i76-map L083/L084) `[built, untested]`: `0x52bbcc` is printed as
  the `Forcefeed` heap handle, not an "effect object"; `[0x52bbe4]` (device presence in the static map) is
  printed for information; the registry key line is informational, since no registry key gates FFB in the exe.
  The verdict logic (`0x52bbd0` and `0x52bbdc`) is unchanged. Not run against a live game.
- **`THIRD-PARTY.md`** (backlog P3-05): the committed binaries of our own code are stated; rows added for
  Lossless Scaling, opentrack, GE-Proton, Steam ROM Manager, input-remapper, w64devkit, the MSVC build tools,
  RAD Smacker, Cheat Engine, the RE tools, i76fix / D2DX, the VC5 media; the dgVoodoo row says where it is
  fetched from and makes **no** redistribution claim (the licence text was not checked).
- **README**: the "Open improvements" table (a 2026-08-16 snapshot) is replaced by a pointer to the backlog and
  the status doc (backlog P3-07); the preset section says multiplayer is untested with any preset but `stock`
  (P3-20). **CONTRIBUTING**: the committed `saves/` and the three own-code binaries are named exceptions to
  "never commit save files / binaries" (P3-10).

#### Fixed

- **`LAUNCHER.ps1` "Save index" health check used the wrong `savegame.dir` model** (backlog P3-04) `[measured]`
  (offline, on files): it wanted `0x28 + 60 x count` bytes, so every game-written file read as "TRUNCATED" (the
  sandbox's own 9-bookmark file is 544 B = `4 + 60 x 9`; the old check wanted 580). It now checks
  `size >= 4 + 60 x count`, reports padding as harmless, and flags records whose state is not 1 or 8. Layout:
  `u32 count`, then `{u32 scene, char name[32], char file[16], u32 state, u32 0}` at `4 + 60k`.
- **Save Bookmark screen mouse** (owner's playtest row 8) `[measured, sandbox]`: fixed by the ghosting call in the
  u32x build above (with `u32x_min`: 10 s idle, row click, SAVE twice, overwrite prompt reached by mouse; the
  full mouse-only save through YES was shown with the withdrawn `037fcb3a` build, which carries the same call).
- **18 stale or contradictory doc claims** in this repo (backlog section 2), and on 2026-10-02 the remaining
  sibling-repo ones listed in [docs/DOC-CORRECTIONS-PENDING-SIBLINGS.md](docs/DOC-CORRECTIONS-PENDING-SIBLINGS.md)
  were applied in `i76-uncap-lab` and `i76-map`.

#### Retracted

- **Fullscreen Esc-menu Exit fix** `[retracted]`: the rebuilt u32x with the Esc-menu box mapping (md5 `037fcb3a`)
  reached the Exit button but **broke TRIP -> LOAD BOOKMARK -> garage -> DONE** (leg-b B1.9: 4 of 4 failing;
  found by the owner on `TEST-FRAMERATE` option 6). It had been tested on the direct mission boot, melee, the Esc
  menu and the save screen, not on the bookmark route. The sandbox went back to `u32x_min`; use the keyboard in
  that menu.
- **Always-on CD-prompt instrument** `[retracted]`: its `shell_cb_17` wrapper forwards one argument on an
  unverified signature and logged a -1 on the failing route. It was not the cause, but it is now opt-in
  (`I76_CD_LOG=1`).
- **`savegame.dir` "0x28 header, 36 bytes short on every save"** and **the `.cmp` "truncated final record"**
  `[retracted]`: both were our parsers off by a constant (AGENTS.md invariant rewritten; the launcher's check
  above was the last code site).

- **Frame-rate presets for players (backlog P2-03)** `[built, dry-run tested]`: `PLAY-i76.ps1 -Preset <name>`
  reads `presets\<name>.psd1` (`stock`, `smooth-60`, `smooth-60-bugfixes`, `smooth-120`, `lab-all`; `-Preset ?`
  lists them) and hands the `I76_*` switches to the game process only; `-DryRun` prints the command line and
  environment and exits. Warns, without copying, when the game folder's `Strlkup.dll` is not the current
  `music-fix` build (size + md5) or when `I76PATCH.DLL` still caps the game. `LAUNCHER.ps1` gained the same
  drop-down; `setup-windows.ps1` and the portable zip carry `presets\`. Each preset's header says what is
  verified where (smooth-60 and the bug fixes console-verified 2026-10-02 in the sandbox, 120 measured in the
  sandbox); nothing is deployed to the playable install.
- **Research: raising the REAL frame rate is plausible — but only by inverting the
  question.** A 9-agent research pass (repo RE docs + web prior art) concluded the
  engine has no frame limiter and no sim/render separation: physics, AI, script VM and
  weapon audio advance once per rendered frame with per-frame constants, so scaling the
  physics up inherits unbounded per-subsystem breakage. The viable route keeps the
  20 Hz sim untouched and makes the renderer draw 2–3x per tick with interpolated
  transforms — direct closed-binary precedent exists (D2DX for Diablo II, Kaze's
  pre-decomp SM64 60fps). Blocked today by two unknowns: entity position/orientation
  offsets and the Gold exe's main-loop seam. Full verdict, ordered go/no-go checklist,
  prior-art catalog and the folklore-vs-measured corrections in
  [docs/records/FRAMERATE-UNCAP-RESEARCH.md](docs/records/FRAMERATE-UNCAP-RESEARCH.md). Nothing
  field-tested yet.
  - **2026-10-01 update:** superseded by measurement. The sim turned out to be dt-driven (i76-map
    `subsystems/simclock.md`), the "two unknowns" were pinned (pose at object+0x18; the frame loop at
    0x4039a0..0x403f20), and the proxy now carries the opt-in switch set — `I76_HIRES_CLOCK`, `I76_FIXED_STEP=24`,
    `I76_FRAMERATE_FIXES`, `I76_ENGINE_DT_FIX`, `I76_RENDER_INTERP`, `I76_FPS_CAP` — measured live in the sandbox
    (i76-map `captures/014-framerate`, 2026-09-27: dt exact, gravity dt-correct, 24 Hz body motion as calm as stock
    20, 31-33% motionless frames at 60 fps → 0% with interpolation). Per-switch evidence is the table in
    [music-fix/README.md](music-fix/README.md). Sandbox-verified, and **console-verified by the owner on
    2026-10-02** in the sandbox with every switch on (in-mission music, F6/B at `I76_FAR_CLIP=1800`, flamer,
    music slider, AI behaviour, the Mission 5 jump without nitrous, the out-of-gas jumps, body roll); nothing
    deployed to the playable install (corrected 2026-10-02: this said "not yet console-verified").
- **Wheel buttons moved to the AHK layer, with a shift layer (~27 actions from 13
  buttons).** `input.map` now carries only the analog sinks; every button and the hat are
  emitted as stock keys by [i76-remap.ahk](i76-remap.ahk). **Retraction:** an earlier commit
  claimed AHK could not read this wheel's buttons. It reads all 13 fine, headless, both
  `GetKeyState("Joy1")` and `1Joy1` forms — the finding came from a bug in the probe scripts
  (`FileAppend, % text, f` treats `f` as a literal filename; AHK needs `%f%`), so three probes
  wrote to a stray file called `f` while their intended logs stayed empty, and the empty logs
  were read as evidence. *A probe that reports nothing is not evidence until the probe is
  proven to report something.*
- **SOLVED: I76 force feedback dies if other joysticks are installed.** FFB worked on one
  Windows box and not another; the difference was neither Windows version, nor the exe, nor
  the registry, nor frame generation — it was **two virtual joysticks** on the failing machine
  (vJoy and a 3Dconnexion KMJ Emulator). Uninstalling them and rebooting fixed it immediately.
  `I7FF_InitSystem` acquires a DirectInput device **exclusively, once, at startup** ("try again
  next time" is a give-up, not a retry), so a crowded device list makes that one shot land on
  the wrong device. The tell is `check-ffb.ps1` reporting **module loaded but no device** —
  `0x52bbdc` nonzero while `0x52bbd0` stays 0. A dormant **bus** is harmless (the working
  machine has ViGEm installed with no children); what matters is whether a joystick *device*
  enumerates. Full writeup, disassembly detail and the ruled-out list in
  [docs/records/FFB-LAPTOP-RECON.md](docs/records/FFB-LAPTOP-RECON.md); new
  [`tools/ffb-recon.ps1`](tools/ffb-recon.ps1) dumps machine-side facts in a fixed order so two
  machines diff mechanically — which is how this was found. Generalises: *a 1997 game that
  acquires a DirectInput device once at startup has no tolerance for a crowded device list, and
  the symptom presents as the game being broken rather than the joystick software.*
- **The FFB "crash on fire" was the Thrustmaster control panel being open.** It holds the
  DirectInput device, so the game's FFB init fails (`I7FF_InitSystem Failed to open FF
  Joystick`), the effect objects are never created, and the first shot dereferences a null
  handle — `i76.exe` faults in `I7_SFRCE.DLL` at offset `0x2505`, three times, always the same
  offset. The tell was that the last one had **no force feedback at all**: "FFB stopped
  working" and "crashes on fire" were one problem, not two. Thrustmaster's own control panel
  warns about this on every tab (*"Always close this CONTROL PANEL window before starting your
  game"*). **Two earlier hypotheses are retracted** — that firing two hardpoints from one
  button caused it, and that a repeat-fire mode caused it. Both were removed in turn without
  stopping the crash, which should have been the clue; the repeat-fire mode may be safe to
  restore. Generalises past this wheel: *when a vendor UI warns you to close it before gaming,
  that is about exclusive device acquisition, and it presents as the game being broken.*
  Details in [docs/WHEEL-T300.md](docs/WHEEL-T300.md). Also settled there: **300°** is the
  right wheel rotation (an earlier draft guessed ~240°, too twitchy).
- **FORCE FEEDBACK WORKS.** Confirmed in-sim on a Thrustmaster T300RS, with analog
  steering, analog accelerator/brake and all 13 buttons. This closes the repo's oldest
  open question: [FORCE-FEEDBACK-AND-VISUALS.md](docs/FORCE-FEEDBACK-AND-VISUALS.md)
  had FFB as a Mac dead end and a Windows "should work" resting on two community
  reports. It also resolves that doc's standing contradiction with
  [GAMEPAD-PC-MAC.md](docs/GAMEPAD-PC-MAC.md)'s "no DirectInput — confirmed in the
  exe": **input is winmm, FFB output is DirectInput.** Both were true. The registry
  gate was already satisfied on this GOG install — no admin step needed.
- **Fixed: a latent AHK bug that hangs the game with ANY wheel or stick, on every
  platform.** `RStickGlance` in [i76-remap.ahk](i76-remap.ahk) guarded on `u = ""`, but a
  device with no U axis returns **`0.0`, not empty** — which reached the hysteresis,
  computed `+50`, and **held the Left arrow key down from the moment AHK started**. The
  game booted into a jammed glance-left and never reached the menu, looking exactly like
  a hang at "PLEASE STAND BY". Now gated on the `JoyInfo` capability string. It never
  fired before because the only device ever tested had a U axis. Compounding it,
  `PLAY-i76.ps1` force-kills AHK — skipping its `OnExit` handler — so the synthetic
  key-down never got a matching key-up and stayed **latched system-wide across
  relaunches**; the launcher now releases every key the layer can hold.
- **A force-feedback wheel, measured end to end (Thrustmaster T300RS).** The oldest
  open question in the repo — can a real wheel drive I76 — answered on Windows with
  hardware instead of community reports. Two non-obvious blockers, both found by
  measuring through winmm (`joyGetPosEx`, the API the engine itself reads): a T-series
  wheel enumerates in a crippled **pre-initialisation mode** until its driver is
  installed (`PID_B65D` "Thrustmaster FFB Wheel", pedals frozen at a single value, no
  FFB) — installing it re-enumerates as `PID_B66E` "T300RS"; and the wheel's default
  **Separate (3-axis) pedal mode cannot drive I76 at all**, because both pedals rest at
  an *extreme* while I76's `throttle` is a single bidirectional sink expecting rest =
  *centre*, so it pins at full deflection (runaway throttle). **Combined (2-axis)** mode
  gives one centre-resting axis and the stock binding is then correct. Full axis/button
  map, FFB status and the settings that matter in
  [docs/WHEEL-T300.md](docs/WHEEL-T300.md); new instrument
  [`tools/i76-joyprobe.py`](tools/i76-joyprobe.py) (waits for input rather than racing a
  timer, and warms up before baselining — a naive trigger fires on the device settling,
  not the user). Two more traps found in play: the `mouse` source sitting alongside
  `joystick1` on an analog sink **pins the axis** — steering was dead until it was removed,
  the same trap [DECK-INPUT-SCIENCE.md](docs/records/DECK-INPUT-SCIENCE.md) documented on the Deck;
  and the in-game Control Configuration menu **rewrites `input.map` destructively** (strips
  comments, deletes the keyboard driving bindings, moves `hardpoint2_fire` to the mouse).
  Native `joystick1 Button5`–`Button13` all work — they were briefly and wrongly blamed for
  the hang that was really the stuck arrow key above.
- **Frame generation without Steam.** Lossless Scaling turns out to have no Steam
  dependency at all — no `steam_api64.dll`, no Steamworks imports, and when launched
  directly it loads zero Steam client modules and keeps running with Steam fully shut
  down (verified 2026-08-01). Only the Steam-installed desktop shortcut
  (`steam://rungameid/...`) was pulling Steam in. Added an `Interstate '76 Gold Edition`
  profile with `AutoScale=true` + fixed 2× so frame-gen engages by itself — no Ctrl+Alt+S —
  and [`PLAY-i76.ps1`](PLAY-i76.ps1) now starts/stops it with the game (only if it wasn't
  already running). Physics stay at the 20 FPS base; these are interpolated *display*
  frames only. Details in [docs/WINDOWS-PLAYBOOK.md](docs/WINDOWS-PLAYBOOK.md) sec 2.
  [`Setup-FrameGen.ps1`](Setup-FrameGen.ps1) scripts the whole thing (profile +
  `-FixShortcut` + `-Revert`) so a second PC is one command.
- **Steam Deck: baseline control tier — rumble parity with Mac/Windows (untested on
  device).** The Deck ran Steam Input keyboard emulation and so never got the pad layer
  the other two platforms grew: the rumble mixer, LB shift layer, independent triggers,
  look-back rear gun. New [`deck/setup-deck-baseline.sh`](deck/setup-deck-baseline.sh)
  stages the *same* `i76-remap.ahk` plus AutoHotkey, and
  [`deck/i76-deck-launch.sh`](deck/i76-deck-launch.sh) — a `%command%` wrapper — injects it
  into the live Proton prefix (read from `$STEAM_COMPAT_DATA_PATH`, since Steam runs
  non-Steam shortcuts out of `compatdata/<appid>`, not the install-time prefix).
  [`deck/deck-push.sh`](deck/deck-push.sh) deploys it over ssh. The correct Steam setting
  is the **"Gamepad" template**, *not* "disable Steam Input" — the latter drops a Deck into
  lizard-mode keyboard/mouse. Recipe, decode sheet and rollback:
  [docs/records/DECK-BASELINE.md](docs/records/DECK-BASELINE.md). **Deployable but unverified** — the Deck
  was offline when this landed; button numbering and the XInput→haptics rumble path are
  ASSUMED until the decode sheet comes back.
- **Windows: Nitro Pack fully scripted.** `install.ps1` now auto-detects a GOG Nitro
  Pack install and applies the identical recipe (`setup-windows.ps1 -Exe nitro.exe`):
  dgVoodoo deploy + conf, input.map controls parity, `PLAY-Nitro.bat` + shortcut.
- **Windows fixes shipped from live play:** physics-safe FPS cap; handbrake on Space;
  campaign-save deployment; borderless-windowed 14:9 aspect (matches the Mac look);
  `FullscreenAttributes=fake`/windowed so the engine's modal dialogs no longer
  deadlock behind an exclusive surface; `[GlideExt] pure32bit` restored (16-bit
  fallback was causing purple night terrain); and the KB5101650 `winmmbase` boot
  crash diagnosed (uninstall the update — see docs/records/FINDINGS-2026-07-WINDOWS-AND-TEXTURES.md).
- **HD texture pack RETIRED.** The full-game enhanced-texture pack was built and then
  pulled: the in-game improvement didn't justify shipping it, and palette-indexed
  tiles rendered wrong on night missions (no palette-agnostic fix exists). The
  `-WithHDTextures` build step is gone; the research — including the cracked `.M16`
  format spec — is preserved in [docs/HD-TEXTURES-RESEARCH.md](docs/HD-TEXTURES-RESEARCH.md)
  for future work. The OpenGLide-HD fork ([tools/openglide-hd/](tools/openglide-hd/))
  remains as the unfinished true-HD route.

## v1.0.0 — "Vacation Build" (2026-07-14)

First public milestone: Interstate '76 (GOG Gold, 1997) running well on three platforms
from a free/open-source stack, plus a save editor and reverse-engineered file formats.
Everything below was hit, diagnosed, and verified in play on this port — details in
[docs/VERIFIED-FIXES.md](docs/VERIFIED-FIXES.md).

### Play — Apple Silicon Mac (the shipping build)
- Self-contained Sikarugir **Wine 10 (wow64)** wrapper, software renderer via **DxWnd** — instant
  start, no shader compile, big letterboxed 4:3 window at 1024×768.
- **In-mission music** restored (virtual CD-audio + track relinking; GStreamer env wired into the
  launcher stub).
- **Cutscene-music bug fixed** — proxy `SMACKW32.DLL` recreates the 1997 CD-drive behavior the
  community had called unfixable (ordinal-exact 39-export forwarder).
- **Clean quit** (no lingering black "wine" window), Mac arrow-key steering fix, mouse + Xbox-pad
  input, physics-safe **~19.2 FPS** cap for the Mission 5 jump and later bridge gaps.

### Play — Steam Deck
- Installed & working: Heroic/Proton + **dgVoodoo 2.78.2** Glide path (native Vulkan — bright
  3dfx color, 2× res, MSAA) **with force feedback**, full controller layout, library artwork.
- **One-liner installer** (`deck/deck-install.sh`, zenity-guided) — extracts *your* GOG installer,
  fetches dgVoodoo from the public mirror, registers the game with artwork and controls.

### Play — modern Windows
- One-command `install.ps1`: max-graphics dgVoodoo, force feedback, optional HD texture pack built
  locally from your own files.

### Tools
- **Save editor** — browser page styled as the game's Build & Repair Form (equipped loadout,
  editable armor, van/repair inventory, measured weapon DPS + range, part swaps, condition, scene
  select). Runs three ways: one-click Mac launcher with write-back + timestamped backups, a
  terminal CLI, and a **zero-install drag-and-drop browser page** (now hostable on GitHub Pages).
- **Reverse-engineered formats**: the save format (116-byte records, item catalog from I76.ZFS)
  fully decoded in the `.py` docstring; the VQM/M16 texture formats cracked with round-trip
  encoders in `texture-lab/`.

### Docs & research
- The doc map ([docs/README.md](docs/README.md)) tags every approach **working / parked dead-end /
  other-platform / reference** so nobody re-chases a settled problem (Voodoo-on-Mac shader
  persistence, Mac force feedback, HD-on-Mac renderer switch).
- New: **phone-port research** ([docs/records/PHONE-PORTS.md](docs/records/PHONE-PORTS.md)) — Android via Winlator,
  iPhone via streaming/UTM.

### Project
- Now MIT-licensed ([LICENSE](LICENSE)) with full third-party attribution ([THIRD-PARTY.md](THIRD-PARTY.md)).
- Promoted from `mac-gaming-ports/games/interstate-76/` to a standalone repo.

### Known gaps / next
- Universal in-Wine input remapper (AutoHotkey) staged, not yet wired into the launcher.
- Mac from-scratch install still requires the manual Wine-wrapper step (`mac-install.command` is BETA).
- Mission 6 night-texture re-quantize is a Windows texture-lab job.
