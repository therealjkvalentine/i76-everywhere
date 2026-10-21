# Graphics rebaseline for promotion 19 (2026-10-21, rebaseline lane)

Owner, 2026-10-21: "what are the defaults for all the graphics stuff like the draw distances and splits and stuff like that and how far
have we drifted? seems like maybe we could have gotten confused about what does what and have some changes that don't help? maybe we need
to rebaseline?" and "guide me through what you need from me now to finish the gold graphics settings and tuning".

The answer is a ladder. It starts from stock graphics and adds one change per rung, on the promotion-19 candidate's tick (41.667 ms) with
every non-graphics fix on. Each rung is measured and driven by the owner, who keeps or drops it. What he keeps becomes the final preset,
with the reason written next to every line.

**Status:** the ladder is built and dry-run. The measurements are queued behind the candidate's console gate (they start when
`i76-uncap-lab\.gate-done` exists). The owner's verdicts are open, and so are the final values.

## 1. Stock vs promotion 18 vs candidate vs final

| switch | what it does | stock | P18 PLAY.bat (best-wide) | P18 PLAY-balanced | RC as gated 2026-10-20 (tick19g) | candidate (exp-p19, tick19-42) | final |
|---|---|---|---|---|---|---|---|
| `I76_FAR_CLIP` | draw distance (the missions set 600) | 600 m | 1800 | 1200 | 1200 | 1800 | open |
| `I76_ROAD_DIST` | roads drawn | 450 m | 1800 | 1200 | 1200 | 1800 | open |
| `I76_CLUTTER_DIST` / `_FADE` | bushes | 120 m / - | 1800 / 300 | 1200 / 300 | 1200 / 300 | 1800 / 300 | open |
| `I76_TERRAIN_LOD` | sets A and B together (default for both) | x1 | 24 | 24 | 24 | 24 | open |
| `I76_TERRAIN_LOD_A` | terrain split distance (x) | x1 | (24) | (24) | **96** | (24) | open |
| `I76_TERRAIN_LOD_B` | terrain height-error threshold (/) | /1 | (/24) | (/24) | (/24) | **/4** | open |
| `I76_TERRAIN_HYST` | split / merge hysteresis | off | off | off | off | 20 % | open |
| `I76_TERRAIN_FREEZE` | far terrain keeps its first shape | off | off | off | off | 300,40 | open |
| `I76_TERRAIN_TEX` | terrain texture distance | x1 (256 px tile to 50 m) | 8 | 8 | 8 | 8 | open |
| `I76_OBJECT_LOD` | detailed object meshes kept farther | x1 | 8 | 8 | 8 | 8 | open |
| `I76_SHADOW_DIST` | shadows | x1 (50 m) | 4 | 4 | 4 | 4 | open |
| `I76_ROAD_TEX` | sharper road texture | x1 (60 m) | 8 | 8 | 8 | 8 | open |
| `I76_MIRROR_FAR` | rear mirror far clip | 100 m | 300 | 300 | 300 | 300 | open |

(Values in brackets come from `I76_TERRAIN_LOD`; the proxy uses LOD for A and B unless `_A` / `_B` is set.)

Where each value came from (the daily driver's PROMOTIONS.md):
- Promotion 2 (2026-10-03) made best-wide PLAY.bat with the detail set: far clip 1800, terrain x8, texture x8, objects x8, shadows x4, road
  texture x8, mirror 300. The texture, object, shadow, road-texture and mirror values have never been judged by eye (backlog G-04). COST.md
  (2026-10-05, t04) found no measurable cost for any of them in the cockpit.
- Promotion 13 added best-wide-balanced = far 1200.
- Promotion 16 set roads to 1800 / 1200 (owner-verified 2026-10-12).
- Promotion 17 set the bushes to the road distance (dense, fade 300) and terrain 8 -> 24.
- The release candidate's tick presets were generated from *balanced*, which is why its far clip is 1200 (RC-DRAW-FPS s.1). The LOD_A 96
  came from the lod-sweep lane.

**Drift found while building the ladder.** The candidate's terrain is **A x24 / B /4**, not "x24":
- `I76_TERRAIN_LOD 24` stays in the preset, and its comment still describes x24.
- `I76_TERRAIN_LOD_B 4` then overrides the height-error half of it.

So the candidate splits terrain as far out as promotion 18 does, but with a height-error threshold 6x larger. The brief's rung 4 adds
"threshold / 4 (LOD_B 4)" on top of the stock split distance (A x1). The ladder's R11 is therefore the candidate minus the split distance
x24. **R12 - R11 = `I76_TERRAIN_LOD 24` (split distance x24) and nothing else**: the env of every preset was diffed key by key (s.2). The
sanity rung became a measurement of the one switch the ladder does not otherwise isolate.

## 2. The ladder (lab copy `i76-uncap-lab\exp-rebase`)

`exp-rebase` is a copy of `exp-p19` (the candidate as applied; 94 / 94 files of its MD5SUMS verified after the copy). Proxy: the
candidate's 8f8da929. Base preset: the candidate's `tick19-42.psd1` (f7e589ef) with the 13 graphics keys removed (= stock). Every rung
otherwise runs the candidate's tick 41.667 and keeps every non-graphics fix on, including:
- cam-ground and hull fixes
- ZGLIDE TMU fix, Glide refresh 120, Hor+ 3440x1440
- cursor map
- breakable box, sign sound, fade
- LAN switches

Written by `i76-uncap-lab\tools\rebaseline\rungs.py`. Each `PLAY-Rnn.bat` opens a console window titled "I'76 ladder Rnn - <what it
adds>". The window stays open while the game runs and closes when it exits. Each `presets\rebase-rNN.psd1` carries the reason in a comment
on every graphics line.

| rung | launcher | adds (cumulative unless stated) | env diff to the rung before (checked) |
|---|---|---|---|
| R00 | PLAY-R00.bat | stock graphics: far clip 600, roads 450, bushes 120, terrain x1 / threshold /1, no hysteresis / freeze, textures / objects / shadows / road textures x1, mirror 100 | candidate minus 13 keys |
| R01 | PLAY-R01.bat | + far clip 1800 | FAR_CLIP 1800 |
| R02 | PLAY-R02.bat | + roads 1800 | ROAD_DIST 1800 |
| R03 | PLAY-R03.bat | + bushes 1800, fade 300 | CLUTTER_DIST 1800, CLUTTER_FADE 300 |
| R04 | PLAY-R04.bat | + terrain height-error threshold /4 | TERRAIN_LOD_B 4 |
| R05 | PLAY-R05.bat | + hysteresis 20 | TERRAIN_HYST 20 |
| R06 | PLAY-R06.bat | + freeze 300,40 | TERRAIN_FREEZE 300,40 |
| R07 | PLAY-R07.bat | R03 + the old x24 split (promotion 18's terrain) INSTEAD of R04-R06 | (vs R03) TERRAIN_LOD 24 |
| R08 | PLAY-R08.bat | R06 + terrain texture distance x8 | TERRAIN_TEX 8 |
| R09 | PLAY-R09.bat | + object detail x8 | OBJECT_LOD 8 |
| R10 | PLAY-R10.bat | + shadows x4, road texture x8 | SHADOW_DIST 4, ROAD_TEX 8 |
| R11 | PLAY-R11.bat | + mirror 300 | MIRROR_FAR 300 |
| R12 | PLAY-R12.bat | the candidate's own tick19-42, as is | (vs R11) TERRAIN_LOD 24, the split distance x24 (s.1) |

`PLAY-i76.ps1 -DryRun` exits 0 for all 13 presets.

## 3. How each rung is measured (`i76-uncap-lab\tools\rebaseline\rb-queue.ps1`, results under `captures\rebase-20261021\`)

Nothing boots before `.gate-done`. Every step does the following:
- It takes `.console-owner` and `.fps-lock` (exclusive create) and releases both after the step.
- It waits until no other game runs.
- A watchdog voids the step if another i76 / nitro runs beside it. If a game outside the lab starts, the watchdog stops the lane's own
  game at once, because route keys go to the foreground window.
- The step is void if an rdp-tcp session is Active before or after it. Up to 3 tries.
- Each boot sets `I76_MUTE=1`, starts a per-pid mute watcher and sets `I76_SHM_SUFFIX=exp-rebase`. The persisted mutes of
  `exp-rebase\Interstate 76\i76.exe` are cleared at the end.

The measurements:
- **fps, n 3, console:** `autotest\t05-route-fps.ps1` (gate row 9) through `PLAY-Rnn.bat`, with the folder's own 8f8da929. Rounds: R00 -> R12,
  then R12 -> R00, then R00 -> R12, so time drift falls on every rung. Columns: the hill leg's median, mean, 1 % low and lowest 1 s, the
  terrain vertex peak, and the ridge leg.
- **trip row, n 1, console:** `gate-folder.ps1 -Only 3 -TripRuns 1` through `PLAY-Rnn.bat`.
- **hill-top view, n 1, console:** `rb-hill.ps1`, which uses the same pose every rung: I76_START_POS 7972, 101.8, 44035, yaw -90, the car held
  by the trainer freeze, cockpit. It takes one 3440x1440 desktop capture 4 s after the hold and records the vertices and the far clip read back.
  The barn is 1747 m away.
- **churn census, n 3, headless (private desktop):** `rb-census.ps1`, the rc-draw lane's census on its lab twin `Strlkup-rcd2-lab` a944eb21.
  The twin is tick19g plus the same terrain switches, a drive block and the census. Its graphics code is identical to 8f8da929's: `git diff
  64d9361 5a7f83b -- music-fix` changes no far-clip / clutter / detail / terrain path except dc008e2 + 74fb9f4, which the twin carries. So
  the twin's churn numbers apply to the candidate, but its frame rate is not used.

## 4. The owner's drive

Drive each launcher on T05 (the canyon road, then over the hill top toward the barn), about 2 minutes each, at the physical console.
Mark **keep / drop / unsure** with a note. Judge each rung against the one before it (R07 against R06, R08 against R06, R12 against R11).
The measured columns are filled from s.3 when the queue has run.

| rung | launcher | what it adds | hill median / 1 % low fps | splits+merges /s | change px/s near / mid / far | barn from the hill top | verdict (keep / drop / unsure) | note |
|---|---|---|---|---|---|---|---|---|
| R00 | PLAY-R00.bat | stock graphics | (queued) | | | | | |
| R01 | PLAY-R01.bat | + far clip 1800 | | | | | | |
| R02 | PLAY-R02.bat | + roads 1800 | | | | | | |
| R03 | PLAY-R03.bat | + bushes 1800 (fade 300) | | | | | | |
| R04 | PLAY-R04.bat | + terrain threshold /4 | | | | | | |
| R05 | PLAY-R05.bat | + hysteresis 20 | | | | | | |
| R06 | PLAY-R06.bat | + freeze 300,40 | | | | | | |
| R07 | PLAY-R07.bat | R03 + old x24 terrain (instead of R04-R06) | | | | | | |
| R08 | PLAY-R08.bat | R06 + terrain textures x8 | | | | | | |
| R09 | PLAY-R09.bat | + object detail x8 | | | | | | |
| R10 | PLAY-R10.bat | + shadows x4 / road texture x8 | | | | | | |
| R11 | PLAY-R11.bat | + mirror 300 | | | | | | |
| R12 | PLAY-R12.bat | the candidate as is (= R11 + split distance x24) | | | | | | |

## 5. Final values

Open: written from the owner's verdicts, then staged in `i76-uncap-lab\builds\rebaseline-20261021\stage` (the rc-draw stage's layout,
the seven tick19 presets).
