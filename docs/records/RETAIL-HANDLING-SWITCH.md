# Retail handling: data check, the I76_RETAIL_HANDLING switch, A/B launchers (2026-10-16, console lane)

Companion to [RETAIL-HANDLING-DIFF.md](RETAIL-HANDLING-DIFF.md) (the static lane), which explains the retail 1.0 vs Gold
yaw gap: **not a code change, the "Arcade Phys." option**. The retail emulator runs had it on by accident (a Gold-layout
I76PLYR.DEF read by the 1997 exe). Both exes default it to off. This file adds what the console lane did the same night.

- **Not touched:** the daily driver and the golden copy (the golden exe was only read). Nothing was installed in the
  lab twin; its STRLKUP.DLL is still b3 `33211f11` (read back).
- **Raw material:** lab `tools\retail-handling\` (scripts), lab `emu\work\retail-data\` (the retail I76.ZFS and
  MISSIONS\*.MSN taken from the owner's CD 1 image with 7-Zip, gitignored).

## 1. The vehicle data is the same (fills RETAIL-HANDLING-DIFF "Not done: vehicle data")

Retail CD 1 `I76.ZFS` against the GOG `I76.ZFS` (55,535,506 B, the twin's), every vehicle file decoded and compared
field by field (`datadiff.py`, `chunkdiff.py`, `vehfields.py`, `msndiff.py`):

| data | result |
|---|---|
| `compnent.cdf` (engine power, brakes, **suspension handling**, masses) | **byte-identical** |
| `.wdf` wheels (70 files) | all differ, but only in body +0x24 (retail 3.4e38, GOG 1e5; a field nothing reads, VEHICLES.md s.5) and last-digit geometry rounding. Hit points, mass, **size factor** (the +0xc the steering limit sums) identical |
| `.vdf` chassis (34) | mass, drag, class, size identical except `vxbus.vdf` mass 9,000 -> 12,730. LOD distances and geometry chunks differ |
| `.vcf` (280) | mostly identical; Gold renames some chassis files (`vccameo` -> `vccavera`, ...), engine-sound ids and a few armour values. Suspension / brake ids unchanged |
| WRLD surface records in all 40 missions (grip, rolling drag, bump, damage rate) | **identical** (retail WRLD is revision 8, without the horizon name, so its records sit at +0x8a, Gold's at +0x97) |

So the lateral limit A (vehicle grip x surface friction) is the same data in both installs, which the static lane's
0x2000-threshold estimate (A_gold 22-23.4) already suggested.

## 2. The lateral limit measured directly (`latlimit.py`)

In the grounded, non-sliding state the engine sets the yaw rate (0x43ce10): r = steer x min(k v, C / v). From the
traces, C = |r| v / |steer| on steer-phase frames with |steer| >= 0.2, v >= 8 and no slide or airborne bit on this or
the previous frame:

| exe | runs / steer phases | C, median per phase | C / n.y^3 (n.y = ground normal, median per phase) |
|---|---|---|---|
| Gold (arcade off) | 5 / 16 | **31.48-31.75**, whatever the slope (n.y 0.972-1.000) | 31.6-34.3: the fixed limit 7.84 x 4.04 has no slope term |
| retail (arcade on) | 6 / 18 | 19.3-23.5 | **23.32-23.47 in 16 of 18**; 21.0 / 21.1 in the 4th loop repeat (not explained: surface or wheel damage) |

The first retail run's low value (21.2 in RETAIL-HANDLING-DIFF s.4, "not explained") is slope: that run steered on
ground with n.y 0.96-0.97, and 21.44 / 0.9724^3 = 23.32.

The slope dependence is a second, independent signature that retail ran the grip-based (arcade) limit.

## 3. The switch: I76_RETAIL_HANDLING=1 (proxy, lab build only)

- **What:** at the top of every frame (frame hook, before simclock and the tick; where the trainer and I76_START_POS
  run), if the game state is 5 and the local player's car exists, set entity +0x454 bit 0x10000 when it is clear. Logs
  `retail-handling: on` at startup and the first sets (`flag 0x10000 set on the player's car (set #n, frame f, flags
  now ...)`).
- **Equivalent to:** ticking Options > Play Options > Arcade Phys. (physics_InitEntity 0x438a90 and
  physics_SetPlayerArcadeMode 0x43d1a0 set exactly this bit), except that nothing is saved: options_play_flags and
  I76PLYR.DEF are not touched, and a respawned car gets the bit again on the next frame.
- **Effects (both from the bit, not separable without a code patch):** grip-based steering limit (about a quarter
  less turn at speed on the melee car, almost no sliding); a car at rest on its roof is flipped upright instead of
  destroyed (offline only).
- **Source:** `music-fix/strlkproxy.c` (`apply_retail_handling` / `retail_handling_frame`), off unless set.
- **Build:** `music-fix/out/Strlkup-rh2.dll`, 338,432 B, md5 `0406e90980d1b15b154f44c7a3ea99e3` (MSVC x86, lab
  `builds\retail-handling-20261016\`, source snapshot `src-rh2\`, md5 of strlkproxy.c `a3f97192`). It is HEAD plus this
  switch only: the replay code another lane is writing in the same file (I76_REPLAY, `replay.c`) is not in it.
  Not committed as a binary. `rh1` (73eb2cfd) was the first build; same code, a wrong log text ("1997 retail default").
- **Verified:** loads in the twin's i76.exe, logs the switch line with every other switch as before (two boots).
  **Not verified by this lane:** any mission frame. See section 5.

## 4. A/B launchers for the owner (lab twin, read back, not promoted; owner test 44)

Made by lab `tools\make-test-variants.ps1 -Only p166-retail-*` from `presets\lab-p166-retail.psd1` (TEST-p166-retail-step):

| launcher | differs from TEST-p166-retail-step in | read back |
|---|---|---|
| `TEST-p166-retail-step-43.bat` | `I76_ASPECT` removed (no Hor+: 90 deg instead of 121.7 horizontal FOV, no HUD squeeze), `I76_U32X_MENU_ASPECT` 3440:1440 -> 4:3, conf `dgVoodoo.wide-43.conf` = the wide conf with `[Glide] Resolution 3840x2880` (4:3, 2x of 1920x1440, side bars under stretched_ar) | preset diff = exactly those two lines; conf diff = the one Resolution line + the generated header |
| `TEST-p166-retail-handling.bat` | `I76_RETAIL_HANDLING=1`; refuses to start (message + pause) unless the installed STRLKUP.DLL md5 is `0406e909` | preset diff = that one line |

Neither has been booted by hand. The 4:3 launcher works with the installed b3 proxy; its in-mission menu mapping at 4:3
is the u32x default and still needs one Esc-menu click check.

## 5. Why nothing ran live

- `query session` from 22:33 to 23:15: the user session (1) **Disc**onnected, the console session at the logon screen, no
  RDP connection. At 23:16 session 1 became **Active over RDP** (`rdp-tcp#11`) and another agent (`.console-owner`
  "lab-retail-handling") started proxy-run boots of the twin; this lane stopped live work there, as its brief says for
  RDP. In the disconnected state the game cannot initialise its display:
  - autotest\proxy-run.ps1 (t06): Glide context created, never reached the mission in 120 s (its Esc goes through
    SendInput, which reaches nothing in a disconnected session);
  - `tools\retail-handling\run-twin.ps1` (keys by PostMessage instead): crash in the DirectDraw mode set,
    `CRASH: code 0xC0000005 at 0x00475C36` (0x475b60, the video-mode switch: a released surface pointer is 0), frame 0.
  - An unknown launcher's `m01` boot at 22:35 (not this lane's) ended right after DllMain the same way.
- Not done as a workaround: reconnecting the owner's session to the console (`tscon`) would unlock his desktop on the
  monitor; not this lane's call.
- Audio: `tools\mute.ps1` failed ("Element not found": no default playback endpoint in a disconnected session), so
  nothing was muted or unmuted.
- The twin was left as found: STRLKUP.DLL `33211f11`, no `.pretest`, no lock. The stale twin lock from 2026-10-15 14:19
  (pid 32896, not running) was moved aside as `.console-test.lock.stale-20261015-1419`.

## 6. Ready to run when the console is back (`tools\retail-handling\`)

1. Take `.console-owner`; `run-twin.ps1 -Dll ...\out\Strlkup-rh2.dll -Mission t06 -Env <lab-p166-retail + I76_RETAIL_HANDLING=1>
   -Run "python -I flagpeek.py 6"`: the arcade bit must read back on every player frame (`arcade_frames` = `frames`),
   and absent without the switch.
2. Steering A/A + A/B, n >= 5 per condition, interleaved, the emulator's protocol (bang-bang hold of 18 m/s with the
   brake key, keyboard steer 3 s): `latlimit.py` on the phases. Prediction from the traces: C = 31.4-31.7 without the
   switch (Gold), 23.2-23.5 on level ground with it (retail); yaw_ss 1.35-1.43 vs 0.95-1.0.
3. Accel / brake / gravity with and without: unchanged expected (the bit is read only by the lateral function,
   CheckImpact and the AI's model of its own car).
4. Then install rh2 in the twin (backup `STRLKUP.DLL.33211f11-pre-rh2`) and run the owner's routes before leaving it
   there (memory: test the owner's route before installing).

## 7. Second lane, 23:05-00:00: live attempts, an input instrument, one-click A/B (lab-retail-handling, run 2)

A second agent with the same brief worked in parallel from 23:05 (the `.console-owner` the first lane saw at 23:16 was
this one). It did not change the switch source; it reused rh2 and added what the first lane listed as blockers.

- **Arcade bit read back in a mission: yes, n = 1 run.** 23:16, lab twin copy, T06, rh2, `I76_RETAIL_HANDLING=1`,
  `I76_FPS_CAP=20`: the proxy logged `flag 0x10000 set on the player's car (set #1, frame 1, flags now 0x00091041)`,
  and the telemetry flags dword (the proxy's per-frame copy of entity +0x454) carried 0x10000 in **158 of 158** mission
  frames. That run was during the RDP-active window (section 5), so it says nothing about rendering; it is the only boot
  that reached a mission. The external ReadProcessMemory read-back in that run read the wrong pointer level (fixed
  since: `[[[0x54a264]]+0x70]+0x454`), so the in-process telemetry copy is the only read-back so far.
- **Steering was not measured in it:** `keybd_event` reached nothing (applied steer 0 and throttle 0.002 in every
  frame, 77 + 81 frames), so the yaw numbers of the brief (12 / 18 / 25 m/s, n >= 5, A/A) do not exist yet.
- **Boots after 23:20: 0 of 8 reached the mission** (session 1 disconnected again; `quser` idle 31 min at 23:48; the
  only display is `WinDisc` 800x600):
  - the boot stops on a modal `#32770` "Running software emulation mode" / "Failed to initialize 3D hardware
    acceleration" (window enumeration, n = 2); its only button "OK" has control id **2**;
  - dismissing it (`dismiss-swemu.ps1`, WM_COMMAND 2) leads to `CRASH 0xC0000005 at 0x00475C36`, frame 0, n = 2 (`-glide`
    and `-d3d` the same): the crash the first lane saw is the software-emulation fallback after the 3D init failed;
  - dgVoodoo `OutputAPI = d3d11warp` (own copy only): `CRASH 0xC0000094` (integer divide by zero) in
    `glide2x.dll+0x49836`, n = 1. Not chased further.
  - So a live run needs the owner's session at the console (or RDP with a 3D path). Not done: `tscon` (would unlock
    the owner's desktop on the monitor).
- **Input without a keyboard: `I76_RH_DRIVE=1`** (lab build rh3 only: `builds\retail-handling-20261016\drive-block.c`,
  inserted into a copy of the rh2 source by `insert-drive.py`; md5 `b35547d1`; not in this repo). It wraps the one call
  of `input_ApplyToEntity` 0x44f1c0 at 0x44df61 and, before the stock code, sets the held-key bytes from
  `Local\I76RhDrive` (throttle_up 0x5367d0, throttle_down 0x5367d1, steer_left 0x5367d9, steer_right 0x5367da). The
  stock code then runs its own keyboard ramp (steer = sqrt(hold / 3), so 0.9 after 2.43 s, matching the emulator's
  2.41 s, EMU-MEMTRACE s.3). Loaded and logged `rh-drive: on` (n = 2 boots); **never exercised in a mission** (no boot
  after it was built reached one). The same call site is patched by `I76_REPLAY`; do not set both.
- **Measurement scripts** (lab `tools\retail-handling\`, commit lab `efe6687`):
  - `steerhold.py`: per speed 12 / 18 / 25 m/s and side, TELEPORT onto the T06 flat strip with that speed, throttle
    governor, 1 s later full keyboard steer for 3 s; then accel from rest and full brake; arcade bit read from outside
    the process before and after;
  - `run-rh.ps1`: one boot per run on `game-rh` (a gitignored copy of the twin's files, so the twin is untouched),
    conditions `off` / `offaa` / `on` (stock exe behaviour + `I76_FPS_CAP=20`, `on` adds `I76_RETAIL_HANDLING=1`),
    plus `phys-suite.py --phases drop` for g; console lock per run;
  - `steerhold-analyse.py`: yaw_ss (1-2 s after key-on, the EMU-MEMTRACE window), K = |r| v / |steer| on non-skid
    frames, skid / 0x2000 / arcade shares, 0-10/20/30 m/s, brake distance, drop g; mean +- sd (n) per condition.
  - `run-rh-night.ps1`: retries boots; ran 23:50-00:00, 0 good runs; stopped so it cannot take the console when the
    owner is back.
- **Expected numbers** (from the traces, RETAIL-HANDLING-DIFF s.4 and section 2 here; not measured on our exe yet):
  off K 31.4-31.7, on K 23.2-23.5 on level ground; at 18 m/s yaw_ss about 1.35-1.43 off and 0.95-1.0 on; accel,
  brake and drop g unchanged (the bit is read only by the lateral function, CheckImpact and the AI's own-car model).
  The retail fingerprint file `emu\results\gold-standard\retail-p166-low.json` does not exist yet; the comparison
  targets are the EMU-MEMTRACE retail numbers (arcade on, as measured) and, for the gold standard proper (retail,
  arcade off), our exe with the switch **off**.
- **Owner one-click files (lab root):**
  - `PLAY-RETAIL-HANDLING-ON.bat` / `PLAY-RETAIL-HANDLING-OFF.bat`: game-rh with rh2 (md5 checked / installed), presets
    `lab-p166-retail-handling` / `lab-p166-retail` (dry-run checked: the only difference is `I76_RETAIL_HANDLING=1`).
    Unlike the twin's `TEST-p166-retail-handling.bat` these work today (rh2 is installed in game-rh, not in the twin).
  - `MEASURE-RETAIL-HANDLING.bat`: the whole off / offaa / on campaign, n 5 each, about 45 min unattended at the
    console, writes `captures\retail-handling-<ts>\owner\RESULTS.md`.
