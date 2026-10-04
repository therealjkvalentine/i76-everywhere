# Soak: best-wide and exp-detail-16 across the trip missions (2026-10-03, lab sandbox)

Backlog P1-14 follow-up. The owner's daily driver runs `presets\best-wide.psd1` (widescreen Hor+ `I76_ASPECT=3440x1440`,
terrain x8, terrain textures x8, objects x8, bushes 300 m, shadows 200 m, road textures x8, **roads 1800 m**, far
clip 1800, 120 Hz). Before this soak it had only been run on t01. The far-clip soak of 2026-10-02 covered t01-t17
without the detail switches.

**Where:** `C:\Users\james\i76-uncap-lab\game` only, with `dgVoodoo.aspect-wide.conf` swapped in for each batch.
`i76.exe` md5 85de44a7 (file-patched far clip 1800, pools x16). Every run used proxy `music-fix\Strlkup.dll` built
**10-03 12:38:08, md5 0b18d77c**, installed and restored per run by proxy-run. At the end the folder's conf
(6be07be8), STRLKUP.DLL (54f2de9d), every save*.cmp, savegame.dir, *.def, *.spc and input.map were byte-identical to
the backup taken before the first run (`preset-soak.ps1` checks the saves under the lock on every batch).

## Result

1. **New crash (ceiling #4): `I76_ROAD_DIST=1800` overflows the depth-bucket span-node pool. It faults at
   `exe+0x9051B` and kills the game on t11 every time.**
   - The fault is a `fstp [eax+4]` write to 0x7EF40004 in `0x490470` (`eax` = 0x7EF40000, a page end).
   - `0x490470` is called from the depth queue `0x48fe10` for kind-1 and kind-0xb records. It takes one 16-byte node
     from `[0x6543b8]` for each 1 m depth bucket a polygon spans, and nothing checks the end of the pool.
   - The pool is one `0x1f400` B block, about 8,000 nodes (`push 0x1f400` at 0x48f9d6 in `0x48f9b0`). It is reset per
     flush and is **not** one of the pools that `I76_FAR_CLIP` (x16) or `I76_CLUTTER_DIST` enlarge.
   - The roads drawn out to 1800 m are long polygons that span hundreds of buckets each. At the fault, the loop is
     filling buckets 1665 to 1734 (t01) or around 933 (t11).
   - **Bisect on t11 (one boot per variant, 2 binocular cycles each):**
     - The full preset crashes.
     - Removing any single switch other than roads still crashes: `I76_TERRAIN_LOD`, `I76_ASPECT`,
       `I76_SHADOW_DIST`, `I76_CLUTTER_DIST`, `I76_OBJECT_LOD`, `I76_ROAD_TEX` or `I76_TERRAIN_TEX`.
     - **Removing only `I76_ROAD_DIST` (450 m, stock) gives no crash.**
     - The all-detail-off control gives no crash.
     - Sweep: 600 m no crash, 900 m crash (that one was survived), 1200 m crash, 1500 m crash.
     - Report files: `autotest\runs\preset-soak\20261003-133513-bisect-best-wide-t11.md` and `...135327-...md`.
   - **Survival is not guaranteed.** On t11 the exception was fatal in 2 of 2 soak boots, at frame 143 or 224. In the
     other missions the game kept running after the logged fault: frames kept advancing and the clutter log continued.
     The proxy's handler is vectored (first chance) and logs only once, so a handler further down caught those cases.
     Either way, the frame lost its draw. On t16 the camera was left in mode 6 for the rest of the run.
2. **The int16 terrain-vertex ceiling still has the same margin.**
   - Measured peaks of `[0x6442ec]`: cockpit 4.7k-7.2k, hood 17.0k-17.9k, binoculars 16.9k-18.1k. Glances are the
     same as cockpit.
   - The binocular peak is 55% of 32,767 on every mission and under both presets. Terrain x16 (exp-detail-16) did not
     change it: hood and binoculars stay on the same tessellation level (~17k) as plain far-clip 1800, which measured
     17,068 on 2026-10-02.
   - Terrain LOD lifts only the cockpit, by one level (1.4k to ~5.5k).
   - No mission reached the next level (~65k = crash). The ceiling is not what fails here.
3. **Frame time.**
   - Cockpit, hood and glances hold 118-120 fps with p99 9-17 ms.
   - **Binoculars run at 55-80 fps** (p99 15-31 ms) under both presets. This is a base cost, not the detail set: the
     t01 bisect gave 72-77 fps with each detail switch removed and **79 fps with all of them off** (3 cycles per
     variant). The control was repeated twice with a spread of about 1 fps.
   - The first best-wide pass (13:05-13:30, with other agents interleaving on the console) also showed 200 ms hitches
     on t08-t10 and binoculars at 15-40 fps. **This did not reproduce** in the re-run at 14:08 (t05, t08, t09, t10: cockpit
     118-120 fps, p99 9-10 ms; binoculars 56-67 fps). Treat the first-pass binocular and hitch numbers as environment
     noise.

**Proposed safe values:**
- Set **`I76_ROAD_DIST` to 600 in best-wide** (and in exp-detail-8 / exp-detail-16), or remove it (450 = stock),
  until the node pool is enlarged. 600 was clean on t11 in 1 of 1 runs, so it is not a measured margin.
- Everything else in both presets passed: far clip 1800, terrain x8/x16, textures x8, objects x8, shadows x4, road
  textures x8, bushes 300/400 m, aspect 3440x1440.
- **The real fix is in the proxy**, not done here: enlarge the span-node pool with the other pools (`push 0x1f400` at
  0x48f9d6, imm at 0x48f9d7, x16 = 2 MB), or clamp the span in `0x490470` to the pool's free space. After that,
  re-run `binoc-bisect.ps1 -Mission t11 -Variants full` and then this soak.

## Table: best-wide (widescreen conf), one row per mission

Phases per mission (`autotest\soak-phases.ps1`):
1. A screenshot at the start position.
2. Cockpit idle, 10 s.
3. Hood (F6), 5 s.
4. Binoculars (B), 5 s.
5. Glances left, right, up and down (Grey arrows), 2 s each.
6. Cockpit driving with W held, 10 s.

Columns: fps / p99 are for the cockpit phase; "worst" is the worst phase p99. Verts are peaks for
cockpit / hood / binoculars. The camera modes seen confirm that the keys landed: 0 cockpit, 1 hood, 2 binoculars; a
glance-left screenshot shows the side window.

| mission | survived | cockpit fps | cockpit p99 ms | worst p99 ms (view) | verts c / h / b | crash: offset, view | screenshot |
|---|---|---|---|---|---|---|---|
| t01 | yes (fault logged) | 101.8 | 11.9 | 92.3 (binoc, 1st pass) | 5.6k / 17.5k / 17.9k | exe+0x9051B, cockpit right after binoculars off (2/2 runs: smoke + pass); 0/6 binocular cycles in the bisect | captures\soak\20261003-124107\best-wide-t01.png |
| t02 | yes | 118.7 | 13.8 | 62.2 (binoc) | 5.2k / 17.3k / 17.0k | none | captures\soak\20261003-124107\best-wide-t02.png |
| t03 | yes | 117.7 | 15.1 | 43.0 (drive) | 5.7k / 17.6k / 18.1k | none | captures\soak\20261003-131640\best-wide-t03.png |
| t04 | yes | 112.1 | 16.7 | 74.7 (binoc) | 5.3k / 17.3k / 17.3k | none | captures\soak\20261003-131640\best-wide-t04.png |
| t05 | yes (fault logged) | 118.9 (re-run) | 9.3 | 18.4 (binoc, re-run) | 5.2k / 17.2k / 17.5k | exe+0x9051B, cockpit glance-right (2/2 runs) | captures\soak\20261003-140834\best-wide-t05.png |
| t06 | yes | 120.1 | 13.5 | 29.4 (binoc) | 5.0k / 17.0k / 17.3k | none | captures\soak\20261003-131640\best-wide-t06.png |
| t07 | yes | 119.7 | 12.3 | 33.5 (binoc) | 5.0k / 17.1k / 17.4k | none | captures\soak\20261003-131640\best-wide-t07.png |
| t08 | yes | 119.6 (re-run) | 9.8 | 24.8 (binoc, re-run) | 5.2k / 17.1k / 17.4k | none | captures\soak\20261003-140834\best-wide-t08.png |
| t09 | yes | 119.2 (re-run) | 9.6 | 25.1 (binoc, re-run) | 7.0k / 17.5k / 17.4k | none | captures\soak\20261003-140834\best-wide-t09.png |
| t10 | yes | 118.3 (re-run) | 10.0 | 30.9 (binoc, re-run) | 5.4k / 17.2k / 17.9k | none (starts in an external camera) | captures\soak\20261003-140834\best-wide-t10.png |
| **t11** | **NO: dies at boot** | - | - | - | - | **exe+0x9051B, cockpit, frame 143 / 224 (2/2 runs), fatal** | captures\soak\20261003-131640\best-wide-t11.png (desktop: the game was gone) |
| t12 | yes | 104.1 | 16.8 | 200 (glance-right, 1st pass) | 4.7k / 17.0k / 17.0k | none | captures\soak\20261003-131640\best-wide-t12.png |
| t13 | yes (fault logged) | 119.2 | 8.9 | 28.2 (binoc) | 5.1k / 17.1k / 17.7k | exe+0x9051B, cockpit right after binoculars off | captures\soak\20261003-132659\best-wide-t13.png |
| t14 | inconclusive | (946 fps, dt 0) | - | - | 5.3k all | none; the direct boot's Esc opened Spanner's Cafe and the mission never ran (as in the 2026-10-02 soak) | captures\soak\20261003-132659\best-wide-t14.png |
| t15 | yes (fault logged) | 120.0 | 8.5 | 15.7 (binoc) | 6.6k / 5.0k* / 17.4k | exe+0x9051B, cockpit at the start position (before the first phase) | captures\soak\20261003-132659\best-wide-t15.png |
| t16 | yes, but camera stuck | 120.1 | 8.5 | 10.1 (hood) | 5.3k / 17.9k / 5.5k* | exe+0x9051B **in hood view**; afterwards camera mode 6 for the rest of the run (B and glances had no effect) | captures\soak\20261003-132659\best-wide-t16.png |
| t17 | yes | 120.1 | 8.5 | 16.0 (binoc) | 5.0k / 4.7k* / 16.9k | none (starts in camera 5) | captures\soak\20261003-132659\best-wide-t17.png |

\* The view did not take: the hood key on t15/t17 landed while another camera was active (modes in the raw .txt).

Not covered: m01-m15, s01-s07 and a01 cannot boot directly through `I76_MISSION` (FARCLIP soak 2026-10-02: m01 dies at
frame 0) and need the menu route. Every screenshot also shows a Windows Defender Firewall prompt for
`game-alt\i76.exe`, which another agent's game raised. It was left alone (a security prompt is the owner's call), so
the owner-facing screenshots carry it.

## Table: exp-detail-16 (+ I76_ASPECT=3440x1440, widescreen conf) on five open-vista missions

The missions were picked from the best-wide screenshots: open flats or long sight lines. `I76_ASPECT` was added because
that is the worst case (the widest frustum) and how the owner would run it on this panel.

| mission | survived | cockpit fps | cockpit p99 ms | hood fps / p99 | binoc fps / p99 | verts c / h / b | crash: offset, view | screenshot |
|---|---|---|---|---|---|---|---|---|
| t04 | yes | 120.1 | 9.8 | 120.4 / 10.1 | 77.8 / 15.0 | 5.9k / 17.8k / 17.7k | none | captures\soak\20261003-140334\exp-detail-16-t04.png |
| t07 | yes | 120.1 | 9.8 | 119.2 / 11.2 | 71.6 / 16.5 | 5.8k / 17.7k / 17.8k | none | captures\soak\20261003-140334\exp-detail-16-t07.png |
| t12 | yes (fault logged) | 120.1 | 8.5 | 119.8 / 9.5 | 81.4 / 14.5 | 5.1k / 17.2k / 17.1k | exe+0x9051B, cockpit glance-right | captures\soak\20261003-140334\exp-detail-16-t12.png |
| t13 | yes (fault logged) | 120.0 | 9.8 | 117.8 / 11.2 | 68.0 / 18.2 | 5.8k / 17.5k / 18.0k | exe+0x9051B, cockpit right after binoculars off | captures\soak\20261003-140334\exp-detail-16-t13.png |
| t17 | yes | 120.0 | 9.2 | 107.4 / 13.3 | 72.4 / 16.0 | 5.3k / 17.1k / 17.0k | none | captures\soak\20261003-140334\exp-detail-16-t17.png |

exp-detail-16 also has `I76_ROAD_DIST=1800`, so it carries the same t11 crash. Its terrain x16 and bushes at 400 m added
no vertices in hood or binoculars and cost no frame rate here. The draw-record pool peaked at 313 KB, 11% of the 2.96 MB pool
that clutter enlarges, across all runs of both presets, and the clutter guard reported 0 refusals.

## Binocular frame-rate bisect (t01, roads 450 m unless noted, 3 binocular cycles per row)

| variant | binocular fps per cycle |
|---|---|
| best-wide minus ROAD_DIST (control, run 1) | 73.3 / 72.3 / 76.7 |
| same (control, run 2) | 73.0 / 72.0 / 77.0 |
| minus TERRAIN_TEX | 72.0 / 74.3 / 71.3 |
| minus OBJECT_LOD | 74.0 / 74.3 / 71.7 |
| minus TERRAIN_LOD | 76.6 / 78.3 / 76.0 |
| minus ASPECT | 73.3 / 72.7 / 77.0 |
| minus ROAD_TEX | 72.3 / 72.0 / 77.7 |
| minus SHADOW_DIST | 72.0 / 74.0 / 71.0 |
| minus CLUTTER_DIST | 71.3 / 73.6 / 72.0 |
| all detail off (far clip 1800 + 120 Hz base only) | 79.0 / 79.3 / 77.7 |
| full best-wide (roads 1800), 2 runs | 72.0 / 72.6 / 70.0 and 71.7 / 72.6 / 71.0 |
| roads 600, 2 runs | 73.0 / 74.3 / 70.3 and 72.7 / 73.3 / 71.3 |

No single switch accounts for the binocular drop. Terrain LOD is the largest share (about 4 fps) and the whole detail
set costs about 6 fps. Binoculars at zoom 8 are below 120 fps on the base settings alone.

## Instruments (new, in autotest)

- `preset-soak.ps1` runs a preset across missions. It takes the `.console-owner` lock, swaps the conf in and out with
  a hash check, snapshots and checks the saves under the lock, records the Strlkup.dll timestamp and md5, and writes a
  report plus raw phase lines to `runs\preset-soak\`.
- `soak-phases.ps1` runs the in-mission sequence. It sends raw VKs. **Finding:** inputlib's `$VK` has no `F6`, so
  `farclip-soak.ps1`'s `Send-Key $VK.F6` sent VK 0, and the 2026-10-02 soak's "hood (F6)" column never left the
  cockpit. Its hood-view rows are cockpit data. Hood view at far clip 1800 is covered here instead (17k vertices,
  survived).
- `lib\phase_stats.py` takes frame times from telemetry and reads, from the game's memory, the peak terrain vertices
  `[0x6442ec]`, the span-node and draw-record pool cursors, the camera mode `0x4c2728`, and the proxy frame range
  (to map a CRASH frame to a phase). The span-node peak read 0 in every phase. The pool is used only by the rare
  long-span records and is reset at the flush, so a 1 kHz outside sampler misses it; the crash is the evidence.
- `binoc-bisect.ps1` runs one boot per variant (`full`, `-SWITCH,...` to drop, `SWITCH=value` to override) and
  counts CRASH lines and binocular fps.
- `proxy-run.ps1` now waits for the killed game to exit, and its DLL restore retries for 10 s. Before this change, a
  1 s wait threw "file in use" and left `STRLKUP.DLL.pretest` and the test lock behind.

Raw: `autotest\runs\preset-soak\20261003-*.txt` (all phase lines and the relevant proxy-log lines per mission).
