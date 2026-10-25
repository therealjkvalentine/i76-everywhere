# What supersampling costs in fps, 2026-10-25

Owner's question: "How many fps is supersampling costing us?" The desktop (GTX 1080 Ti, 3440x1440 panel) renders dgVoodoo `[Glide] Resolution`
6880x2880 (2x per axis) with 4x antialiasing.

**Answer: not resolvable here.** Four conf variants were run on the T05 hill leg. The run-to-run spread of one and the same conf (a: 112.9 and 92.1
fps) is about 20 fps, larger than any difference between the variants. There is no measurable fps cost of 2x on this GPU at this frame pace. The
1 % low sits at 62-74 fps in every variant, so the hitches come from the engine, not from the fill rate. The laptop number was not taken (s.4).

## 1. Method

- Twin `C:\Users\james\i76-uncap-lab\test-gold` (gate twin of main Gold, STRLKUP.DLL 5dca9d79 on the gate line, i76.exe 6319abf7), launcher PLAY.bat
  = preset OWNER-2300-ALL. Gate row 9 (`autotest\t05-route-fps.ps1`): 15 s ridge, then the 2.6 km hill leg, fps from `I76_FRAME_LOG`.
  A hill leg counts only with >= 2000 m driven.
- opentrack not running; head look off (`-NoHeadTrack`) and the T300RS interposer off (`-NoFfb`) in every run. `t05-route-fps.ps1` starts
  PLAY-i76.ps1 itself and never passes those switches, so I added two inert hooks to it: `LAB_T05_EXTRA` (extra PLAY-i76.ps1 switches) and
  `LAB_T05_CONF` (a conf file copied to dgVoodoo.conf instead of the one the .bat names). Unset, it behaves as before. The twin's
  dgVoodoo.wide.conf was never edited, so the other lanes that use test-gold were not affected.
- The four confs are byte copies of the twin's dgVoodoo.wide.conf (dccd379a) with only line 94 (`Resolution`) and/or line 95 (`Antialiasing`) changed
  (CRLF kept; checked with diff):

  | row | conf | Glide Resolution | Antialiasing | md5 |
  |---|---|---|---|---|
  | a | current | 6880x2880 (2x) | 4x | dccd379a |
  | b | 1x | 3440x1440 | 4x | 0eb52fd6 |
  | c | 2x, AA off | 6880x2880 | off | 59d369f8 |
  | d | 1x, AA off | 3440x1440 | off | 9edde827 |

  (`Make-Wide-Conf.ps1 -Scale 1` was not used because it also rewrites the presets; the digits are the only difference either way.)
- Console: run-gate.ps1 queue (global dgVoodoo.conf hidden by the gate, keep-display held by another lane, mute via I76_MUTE + per-pid watcher, persisted
  mute cleared on every release). The console was shared with at least 8 other lanes and held by the owner 09:40-11:30, so the runs span 06:19-11:56.

## 2. Hill leg, every run (median fps / 1 % low; metres driven)

| row | run 1 | run 2 | run 3 | valid n |
|---|---|---|---|---|
| a 2x + AA 4x | 112.9 / 73.7 (2614 m) 06:19 | 92.1 / 62.6 (2606 m) 11:48 | - | 2 |
| b 1x + AA 4x | 115.4 / 74.1 (2608 m) 08:47 | 96.2 / 61.7 (**1891 m, void**) 11:35 | - | 1 |
| c 2x, AA off | 107.3 / 67.8 (2633 m) 09:34 | 99.9 / 63.6 (2615 m) 11:40 | - | 2 |
| d 1x, AA off | 126.0 / 67.0 (**1867 m, void**) 09:37 | 82.6 / 24.6 (2613 m) 11:44 | 101.6 / 63.8 (2608 m) 11:52 | 2 |
| a (extra) | game exited 0.8 s into the hill leg, **void** (0 m) 09:41, at the time the owner took the console | | | |

Voids: b2 and d1 left the road (36 m off) and stopped short of 2000 m; a3 died at the start of the leg with no CRASH line while the owner's
"at the console 09:40" line appeared. d3 (82.6, 1 % low 24.6) is valid by the distance rule but has a stall in it.

| row | mean of valid hill medians | spread | mean ridge median (15 s, ~335 m, all complete runs) |
|---|---|---|---|
| a 2x + AA 4x | 102.5 | 112.9, 92.1 | 106.9 (116.7, 97.0) |
| b 1x + AA 4x | 115.4 (n 1) | - | 115.5 (122.4, 108.5) |
| c 2x, AA off | 103.6 | 107.3, 99.9 | 103.5 (106.2, 100.7) |
| d 1x, AA off | 92.1 | 82.6, 101.6 | 110.0 (109.8, 106.3, 113.8) |

Reading: the 1x rows are not systematically faster (d is the slowest on the hill, b the fastest), AA off is not systematically faster, and the same
conf drifts by 20 fps between a morning run and a late-morning run (a: 112.9 -> 92.1; every run in the 11:35-11:56 batch is lower than the
early ones, which points at the machine's state and the other lanes' background load, not at the conf). n is 1-2 per row, so no ranking is claimed.
If a cost exists at all it is below the noise, i.e. well under 10 fps on a 1080 Ti.

## 3. Restores

- Twin `Interstate 76\dgVoodoo.conf` was left at the last variant by the launcher copy (9edde827); copied back from dgVoodoo.wide.conf and read back
  as dccd379a. wide.conf dccd379a, 16x10 299a6811, tick aa6414e4: unchanged (md5 checked after). Global %APPDATA%\dgVoodoo\dgVoodoo.conf put back by the
  gate (PASS in each run). No exe/dll in the twin was touched. Mute: cleared by run-gate's release after each group.
- Lab hooks `LAB_T05_EXTRA` / `LAB_T05_CONF` in `autotest\t05-route-fps.ps1` stay (inert when unset). Scripts and raw outputs:
  `i76-uncap-lab\supersample-cost\` (confs, drivers, batch logs); per-run frames under `autotest\runs\gate\20261025-*`.

## 4. Not done: the laptop (1080p 2x vs 1x)

Skipped. LAPTOP-BENCH-2026-10-24 s.4 and DGVOODOO-UPDATE-2026-10-24 say the bench twin (dgVoodoo 2.87.3) crashes at launch on the 26100.9711
update and that even with 2.87.5 about 60 % of boots die at `winmmbase.dll+0x5AB3`, so a bench row would be a crash, not an fps number. I did not
re-probe the laptop (its `laptop-run.ps1` is blocked by the PowerShell execution policy in this shell) and did not swap its dgVoodoo. The
"typical user" number is still missing; it needs the winmmbase problem solved first.

## 5. Recommendation

Keep 2x + 4x AA on this desktop: measured no cost above the 20 fps run-to-run noise on a 1080 Ti. For mid-range GPUs there is no measurement
(the laptop could not boot), so the tier presets should not claim a number; until one exists ship 1x with 4x AA for the mid tier (the cheapest
change that keeps the edge smoothing) and 2x + 4x for the high tier, and re-run these four rows on the laptop once it boots, with n >= 3 per row
and an interleaved order to cancel the time drift seen here.
