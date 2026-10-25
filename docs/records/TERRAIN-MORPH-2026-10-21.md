# Terrain geomorph and flat-tile split (2026-10-21 evening, terrain-geomorph lane)

The owner photographs the T05 terrain "redrawing" as he drives (REBASELINE-2026-10-21 trace v2: a quadtree level split at fixed
distance rings, one ring per tile size; each node flips once, so hysteresis / freeze have nothing to act on). This lane removes the pop
in the renderer instead of the preset: the vertices a split adds are blended in. Code: `music-fix/terrainmorph.c` (610ef86, final
state f613b78 = 992cb8f's content, the staged d3e24caa), three lines in `strlkproxy.c` (include, report, apply; 610ef86). Off unless
set; Gold only; every site signature-checked.

## 0. Short answer

- **The pop is gone when the morph is on.** No-dashboard view (F6, camera mode 1, in-cockpit flag 0), T05 hill leg, per split:
  the largest one-frame height move falls from median 4.0 / 95th 217 / max 3130 px to **0.02 / 2.2 / 30 px**, and the largest
  one-frame shade step from 95th 0.306 (78 grey levels on a white texel) to **0.0036 (0.9 grey)**. Snaps (> 4 px in one frame) from
  vertices born by a split: 3442 px/s -> **0**. Mid distance (300-900 m) snaps: 273 -> **0** px/s.
- **The sim is untouched:** the T05 jump from a stored state, 8 descents per boot. All 910 sampled tick states of the control boot
  (18 columns: position, velocity, rates, rotation, armour, ground normal) appear unchanged in a second control boot and in three
  morph + flat-split boots (s.3.1).
- **But it costs too much in this form:** in the no-dashboard view the terrain has ~18,000 vertices a pass (6,500 in the cockpit),
  and the per-vertex memory (two hash tables across passes) costs ~2.6 ms a frame: **91.5 fps against 118.5 plain** (morph alone,
  hill-leg median, n 2 / 3). The blend itself is a few flops per vertex; the cost is the table work (s.4). Not shippable as is.
- **Flat split:** vertices -0.6 % (cockpit) / 0.0 % (F6), no fps gain: leave it off.
- **Recommendation (s.6):** do not promote this build. The next build should take the stateless form (the blend factor from the
  vertex's own ring distance, parents from a hook on the edge split 0x4918f0, no tables). The pop numbers above say what the blend
  buys; that build has to show the same numbers at < 0.3 ms a frame.
- **Correction to the trace v2 reading:** there is no forced split of flat tiles at 12.9 x the node size. The stock forced ring is
  0.71 node sizes (s.1). What splits flat ground at the ring is the surface-type split (0x491541).

| switch | value | what |
|---|---|---|
| `I76_TERRAIN_MORPH` | `<band>`: <= 1 = fraction of the distance the vertex appeared at, 5..1000 = metres; 0 / unset = off | geomorph (height and shade) |
| `I76_TERRAIN_FLAT_SPLIT` | `<f>[,<eps m>]`, 0 < f <= 1, eps default 0.3 m | a flat node skips the surface-type split until f x its split ring |
| `I76_TERRAIN_MORPH_LOG` | `<csv>` | lab instrument: per main terrain pass, how far vertices jump on screen (runs with the morph off too) |

## 1. The mechanism, as found in i76.exe 6319abf7

- **renderer_QueueTerrain 0x490a00** rebuilds the quadtree **0x4911e0** every pass: main camera (call at 0x4020a4) and, in the
  cockpit, the rear mirror first (0x44594e, camera 0x608c80). Vertices go to `[0x5dd320]`, stride 12: x, y, z floats, x / z = integer
  sample coordinates (5 m), **y = the raw 12-bit height** (x 0.1 m). UV and shade go to `[0x5dd2ec]`, stride 12: u, v, shade. The
  frame's vertex count is `[0x6442ec]`; the 4 root corners are vertices 0..3 (0x490be4..0x490df5).
- **Edge split 0x4918f0** makes one vertex at the integer midpoint of an edge with its **true** height `0x493160(mx, mz)` (0x491988),
  unless the edge already has children (a shared edge is split once per pass). Edge record (pool `[0x654380]`, 12 bytes): word v0,
  word v1, child 0, child 1. A node split (0x49167c) splits its four sides, then the edge between two opposite side midpoints (the
  centre). Leaf record (0x491810, 0x1c bytes, list from `[0x59c560]`, next at +8): word x, word z, int size, the 4 edge pointers.
- **The split test** (node of half size h, d2 = squared distance eye -> node centre in samples, `K = [0x6442c8]`,
  `B = [0x6442cc]`):
  - h >= 32: always split (0x4912f0);
  - d2 > (2h)^2 K: leaf (0x491358) - **the split ring at 2h sqrt(K)**, 18.3 x the node size with LOD 24;
  - **2 d2 < (2h)^2: split (0x49135e..0x49136d)** - the eye is within 0.71 node sizes of the centre (the node under the camera);
  - otherwise the five midpoint errors |h(mid) - mean(ends)| x 2h against floor_pow2(d2) x B (0x491373..0x49153b): any above -> split;
  - all below and 2h > 4 samples (`[0x4be7f8]` = 4.0, 0x491541): split if a sample on the node's scan lines carries **surface type
    2, 3, 4, 6 or 7** (.ter bits 13-15: `v >= 0x4000 && (v & 0xe000) != 0xa000`, 0x4915f5..0x49166a); else leaf.
- **Correction to the trace v2 reading ("every tile, flat ones too, is force-split at about 12.9 x the size").** The x87 stack at
  0x4912fe..0x49136d multiplies a COPY of (2h)^2 by K (`fld st(2); fmul [0x6442c8]`); the forced-split compare uses the unmultiplied
  (2h)^2. So the stock forced ring is 0.71 node sizes, not 12.9. The trace twin's computed decision model put the N band at
  2 d2 < (2h)^2 K and called it split without the error test, so its "ring E->N" flips (58.6 % of v2) are the model's, not the game's.
  The same trace's v1 lines (actual splits, a child visited) agree: "forced" (q 0.45-0.5) is 2.9 % of v1's flips, against 12 % at
  the real ring (band-entry). <re-archive> `subsystems/renderer.md` (row "terrain quadtree LOD") reads it the same way. What does split
  flat ground at the ring is the **surface-type split** above: on T05 most samples are dirt / paved types, so flat ground in the band
  splits down to 20 m at 18.3 x the size.
- **After the quadtree:** `0x4937c0` transforms every vertex IN PLACE to view space (call at 0x490eed); then, when lighting is on
  (`[0x5a4618]`), 0x490f08..0x490f6d computes each vertex's shade from the heightmap around its sample (0x490fb0: neighbour heights,
  view depth) into `[0x5dd2ec]+8`. So a new vertex brings a new height AND a new shade in one frame (the owner's "shade changes in
  flat tiles": the new vertex's Gouraud value differs from what the coarse polygon interpolated there). Then `0x491a30` emits the
  leaves (call 0x490f9b hardware, 0x490f82 software).
- **The sim does not read these arrays.** The ground query is 0x493550 (bilinear on the heightmap, ENGINE-REFERENCE); `[0x5dd320]`
  is the renderer's shared scratch vertex pool, rewritten every pass.

## 2. What was built (patch sites)

| site | bytes (expected) | becomes | what |
|---|---|---|---|
| 0x490eed | `e8 ce 28 00 00` (call 0x4937c0) | call tm_xform_wrap | before the in-place transform: blend split vertices' y |
| 0x490f9b | `e8 90 0a 00 00` (call 0x491a30) | call tm_emit_wrap | after the shade loop: blend shade, log, close the pass |
| 0x490f82 | `e8 a9 0a 00 00` (call 0x491a30, software) | call tm_emit_wrap | same, software renderer |
| 0x491556 | `2b f3 2b fb 8b c6` | jmp tf_stub + nop | flat split: keep a flat node a leaf (to 0x4917b4) or run the stock scan (back to 0x49155c) |

**Morph.** Each vertex (index >= 4) is named by its sample (x, z). Its level follows from the coordinates relative to the root square
(`[0x6442e0]`, `[0x6442e4]`, size `1 << [0x6442e8]`): m = the lowest set bit of the relative x or z. One coordinate odd in m: a side
midpoint of a node of size 2m, parents (x -+ m, z) or (x, z -+ m). Both: the centre, parents (x - m, z - m) / (x + m, z + m), the
diagonal of the fan 0x491a30 draws from the leaf's min corner. Parents always have lower indices (an edge's ends exist before it
splits), so walking up the indices blends every vertex against already blended parents:
`y = lerp(mean(parents), true, t)` - a chain of levels morphs continuously. t comes from a per-vertex memory across main passes
(hash tables keyed by sample, as the hysteresis code's node table): a vertex new in this pass, where a node that has it as a midpoint /
centre (or that node's parent / grandparent) was a LEAF in the previous main pass, was born by a split. It keeps d0 = its distance then;
`t = clamp((d0 - d) / band)`, band = fraction x d0 or metres. Any other new vertex is mature (t = 1): view-edge entries, the first
pass, a camera jump of more than 40 m. So turning the head or a start / teleport never shows flattened ground. Driving away, d grows
back to d0 and t returns to 0 before the node merges at the same ring: the merge direction morphs too. The mirror pass stays stock.
The eye is read from the camera (+0x160 / +0x170 x `[0x6442c4]`), not from `[0x6442f8]`, so the hysteresis switch can be combined.
The shade is blended with the same t after the stock shade loop.

**Flat split.** At 0x491556 the node has passed every height-error test and is larger than 4 samples, i.e. only the surface-type scan
can still split it. If it is farther than f x its split ring and every sample in it lies within eps of its coarse two-triangle
surface (the fan diagonal), it stays a leaf. The flatness is computed once per node and cached (key = corner + size, checked against
two corner heights).

**Instrument** (`I76_TERRAIN_MORPH_LOG`, runs with the morph off too, so stock and morph are measured by the same code). Per main
pass, every vertex >= 20 m away inside the cockpit-wide cone (121.7 deg) about the direction of travel: its on-screen height change
since the previous pass, in cockpit pixels (3440 px over 121.7 deg, the rc-draw census's scale). A new vertex is measured against its
parents' mean (what was drawn there), a vanished one against the parents' mean now. A **snap** is > 4 px in one pass. The class
histograms split carried / born by a split / new but mature (view-hull edge) / gone vertices. `<log>.events.csv` has one line per
split: its largest one-pass height move (px) and shade step from birth to the end of its blend, and the shade step the split would
show unblended (`|true shade - parents' mean|`). Shade is the 0..1 texel multiplier (0x490fb0 clamps it at 1.0, `[0x4be830]`), so
x 255 is the grey step on a white texel (an upper bound).

## 3. Measurements (lab copy exp-morph; the rows' preset = R07's terrain: tick19-42 minus LOD_B / HYST / FREEZE, LOD 24, far clip 1800)

Conditions (launchers in exp-morph): **plain** = the candidate's own proxy 8f8da929, no instrument; **base** = the morph build with
only the instrument (morph off); **on** = `I76_TERRAIN_MORPH 0.25` + instrument; **flat** = on + `I76_TERRAIN_FLAT_SPLIT 0.6,0.3`;
**tick-morph** = on without the instrument (the clean cost). Route = gate row 9's T05 route (autotest\t05-route-fps.ps1; for F6 the
copy tools\terrain-morph\tm-route.ps1, which presses F6 after the hill placement and logs `view f6: camera mode 1, in-cockpit flag 0`
for every boot). Console, physical session, display held awake (main's .display-hold), one boot per .fps-lock.

### 3.1 Physics (headless, private desktop, tools\jump-fix2\j2-run.ps1 -Game exp-morph)

Lab twins of the same source with the jump lane's drive / sequence blocks: lab-plain 161711f2, lab-morph (9ebf5639, ec0d1847,
9150dbc9 = the staged source, 911fbd9a = the discarded grid layer). T05 canyon jump from `straight.state`, 8 descents at deltas
0..2.1 s, preset rc42, morph boots with `I76_TERRAIN_MORPH=0.25;I76_TERRAIN_FLAT_SPLIT=0.6,0.3` (the log shows both on, 600+ vertices
born and ~100 morphing a pass).

| boot | proxy | jumps | per-jump table (v_to, vy_to, apex, dist, kick, q_air ...) | tick states (910 rows x 18 columns) found in the boot |
|---|---|---|---|---|
| p1 (control) | lab-plain | 8 | reference | 910 / 910 |
| p2 (control) | lab-plain | 8 | identical to p1, every column | 910 / 910 |
| m1, m2 | lab-morph 9ebf5639 | 8 + 8 | identical to p1, every column | 910 / 910 each |
| m3 | lab-morph 9150dbc9 (= stage) | 8 | - | 910 / 910 |
| m4 | lab-morph 911fbd9a | 8 | - | 910 / 910 |

The sim reads the ground through 0x493550 (the heightmap); the morph writes only the renderer's scratch arrays `[0x5dd320]` /
`[0x5dd2ec]`. Captures: `captures\morph-20261021\phys\`.

### 3.2 Cockpit view (camera mode 0), T05 hill leg, proxy e94389d8 (hash tables, 40 m band floor) / d6e6b891

| condition | n | median fps | 1 % low | snaps px/s near < 300 m | mid | far > 900 m | largest snap px | terrain verts (median) |
|---|---|---|---|---|---|---|---|---|
| plain | 2 | 119.9 | 87.1 | - | - | - | - | 6,490 |
| base (instrument only) | 3 | 110.7 [106.1..113.2] | 71.9 | 2924 | 1027 | 1023 | 2695 | 6,538 |
| on 0.25 | 2 | 113.0 [113.0..113.1] | 76.2 | 159 | 0 | 778 | 194 | 6,526 |
| flat | 2 | 109.4 [105.0..113.8] | 71.5 | 170 | 0 | 761 | 194 | 6,488 |

The snap totals still left with the morph on come from vertex classes the morph does not touch, and they are the same with the morph
off (on vs base, px/s of > 16 px snaps): **born by a split 3234 -> 0**; new at the view-hull edge 376 -> 371; gone 304 -> 286. Plus
carried vertices: 150 px/s of 4-16 px steps, which is the morph's own motion close in. The view-edge and gone classes are vertices
entering / leaving the footprint hull at the edge of the view (the instrument counts them against their parents' mean). They are the
instrument's floor, not pops the owner sees in the middle of the screen. The 194 px largest snap is the same pass in every morph boot,
at the hill-leg start (8943, 44070) right after the placement.

### 3.3 No-dashboard view (F6: camera mode 1, in-cockpit flag 0; the owner's request), T05 hill leg

Per split (events log; n = boots, ~11,700 splits per morph boot):

| condition | boots | splits / s | height move per split px: median | 95th | max | shade step per split: median | 95th | 95th as grey (x255) | the split's shade delta unblended: median / 95th |
|---|---|---|---|---|---|---|---|---|---|
| stock (base) | 2 | 93.5 | **3.98** | **217** | **3130** | **0.0135** | **0.306** | **78** | 0.0135 / 0.306 |
| morph 0.25 | 3 | 102.3 | **0.02** | **2.2** | **30** | **0.0007** | **0.0036** | **0.9** | 0.0132 / 0.295 |
| morph + flat | 2 | 102.2 | 0.02 | 2.05 | 26 | 0.0007 | 0.0033 | 0.8 | 0.0133 / 0.295 |

(The last column shows the splits carry the same shade step in both: the blend is what removes it. In the stock every split's whole
step lands in one frame. Splits/s differ because the stock records a split only when it is born inside the view cone, the morph when
it is in view at any time during its blend.)

Per pass (morph log):

| condition | n | snaps px/s near | mid | far | largest snap px | verts median |
|---|---|---|---|---|---|---|
| base | 2 | 3634 | 273 | 445 | 3106 | 17,980 |
| on | 3 | 855 | 0 | 252 | 98 | 17,986 |
| flat | 2 | 715 | 0 | 227 | 76 | 17,984 |

Frame rate, hill leg, proxy d3e24caa (= stage) unless said:

| condition | n | median fps | 1 % low |
|---|---|---|---|
| plain (8f8da929) | 3 | **118.5** [118.2..118.9] | 76.9 |
| base (instrument only) | 1 | 84.2 | 52.4 |
| on + instrument | 2 | 83.7 [82.8..84.5] | 52.0 |
| flat + instrument | 2 | 83.6 [83.2..83.9] | 51.6 |
| **tick-morph (on, no instrument)** | 2 | **91.5** [91.2..91.8] | **58.2** |

Two discarded layers, each recorded so nobody tries them again. (a) 8107233 replaced the hash tables with grids over the root square.
It measured 117.6 fps, but only because the F6 root square is larger than its 2048-sample limit (the hood view's far corners reach
~3.6 km), so 7,218 of the passes ran stock (its own counter). (b) 769b8e2 used Morton-order hash slots. Dense near-ground vertices form
long linear-probing runs: 1.3-10 ms a pass (its own meter), 56 fps with the morph on or off. Both reverted (f613b78). Those boots'
pop numbers are kept (same morph logic); their fps is not used.

## 4. What the morph costs and why

- The blend is cheap: per vertex, two parent heights, one lerp, and the same for the shade.
- The cost is the **per-vertex memory**. Each main pass inserts every vertex into a hash table keyed by its sample. It looks up its
  two parents and its entry in the previous pass's table, checks up to 6 leaf keys for a newly born vertex, and walks the leaf list
  into a second table. That is ~5 random accesses into 3-6 MB tables per vertex, plus the instrument's extra pass over the previous
  table.
- At 6.5k vertices (cockpit) that stays under the 120 cap's slack. At 18k (F6) it is +2.6 ms a frame (118.5 -> 91.5).
- **Not the band, not the shade blend, not the flat split.** Base (instrument, morph off) costs the same as on (84.2 vs 83.7), and
  flat costs the same as on.
- **The cheaper form is the stateless one** (Röttger 1998 / CDLOD, the coordinator's research notes): t = clamp((ring(S) - d) /
  band), where ring(S) = S sqrt(K) is the split distance of the vertex's level (`[0x6442c8]`) and d is the distance of the nearer of
  its nodes. Parents come from a hook on the edge split 0x4918f0, which knows the edge's two ends when it makes the vertex: an array
  write per new vertex, no lookups.
- Expected: O(1) per vertex, no tables, well under 0.3 ms at 18k vertices. Merges are symmetric for free. Shared vertices stay
  crack-free (one vertex, one t).
- What it gives up: splits that do not happen at the ring (the error-threshold steps, ~7 % of the trace's computed flips) would
  start partly blended, a residual pop of t x their error. The memory version handles those, at the cost measured above.
- The coordinator's other options do not remove the cost: blending only the finest two levels still visits every vertex for its
  level, and height-only blending saves only the cheap shade lerp. Dropping the x24 split distance (R14) lowers the vertex count;
  that would help any form.

## 5. Not done

- Hill-top screenshots and the canyon-slope approach sequence (`tools\terrain-morph\tm-hill.ps1`, `tm-slope.ps1` / `tm_slope.py`,
  F6, the slope at (7125, 43475) found offline, start (6975, 43735) yaw 150): written and dry-run, never booted. The console was
  withdrawn from this lane at 07:31 (the nitro-mp LAN host).
- Clean F6 cost rows of the final build: queue e ran plain r1 (118.3), base r1 and on r1 only, on the Morton build. Not repeated.
- The cockpit morph without the instrument (tick-morph in cockpit) was not run. On the cockpit's 6.5k vertices the cost scales down
  (~1 ms), but it is unmeasured.
- The stateless form (s.4): designed, not built.

## 6. Recommendation

**Do not ship this build as a default and do not put it in the release candidate.** It removes the pop: per split, 217 -> 2.2 px at
the 95th percentile, and shade 78 -> 0.9 grey levels. But it costs ~27 fps in the no-dashboard view and an unmeasured ~1 ms in the
cockpit. Next: build the stateless form (s.4) behind the same switch with the same band (0.25 of the split distance, 40 m floor),
re-run the F6 rows here (pop per split and the clean cost against plain), and promote it only if it matches these pop numbers at
<= 1 fps. Flat split: off (no vertex or fps gain; keep the code for the record). The staged set (`<lab>\builds\terrain-morph-20261021\stage`)
is the measured build. If the owner wants to judge the look now, it can be driven at lab exp-morph `PLAY-TICK-MORPH.bat` (or
the stage copied over a release-candidate-shaped folder). Expect 90 fps where the plain build gives 118 in F6, and closer to plain in
the cockpit.

## 7. Files

- Code: i76-everywhere `music-fix/terrainmorph.c` (610ef86, 32751d4, 992cb8f, 8107233 / 769b8e2 discarded, f613b78 = final), strlkproxy.c 3 lines (610ef86).
- Builds, stage, MD5SUMS, README: `<lab>\builds\terrain-morph-20261021\`. Stage: `Interstate 76\STRLKUP.DLL` d3e24caa2a7e6c9de9ba4c925607e946,
  `Interstate 76\presets\tick19-42-morph.psd1` 8cda451c2b4affe48fef59741aaf267d, `PLAY-TICK-MORPH.bat` b841aecfc771c391d775164d133ed294.
- Runners: `<lab>\tools\terrain-morph\` (tm-queue.ps1, tm-route.ps1 / tm_drive.py, tm_tab.py, tm_events.py, tm-hill.ps1, tm-slope.ps1 / tm_slope.py, mk-*.py).
- Captures: `<lab>\captures\morph-20261021\` (`route` cockpit, `f6-final` the no-dashboard rows used above, `route-f6-d` /
  `route-f6` raw F6 queues, `phys`, `pilot-v1` = the first evening's three cockpit rows on the pre-floor build).
- Lab copy: `<lab>\exp-morph` (its STRLKUP.DLL = d3e24caa; the candidate's proxy kept as `STRLKUP.DLL.8f8da929-candidate`).
