# TRAINER-LOGGER: the physics / memory logger in I76 Debug (modern port)

Lane trainer-logger, 2026-10-17 (resumed after the owner's pause). Lab copy only. The daily driver's
`_tools\trainer` was not touched. The game was not run by this lane after the resume: the owner held the console lock
(OWNER-TESTS) for the whole resumed session. The live numbers below come from the boots made before the pause, at
07:11-07:50.

## 1. What the owner gets

- **One click (lab twin):** `C:\Users\james\i76-uncap-lab\game-dd-20261003\Interstate 76\TEST-logged-play.bat`.
  It calls `tools\debug\PLAY-LOGGED.bat` (i76-everywhere), which does two things:
  - starts I76 Debug on the Trainer tab with the logger armed (`--log-auto --hotkeys`);
  - starts the twin's game through its own `PLAY-i76.ps1` (preset best-wide by default) with `I76_TELEMETRY=1`.

  `PLAY-LOGGED.bat` refuses any folder whose path contains `Interstate76-` or `Downloads`, so it cannot run on a
  playable install.
- **Controls:**
  - Scroll Lock = **mark**: a numbered row in `marks.csv`, and `phase` switches to `markNN`, the I76DRV rule.
  - Shift + Scroll Lock = stop / start the logger.
  - The **Log** / **Mark** buttons in the dashboard header (every tab) and the logger card on the Trainer tab do the same.
  - HTTP: `POST /api/logger {op: start|stop|toggle|mark|auto}`.
  - The hotkeys are global (RegisterHotKey), so they work while the game has the focus.
- **Per mission:** with `--log-auto`, a new `sNN` starts when the player car appears and stops 3 s after it is gone.
  A stop by hand holds until the next mission.
- **Output:** `C:\Users\james\i76-uncap-lab\captures\trainer-log\<date-time>-<preset>\sNN\`. After each stop,
  `summary.md` / `summary.json` are written by the lab's `owner_log.py summary`. Closing the dashboard waits up to 30 s
  for the last summary.

Code (i76-everywhere): `tools/debug/debug_logger.py` (commits 25b5d7e, 57885c0, b5596ab), `i76debug.py`, `static/`,
`PLAY-LOGGED.bat` (ffa507c). Tests: `tools/debug/tests/test_logger.py`, which re-ran today: 6 tests OK, 7.5 s.

## 2. Same columns, same files as I76MEM

`mem.phys.csv` holds mem2csv.py's LAB + EXTRA columns in mem2csv's order. Three columns of our own come after them:
`health_pct`, `tel_music_track`, `mark`. `mem.frames.csv` and `mem.music.csv` are also written as mem2csv writes them,
plus `marks.csv` and `meta.json`, in owner_log.py's session layout (`raw\SNN.LOG` included). Each of the requested
fields maps to these columns:

| asked for | columns | source |
|---|---|---|
| frame, sim_dt | `frame`, `sim_dt`, `dt`, `step_count`, `step_ms`, `tick` | telemetry: per frame, frame-consistent (`verify` = 1 on every row) |
| position, rotation, velocity, rates | `x y z`, `rot1 rot4 rot6 rot7 rot8`, `vx vy vz speed`, `pitch_rate yaw_rate roll_rate` | telemetry |
| steer / throttle | `steer`, `throttle`, `handbrake` | telemetry |
| flags 0x10000 / 0x200 / 0x8000 / 0x4 | `flags` (entity +0x454, as I76MEM's eflags) | telemetry |
| armour | `health`, `health_max`, `health_pct`; nearest AI `n_health` | telemetry; the reader for AI |
| rpm / gear | `rpm`, `gear` | telemetry |
| music intent | `cd_track`, `cd_playing` and `mem.music.csv`; `tel_music_track` | the reader (0x4ed800 ...); the proxy |
| game state, object flags, AI | `game_state`, `oflags`, `ai_alive ai_total n_*` | the reader, 8 Hz, read-only |

The reader's player object is checked against the telemetry's `obj_addr` on every read and logged as
`meta.json reader_check`. The check matched on every read in all 6 logged boots (400-452 reads per boot, 0
mismatches).

**Read by the analysis tools (checked today on a live log, `t01-log-cap120-c1`):**
- `owner_log.py summary` wrote a summary. It found 7321 frames, 0 missed, and Arcade Phys. (0x10000) on 0 of 7321
  frames.
- `fingerprint.py metrics` read the folder. Its context is `unknown` because t01 is not a fingerprint map.

## 3. Fixed-step alignment (PHYSICS-STEP-STUDY-DESIGN)

The port will run a fixed whole-sim step (the owner's decision). Under `I76_FIXED_STEP`, the logger handles step data
in two ways:
- It keeps `step_count` 0 on frames that ran no physics step.
- It writes `step_ms` as the stepper's own step (entity +0x448). The proxy writes `stepper[1] = g_fixed_step` there.
  The logger uses that value once the reader has seen it constant over 8 reads (about 1 s). Before that, `step_ms` is
  sim_dt / count, or 0 on a 0-step frame.

For the step-grid study (27-49 ms, 40 first), this gives a check of the step that was actually used, which can be read
back on every run, and gives mark timestamps for the owner's blind A/B notes.

**Fixed: `fingerprint.py` was mis-measuring fixed-step logs** (lab 9d3ba95). `frame_metrics` took the step as
sim_dt / count. Under a fixed stepper, sim_dt is the render frame time, not the step.
- **Test:** a synthetic trace with 40 ms steps at 60 fps.
  - Before the fix it read step_ms 25.3, 39.6 steps/s and step p50 16.7 ms.
  - After the fix it reads 40.0 ms, 25.0 steps/s and p50 40.0. 30 ms at 120 fps reads 30.0, and 40 ms at 30 fps reads 40.0.
- **Scope:** the new branch runs only on traces that contain a frame with count 0 and sim_dt > 0. The stock stepper
  never produces one (its count is always 1 or more), so emulator and stock traces are unaffected.
- **Check:** `fingerprint.py selftest` output (text and md) is byte-identical before and after the change.

## 4. Cost

**Setup (live):**
- Our exe `6319abf7` with the side proxy `cbcff703` on the lab copy `game-trnlog`, I76PLYR.DEF `509ac8f8`.
- Headless nullglide (`-glide`), I76_MISSION t01 direct boot, `I76_KEEP_ACTIVE` + `I76_HEADLESS_ACTIVE`.
- Host i7-7700K (8 logical CPUs). **4 86Box VMs were running in every boot** (other lanes, before the owner's 3-VM rule).
- 60 s hold after the first mission frame. Conditions rotated per round. Frame periods come from the proxy's
  I76_FRAME_LOG (QPC); CPU from psutil.
- The tools are lab `tools/trainer-logger/` (`trnlog_run.py`, `trnlog-campaign.ps1`, `offline_cost.py`,
  `summarise.py`). The tables are in `captures/trainer-logger-20261017/SUMMARY.md`.

**Conditions:**
- notel: telemetry off.
- tel: export on, nobody listening.
- dash: the dashboard listening, logger idle.
- log: the logger recording, with its 8 Hz reader.

**Correction to the harness:** its docstring said the car stays parked. In the logged boots it was not. The car moved at
5-13.8 m/s and covered about 600 m in 61 s, with throttle and steer swinging between about -1 and +1. The source of that
input is not identified. The other conditions have no physics log, so whether their car moved the same way is
unverified.

### 4.1 Live, I76_FPS_CAP 120 (n = 3 per condition)

| condition | fps mean (range) | frame p99 ms mean (range) | long frames > 16.7 ms, s per hold (range) | game CPU (one logical CPU = 1) | dashboard CPU |
|---|---|---|---|---|---|
| notel | 118.4 (117.8-119.1) | 18.5 (15.0-20.4) | 2.34 (1.32-2.92) | 0.245 (0.235-0.259) | - |
| tel | 119.3 (119.0-119.7) | 13.7 (10.4-16.8) | 1.12 (0.48-1.74) | 0.261 (0.251-0.271) | - |
| dash | 119.5 (118.8-119.9) | 14.4 (11.4-18.4) | 1.11 (0.48-2.21) | 0.258 (0.254-0.261) | 0.018 (0.018-0.019) |
| log | 115.6 (108.3-119.5) | 23.9 (15.0-40.5) | 5.19 (1.19-12.84) | 0.228 (0.176-0.257) | 0.035 (0.033-0.036) |

**A/A (the spread within one condition):**
- The long-frame time ranges 1.3-2.9 s in notel and 0.5-2.2 s in dash.
- No-telemetry is not better than telemetry. The noise is the host, which had 4 VMs running.

**The logger itself:**
- 87-90 µs per frame of its own time.
- 0 frames missed, on 7321 / 6768 / 7318 frames.
- Reader reads took 0.39-0.52 ms.
- Dashboard CPU goes from 0.018 to 0.035 of one logical CPU, a gain of 0.017. That is about 0.2 % of the host.

**Game side:**
- Two of the three log boots (c1, c3: 1.19 / 1.53 s of long frames, p99 15.0 / 16.1) fall inside the A/A range of the
  other conditions.
- **One boot, log-c2, is an outlier.** It had 428 long frames (12.8 s), p99 40.5 ms and 108 fps.
  - Its stalls are spread over the whole hold (per 5 s: 5, 13, 12, 24, 16, 50, 67, 24, 23, 38, 71, 75, 6), not one burst.
  - Its game CPU share was the lowest of all 12 boots (0.176).
  - Its host CPU % was not recorded.
- I cannot tell a logger effect from host contention with n = 3 under 4 VMs. **Unresolved:** the next step is n ≥ 5 per
  condition on a quiet host (section 6).

### 4.2 Live, uncapped (stress case)

- **n:** 3 per condition, except notel n = 2. Boot notel-u3 was cut off by the pause, with 4.8 s of frames, and is
  excluded.
- **A/A:** fps ranges 846-1826 within tel and 900-1680 within dash. Host CPU was 80-100 %. No condition difference is
  resolvable.
- **The logger kept up:** 50162-91589 frames logged at 819-1472 fps, 0 missed, 72-89 µs per frame. The dashboard used
  0.14-0.20 of one logical CPU.

### 4.3 Offline: the dashboard alone, with no game (n = 3 per cell, interleaved)

A real telemetry recording (overnight P2 t05) was replayed at a fixed rate. The table shows the dashboard's CPU (one
logical CPU = 1).

| rate | idle mean (range) | logging mean (range) | logger µs/frame | missed |
|---|---|---|---|---|
| 120 /s | 0.025 (0.019-0.030) | 0.033 (0.030-0.039) | 80-83 | 0 |
| 240 /s | 0.048 (0.030-0.057) | 0.053 (0.042-0.067) | 77-80 | 0 |
| 1000 /s | 0.089 (0.062-0.113) | 0.164 (0.156-0.172) | 68-69 | 0 |

- At 120 /s and 240 /s, the idle and logging ranges overlap.
- At 1000 /s, logging costs about 0.07 of one logical CPU more than idle.
- The port's planned rates are 25-37 physics steps/s and a 60-120 fps render. Both are at or below the 120 /s row.

**Cost verdict (measured):**
- On the dashboard side, the logger costs at most about 2 % of one logical CPU at 120 fps.
- It missed no frames anywhere, up to about 1470 frames/s (the fastest logged boot).
- On the game side, 2 of 3 capped boots are inside the A/A spread and 1 is an unexplained outlier. Not settled.

## 5. Observations, not explained

- **Stock clock at 120 fps, cost boots only.** In the 120 fps cap boots (stock stepper), sim time ran 64.9 s over
  61.3 s of wall time. sim_dt takes the values 1 ms (3424 frames), 15.99 (2418) and 15.02 (1454), which is consistent
  with GetTickCount's 15.6 ms granularity. This is the stock stepper above 64 fps, not the logger. It does not apply to
  the fixed-step port, but any analysis of stock high-fps logs must not take sim_dt as the frame time.
- **Car input in the harness boots:** see section 4. The source is not identified.

## 6. Not done / next

- **Blocked:** live boots after the resume. The owner held `.console-owner` (OWNER-TESTS f2-control, from 08:05).
  - The pending re-run: `trnlog-campaign.ps1 -Conds notel,tel,dash,log -Rounds 5 -Cap 60`, then the same at
    `-Cap 120`, with 0-1 VMs running, under BELOW_NORMAL priority. That is 20 boots, about 25 min, light CPU at a cap.
  - It settles log-c2 (section 4.1).
- **Not verified live on the twin's proxy.** The twin's STRLKUP is `33211f11`. It is neither the driver's `509c6df0`
  nor the `cbcff703` the cost boots used. It contains the `I76_TELEMETRY` string, but the logger has not been run
  against it. The owner test below covers this.
- **Not tried with I76_FIXED_STEP live.** The `step_ms` / `step_count 0` path has been checked only by the unit tests
  and the synthetic fingerprint test.
- **Proposal:** start I76AIM-equivalent AI / damage fields from the dashboard's reader (AI-DAMAGE-METRICS next step).
  Not done here.

## 7. Owner test

Run `TEST-logged-play.bat` on the twin at the physical console. That needs about 10 minutes:
1. Play one mission.
2. Press Scroll Lock twice at events you want to remember.
3. Quit the mission.
4. Close the dashboard window.

Expected:
- a new folder under `captures\trainer-log\` with `s01\`;
- `marks.csv` with 2 rows;
- `summary.md` naming the mission, 0 missed frames, and Arcade Phys. off;
- no visible stutter compared with `PLAY-i76.bat`. Your feel is the measurement here.
