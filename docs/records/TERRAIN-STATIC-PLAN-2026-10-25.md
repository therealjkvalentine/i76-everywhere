# Terrain static plan (2026-10-25, terrain-static design lane; an Opus lane executes s.5)

Owner: "Go further with making the terrain not pop; see how static we can possibly get it, even at the expense of SOME accuracy. Nail
that once and for all." Outside tester: "popping definitely reduced; I do see the morph now and then."

Inputs: reports/"Terrain LOD retrofit options.md" (the LOD-algorithm survey), TERRAIN-MORPH-2026-10-21, TERRAIN-POPS-2026-10-23,
RENDER-FINISH-2026-10-23, TERRAIN-PASS-OPT-PLAN-2026-10-25, music-fix/terrainmorph.c, the hysteresis / freeze block of strlkproxy.c,
i76-map subsystems/renderer.md. Measurements: the laptop bench (C:\i76-bench\ts, this lane's twin of the terrain-pass-opt twin,
1920x1080 window), preset OWNER-2300-ALL (= the owner's "I76 ALL" set: LOD 24, stateless morph 0.25 / SHADE 3 / NEAR 100, BIG off,
SMOOTH, TEX 8, far 2300, FEATHER 0.75 + alpha), pad-driven routes. Prototype proxy: this lane's worktree (origin/main 119944c +
three lab switches, s.3; the laptop build also carries the analog lane's uncommitted I76_DRIVE_INJECT harness patch, as every laptop
measurement build does). Lab folder: `builds\terrain-static-20261025\` (ter_t05.py, ts_tab.py, laptop\ts-job.ps1 / ts-batch.ps1 /
rcd_drive_ts.py / t05-leg-*.json / steps-*.txt, dlls\, runs\).

## 0. Short answer

(filled from s.2 / s.4 below)

## 1. Method: what "pop" is measured as, and what the instrument cannot see

**Instrument.** The in-engine vertex-stream diff of the geomorph lane (`I76_TERRAIN_MORPH_LOG`, terrainmorph.c): per main terrain
pass, every terrain vertex inside a cone about the direction of travel and >= 20 m away gets its one-pass on-screen height change in
pixels at the instrument's fixed scale (1620 px per radian = 3440 px over 121.7 deg; the laptop's 1920 px / 90 deg cockpit view is
960 px/rad, so **multiply by 0.59 for the laptop screen**, by 1.5 for the owner's 3440 px panel at 90 deg). The change is classed by
what the vertex is (carried from the previous pass / born by a split, measured against its parents' mean = what was drawn there /
new but mature = entered at the view edge / gone = merged, measured against the parents' mean now) and binned by size (<= 1, 1-4,
4-16, > 16 px). A **snap** is > 4 px in one pass (the literature's 1-2 px per frame "invisible" line, with margin for the 0.59 scale).
The same log carries the shade: carried vertices whose one-pass shade step is >= 1/32 (a stock hardware row, 20-23 grey) by band,
hardware row crossings (under SMOOTH these are 1/255 steps, not pops), root-square moves, and the snaps / slides within 100 m.
Texture-ring switches come from `I76_TEX_LEVEL_LOG` (terrainpops.c: a leaf drawn with another texture level than the previous
frame, by the picker's z band). Frame rate from `I76_FRAME_LOG` through rcd_tab.py (median, 1 % low). Tabulator: `ts_tab.py`.

**Why not the screen-difference method.** The research report's "pixels changed per second" was built and run by the terrain-pop
lane (tp_capture.py, TERRAIN-POPS s.4.1): at ~23 captures/s and 80 px blocks it measures the ground texture sliding under the car and
the road signs passing; SMOOTH (which removed every 32-row shade step from the vertex colours, census-verified) read the same as ALL
on it, and the BIG-2 far flicker was invisible to it (RENDER-FINISH s.1). It says what pops are NOT; the vertex stream says what they
are, with the class attached. The vertex stream's own blind spots, stated: (a) it does not see the Gouraud interior change when a
fan diagonal flips at a split (de Boer's residual: no vertex moves, the interpolation across the tile changes); (b) it does not see
texture grain / minification sparkle (TERRAIN-POPS s.6: not shade, not geometry); (c) a vertex that enters at the view edge is scored
against its parents' mean, so the "mature / view-edge" class is the instrument's floor, not a pop in the middle of the screen;
(d) with the instrument on, the proxy runs its hash tables (~1.8 ms per frame, TERRAIN-PASS-OPT s.0), so **fps rows are separate
boots without the log**.

**Routes** (T05, the owner's mission; the car placed by I76_START_POS, the road follower of rcd_drive_bench.py with the analog pad
harness at 22 m/s; slope statistics from the .ter through `ter_t05.py`: grade = |dh| / ds along the road, relief = height range across
+-200 m of the road, "err40 / err80" = |h(mid) - mean(ends)| over 40 m / 80 m edges within 300 m of the road = what a 40 m / 80 m
tile hides):

| leg | where | length | mean grade | relief p50 / p90 | surface types | err40 p50 / p90 / p99 | err80 p50 / p90 / p99 |
|---|---|---|---|---|---|---|---|
| **hill** (the owner's route, roads 3+4 west from (8945, 44070)) | the hill top at 101 m, the road-closed bars, toward the barn | 2.7 km | 6.2 % | 127 / 158 m | 68 % paved, 21 % type 0, 11 % sand | 0.1 / 10.6 / 46.7 m | 0.5 / 17.2 / 48.2 m |
| **flat** (road 5 west from (6735, 43910)) | sand and paved desert past the hill road's end | 1.9 km | 0.8 % | 12 / 29 m | 57 % sand (type 1: no surface-type split), 40 % paved | 0.05 / 3.5 / 19.5 m | 0.35 / 6.6 / 22.2 m |
| **pass** (road 7 west from (10460, 44060)) | between canyon walls toward the hill road start | 1.9 km | 6.5 % | 158 / 158 m | 74 % paved, 17 % type 0 | 0.05 / 7.6 / 45.4 m | 0.2 / 13.8 / 47.0 m |

(The owner's ridge leg, for reference: 1.7 % grade, relief 32 / 108 m.)

**The rings the owner's preset draws** (LOD 24: ring = 18.3 x the node size; the forced split of 160 m nodes lies beyond the clip):
10 m tiles split to 5 m within **183 m** (steep ground only, the height test), 20 m within **366 m** (steep), 40 m within **732 m**
(typed ground: the surface-type scan), 80 m within **1464 m** (every 80 m node), the morph band = 0.25 of each ring = 46 / 92 / 183 /
366 m, i.e. at 22 m/s a split's blend lasts 2 / 4 / 8 / 17 s; NEAR 100 cuts every band to end at 100 m and leaves splits born within
100 m as stock pops; the texture-level rings at TEX 8 sit at 640 / 1280 m (and 2560 beyond the clip).

## 2. Inventory: what still pops today (OWNER-2300-ALL, laptop, n in the table)

(filled from the runs: tables per leg, shares per class)

## 3. The levers, each with the accuracy it trades

Notation: pop = the one-frame on-screen move a split would make unblended (K / C x delta / s px, research report s.1); band = the
morph's blend length in metres; v = speed. A vertex in its band moves pop x v dt / band per frame and pop x v / band per second.
At 22 m/s and the hill's 10 m-class deltas a 732 m-ring split is a ~20 px pop; over the present 183 m band that is 0.05 px per
frame at 48 fps and 2.4 px/s - under the per-frame "pop" threshold (1 px) but ABOVE the eye's motion-detection threshold against a
reference edge (~0.1 deg/s = 1.7 px/s on the laptop view): this is the tester's "I do see the morph now and then". Making the
blend slower (longer band) lowers px/s; making it absent (static far field) lowers it to 0 at the price of detail.

| # | lever | what it changes | accuracy it trades (metres / levels) | state | cost |
|---|---|---|---|---|---|
| L1 | **longer morph band** `I76_TERRAIN_MORPH` 0.25 -> 0.5 / 1.0 | the same splits blend over 2x / 4x the distance: per-second motion 1/2 / 1/4; with NEAR 100 every band still ends at 100 m (full detail inside 100 m) | a vertex is drawn below its true height for longer: at band 1.0 a 40 m-ring split (732 m) is half-blended at 366 m - the mid field carries HALF its height detail at half the ring (err40 p90 10.6 m on the hill -> ~5 m error at 366 m = 13 px on the laptop view), full only at 100 m | key only (built) | the listed-vertex loop grows with the band (~+50 us) |
| L2 | **morph on merge** (symmetric) | the stateless form IS symmetric at the ring (t -> 0 as d -> D); the only asymmetric merges are nodes merged away from their ring, which the trace says are error-step merges or view-hull culls (s.2 settles which with the 90 deg cone row) | none | built (stateless); the hull-edge class is the instrument's, not the screen's | - |
| L3 | **split / merge hysteresis** `I76_TERRAIN_HYST` 10-20 | a node splits p % nearer and merges p % farther than stock; with the morph the split distance moves but t is still computed from the stock ring, so a hysteretic split starts at t = p/25 (20 % -> t = 0.8: a partial pop!) | none in detail; it ADDS a pop under the morph unless the morph is told the biased ring | built; measured 24 % fewer flip events in the pre-morph era (RC-DRAW-FPS) | - |
| L4 | **screen-space error** (tau px) instead of distance rings | splits where the projected error exceeds tau; flat tiles never split, rough tiles split earlier; with FLAT_SPLIT it also neutralises the surface-type scan | reallocates detail, does not remove pops: every split is a tau-px jump, morphed as now; the vertex budget on canyon ground is unknown until measured | not built (node-test hook exists: the hysteresis stub at 0x4912f6) | a day; a measured experiment |
| L5 | **static far field** `I76_TERRAIN_FAR_LEAF=<f m>,<S samples>` (new, s.3.1) | beyond f no node of S or smaller splits: the field beyond f holds S-size tiles whatever the distance; the split on crossing f starts its blend at f (the morph is told); the 732 m / 1464 m rings become one ring at f, OR vanish when f > their ring | the hidden detail is the (S/2) midpoints' error between f and the stock ring: hill err40 p90 10.6 m (40 m tiles kept to 400 m: 10 m at 500 m = 19 px), err80 p90 17.2 m (80 m tiles kept to 800 m: 17 m at 1000 m = 16 px); p50 is 0.1-0.5 m (most tiles lose nothing) | built (prototype) | fewer vertices -> fps UP |
| L6 | **two-level ladder** `I76_TERRAIN_FORCE_SPLIT=<S>` (new): nodes >= S always split | the 1464 m ring (S = 16: 80 m nodes) disappears; 40 m tiles out to the clip | none (more detail) | built (prototype) | +vertices: ~1,900 for S 16 (+30 %), fps down ~15-20 % by the LOD sweep's slope (RENDER-FINISH s.7) |
| L7 | **temporal shade smoothing per vertex** | a per-vertex previous shade keyed by sample, blended frame to frame | none in geometry; shade lags by the blend | not built: it is stateful (the sample-keyed table the stateless morph exists to avoid: 1.8 ms at 18k vertices, or a 1024x1024 direct grid around the camera = 4 MB, no hashing, ~0.2 ms); the only shade pops left (s.2) are the births (already blended) and the sj jumps - measure first | ~0.2 ms (grid) |
| L8 | **texture-ring crossfade** | leaves in a band about a texture ring drawn twice (both levels, alpha blended) - the far-edge lane's blend-state machinery exists (fe_* hooks, bush alpha) | none | not built; ~20 % of leaves drawn twice = +1,100 triangles / frame (~0.6 ms, U1's 560 ns per triangle) | vs **`I76_TERRAIN_TEX=32`**: the only ring moves to 2560 m, beyond the clip - zero switches, cost none (the owner's sweep to 24 measured none), the grain sparkle of the 256 px level minified without mips grows with distance (TERRAIN-POPS s.6) |
| L9 | **freeze while moving slowly** `I76_TERRAIN_FREEZE=f,m` with the morph | nodes beyond f keep their first decision; a frozen leaf that comes within f splits at f with t = (ring - f) / band = a partial or full pop unless the morph is told (L5 is the told version: the cap is the same f) | the frozen field is "as first seen": detail depends on where the camera was when the node entered the view, not on where it is now (nondeterministic look) | built (pre-morph); superseded by L5 | - |
| L10 | **rebuild at 24/s, draw interpolated** | the quadtree at the sim rate, vertices interpolated between two trees | none | **do not**: a split still pops, now at 24 Hz; interpolating two trees needs vertex correspondence across trees = the sample-keyed table (the memory form, 27 fps in F6); TERRAIN-PASS-OPT s.3 already rejected caching the quadtree (arenas, int16 pool, mirror pass, binoculars) | - |
| L11 | **coarser rings with the morph** (LOD 24 -> 12) | fewer events, each 2x larger, morphed over half the band length: per-frame and per-second motion x4 | detail radius halves (the 10 m detail from 129 to 91 m) | key only | fps UP ~10 % |
| L12 | **flat-node split skip** `I76_TERRAIN_FLAT_SPLIT` | a flat node (every sample within 0.3 m of its coarse surface) skips the surface-type split | 0.3 m | built; measured -0.6 % vertices, no fps gain (TERRAIN-MORPH s.3.2) - its value under the morph is fewer morphing vertices on flat ground | - |

### 3.1 The prototype switches (this lane's worktree; lab only, off unless set; Gold; every site signature-checked)

- `I76_TERRAIN_MORPH_LOG_CONE=<deg>` (terrainmorph.c): the instrument's cone, full width (default 121.7; 90 = the cockpit fov).
- `I76_TERRAIN_FAR_LEAF=<f m>,<S samples>` (strlkproxy.c th_node, the hysteresis stub at 0x4912f6, enabled by the key alone): a
  node of size <= S whose centre is farther than f returns "leaf" before the stock tests (as the freeze does); terrainmorph.c caps a
  vertex's split distance D at f when its parent edge is <= S samples (main pass only), so the split on crossing f starts at t = 0.
  S in 2 / 4 / 8 / 16 / 32 (10 .. 160 m nodes; 320 m nodes are forced split before the stub).
- `I76_TERRAIN_FORCE_SPLIT=<S samples>`: a node of size >= S returns "split" (through the vertex guard); terrainmorph.c leaves vertices
  on edges >= S at t = 1 (otherwise a forced split beyond its ring would be drawn flat, t = 0, and buy nothing).
- Counters on the terrain-hyst report line (`far-leaf N, force-split N`).

## 4. Prototype measurements

### 4.1 L1 morph band 0.25 / 0.5 / 1.0, hill leg (run 2026-10-25 evening, laptop, Patch Kit v0.8.1 question)

Setup: laptop bench `C:\i76-bench	s`, preset OWNER-2300-ALL, 1920x1080, hill route (ridge then 2.7 km hill leg), pad-driven. DLL = lab
`base-f627e5ba` (origin/main 119944c + I76_DRIVE_INJECT harness; carries the morph log). The shipped v0.8.0 Strlkup.dll (f2856def) also carries
the log but NOT the drive harness, so it cannot run the pad-driven route; the base DLL differs from it by the commits after 9496235. Env on every
boot: I76_SKIP_MOVIES, I76_SKIP_CUTSCENES, I76_FFB_OFF, I76_MUTE (+ the job's mute watcher). Key proof: the result file's `keys` line and the
proxy log line `terrain-morph: ... band 0.25 | 0.50 | 1.00 x the ring distance` of every run. Steps `laptop\steps-l1.txt`, tabulator
`l1_tab.py`, runs `runs-l1\` (lab builds	errain-static-20261025). No crashes. Flat leg not run (no winner to test).

Units: the log's class bins are SUMS of on-screen px (not vertex counts), so "snap px/km" = px moved in >4 px one-pass steps per km,
at the instrument's scale (x0.59 for the laptop view). Log runs n=2 per band; fps from separate no-log boots n=2.

| band | n | split px/km | merge px/km | view-edge px/km | carried snaps px/km | within-100 m px/km | carried 1-4 px slide p90, px/s (per pass, all carried) | fps med | 1 % low |
|---|---|---|---|---|---|---|---|---|---|
| 0.25 (control a / b) | 2 | 31375 / 31048 | 116651 / 113343 | 85445 / 86183 | 12794 / 12801 | 52268 / 44182 | 2910 / 2853 | 49.1 / 49.6 | 14.4 / 14.4 |
| 0.5 (a / b) | 2 | 29729 / 30367 | 71047 / 82530 | 41559 / 42175 | 5686 / 6463 | 28444 / 36259 | 3357 / 3279 | 49.6 / 49.6 | 14.3 / 14.4 |
| 1.0 (a / b) | 2 | 34295 / 35822 | 28213 / 94516 | 24378 / 41930 | 5602 / 6053 | 16700 / 35882 | 3476 / 3218 | 49.9 / 49.2 | 14.4 / 14.3 |

Per-vertex carried slide (1-4 px bin, per pass): p50 0.027 / 0.016-0.025 / 0-0.038, p90 0.39-0.41 (0.25), 0.47 (0.5), 0.45-0.50 (1.0) px/s.
(The 1-4 px p50 is ~0 on most passes; p90 is the number to read.)

Same-rate control spread (0.25 twice): carried snaps 0.05 %, split 1 %, merge 3 %, view-edge 1 %, within-100 m 16 %, slide p90 2 %, fps +-0.5, 1 % low 0.
The 1.0 pair is not that tight: merge 28k vs 95k, view-edge 24k vs 42k, within-100 m 17k vs 36k (route/phase noise on gone / edge classes).

Reading: a longer band halves the carried snaps (12.8k -> 5.6-6.5k px/km, far above the control spread) and cuts view-edge entries and
merges (merge / edge noisier), by turning >4 px steps into 1-4 px slides; it does NOT lower the slide motion (p90 +15-20 % at 0.5 and 1.0, more
vertices in motion at once, as s.3 predicted per vertex but not in total). Split snaps and the stock within-100 m class are unchanged (NEAR 100).
0.5 and 1.0 are indistinguishable on carried snaps and slide; 1.0 adds merge / edge noise and the accuracy cost. fps: no difference (spread
+-0.5; 0.5 = 49.6 vs 0.25 = 49.4 mean). The instrument cannot say whether the eye prefers fewer snaps or less slide.

Recommendation: 0.5 if the preset is to change at all (halves carried snaps, same fps, half the accuracy cost of 1.0); 0.25 stays defensible
(no tester-visible evidence yet). 1.0 is not worth it. Accuracy cost of L1 (s.3): at 0.5 a 732 m-ring split is half-blended at ~550 m, so mid-field
detail (err40 p90 10.6 m) is drawn about 2-3 m low at 370-550 m for longer, ~3-6 px on the laptop view; at 1.0 about twice that.

## 5. Execution plan for the Opus lane

(filled after s.4)

## 6. The "max static" preset candidate

(filled after s.4)

## 7. Files

- This record. Lab `builds\terrain-static-20261025\`: `ter_t05.py` (heightmap + roads + leg statistics), `ts_tab.py` (the inventory
  tabulator), `laptop\` (ts-job.ps1, ts-batch.ps1, ts-run-all.ps1, rcd_drive_ts.py = rcd_drive_bench.py + the `leg` mode, mk_driver.py,
  t05-leg-flat.json, t05-leg-pass.json, steps-a.txt, steps-b.txt), `dlls\` (base-f627e5ba = origin/main 119944c + the harness patch;
  ts-501924b0 = + the three switches), `wt\` (the worktree), `runs\` (the laptop runs copied back).
- Laptop: `C:\i76-bench\ts\` (twin, dlls, steps), `C:\i76-bench\ts-job.ps1`, `ts-batch.ps1`, `ts-run-all.ps1`,
  `tools\rc-draw\rcd_drive_ts.py`, `t05-leg-*.json`, runs `C:\i76-bench\runs\ts-*`.
