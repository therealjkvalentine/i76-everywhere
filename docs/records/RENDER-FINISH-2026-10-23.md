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
  sitting's rf-cbase row at 99.1 fps was the boot right after the scott-build gate's display tests; void.) CRASH 0 in every boot.

N = 150 m: at road speed (~30 m/s) a bush takes ~5 s to come in, and the admission line sits 450-2300 m out, where a bush is a few
pixels; a shorter N would be a quick dissolve, a longer one keeps many far bushes half-transparent.

## 4. Final configuration and install

`exp-polish2\Interstate 76\presets\OWNER-2300-ALL.psd1` (edited in place, comments kept; lab commit below): `I76_TERRAIN_MORPH_BIG`
commented out with the reason, `I76_TERRAIN_MORPH_NEAR = '100'`, `I76_CLUTTER_ALPHA_FADE = '150'`, Summary updated. Everything else as
the owner's afternoon picks.

Build: `builds\nitro-port-20261021\build.ps1 -Tag rf-4c64917 -Ref 4c64917` (latest main at the time: this lane's a8f694a plus the
Nitro-port lane's c349c82 / 314aff8 and the scott-build records), **md5 6e4e7c49fbea42a6e4eda6a620abac32**.

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

## 5. Scott's full zip

All three passed, so the private zip was refreshed. Stage folder `downloads/scott-full/Interstate76-i76e-ALL-20261023` (it matched the
old zip file for file, 543 entries): `Interstate 76/STRLKUP.DLL` -> 6e4e7c49, `Interstate 76/presets/OWNER-2300-ALL.psd1` -> the final
preset (md5 375425b7, = exp-polish2's). New zip **`Interstate76-i76e-ALL-20261024.zip`** (543 entries, same order and top folder,
440,767,896 bytes, md5 8535ee98e2ce34af8da3ce2dda1632ba); the old `...-20261023.zip` kept. Its README still dates the build 2026-10-23.

Boot from a fresh unzip through its own `PLAY-T05.bat` (fit-and-play -> PLAY-i76.ps1 -> i76.exe; I76_MUTE + start-mute-watch, own shm
suffix, under the console lock; `tools/render-finish/rf-zipboot.ps1`): T05 drawn after 50 s (`downloads/scott-full/test/boot-20261024/t05.png`,
the mission's opening camera, bushes keyed), CRASH 0, the log carries the new lines (`no blend nearer than 100 m; 64+ levels stock`,
`clutter-alpha: on`, shade-smooth, feather, density 0.50). A first try without bringing the window to the foreground drew black (the
game does not render inactive); the script now does what proxy-run does. The unzip was deleted afterwards (486 MB).
