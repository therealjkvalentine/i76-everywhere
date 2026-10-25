# I76 Debug as the debug / cheat tool, 2026-10-20: full car state store / restore, DEBUG.bat, the haptics button

Owner (verbatim, 2026-10-20 evening): *"the teleport capability in the trainer should also teleport 6 axis position and speed
when stored, and it should be called debug.bat not trainer, and should be included in the daily driver as a cheat tool or a
debug tool for others when we ship."* and *"not sure why no haptics host data in debug"*.

Commits (i76-everywhere main): `2d6e7e8` proxy + `i76trn.h`, `0abf540` I76 Debug (trainer, haptics starter, launchers, tests),
`3401323` READMEs, this record + `docs/OWNER-TEST-LIST.md` item 33b. Lab: `tools\debug-tool\` (stage, run, analyse scripts),
`builds\debug-tool-20261020\` (builds + the staged set), evidence `captures\debug-tool-20261020\`.

## 0. Result

* **Store / restore puts the whole car back and the run replays bit for bit.** Lab copy `exp-debug` (= the release candidate,
  tick19-42 preset, headless), T05 crest: 7 store / teleport-away / restore cycles per boot, 2 boots (5 rolling down the slope at
  68-72 km/h, pitch -5.4 to -6.0 deg; 2 in the air at 57 km/h, airborne bit set), each restored after the car had been
  teleported ~390-410 m away and stopped. The restored run vs the stored run, tick for tick over 24 ticks (1.0 s, 16-20 m of
  travel): **position, velocity and heading / pitch / roll differences 0 (exactly; the telemetry carries the position as
  doubles), n 14 of 14**. Every restore read back exact (`readback_bad` 0). Tolerance stated: 0 measured; any difference
  > 1e-6 m would have shown.
* **DEBUG.bat is the one entry** ("I76 Debug: debug / cheat tool"); `TRAINER.bat` is a one-line shim to it on the Trainer tab.
* **Haptics tabs explain themselves and start the host in one click** (dry run by default; refuses without a wheel or pad and
  offers "Start anyway (dry run)"). In the lab boot the forced dry run went live: host data on the dashboard within seconds.
* **Staged, not installed**: `<lab>\builds\debug-tool-20261020\stage` + `MD5SUMS` (section 5). Nothing was copied into
  the release candidate, the daily driver, golden, lan or the twin.

## 1. What the full state is

`tools\trainer\i76trn.h`: the 168-byte `i76trn_ctl_t` is unchanged (version 1, size 168), so every older front end (the
2026-10-12 I76 Debug in the daily driver, the classic tkinter window) still drives the block. The mapping grows to 168 + 1304
bytes and `i76trn_ext_t` follows at +168 with its own magic (`'I76S'`); a front end that does not find it keeps the
position-only teleport. Commands 7 `STORE_STATE` and 8 `SET_STATE`; an older proxy answers "unknown command".

`i76trn_state_t` (632 bytes), captured and written by the proxy on the game thread at the top of a frame, before the tick
(fields from <re-archive> `subsystems/physics.md`, the veh+ / w+ tables):

| part (`I76TRN_ST_*`) | fields |
|---|---|
| POSE | rotation rows right / up / forward obj+0x18 (heading, pitch, roll), position obj+0x40 (doubles) |
| MOTION | world velocity ent+0xbc, \|v\| ent+0xac, 1/\|v\| ent+0xb0, body rates pitch / yaw / roll ent+0xc8, last acceleration ent+0xd4 (the next step's weight transfer reads it) |
| CONTACT | ent+0x454 bits 0x2 skid / 0x4 airborne / 0x10 body contact latched, surface ent+0x45c, probe normal ent+0x460, ground g ent+0x46c, clearance ent+0x470, fall-kill reference ent+0x474 (a landing 35 m below it kills) |
| WHEELS | per wheel (slots 0-5, type 30): spin speed w+0x20, suspension offset w+0x24, ground height w+0x2c, previous bump / bump change w+0x30 / +0x34, unloaded w+0x40, the suspension filter {a1, a2, b0, y1, y2} w+0x58, local y (wheel object +0x48) |
| ENGINE | gear, drive power, rpm, speedo (engine component +0x08 / +0x10 / +0x1c / +0x24) |

Not carried: the camera, AI cars, scripts, damage, ammo and the input. A restore onto a car of another mass skips WHEELS and
ENGINE. Every field written is read back (`ext.readback_bad`). Under the sim tick the restored pose differs from the recorded
interpolation end, so the draw shows it as written (an outside write), as for a teleport. The 7 lab cycles captured all five
parts (`parts` 0x1f; wheel mask 0b110011 = the four wheels, no mid pair).

In-game keys: **Ctrl+9 store, Ctrl+0 restore** (opt-in: the proxy watches them only while a front end sets
`ext.hotkeys`; I76 Debug sets it while it drives the block and clears it when it closes; only while the game window has
the focus; edge-triggered once a frame). Every F key is a camera in `gamekey.map` (F1-F11) or the video mode (F12); 9 and 0
are bound nowhere in `gamekey.map` or the shipped `input.map`. Not pressed at a console yet (section 6).

If the classic tkinter window starts before the game it creates `Local\I76Trainer` at 168 bytes; the proxy then maps only the
version-1 block and logs `trainer: full-state store / restore OFF (the section was created at the old size ...)`.

## 2. The Debug tool (front end)

* Trainer tab: Store now / Restore / Restore stopped, the quick slot shown as position, km/h, heading, pitch, roll, airborne;
  the in-game keys box; three waypoints: Save here (full state), Go (full state), Go stopped (pose, zero motion), "<- quick".
* `waypoints.json`: `x`, `y`, `z`, `saved` stay at the top (old readers); new `how`, `summary`, `state`. An old position-only
  entry loads and Go teleports the position (log: "holds a position only ... teleporting the position"). Measured: the shipped
  waypoint 1 (8231.4, 20.8, 44286.3, saved 2026-10-03) loaded as `position only` and Go sent the TELEPORT (ack ok).
* Direct mode (no proxy block): store / restore of pose + motion through WriteProcessMemory (written twice, read back).
* `DEBUG.bat` (driver and repo): console title "I76 Debug: debug / cheat tool", new options `--haptics`, `--haptics-live`.
  `TRAINER.bat` (driver and repo): `@call "%~dp0DEBUG.bat" --tab trainer %*` (+ a REM line). The classic window is
  `python i76trainer_gui.py`.

## 3. Measurements (lab copy `exp-debug`, headless)

Copy: `<lab>\exp-debug` = `Games\I76\release-candidate` (lab `game-tick`) copied 2026-10-20 17:04
(583 files, 491.7 MB), its proxy `adc4fd49` kept in `exp-debug\_lane`. Proxy in the runs: the lab twin
`Strlkup-dbg-lab.dll` `d7a0e9d6` = the candidate's source (`2d6e7e8`) + the lab drive block / `I76_HEADLESS_ACTIVE` /
drive-block names (the tick-range recipe, `builds\debug-tool-20261020\make.ps1`). Preset `tick19-42` + `I76_MISSION=t05.msn`,
`I76_START_POS=7972,101.8,44035,-90`, `I76_TELEMETRY=7731`, `I76_SHM_SUFFIX=exp-debug`, `I76_MUTE=1` + the per-pid mute
watcher, private desktop (`tools\debug-tool\dt-run.ps1`). The Debug under test is the staged one, run from
`exp-debug\_tools\debug\i76debug.py --any` (`tools\debug-tool\dt_roundtrip.py` drives it over its HTTP API; the launch
velocity is the harness's own TELEPORT-with-velocity on the block). Analysis `tools\debug-tool\dt_analyse.py`.

Method per cycle: crest at rest; TELEPORT with velocity along the car's forward row (slope: 18 m/s; air: +3 m, 16 m/s
forward + 6 m/s up); after a delay, Store (quick slot); 1.6 s later teleport ~400 m away (to waypoint 1's xz) and wait 1.5 s;
Restore. Under the tick the proxy publishes one telemetry frame per tick, so tick k after an event = the k-th published
frame at or after the event's proxy frame. Instrument check: the two compared series share no frame, the frame before each
restore was at the far point (8232, 56-66, 44317) at 6 m/s, and the stored run moved 16-20 m inside the 24-tick window
(the window ends before the harness teleports the stored run away: at 48 ticks the comparison catches that teleport, as it
should).

| boot | cycle | kind | stored state | away | readback | 24 ticks: max dpos / dvel / dang |
|---|---|---|---|---|---|---|
| r3 | 1 | slope | (7957.5, 99.95, 44035.0) 68.3 km/h, hdg -90.0 pitch -5.4 roll 0.6 | 396 m | exact | 0 / 0 / 0 |
| r3 | 2 | slope | (7951.1, 99.3, 44035.0) 69.3 km/h, pitch -5.4 | 400 m | exact | 0 / 0 / 0 |
| r3 | 3 | slope | (7945.5, 98.8, 44035.0) 70.2 km/h, pitch -5.4 | 404 m | exact | 0 / 0 / 0 |
| r3 | 4 | slope | (7939.8, 98.2, 44035.0) 71.1 km/h, pitch -5.4 | 408 m | exact | 0 / 0 / 0 |
| r3 | 5 | slope | (7934.0, 97.6, 44035.1) 72.1 km/h, pitch -6.0 | 412 m | exact | 0 / 0 / 0 |
| r3 | 6 | airborne | (7966.0, 106.3, 44035.0) 57.5 km/h, pitch -5.8, airborne | 391 m | exact | 0 / 0 / 0 |
| r3 | 7 | airborne | (7964.7, 106.4, 44035.0) 57.4 km/h, pitch -6.1, airborne | 392 m | exact | 0 / 0 / 0 |

Second boot r4 (19:0x, same set, after the other lanes' boots): the same 7 cycles, stored states within 0.1 km/h and 0.1 deg
of r3's, **24-tick max dpos / dvel / dang 0 / 0 / 0 in 7 of 7**, every restore read back exact, CRASH 0. **Total n 14 (10 slope,
4 airborne) over 2 boots, all bit-identical.** The display-frame offset of tick 1 after the event differed by 0-2 frames
between the stored and the restored run (the tick's wall-clock phase); the sim does not depend on it.

Also in these boots: waypoint 2 Save (full state, 67 km/h on the slope) + Go: "restored parts 0x1f, read back exact" (n 2
boots); cheats-used marker 0x535f78 = 0 and play flags 0x00 after all of it (n 2); proxy log `trainer: cheat-marker guard
4/4 sites` (the guard code is unchanged, PROMOTIONS row 11) and `trainer: full-state store / restore on (1304 B extension at
+168 ...)`; CRASH lines 0. r1 did not run its cycles (the harness, not the game: the driver exited at start, no output; r2
added the driver's own diagnostics and ran); r2 ran all cycles and every restore read back exact, but its tick comparison
was wrong (it keyed ticks on the sim frame counter; under the tick the proxy publishes per tick, fixed in `dt_analyse.py`), so
r2's numbers are not in the table; its stored states match r3's to 0.1 m (the start is deterministic).

Observation (not this change): a position-only TELEPORT to a point below the ground is pushed out by the physics on its first
tick. Waypoint 1 (y 20.8, saved 2026-10-03, probably in another mission) landed at (8232.3, 66.1, 44316.3) in T05: 44 m up and
30 m sideways. A full-state waypoint does not have that problem (it carries the pose it was taken in).

## 4. Haptics: why "no haptics host data", and the fix

Cause: the Force feedback / Rumble / LFE / Motion tabs only show what the haptics host (`tools\haptics`) publishes with
`--debug-udp`; `PLAY.bat` never starts it, and the tab only said "start it with ..." (by design, `tools\debug\README.md`).
Now (`tools\debug\debug_haptics.py`): the tab lists the wheel / pads the host could drive (winmm joysticks that answer
`joyGetPosEx`, XInput pads; enumeration only), where the host is (`I76_HAPTICS_HOST`, `tools\haptics` beside the tool, else
the owner's checkout `tools\haptics`; a shipped folder has none and the tab says so), and offers
Start. Start adds a tee 17676 to the dashboard's telemetry socket at that moment and runs `i76haptics.exe live --source udp
--port 17676 --debug-udp 127.0.0.1:<port> --out %TEMP%\i76debug-haptics` (dry run: drives nothing). `--live` only by the
"drive the devices" box (with a confirm) or `DEBUG.bat --haptics-live`: a wheel must not get two force sources. The child
sits in a kill-on-close job (closing the dashboard window ends it; tested: the child exits when the job handle closes), and
only the host the dashboard started is ever stopped.

Measured: on this PC at 18:30 no wheel or pad answered (joysticks 0, XInput 0). Lab boot r2: Start -> refused, "no wheel or
gamepad found (winmm joysticks 0, XInput pads 0) ..."; Start anyway (dry run) -> host started, `hap_live` true (first datagrams
within the poll), Stop -> stopped (n 1). Offline (`tests\test_fullstate.py`): refusal message, forced dry run with the tee
added and no `--live`, `--live` refused without a device, refusal when the dashboard could not bind the telemetry port.
Not measured: Start with a wheel plugged in, and `--live` (the owner's test 33b).

## 5. The staged set (not installed)

`<lab>\builds\debug-tool-20261020\stage` in the daily driver's layout, from committed sources
(`git archive`, `tools\debug-tool\stage.ps1`), `MD5SUMS` beside it:

From i76-everywhere `3401323` (20 files):

```
9e1f401f3e8685dfd7a56d4092b2e9f9  _tools\debug\debug_core.py
ab518dca8c4fc83f9124c5ea16019c20  _tools\debug\debug_haptics.py
b998692aec77af696e529012a5a6b346  _tools\debug\debug_logger.py
8c5637a230f217d1f806d19b14be2808  _tools\debug\debug_trainer.py
292fb82dbbd18de668ea181ab98c2705  _tools\debug\i76debug.py
3c84525d033f5e32489dbca2014e456a  _tools\debug\README.md
bbc7c0a684731b2afb0e4a8aa82f58a1  _tools\debug\static\app.css
ec9c987a72d0f3511bcb5b80a00a0031  _tools\debug\static\app.js
157732631a854fae58c8450295ff7035  _tools\debug\static\charts.js
c229d3191d86ae6ce364aa8b749742bc  _tools\debug\static\index.html
6a62b92d6d1507e8099d10afd826f4b9  _tools\telemetry\i76tel.h
4eef584572d89fe5ec51b76c8c9cfe3b  _tools\telemetry\i76tel.py
94165e67af5f3647ddac84e0ff069cff  _tools\telemetry\i76tel_v2.h
0077c65bfcfd09623098bcc410355a49  _tools\trainer\i76trainer.py
fc1c6a3378ba61435b2276b3d6de3002  _tools\trainer\i76trainer_gui.py
35200c2ca7f356537aaf393bea9f9733  _tools\trainer\i76trn.h
4d3ffd8605b9454ae6342608b63adfdd  _tools\trainer\README-GUI.md
45569f03557cbc3a087c40206c1d09b1  DEBUG.bat
31842e34d2523c95b8aa7e3efdab6350  Interstate 76\STRLKUP.DLL
7c26f7218cd071f2f6b47e81bdec05d1  TRAINER.bat
```

The copy in `exp-debug` that the runs used was staged from `0abf540` (same code; only `_tools\debug\README.md` and
`_tools\trainer\README-GUI.md` differ).

Proxy `STRLKUP-dbg.dll` `31842e34d2523c95b8aa7e3efdab6350`: i76-everywhere `2d6e7e8` (= main at that commit: tick19g `64d9361`
+ the multiplayer commits up to `d249380` + the full-state block), MSVC 2019 x86 `/LD /MT /O2 /W3`, link `/Brepro`, built twice
(`b1`, `b2`): byte-identical (the lab twin `d7a0e9d6` too). The other lane's uncommitted proxy edits (`polish.c`, `simtick.c`
sign sound) were not in the working tree I committed from (only my hunks were staged) and are not in this build.

For the install (main, after its gate):
* the proxy is a release-candidate-class proxy (the tick code, the MP commits); for the daily driver it belongs with
  promotion 19 rather than on promotion 18's `33211f11`. Without it the new Debug still works: "full state: no: this proxy
  predates it", Save / Go position-only.
* keep the folder's own `_tools\trainer\waypoints.json` (not staged: untracked, it holds the owner's waypoints).
* `_tools\telemetry\i76tel.py` and `_tools\trainer\i76trainer_gui.py` changed since promotion 16 (the shm-suffix and other
  lanes' work); the Debug imports both, so they go together with `_tools\debug`.

## 6. Open

* Ctrl+9 / Ctrl+0 not pressed at a console (headless lab runs have no focus), n 0. The owner's item 33b.
* The haptics Start with a real wheel / pad, and `--live`: not run (no device answered here).
* Not tested on promotion 18's proxy family (the staged proxy is the tick candidate's).
* Restoring onto another car (mass differs, wheels / engine skipped) is code-read only.
* `docs/OWNER-TEST-LIST.md` carries a pre-existing corruption: the line "- **Owner smoke test 2026-10-17 (daily driver,
  promotion 16, keyboard) ..." repeated after most lines (728 copies, already in `b778c6a~1`); not touched here.
