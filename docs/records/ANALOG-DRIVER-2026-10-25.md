# Analog drive mode for the test harness (2026-10-25)

Issue #89. Owner: "Could the automated test driving algorithm use analog / smoother inputs so it doesn't look so jerky?"
(the hill-route captures in the launch video show stepped steering).

**Verdict.** Delivered: a harness-only proxy switch `I76_DRIVE_INJECT` (joystick1 becomes a synthetic pad that a test harness
writes at 100 Hz), the route driver's `--input pad` mode (same route, same road follower, same 22 m/s target), the analog
default in `record-shot.ps1`, and an opt-in for the T05 gate (`LAB_T05_INPUT=pad`). On the laptop bench the analog car's
steering is about **4x smoother** (applied-steer steps per second 1.5 vs 4.9-6.9, yaw-rate jerk RMS 1.6-1.9 vs 5.6-6.3
rad/s^2) and the **hill-leg frame rate is the same** within run noise (pad - keys -0.4 fps on a 48 fps median, n 3 vs 4;
clip runs 47.8 vs 47.8). The **mph curve is NOT within noise**: the pad car runs the leg 4-8 % slower (124.5-132.0 s vs
119.7-124.0 s; about 2.5 mph lower outside the road-closed bar, 16 mph lower in the bar's 250 m bin), so a pad row is not
comparable with a keys row; the gate stays on keys and the pad stays opt-in until the rows are re-baselined with it (issue
follow-up in s.7). The laptop clip pair exists but a Windows Firewall prompt sits over the middle of both clips (s.5, s.7).

## 1. How input reaches the game (survey)

- The gate's driver (lab `tools\rc-draw\rcd_drive.py`, laptop copy `rcd_drive_bench.py`) follows the T05 road with a
  look-ahead point and sends **scan-code key events** to the foreground game: W below 22 m/s, S above 26 m/s, and A / D as a
  **duty cycle over 200 ms slots** (duty from the heading error). `record-shot.ps1` (launch video) holds W for the drive and
  A / D for the shot's steer windows. A lab-only drive block (`Local\I76RhDrive`, lab builds only) writes held-key bytes.
- `input.map` binds `steer` = `joystick1 Left/Right` (X) and `throttle` = `joystick1 Down/Up` (Y); the engine reads the pad
  through winmm `joyGetPosEx`, which the proxy already hooks (`I76_JOY_MAP`, `I76_JOY_SYNTH`; proxy-run sets
  `I76_JOY_SYNTH=0:32767` so a resting wheel cannot steer a test).
- ViGEm (Nefarius bus) is installed on both the PC and the laptop, and vJoy on the PC (device in error). Not used: a virtual
  XInput pad needs a client process, appears to every program on the machine (the owner's game included), and reaches the
  1997 engine only through winmm's XInput mapping (triggers on one shared axis). The proxy hook is per process, needs no
  driver and works on every bench.

## 2. Calibration (laptop, run `an-cal1`, one boot, the hill-road start)

Read back from the entity (applied steer +0xE0, applied throttle +0xE4) and the input ints (0x5367D4 / 0x5367CC):

| input | applied |
|---|---|
| pad X 0 / 16383 / 24575 / 29490 / 32767 / ... / 65535 | +1.0 / +0.25 / +0.0625 / +0.01 / 0 / ... / -1.0: **the engine squares the axis** (sign kept); X 0 = full left (as A) |
| pad Y 0 / 16383 / 24575 / 32767 / 49151 / 65535 | throttle +1.0 / +0.25 / +0.0625 / 0 / -0.25 / -1.0 (Y 0 = full throttle, 65535 = full brake) |
| key A / D held | **sqrt(k / 72) after k sim ticks** (0.1179, 0.1667, 0.2041, ... 41.667 ms ticks; full lock after 3 s), 0 one tick after the release |
| key W | 0.39, 0.78, 1.0 over 3 ticks |

So the keyboard driver's steering is a saw-tooth: each 200 ms slot ramps from 0 to at most ~0.26 and drops to 0. That
is the stepping in the video. The pad write landed every time (proxy read-back of x / y matches the harness; `drive-inject:
harness values live` in the log).

## 3. Design

**Proxy (`music-fix/strlkproxy.c`, joystick routing):** `I76_DRIVE_INJECT=1` (or `=<winmm id>`; default id 0 = joystick1)
makes that id a synthetic 2-axis pad (as `I76_JOY_SYNTH`) whose X / Y / buttons come from the file mapping
`Local\I76DriveInject<I76_SHM_SUFFIX>` (64 bytes: magic `DRVI`, x, y, buttons, seq, the harness's GetTickCount heartbeat;
the proxy writes back polls, x / y read, seq read, stale). A block that is unset or whose heartbeat is older than 500 ms
reads as the **centred pad** (no steer, no throttle: a dead harness leaves the car coasting). Off by default, never in a
launcher preset. Built as lab `builds\analog-driver-20261025` (HEAD 6d7ca85 + this change, STRLKUP md5 ab07561d); the
committed `music-fix/Strlkup.dll` is not rebuilt in this commit (other lanes had uncommitted proxy work in the tree).

**Harness (lab `tools\rc-draw\pad_inject.py`):** `Pad` (the block writer, sign: steer -1 = left, throttle +1 = full),
`Smooth` (critically damped ease with a rate cap), and a CLI for `record-shot.ps1`: centred for `Still` s, then the throttle
eased in over 0.3 s, and each A / D steer window a pulse with 0.35 s raised-cosine edges whose plateau applies what the held
key applied **on average** (key held d s: (2/3) sqrt(d / 3)); glance keys stay keys.

**Route driver (`--input pad`), versions on the laptop:**

| version | steer | throttle | result (hill leg; keys: 119.8-124.1 s) |
|---|---|---|---|
| v1 | the key duty as a deflection, eased (omega 9, 2.5 / s) | W / S as +1 / -1, ramped 2 / 4 per s | 138 s, one off-road; lagging |
| v2 | x 1.3 gain, faster ease | ramp 8 / s | wedged on the road-closed bar 105 s |
| v3 | **the keys' own applied steer** (modelled per tick as in s.2) averaged over the last 200 ms (one slot: the ripple cancels, the mean stays) -> deflection sqrt | same treatment for W / S | 128-132 s, 6 % slow: the engine's response to the averaged W / S chatter is not linear |
| v4 | v3 | the keys' modelled throttle, not averaged | 129-158 s: 2 of 3 wedged on the bar (36 / 30 s) |
| v5 | v3 | v4 + the keys driver's stall kick + **unstick**: no progress (< 4 m in 2 s) -> 1 s reverse, 1.2 s forward at 0.8 lock | 124.5-131 s, 1 unstick per run |
| v6 (dropped) | v3 | PI hold of the engine speed (+0xAC) at 22.8 m/s (the keys' measured mean cruise) | 2 runs, both void: x2 the engine never applied the pad (input int 0 for the whole run although the proxy served live values: unexplained), x4 the unstick drove it 37 m off the road. **Committed driver = v5** |

Why the bar matters: the T05 hill road has a road-closed bar at about (8394, 44019). The keys' weave meets it turning (yaw
rate 0.17-0.40 rad/s at the bar) and glances through (0-2 s slow); the smooth car meets it square-on (0.04-0.13 rad/s) and can
stay wedged at full throttle while its speed bounces 0-5 m/s (5 of 9 v2-v4 runs, 10-159 s). v5's unstick is the only
behaviour the keys driver does not have; it fires only in that state and is counted in the drive log
(`pad unstick episodes: ridge n, hill n`).

Open-loop check (`an-c2`, `--mode cal2`): from rest, 4 s full throttle by key W 1.6 -> 23.3 m/s, by the pad 0.2 -> 24.5 m/s
(alike); 4 s of 100 ms on / 100 ms off: key W 0.6 -> 8.3 m/s, pad 0.0 -> 15.9 m/s. The keyboard path does not respond to a
chattering W as its applied value suggests, which is why v3 / v4 could not copy the keys' speed and v6 holds the speed instead.

## 4. Results (laptop LAPTOP bench, launch-video twin copy, OWNER-2300-ALL, 1920x1080 window, dgVoodoo.lv1080.conf)

Every boot: `I76_SKIP_MOVIES=1`, `I76_SKIP_CUTSCENES=0` (T05's skip path leaves the start inverted), the player's route
through the briefing (Esc on the movie after 1 s, Esc once on the scripted opening; eye roll at the hill start 0.0-0.8 deg in
every run), `I76_FFB_OFF=1`, muted, own shm suffix, I76_START_POS on the hill road; the hill leg is the gate's row 9 leg
(2.6 km). Medians from `rcd_tab.py` (frame log), smoothness from the 50 Hz control log (`an_cmp.py`).

Valid hill legs only (the leg finished, no wedge longer than 5 s). Sets: "IPX" = the twin as copied (IPXWrapper present),
"no IPX" = from run w1 on. Clip runs also ran ffmpeg.

| run | input (version) | set | hill leg s | median fps | 1 % low | mean mph | steer steps/s | yaw jerk rms |
|---|---|---|---|---|---|---|---|---|
| r1 | keys | IPX | 119.8 | 49.0 | 14.1 | 51.5 | 6.56 | 6.11 |
| r3 | keys | IPX | 124.0 | 48.5 | 14.2 | 50.1 | 6.90 | 6.31 |
| s2 | keys | IPX | 123.0 | 48.6 | 14.1 | 49.9 | 4.90 | 5.59 |
| u2 | keys | IPX | 119.7 | 48.2 | 14.2 | 50.9 | 6.93 | 6.31 |
| x1 | keys | no IPX | 120.2 | 46.5 | 12.5 | 52.3 | 5.97 | 5.60 |
| x3 | keys | no IPX | 119.9 | 46.2 | 12.9 | 51.9 | 6.11 | 5.79 |
| r5 clip | keys | IPX | 119.7 | 48.4 | 13.3 | 51.7 | 6.05 | 5.69 |
| w5 clip | keys | no IPX | 120.3 | 47.8 | 13.2 | 51.4 | 6.56 | 6.31 |
| s1 | pad v3 | IPX | 128.2 | 48.5 | 14.1 | 47.6 | 1.47 | 1.86 |
| s3 | pad v3 | IPX | 132.0 | 48.3 | 14.4 | 45.6 | 1.56 | 1.75 |
| v3 | pad v5 | IPX | 124.5 | 47.9 | 13.9 | 48.8 | 1.70 | 1.66 |
| w4 | pad v5 (1 unstick) | no IPX | 130.6 | 47.8 | 13.7 | 47.2 | 1.55 | 1.66 |
| s4 clip | pad v3 | IPX | 128.5 | 48.0 | 13.3 | 47.2 | 1.67 | 1.63 |
| u4 clip | pad v4 | IPX | 129.0 | 48.0 | 13.4 | 47.9 | 1.46 | 1.84 |
| w6 clip | pad v5 (1 unstick) | no IPX | 129.3 | 47.8 | 13.4 | 47.8 | 1.49 | 1.88 |

- **fps:** IPX set, non-clip: keys 48.2-49.0 (mean 48.6, n 4), pad 47.9-48.5 (mean 48.2, n 3): -0.4 fps, inside the keys'
  own 0.8 fps spread. Clip runs: keys 48.4 / 47.8, pad 48.0 / 48.0 / 47.8. The no-IPX keys pair (46.2 / 46.5) ran while
  other lanes were active on the same laptop; w4 (pad, same set) 47.8. 1 % lows alike (13.3-14.4).
- **mph per 250 m (mean of the runs above):** keys 45.5 51.7 52.8 48.9 52.0 51.7 55.9 53.9 51.2 50.9 51.0; pad 43.8 49.0
  50.0 32.6 49.2 49.4 53.6 55.5 51.2 50.3 49.4. Bin 3 holds the road-closed bar. Outside it the pad runs 0-2.8 mph lower
  (keys run-to-run spread there up to ~3 mph): not within noise.
- **Smoothness:** applied-steer steps (> 0.05 between 20 ms samples) 1.5-1.7 / s vs 4.9-6.9 / s; steer total variation
  0.37-0.42 vs 1.47-1.97 per s; yaw-rate jerk RMS 1.6-1.9 vs 5.6-6.3 rad/s^2. Lateral tracking alike: mean distance from
  the road 3.6-3.9 m (pad) vs 3.5-3.8 m (keys); the pad's maxima are larger (11-16 vs 9-12 m, the bar).
- Void runs (not in the table): keys v2 / w1 / w3 (game lost the foreground, key-downs blocked); pad r4 (v1 off-road),
  r6 / u1 / u3 / v1 / v4 / w2 (wedged on the bar 30-160 s, before the progress-based unstick), x2 / x4 (v6), x5 (the job
  stopped 5 s after the lock: no driver output; not investigated).

## 5. Clip pair for the video lane

`<lab>\captures\launch-video\raw\drive-analog\`: `hill-keys.mp4` (keys) and `hill-analog.mp4` (pad), 20 s each from the
start of the hill leg, 1920x1080 window at 60 fps capture (the game renders ~48 fps on the laptop), with each run's control
log (`*.ctl.csv`: applied steer / throttle, yaw rate, speed, 50 Hz) and `hill-keys-vs-analog-sbs.mp4` (two 960x540 halves,
labelled). Both are v5-era runs w5 / w6 (no-IPX set). **A Windows Firewall "allow i76 on public and private
networks" prompt is over the middle of both clips** (s.7); the clips show the steering difference, but they are not
usable as video footage until a run without the prompt is recorded.

## 6. Where it is the default and where it is not

- **Video:** `record-shot.ps1 -Drive analog` is the default (`-Drive keys` = the old holds). It checks the twin's
  STRLKUP.DLL for the `I76_DRIVE_INJECT` string and **falls back to keys** with a warning when the proxy is older: the
  launch-video twin (test-gold, proxy 5d6f9828) has no such proxy yet, so its shots stay keyboard until a proxy with this
  source is installed through dev-gold (the video lane coordinates that; never under a running capture). The launch-video
  lane renamed the script's `$drive` block to `$driveBlock` (PowerShell names are case-insensitive: the new `-Drive`
  parameter broke every boot from ~11:34 until that rename).
- **Default pad driver = v5** (lab `rcd_drive.py` / `rcd_drive_bench.py --input pad`).
- **Gates:** keyboard by default. `LAB_T05_INPUT=pad` (lab `autotest\t05-route-fps.ps1`) drives row 9 through the pad.
  Opt-in until the row-9 baselines are re-measured with it: the pad's leg timing differs (s.4), so a pad row is not
  comparable with a keys row.
- Laptop bench: `analog-job.ps1 -Drive keys|pad -Mode route|cal|cal2 [-Clip s]`, `analog-batch.ps1 -Steps ...`.

## 7. Notes

- The laptop bench is shared; keys runs need the game in the foreground (the bench driver blocks key-downs otherwise):
  w1 / w3 lost the foreground at the hill start and are void (103 m driven). Pad runs do not need the foreground.
- A Windows Firewall "allow this app" prompt (i76.exe in a new folder) sat over the game in the laptop runs; nobody
  answered it (no firewall rule was added). IPXWrapper was disabled in the laptop twin copy from run w1 on
  (`*.analog-off`) without removing the prompt, so the listener is elsewhere (the proxy opens no listening socket; the
  telemetry socket only sends and was off). Two ways out, both the owner's call: allow / block the bench folder's i76.exe
  once (patch-kit `FIREWALL.bat` style rule, or answer the prompt), or find the listener and switch it off for harness boots.
- The laptop bench was shared with 3-4 other lanes this afternoon; one of my runs waited 38 min for the lock.
- **Incident:** when stopping this lane's own laptop processes I matched command lines on `-GamePid` as well as this lane's
  script names. The terrain-pass-opt / terrain-static lanes had copied this lane's `lv-keeper.ps1` (also `-GamePid`) and a
  walign game was running, so one of the three stopped processes (pids 9064, 1184, 13468) may have been another lane's
  window keeper. Reported to the coordinator.
- Follow-ups (issue #124): pad mph parity with the keys (or re-baseline row 9 on the pad), the firewall prompt on the laptop
  twins, a clean clip pair, the proxy install through dev-gold for the video twin.
- Files: proxy `music-fix/strlkproxy.c` (I76_DRIVE_INJECT); `tools/launch-video/record-shot.ps1`; lab
  `tools\rc-draw\pad_inject.py`, `an_cmp.py`, `rcd_drive.py` (`--input pad`), `autotest\t05-route-fps.ps1`
  (`LAB_T05_INPUT`), `laptop-bench\bench\analog-job.ps1`, `analog-batch.ps1`, `tools\rc-draw\rcd_drive_bench.py`
  (`--input pad`, `--mode cal|cal2`); runs `<lab>\captures\analog-driver-20261025\`.
