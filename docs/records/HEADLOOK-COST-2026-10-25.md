# Head look costs fps: where it goes (2026-10-25, measurement lane)

Owner: "Head look costs fps - why?" (gate row 9: hill-leg median 114 fps without head look, ~97 with opentrack running + the head-look layer).
Scripts: `tools/headlook-cost/` (hlcost-run.ps1 orchestrator, t05-hl.ps1 = gate row 9's t05-route-fps.ps1 + launcher args + a CPU/GPU/FT sampler, sampler.ps1, ftsim.ps1, analyze.py, aggregate.py). Raw data (frames, 1 Hz CPU, GPU) in lab `autotest\headlook-cost\out-*`.

## Method
- Desktop (i7-7700K 4C/8T, GTX 1080 Ti), `test-gold` (proxy 5d6f9828, PLAY.bat preset OWNER-2300-ALL, far clip 2300), row 9's route (ridge 15 s, hill 2.6 km, ~118 s), median fps of the hill leg, 1 % low from the same frame log. Console protocol followed (.fps-lock + .console-owner, queue, idle >= 120 s, display hold). Opentrack = the owner's install (neuralnet tracker, Insta360 Link 2C Pro, freetrack output), started and stopped by the script; its `default.ini` (md5 37206F16) and the registry game-detection setting were swapped/changed only per run and read back at the end (matches / `true`). Nobody sat in front of the camera, so the neuralnet tracker saw no face (head still, yaw 0): real use may cost more.
- Sampler (1 Hz system CPU + FT_SharedMem; 5 s CPU time of every process; nvidia-smi 1 Hz). Its own cost: none measurable (hill 83.8 vs 84.3 and 90.3 vs 91.8 fps with / without it, n 2).
- **The box is not quiet**: Windows Defender (MsMpEng) used 11-165 % of a core during rows and the same condition ranged 88-106 fps (condition `a`, n 3: 106.2 / 88.6 / 96.8). The 114 of the earlier gate was a quiet moment. Defender's CPU per row is recorded; the effects below come from a regression `fps ~ condition + MsMpEng` (24 rows, residual sd 3.6 fps; -14.9 fps per +100 % of a core of Defender).

## Result (hill-leg median fps; CPU = % of ONE logical core, hill window)

| cond | what | n | fps mean (sd) | each | 1 % low | opentrack | layer (AHK) | Defender | i76 | GPU % |
|---|---|---|---|---|---|---|---|---|---|---|
| a | no opentrack, `-NoHeadTrack` | 3 | 97.2 (8.8) | 106.2 / 88.6 / 96.8 | 64.7 | - | - | 32 | 110 | 39 |
| b_idle | opentrack running, game detection off (no tracking) | 1 | 102.1 | 102.1 | 66.0 | 0.1 | - | 17 | 114 | 40 |
| b | opentrack tracking (neuralnet), layer NOT running | 3 | 91.3 (6.6) | 96.0 / 83.8 / 94.1 | 61.9 | 62 | - | 30 | 113 | 37 |
| c | opentrack + layer ANALOG (the default) | 3 | 93.6 (0.6) | 93.3 / 93.3 / 94.3 | 63.0 | 59 | 32 | 16 | 113 | 37 |
| d | opentrack + layer DIGITAL | 3 | 92.8 (5.9) | 98.5 / 86.7 / 93.2 | 61.8 | 72 | 0 | 32 | 113 | 37 |
| e_pt | opentrack, tracker = PointTracker (profile copy), no layer | 3 | 94.8 (4.0) | 98.3 / 95.6 / 90.4 | 63.5 | 76 | - | 20 | 112 | 37 |
| f | layer ANALOG alone, simulated freetrack (ftsim, moving head, 60 Hz), no opentrack | 3 | 93.2 (9.6) | 98.7 / 82.2 / 98.8 | 62.6 | - | 33 | 68 | 110 | 36 |
| g_bn_b | b with opentrack at BelowNormal | 1 | 93.1 | | 62.8 | 71 | - | 21 | 112 | 36 |
| g_aff_b | b with BelowNormal + affinity logical CPUs 4-7 | 1 | 95.3 | | 62.5 | 71 | - | 20 | 120 | 38 |
| c_self | opentrack + layer ANALOG started by the script, original script | 1 | 92.6 | | 61.8 | 73 | 33 | 20 | 111 | 38 |
| c_fix | same with the fixed script (below) | 2 | 94.5 | 94.1 / 95.0 | 63.9 | 58 | **0.0** | 20 | 108 | 37 |

Regression, fps relative to `a` (intercept 101.9 at no Defender load, se 2.3): b -6.3 (se 3.0), c -5.9, d -4.4, e_pt -4.2, f +1.5 (se 3.1), b_idle +2.7 (n 1), g_bn_b -5.8, g_aff_b -3.7 (n 1 each, se 4.2), c_self -6.4, c_fix -4.4 (se 3.3).
Opentrack publishes 250 updates/s (60/s for ftsim) whatever the head does. GPU load is 36-40 % in every row (not GPU bound; clocks 1.86-1.92 GHz); the game process uses ~110 % of a core in every row, so the game's own CPU time does not change.

## Attribution of the "17 fps"
1. **Most of it was noise in that comparison**: a single baseline swings 88-106 fps on this machine with Defender's load alone, more than the effect. A fair figure is **about 5-6 fps (5-6 %)** for opentrack running and tracking, standard error 3.
2. **The cost is opentrack's tracking, not the head-look layer.** `b_idle` (opentrack open, not tracking) is the baseline (102); `b` (tracking, no layer) already shows the whole drop (-6); `c` (+ layer ANALOG) is no lower than `b`; `d` (DIGITAL) is not lower; `f` (the layer alone with a moving simulated head) is not lower than `a` (+1.5 +- 3). The layer is **free in fps terms** at this resolution.
3. **A cheaper tracker does not help**: PointTracker (e_pt) still costs about -4 and opentrack still burns 50-76 % of a core. What both trackers share is the camera path (Insta360 Link 2C Pro, MJPEG/USB decode, the 250 Hz pipeline loop), not the neural net. (PointTracker saw no LEDs, so its tracker work is idle; the camera work is not.)
4. **Mechanism, probably**: opentrack's 0.6-0.9 core on a 4-core / 8-thread part shares cores and cache / memory bus with the game's render thread and dgVoodoo, and keeps the camera's USB load on; the game needs the same CPU time but takes longer per frame. Lowering opentrack's priority (g_bn_b) or pinning it to cores 2-3 (g_aff_b) showed no benefit beyond the noise (n 1 each: 93 / 95).
5. **Camera writes forcing extra work in the engine**: not seen. i76.exe's CPU time (108-120 %) is the same with and without the layer (110-114), and the digital layer, which only sends keys, costs no more than the analog one.

## The one real finding: the layer's 33 % of a core
In ANALOG the layer (`i76-opentrack-headlook.ahk`) uses **33 % of a core** (digital 0 %). Cause: `OpenGame()` runs once or twice per 8 ms tick in ANALOG and starts with `Process, Exist, i76.exe`, which builds a toolhelp snapshot of every process on the machine each time. Fix (7 lines at the top of `OpenGame()`: while we hold the game handle and `GetExitCodeProcess` says STILL_ACTIVE (259), return true without the snapshot) is in `tools/headlook-cost/i76-opentrack-headlook-fix.ahk.proposed` (the whole script with the change; selftest PASS 14 of 14). Measured: layer CPU **32.8 -> 0.0 %** (c_self vs c_fix). On this PC it did not move fps measurably (c 93.6, c_fix 94.5; se 3), but it is free and removes a third of a core of pointless work (more on weaker PCs). Not deployed: the script ships from the repo; apply it with the next controls change. It ran only from a temporary copy in test-gold's `_ahk` (removed again).

## Recommendation (cheapest first)
1. Tell the owner: **head look costs about 5-6 fps (~5 %) on this PC, all of it opentrack tracking**; the layer, analog or digital, costs none. The earlier 114 -> 97 was mostly Defender noise on the baseline.
2. Apply the 7-line `OpenGame()` fix (removes 33 % of a core of AHK work).
3. When fps matter more than head look, do not start opentrack (the launcher already skips head look when it is not running). Untested one-line candidates to cut opentrack's own camera load, for the next slot: a lower camera frame rate / resolution in opentrack (neuralnet `force-fps` / `force-resolution`, currently `force-fps=2`; conds `b_fps0/1/3` are in hlcost-run.ps1) and `num-threads`.
4. Defender: a folder / process exclusion for the lab and game folders and `i76.exe` would stabilise every fps row on this PC (needs the owner's admin rights); it is the biggest source of run-to-run spread (-15 fps per core of Defender).

## Not done / limits
- The last batch (b_fps0, b_fps1, c_fix / c_self repeats) was not run: the owner took the console at 09:40 (`.console-owner` = OWNER) while this run was queued; I stopped it, nothing was left running. n is 1-2 for the fix, priority and affinity rows.
- No face in front of the camera (the neuralnet tracker may cost more with one); head movement was simulated only for the layer (f).
- The harness adds ffb-interposer (~42 %), mute-proc (~25 %) and the python route driver to every row (same in all rows).
- Raw per-row data: lab `autotest\headlook-cost\out-main-20261025-061920`, `out-extras-20261025-080019`, `out-calib-*`, `out-smoke-*`.

## Restored
opentrack `default.ini` md5 37206F16 (read back), registry `executable-detector-enabled=true`, global dgVoodoo.conf back, no opentrack / i76 / AHK left from test-gold, keep-display stopped and its marker removed, queue line removed, `.fps-lock` / `.console-owner` released. The temporary fixed script removed from test-gold.
