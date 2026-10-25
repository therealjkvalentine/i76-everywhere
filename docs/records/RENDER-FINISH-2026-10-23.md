# Render finish 2026-10-23 night: the far flicker, the near "morph", bushes fading in

Overnight lane on the owner's verdict (~16:30) on lab exp-polish2 `presets\OWNER-2300-ALL.psd1` (SMOOTH, stateless morph 0.25 / SHADE 3 /
BIG 2, TEX 8, SPARSE 0.5 / 450, FEATHER fog 0.75 + alpha, 2300 m): near and mid range "really, really good", SPARSE great, FEATHER "about
perfect". Three things left:

1. "Flickering between light and dark on the FURTHEST drawn textures."
2. "Still seeing morphing pretty close (maybe the texture print, not the altitude)."
3. Bushes pop in: fade them in.

The lane ran in two sittings. The first (stopped mid-run) committed 9fe3510 (`I76_TERRAIN_MORPH_NEAR` + the instrument's render-finish
columns), ran 14 ridge-route boots (`rf-*`, below) and left the clutter alpha fade written but untested and uncommitted. The second
sitting (this record) analysed those boots, committed the fade (b43b39a), ran the bush boots and the final configuration, and
installed. Data: lab `captures\terrain-pops-20261023\rf-*` (frames.npy, morph.csv, captures), `tools\far-edge\runs\*-rf-*`,
analysis scripts `tools\render-finish\` (rf_bands.py, rf_farflash.py, rf_dis.py), runner `rf-run.ps1`.

## 1. The far flicker: I76_TERRAIN_MORPH_BIG=2, re-parented at every root-square move

**Cause.** The terrain quadtree's root square is rebuilt from the view's bounding box every pass: 0x4929b0 takes the box's min corner
`and 0xffffffe0`, `sub 0x20` (0x492cb9..0x492cd1), so the root origin moves on a **32-sample (160 m) grid** while driving (about twice a
second on the ridge route). A vertex's level is the lowest set bit of its coordinate *relative to the root*; that is root-invariant only
below 32, i.e. for edges under 64 samples. Every vertex on a 64+ sample edge gets new parents (and a new blend distance) when the root
moves. Stock does not care (those levels are always split, t = 1); `I76_TERRAIN_MORPH_BIG=2` blends their shade toward their parents'
mean, so at each root move hundreds of far vertices change brightness at once and back again at the next move. This is the reason
75b8888 had left the 64+ levels at t = 1 ("their alignment follows the root square: a blend jumped as it moved"); BIG 1 / 2 came back
as an owner option on 2026-10-23 (7dd568c).

**Evidence, in-engine** (`I76_TERRAIN_MORPH_LOG` render-finish columns, ridge route, drive phase only, `rf_bands.py`; per pass, split by
whether the root square moved on that pass):

| run (n) | carried far vertices crossing a shade row, root-move pass / other pass | carried vertices with a one-pass shade jump >= 1/32 beyond 900 m, root-move pass / other |
|---|---|---|
| ALL = owner preset, BIG 2 (rf-all-1, -2) | **1210** / 3.1 | **588-667** (mean step 0.10 = ~3 stock rows) / 0.0 |
| BIG unset (rf-big0-1, -2) | 7.0-7.8 / 2.3-2.4 | 0.4 / 0.0 |
| no morph (rf-nomorph-1) | 7.2 / 1.7 | 0.9 / 0.0 |

The jumps are 100 % on root-move passes: none between moves. Of the >= 1/32 jumps, 83 % beyond 1600 m and 22 % at 900-1600 m sit on
64+ edges themselves; the rest are their children (a child's shade blends toward its parents' mean, which just moved).

**Evidence, on screen** (the same boots' 1/4-scale capture stacks re-mined, `rf_farflash.py`: mean |delta luma| over the far ground band,
rows 195-228 x cols 240-600 of 360 x 860 minus the reticle, minus the frame's median block delta for the car's own motion; a pair
"spans a root move" when a morph pass with root_moved = 1 falls between its two QPC times):

| run | root-move pairs | share above the other pairs' p95 | excess over the neighbouring pairs (median) |
|---|---|---|---|
| rf-all-1 / -2 | 49 / 46 | 33 % / 28 % | 1.51 / 0.62 |
| rf-big0-1 / -2 | 44 / 43 | 18 % / 21 % | 0.82 / 0.34 |
| rf-tex24-1 / -2 | 45 / 52 | 38 % / 37 % | 0.84 / 1.06 |
| rf-noalpha-1 / -2 | 43 / 47 | 37 % / 34 % | 1.31 / -0.21 |
| rf-nomorph-1 | 19 | 5 % | -0.33 |

The screen agrees in direction but is the weaker instrument (the root moves when the view box changes, i.e. on curves, where the screen
changes anyway; BIG 0 keeps a residual that matches the stock's own view-edge vertices, ~67 new at every root move in all runs).

**The other suspects, cleared by the same boots:** the far texture-level ring (`I76_TERRAIN_TEX 24` moves it from 1600 to 1920 m and
cuts switches per pass 1.5 -> 0.7, but the root-move flash stays at 37-38 %), the fade band (`I76_GLIDE_FOG_ALPHA` unset: 34-37 %, as
ALL), SMOOTH (per vertex, root-invariant by construction: terrainpops.c multiplies each vertex's own shade).

**Fix: `I76_TERRAIN_MORPH_BIG` unset** (key; no code). No root-invariant subset of the 64+ blend exists (the 32-sample grid is exactly
the 64-sample edge), and a stateful ease across root moves would need the per-vertex tables the stateless morph exists to avoid. What
BIG 2 bought is the far big tiles' shade drawn as their parents' mean (a softer far shade); with SMOOTH the 32-row steps it was hiding
are gone anyway. BIG 0 also cuts far shade-row crossings between moves (2.3 vs 3.1 per pass).
**After** (rf-final-1 / -2, section 4's configuration on the 4c64917 build): far carried vertices crossing a shade row on a root-move
pass **8.9 / 8.6** (other passes 2.2 / 2.3), one-pass jumps >= 1/32 beyond 900 m on a root-move pass **0.5 / 0.4** - the stock's own
numbers (7.2; 0.9). **The screen instrument does not resolve this fix**: on the far band (and on a narrower band at the far edge only,
rows 195-212, `rf_farflash_edge.py`) ALL, BIG 0 and the final rows all fall inside each other's run-to-run spread (root-move pairs
above the others' p95: ALL 33 / 28 %, BIG 0 18 / 21 %, final 28 / 33 %; edge band 8 / 11, 14 / 9, 12 / 12 %; n 2 each). At 1/4 scale,
~24 Hz and 80 px blocks it sees curves, not a few-percent brightness step on distant vertices. The attribution and the fix rest on the
in-engine census; **the owner's eye on the far ridge is the open check**.

## 2. Near "morphing": I76_TERRAIN_MORPH_NEAR=100

The morph moves a vertex's height, and the UVs are per vertex, so the ground texture's print slides with it: close to the car that
reads as the texture moving, not the land. `I76_TERRAIN_MORPH_NEAR=<m>` (9fe3510): a vertex's height and shade bands are cut to end
at m (t = 1 there); a vertex whose split distance is within m of it is not blended at all (it pops as stock). Ridge route, instrument
columns `slide_px_100` (carried vertices moving <= 4 px in one pass within 100 m: the slide) and `jump_px_100` (snaps > 4 px within 100 m):

| run | slides within 100 m p50 / p95 / p99 / max px | snaps within 100 m p95 / p99 / max | under 300 m: smooth px/pass, snaps px/pass (p99) |
|---|---|---|---|
| ALL (rf-all-1 / -2) | 1/5/8/14, 1/4/8/16 | 0/0/162, 0/0/163 | 7.3 / 0.6 (15), 6.8 / 0.5 (15) |
| NEAR 60 (rf-near60-1) | 0/2/4/7 | 4/10/84 | 7.1 / 0.8 (14) |
| **NEAR 100 (rf-near100-1 / -2)** | **0/0/0/0, 0/0/0/1** | **4/11/82, 4/11/90** | 7.2 / 1.0 (19), 7.2 / 1.0 (18) |
| NEAR 150 (rf-near150-1) | 0/0/0/0 | 4/10/83 | 5.9 / 1.4 (23) |
| no morph = stock pops (rf-nomorph-1) | 0/0/0/0 | 4/10/83 | 1.1 / 4.5 (58) |

**Pick: 100 m.** At 100 the slide inside 100 m is gone (n 2) and the snaps there are the stock error-step jumps, no worse (p99 11 vs
10, max 82-90 vs 83); 100-300 m keeps the full morph (7.2 px/pass of smooth motion, the same as ALL) and a quarter of the stock's snap
motion. 60 still slides (p99 4 px); 150 trims the 100-300 m slide a little (5.9) at more snaps (p99 23). If the owner still sees the
print slide at 100-150 m, 150 is the next value (n 1). rf-near60-2 never ran (the first sitting stopped), rf-near150-2 never ran,
rf-nomorph-2 is void (fps 2993: the capture saw no game; display or focus), so the stock row is n 1.

## 3. Bushes fade in: I76_CLUTTER_ALPHA_FADE=150

**What it does** (b43b39a, fixed in a8f694a; Gold only, needs I76_CLUTTER_FADE or _DENSITY). Stateless, like the morph: the SPARSE keep rule
admits a (template, cell) pair while its cell distance d < d_adm = fade x sqrt(65535 x density / h16) (h16 = the pair's hash; capped
at I76_CLUTTER_DIST), so its alpha is clamp((d_adm - d) / N). The cull call 0x45c634 (the template loop's current entry at [ebp - 8],
checked: set at 0x45c50c, advanced at 0x45c81f) records each visible instance's record-pool start and alpha; the hardware flush's
polygon draw 0x4260d0 at 0x48fb7e finds the current record (type 4 = a face) by binary search and draws it with blend
SRC_ALPHA / ONE_MINUS_SRC_ALPHA and alpha = TEXTURE x ITERATED, the vertex alpha set in the grDrawTriangle hook.

**First result: black squares** (rf-caf150, rf-caf1000 on b43b39a, `runs\zoom-rf-clutter-hill.png`). Not shadows (rf-caf1000-noshadow:
the same with I76_SHADOW_DIST unset). A trace (`I76_CLUTTER_ALPHA_TRACE=400`, rf-ctrace) showed ZGLIDE's own op for a bush record:
acombine SCALE_OTHER(TEXTURE) x ONE, blend SRC_ALPHA / ONE_MINUS_SRC_ALPHA, **grChromakeyMode(1)**, 2 triangles. The chroma call went
through the feather's hook, which re-ran fe_apply_state; when the feather override had been on for the terrain record before
(g_fe_opaque = 1), its "restore" set Blend ONE / ZERO + ZGLIDE's alpha combine. On this driver the key is carried by the alpha blend
(the keyed texels have alpha 0), so an opaque blend shows them as black. **Fix (a8f694a):** fe_apply_state stands aside while the bush
fade holds the state, and the fade takes ownership at begin (g_fe_opaque = 0); fe_cl_end hands ZGLIDE's last requests back.

**After** (rf-tr2 = a8f694a's tree, valley road = T05 mission start, fe-run.ps1, exp-faredge with OWNER-2300-ALL):
- rf2-caf1000 (exaggerated: every bush part-transparent): keyed, faint bush sprites, no squares (`runs\zoom-rf2-s01-t04.png`: base /
  b43b39a / a8f694a; `zoom-rf2-detail.png`: a bush at low alpha keeps its shape).
- rf2-caf150 x 2: bushes as base, no squares (`zoom-rf2-150-s04-t16.png`, base above, fade below). Log per 600 frames: ~396 k instances,
  ~137 k fading, every fading face record drawn under the held blend, 0 past the list.
- fps (render, 12 windows after the first three; the 120 Hz cap hides fps below 8.33 ms of work): base 120.0 / 120.0 (work 8.33 /
  8.33 ms), fade 150 **118.5 / 119.3** (work 8.45 / 8.38 ms, p10 111.8 / 114.7): about +1 % work. n 2 each, interleaved. (The first
  sitting's rf-cbase row at 99.1 fps was the boot right after the tester-build gate's display tests; void.) CRASH 0 in every boot.

N = 150 m: at road speed (~30 m/s) a bush takes ~5 s to come in, and the admission line sits 450-2300 m out, where a bush is a few
pixels; a shorter N would be a quick dissolve, a longer one keeps many far bushes half-transparent.

## 4. Final configuration and install

`exp-polish2\Interstate 76\presets\OWNER-2300-ALL.psd1` (edited in place, comments kept; lab commit below): `I76_TERRAIN_MORPH_BIG`
commented out with the reason, `I76_TERRAIN_MORPH_NEAR = '100'`, `I76_CLUTTER_ALPHA_FADE = '150'`, Summary updated. Everything else as
the owner's afternoon picks.

Build: `builds\nitro-port-20261021\build.ps1 -Tag rf-4c64917 -Ref 4c64917` (latest main at the time: this lane's a8f694a plus the
Nitro-port lane's c349c82 / 314aff8 and the tester-build records), **md5 6e4e7c49fbea42a6e4eda6a620abac32**.

| row (route, n) | result |
|---|---|
| rf-final-1 / -2 (ridge, morph instrument) | fps 87.1 / 88.4 (ALL on 9fe3510: 86.2 / 86.8); far root-move jumps gone (s.1); slides within 100 m p99 0, max 1 px; snaps within 100 m p95 4 / p99 10 / max 84, 83 (stock 4 / 10 / 83); under 300 m smooth 6.7 px/pass, snaps 0.9 |
| rf-smoke (valley, exp-faredge with the final preset copied in, proxy-run) | 120.0 fps (cap); CRASH 0; every key's line present: terrain-morph "no blend nearer than 100 m; 64+ levels stock (t = 1)", clutter-alpha on (150 m), shade-smooth on, glide-fog + alpha, clutter-dist (density 0.50, fade 450), terrain-lod x24, terrain-tex x8, object-lod, shadow-dist, road-tex / -dist, far-clip 2300, mirror-far / -lod / -tex / -m16 / -pal / -every, sky-mirror, jump-nose 0.91, sim-tick, music retail + resume, coop, fix-health / -label, cam-ground, terrain-hull, zglide-tmufix, glide-refresh 120, fade-no-flip, sign-sound |

Installed into exp-polish2 with `tools\far-edge\fe-install.ps1` at 23:04 (no game running then): STRLKUP.DLL dd53b37b -> **6e4e7c49**,
the old one kept as `STRLKUP.DLL.dd53b37b`, md5 verified after the copy. The OWNER-2300 launchers' title text still says "big blend";
the preset is what applies.

Housekeeping found on the way: the stopped sitting had left exp-rebase with its test DLL installed (6208d3ad, original kept as
`.pretest`) and both a lab `.console-owner` and exp-rebase `.console-test.lock` from its dead pid 41800; the DLL was put back (8f8da929)
and the locks moved aside (`*.stale-20261023-*`). tp-run.ps1 gained `-HaveLock`; the lane's runner `tools
ender-finish
f-run.ps1`
follows the .fps-queue / .fps-lock rule, one boot per hold, 30 s apart. Mute: proxy-run's own (I76_MUTE + start-mute-watch on its pid;
CONSOLE-LOCK.md retired the global `mute-proc -Watch` the brief named).

## 5. The tester's full zip

All three passed, so the private zip was refreshed. Stage folder `downloads/tester-full/Interstate76-i76e-ALL-20261023` (it matched the
old zip file for file, 543 entries): `Interstate 76/STRLKUP.DLL` -> 6e4e7c49, `Interstate 76/presets/OWNER-2300-ALL.psd1` -> the final
preset (md5 375425b7, = exp-polish2's). New zip **`Interstate76-i76e-ALL-20261024.zip`** (543 entries, same order and top folder,
440,767,896 bytes, md5 8535ee98e2ce34af8da3ce2dda1632ba); the old `...-20261023.zip` kept. Its README still dates the build 2026-10-23.

Boot from a fresh unzip through its own `PLAY-T05.bat` (fit-and-play -> PLAY-i76.ps1 -> i76.exe; I76_MUTE + start-mute-watch, own shm
suffix, under the console lock; `tools/render-finish/rf-zipboot.ps1`): T05 drawn after 50 s (`downloads/tester-full/test/boot-20261024/t05.png`,
the mission's opening camera, bushes keyed), CRASH 0, the log carries the new lines (`no blend nearer than 100 m; 64+ levels stock`,
`clutter-alpha: on`, shade-smooth, feather, density 0.50). A first try without bringing the window to the foreground drew black (the
game does not render inactive); the script now does what proxy-run does. The unzip was deleted afterwards (486 MB).

## 6. 2026-10-24: dirt roads in the mirror (I76_MIRROR_M16_ROADS)

Owner 2026-10-24: "The mirror palette match issue also applies to dirt roads - in software they are dark brown, accelerated light brown,
so the mirror doesn't match (like the terrain didn't before)."

**Where.** `renderer_QueueRoadsAndDecals` 0x48e900 picks each segment's texture at **0x48ec53**: `0x471f00(&0x59c3a0[idx], cam)`, idx
from the segment's near slot set (midpoint z < 60 m x `I76_ROAD_TEX`) or far set (+10). Each entry is a {8-bit art, .m16 art} pair,
the same layout as the terrain set; 0x471f00 hands the kind-0 (8-bit) mirror bitmap the 8-bit drawing. MIRROR-DETAIL s.6 had noted
"the road textures' two variants happen to match" - true of the asphalt, not of the dirt road (8-bit dark brown, .m16 light brown with
ruts).

**Fix** (music-fix/mirrordetail.c, b38530b + 6b50fb9 + dfc456c): that call is chained; for the mirror camera the segment gets the
.m16 road art quantised into the display palette by the same `md_m16_copy` the terrain uses (no blur; the blur stays sky-only). Key
`I76_MIRROR_M16_ROADS`, **default on whenever `I76_MIRROR_M16=1`** (=0 keeps the 8-bit road art), so OWNER-2300-ALL needs no new key.
Gold only: the Nitro site is not in sites_nitro.h, the proxy logs "roads stay the 8-bit art" there. The copy cache went 16 -> 64
entries (T09 alone: 5 terrain levels + 14 road textures), and every entry now carries a fingerprint of its source (header, 32 spread
texels, 16 palette words): the road sets are not in 69c4a54's mission signature (7 terrain pointers + palette), so a new mission's road
art landing at an old address is caught by the fingerprint and the stale copy released. The dump census line gained
`mirror road segments N (.m16 copy M)`.

**Evidence** (lab, exp-faredge, OWNER-2300-ALL, T09 = the mostly-dirt mission: RSEG sections 2066 dirt / 249 paved; T01 925 / 1853):
`autotest\runs\mirror-detail\RF2-t09-roads-before-after.png` (dumps 210 / 300 flipped to screen orientation; left `ROADS=0`, the dark
brown 8-bit dirt road; right default, the light brown rutted .m16 road as in the main view), per-run montages with the main-view
crop: `20261024-055144-rf2-t09-roads0-dump\montage.png`, `20261024-055241-rf2-t09-roads1-dump\montage.png`. Log of the on-run: 14
`road .m16 ... (64x32 / 32x16) quantised` lines, census 120-152 mirror road segments per dumped redraw, all 100 % swapped; CRASH 0.

Cost (T09, OWNER-2300-ALL in exp-faredge, proxy rf2-dfc456c md5 957cf2c3, drive 15 s, proxy `fps:` 5 s windows; frame_stats counts sim
ticks under the tick preset, so the proxy windows are the display rows): ROADS=0 119.5 / 119.8 fps, work 8.35 / 8.33 ms; default (roads
on) 120.1 / 119.8 fps, work 8.31 / 8.33 ms (n 2 each, 120 Hz cap). Cost: none measurable.

## 7. 2026-10-24: how far can I76_TERRAIN_LOD go at far clip 2300 (paused at ~07:20: owner at the console)

Owner: "Is there no simple option to move the terrain detail distance further out and test when it impacts framerate?" The lever is
`I76_TERRAIN_LOD` (split distance x N, height-error threshold / N; the preset runs 24). Sweep 24 / 32 / 48 / 64 on OWNER-2300-ALL (far
clip 2300), proxy rf2-dfc456c (md5 957cf2c3, = main dfc456c), lab runner `tools\render-finish\rf2-run.ps1` (one boot per console hold,
shared with the RC and Nitro-MP lanes), step list `rf2-steps-main.txt`.

**Where the finest terrain reaches.** The REBASELINE s.7 trace measured the rings at LOD 24 and saw them move x1.41 at LOD 48: the rings
scale with sqrt(LOD), not LOD (d^2 is compared with (2h)^2 x A). Finest tiles (10 m):

| LOD | forced-split ring (every 10 m tile) = 12.9 x 10 m x sqrt(L/24) | split-distance ring (steep 10 m tiles) = 18.3 x 10 m x sqrt(L/24) | 160 m tiles forced |
|---|---|---|---|
| 24 | 129 m | 183 m | 2070 m |
| 32 | 149 m | 211 m | 2390 m (past the far clip) |
| 48 | 183 m | 259 m | 2928 m |
| 64 | 211 m | 299 m | 3380 m |

So doubling the cost-side knob (24 -> 48) buys 1.41x the full-detail radius (129 -> 183 m).

**Rows.**

| LOD | ridge route fps median (a / b) | mean | 1 % low (1000 / p99 frame) | vs 24 (median) | ridge vertex peak | crash check t01 / t05 (hood, binoculars, zoom x8) | vertex peak: drive / binoculars t01, t05 |
|---|---|---|---|---|---|---|---|
| 24 | 105.2 / 102.8 | 91.4 / 89.2 | 47.2 / 45.2 | - | 6,633 | none / none (t01 n 2, t05 n 2) | 7,551 / 18,805; 6,557 / 18,136 |
| 32 | 100.2 / 91.7 | 87.1 / 81.0 | 46.9 / 40.4 | **-7.7 %** (n 2; a alone -3.6 %) | 7,074 | none / none (n 1) | 8,311 / 19,310; 6,977 / 18,338 |
| 48 | 90.4 / 85.9 | 80.2 / 77.2 | 46.3 / 42.2 | -15 % | 8,099 | none / none (n 1) | 9,603 / 19,866; 8,052 / 18,554 |
| 64 | 79.9 / 82.0 | 73.9 / 75.9 | 43.5 / 46.4 | -22 % | 9,283 | none / none (n 1) | 10,714 / 20,519; 9,196 / 18,861 |

Ridge = the lod-sweep / terrain-pops T05 route (tp-run.ps1, exp-rebase, its 30 Hz screen capture running in every row alike), frames from
I76_FRAME_LOG; data `captures\terrain-pops-20261023\rf2-ridge-*`, table `tools\render-finish\rf2_ridge_tab.py`. Crash checks =
owner-farclip-crash's views via `rf2-crash.ps1` on exp-faredge with a 20 ms read of [0x6442ec] and phase marks (`rf2_vsampler.py`,
`rf2_crash_tab.py`); data `autotest\runs\render-finish-20261024\rf2-crash-*`, lines in `tools\render-finish\rf2-results.txt`.

**Findings.**
- **The crash does not bite first.** Binoculars at 2300 m peak at 18-20.5 k terrain vertices from LOD 24 to 64 (the guard's 28,000 and
  the int16 32,767 are far off); the binocular view's count barely moves with LOD (18.8 k -> 20.5 k on t01) while the normal view's grows
  ~40 % (7.6 k -> 10.7 k). No CRASH line, no guard refusal in any of the 10 boots. (The binocular crash on record was at 2500 m.)
- **Frame rate bites first.** Every step up costs more than 5 %: 32 is -7.7 % on the median at n 2 (the two 24 boots differ by 2.4 fps,
  the two 32 boots by 8.5 - the b row may carry another lane's load; n 3 queued), 48 -15 %, 64 -22 %. The 1 % low barely moves (40-47
  everywhere): the low frames are something else (the route's spikes), the median pays for the vertices.
- **Chosen value: 24 stays** (the only value under the 5 % line so far). OWNER-2300-ALL is not changed. A cheaper way to reach the full
  detail farther would be LOD_A alone (the split distance; REBASELINE R13: LOD_A 24 cost more than LOD_B 24), not a bigger LOD.

**Resumed 08:32-10:53 (main: RESUME), then stopped by the owner's rule (keep this desktop's console free) - results as measured:**

| LOD | crash check t01 / t05, n | binocular peak t01 / t05 | drive peak t01 / t05 | ridge fps |
|---|---|---|---|---|
| 24 | none / none, n 2 / 2 | 18,805 / 18,137 | 7,551 / 6,550 | as above (n 2) |
| 28 | none / none, n 2 / 2 | 18,991 / 18,271 | 7,916 / 6,745 | **not measured** (both ridge boots failed, below) |
| 32 | none / none, n 2 / 2 | 19,300 / 18,334 | 8,312 / 6,981 | as above (n 2) |
| 48 | none / none, n 2 / 2 | 19,741 / 18,565 | 9,601 / 8,056 | as above (n 2) |
| 64 | none / none, n 2 (t01) / 1 (t05) | 20,268 / 18,844 | 10,727 / 9,196 | as above (n 2) |

LOD 28's finest rings: forced split 139 m, steep 198 m (+8 % over 24). Its frame rate is **unmeasured (n 0)**: the four resumed ridge boots
(28 a / b, a third 24 and 32) each stopped ~15 s in with `god-shm.py: no trainer block (magic 00000000)` - tp-run's drive block runs
god-shm.py inside proxy-run (ErrorActionPreference Stop), and that reader found no trainer block this time though the same script and
DLL ran eight ridge rows at 06:00-07:10 (suspect: the shm suffix the reader does not follow; not investigated, console use ended). Their
frames.csv hold ~220 boot frames only and are not rows. By the ring maths 28 sits between 24 and 32 (-7.7 %), so it may or may not fit
under 5 %; **28 was not picked and OWNER-2300-ALL keeps 24.** No CRASH / EXCEPTION line and no vertex-guard refusal in any of the 19 crash
boots; the far clip need not drop for a higher LOD (the crash never bit). Persisted mute cleared for exp-faredge and exp-rebase
(`unmute-persisted.ps1`: not muted on both devices); keep-display and the queue line removed.

**Install:** not done by this lane (main: the stability lane, fixing a Gold mission-change crash at Strlkup.dll+0x3D3B1 that may sit in
mirrordetail.c's per-mission cache including this lane's road fingerprints, installs a combined build). The roads change is default-on
under the preset's existing `I76_MIRROR_M16 = '1'`; the lane's own proxy was rf2-dfc456c (957cf2c3).
