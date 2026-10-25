# Skip the mission cutscenes in test boots; FFB off in test boots (2026-10-25)

Owner, watching the desktop: "you're missing a chance to skip the intro movie on your test runs on the desktop and losing time /
iteration speed", then: "on automated tests on the desktop, shut off FFB unless testing it on purpose - it affects the control inputs
and wears the equipment". Two proxy keys (both off by default, player options too) and the lab harness defaults.

## 1. What changed

| piece | commit | what |
|---|---|---|
| proxy `I76_SKIP_CUTSCENES=1` | 9bf575c, corrected fe24821 | each mission's WRLD intro movie (`intNNf01.smk`, 0x5dd300) and closing movie (0x5dd310) is opened and **ended at once through the engine's own movie end 0x49a9f0** (what Esc on the movie calls); `=2` also the movies a script queues mid-mission. Gold only (Nitro: refused, logged). Independent of `I76_MISSION`: menus and campaign too |
| proxy `I76_FFB_OFF=1` | f24df9f | the loader's `test esi,esi; jne` at 0x446058 becomes `jmp 0x4460ba`, the engine's own "Error loading i7_SFRCE.dll" path: I7_SFRCE.DLL is never loaded, DirectInput never opens the wheel, no effect exists. The wheel's axes are untouched (winmm / input.map). Logs `ffb: OFF (I76_FFB_OFF)`. Gold only |
| launcher | 9bf575c, f24df9f | `PLAY-i76.ps1 -SkipCutscenes`, `-FfbOff` (also when `I76_FFB_OFF=1` is inherited: the custom interposer stays off too); `PLAY.bat --skip-cutscenes`, `--ffb-off` (lab `builds\rc-20261024\launchers-20261024\make-launchers.ps1`; the RC stage is not regenerated, the rc lane owns it) |
| lab harness | lab b8c1a72, fe4ba9c, 65c4c5e, 54848f0, 70d238b (+ the deck lane's 702690d swallowed two staged hunks of run-gate / t05-route-fps) | below |

**The first version (9bf575c) was wrong.** It made the movie's open fail (`call 0x49a070` -> `xor eax,eax`), the path every mission
without a movie takes. The kit lane then reported T05 starting "upside down" with the key (CLEAN-INSTALL-2026-10-25.md). That report
turned out not to be the key (section 3), but the reading of 0x49a9f0 it prompted found a real gap: the movie's end does more than
close Smacker - it sets the play mode (0x49cdd0(1)), restores the display through the renderer table ([0x5dd2e4] / [0x5dd2e0] /
[0x5dd2cc] with the saved mode [0x5a7d6c] / [0x5dd2c8] with 0x5dcfa8), resumes the sounds (0x426050 0x2b11 x2), the music 0x4234e0
and the forces 0x445b40, and flushes the input. The open had paused those. fe24821 therefore keeps the open and ends the movie at
once: the state afterwards is the state after a player presses Esc on the first frame. The proxy log says per movie:
`skip-cutscenes: 'int05f01.smk' opened and ended at once (0x49a9f0)`.

## 2. Harness defaults (lab)

- `autotest\proxy-run.ps1`: with `-Mission`, `I76_SKIP_CUTSCENES=1`; `I76_FFB_OFF=1` and `I76_JOY_SYNTH=0:32767` (joystick1 - the only
  id input.map binds - reads as a centred synthetic pad, so a wheel resting off centre with no FFB spring cannot steer a run; every
  scripted drive uses keys or the input block). Opt-outs: `-FfbTest` (real wheel, game FFB on), `-Env @{ I76_SKIP_CUTSCENES = '0' }`,
  `-KeepOpening`. The old Esc spam from 8 s is off when the movie is skipped (a slow boot would open the options menu); instead one
  skip key (Esc, the FSM's isKeypress) is sent when a trip mission's scripted opening latch (0x5244c0) is seen. `-NoEsc` (measurement).
- `builds\rc-20261024\run-gate.ps1`: both keys in the environment and LAB_GAME_ENV; a group with row 8 (the FFB check) keeps FFB on;
  group P's T05 launcher boot waits 20 s instead of 50.
- `autotest\t05-route-fps.ps1`, `TEST-FRAMERATE.ps1`, `tools\content-trial\arena-trial.ps1`, laptop `raw-boot` / `mc-job` /
  `bench-run`: both keys. `tools\replay\with-lock.ps1`: FFB off (`-FfbTest`). Not changed on purpose: the music / sound runners and the
  replay runners (a replay recorded with the movie must keep it), the FFB-panel probes (they test FFB).
- `CONSOLE-LOCK.md`: "Test boots: FFB off, cutscenes skipped".

## 3. Results

Proxy fe24821 (c988c6d9) unless noted; installed build dba46ea2 smoke-tested the same (section 4).

**Time to the end of the opening** (from the launch; "opening over" = state 5, no movie / pause bits, opening latch 0 and camera 0
for 1 s, rcd_drive.py's definition):

| harness | mission | before | after | saved |
|---|---|---|---|---|
| proxy-run.ps1 (desktop test-gold; before = the old Esc spam from 8 s) | T05 | 11.0 / 10.8 / 10.9 s | 8.7 / 8.7 / 8.7 s | **2.1-2.3 s per boot** |
| | T01 | 10.8 / 10.8 / 10.9 s | 8.9 / 8.8 / 8.7 s, 6.7 / 6.7 s | 2-4 s |
| | T03 | 10.8 s | 8.8 s | 2.0 s (n 1) |
| no key sent at all (laptop; what a launcher-booted harness waits through: t05-route-fps / rcd_drive, gate rows, run-gate group P) | T05 | 60.0 s (movie to 51.5 s, then the scripted opening) | 11.3 / 11.4 / 11.5 s | **~49 s per T05 boot** |
| | T01 | not over within 150 s (n 2) | 2.8 s (skip key on the opening) | > 2 min |
| | T17 (no movie) | 15.2 s | 15.4 s | 0 (control) |

The proxy-run gain is small because its Esc spam already cut the movie at ~8 s; the large gain is on every runner that boots
through the launcher and waits. Both "before" laptop rows that never ended had the movie stalled: the movie loop advances only
while the game is the active app (0x40374b tests 0x504c1c) and a Windows Firewall prompt from another lane's network run sat in
front of the game all day on the laptop.

**Same start with and without the skip** (desktop, 1 s after the opening, eye transform 0x5FCDC4 + camera 0x4c2728 + screenshot):
T05 pitch 13.8-14.4 / roll 0.0 / yaw 90.0 at (8505-8510, 29, 44520) skipped and not skipped (n 2 + 2, + 3 more skipped); T01 pitch
13.2-14.2 / roll -0.2..0.3 / yaw 15.0 at (3641-3647, 4, 36424-36446) (n 2 + 2); T03 roll 0.5 / 0.6, yaw -130 (n 1 + 1). Camera 0 in
all. The start pictures (`tools\skip-cutscenes\run-20261025-113534\0N-start.png`) are the normal cockpit in both.

**The "upside-down" T05 start is not the skip.** On the laptop every start picture shows the dash panel huge across the top and sky
below it, with the eye transform reading roll 0.0 / pitch 13 - also when the movie played to its end (T05, 60 s) and in T17, which
has no movie at all. The kit lane's `t05-early` pictures are the same picture. It is the top-left quarter of the 2x supersampled frame
(3840x2160 shown on 1920x1080): the dash scaled 2x, the upper half's sky beneath it. Not a pose: the car and camera are upright. It
is the laptop's present path (every one of those pictures has the Firewall prompt in front of the game); the same likely explains
Nitro P01 by direct boot (kit lane, 9 boots, no key). Handed back to the kit / render lanes with the evidence:
`i76-uncap-lab\captures\laptop-bench\scs-a\` (12 rows, PNGs).

**FFB off, desktop test-gold with the T300 plugged in, T05 driven 12 s with steer taps, `I76_FFB_TRACE=1`:**

| run | ffb-trace CreateEffect | Start | SendForceFeedbackCommand | proxy |
|---|---|---|---|---|
| `I76_FFB_OFF=1` (n 2, + 1 on dba46ea2) | 0 | 0 | 0 | `ffb: OFF (I76_FFB_OFF): I7_SFRCE.DLL load skipped ..., read back ok` |
| control, FFB on (`-FfbTest`, n 1, + 1 on dba46ea2) | 1 | 33 / 35 | 1 | effects as before |

0 CRASH in every boot of the batch (test-gold mciproxy.log).

**Closing movie / end flow:** forcing the mission state by memory (0x4c2164 = 1 success, 2 abort) from a direct boot opened the
mission-over menu (mode 0x10) and the game stayed up, identically with and without the key (T01, n 1 each). That route does not reach
the closing movie (`out01f01.smk` needs a real win), so the outro site is verified only statically: it calls the same function as the
intro and takes the engine's own no-movie branch afterwards. Open item for a played win.

**M03 cannot be booted directly** (melee arenas crash at frame 0 with any proxy: MUSIC-TRACK-MAP.md, `call [0x4c2720]` = 0 at
0x403868); T03 replaced it. M missions have no WRLD movies anyway.

## 4. Installed (not main Gold)

`dba46ea2` = i76-everywhere fe7468c (main, built twice byte-identical) + main's `PLAY-i76.ps1` (3adc51b5), with
`tools\skip-cutscenes\install-scs.ps1` (every replaced file kept as `<name>.<md5-8>-pre-scs`, md5 read back):

- `test-gold`: STRLKUP.DLL d738caac -> dba46ea2, PLAY-i76.ps1 07244591 -> 3adc51b5, PLAY.bat fe6462c5 -> b5461dcf, PLAY-T05.bat
  15cf8ae7 -> b7bfb8c5 (regenerated with `--skip-cutscenes` / `--ffb-off`), VERSION.md note (the two player options).
- `dev-gold`: STRLKUP.DLL 5dca9d79 -> dba46ea2, PLAY-i76.ps1 07244591 -> 3adc51b5, VERSION.md note.
- Smoke on test-gold after the install (desktop): T05 / T01 skipped, T05 not skipped, FFB off and on - the same rows as above, 0 CRASH.

Main Gold takes it with the next gated install (the RC stage needs `make-launchers.ps1` re-run for the two .bat options).

## 5. For players (VERSION.md)

- `PLAY.bat --skip-cutscenes`: skip each mission's briefing and closing movie. Movies a mission plays in the middle stay.
- `PLAY.bat --ffb-off` (or `I76_FFB_OFF=1`): the game's own force feedback off without unplugging the wheel.
