# Terrain white flash under best-wide: TMU cache census (2026-10-03)

Owner report (daily driver, preset best-wide, 120 Hz): "a veeeeery occasional flashing across all the terrain to
white". Hypothesis tested: ZGLIDE's texture cache overflows its 2 MB TMU (docs/TEXTURE-DELIVERY.md s.2): when no
free space and no same-size victim exist, a polygon is drawn with whatever texture is bound and the whole cache is
flushed next frame; the detail switches raise the number of resident textures.

## Instrument

`I76_TEX_CENSUS=1|2` in i76-everywhere `music-fix/strlkproxy.c` (TEXTURE CENSUS section; README row). Count-only IAT
hooks on ZGLIDE's glide2x imports, installed from the LoadLibraryA hook: `grTexDownloadMipMap` (count + bytes via
`grTexCalcMemRequired`), `grTexMinAddress` (call 1 = FirstDevice, later calls = full flushes, 0x100017f7),
`grTexMaxAddress` (readback of what dgVoodoo gave), `grBufferSwap` (frame counter; samples ZGLIDE's next-free
`[0x1001fd20]`, TMU index `[0x1001f894]`, no-slot flag `[0x10178ea0]`). `=2` also dumps, with `grLfbReadRegion`,
the front buffer at the flush, the back buffer at the next swap and a control 30 swaps later (640x480 BMP).
Unset: no hooks, and the refresh wrapper is installed only for `I76_GLIDE_DIR` / `I76_GLIDE_REFRESH` as before.

Observation about the flag: at swap time it always reads 0, and at every mid-mission flush it reads 1. The flag is set
and cleared (by the flush) within the same RefreshDisplay, so every mid-mission flush is one no-slot event; "no-slot"
in the per-600 lines therefore stays 0 and the FLUSH lines are the count.

## Runs

Lab twin `game-dd-20261003\Interstate 76` (stock ZGLIDE md5 05c1dde4, 0x1a93 = 75 24), harness
`autotest\proxy-run.ps1 -GameDir <twin> -Set stock -Dll <new Strlkup.dll>` + `soak-phases.ps1 -Cockpit 60 -View 5`
(cockpit 30 s, hood, binoculars, four glances, cockpit driving 30 s; ~95 s per mission), env = the twin's
`presets\<preset>.psd1` + `I76_TEX_CENSUS=2`. Conf copied over `dgVoodoo.conf` per batch; every batch restored
26 files (confs, ZGLIDE, STRLKUP, saves, .def/.spc, input.map) and checked them byte-identical. Raw:
`captures\whiteflash\20261003-1724*`, `-1730*`, `-1735*` (per-mission mciproxy.log slice, BMP dumps, 150 ms screen
samples). n = 1 run per cell.

Mid-mission flushes (the flush at swap 0, mission start, excluded):

| batch | conf | t01 | t05 | t11 | total | grTexMaxAddress |
|---|---|---|---|---|---|---|
| best-wide (detail x8, bushes 300, shadows, mirror 300) | dgVoodoo.wide.conf, TMU 2048 | 13 | 8 | 2 | **23** | 0x1ffff0 |
| control: best-120 + I76_ASPECT (detail switches off) | same | 2 | 3 | 2 | **7** | 0x1ffff0 |
| best-wide + `MemorySizeOfTMU = 4096` | wide conf with that one line changed | 0 | 0 | 0 | **0** | 0x3ffff0 (setting took) |

- Peak resident: 2048 KB (full) in both 2048 batches; 3.7..4.06 MB with 4096 (it is used, and never overflows).
- Downloads are about 1,800 per 600 swaps (~64 MB) in all three batches, flushes or not: steady same-size recycling
  that a larger TMU does not reduce. Not investigated further.
- Flushes cluster in the hood / binoculars / glance phases (swaps 5,100..6,400) and, in t01, during driving.
- Frame count per mission was the same in all three batches (the last 600-swap summary at 6000 / 9600 / 7800 swaps for
  t01 / t05 / t11), so 4096 costs no visible frame rate at the 120 cap; frame times themselves were not measured
  (phase_stats needs I76_TELEMETRY, not set).
- No crash in 9 missions.

## Do the flushes match white frames?

Not in what was captured. 16 mid-mission flushes were dumped in the best-wide batch and 7 in the control (front buffer at
the flush, back buffer of the frame shown next, control 30 swaps later): none shows white terrain; lower-half mean
brightness of the flush frames is within the spread of their controls (29..72 / 255; at most 2.7 % of pixels > 240,
also seen in controls: dust puffs and sky). The wrong-texture draws of a no-slot frame are not visible at 640x480
in any dump. So flushes are frequent (one every ~12 s in t01 with best-wide), far more frequent than "very
occasional", and their frames look normal: **the TMU-overflow hypothesis is not supported as the cause of the white
flash** (n = 23 dumped flushes of 30; a flush that came while a dump was pending, or a white frame not tied to a flush, is not ruled out).

Open alternatives, not tested here: terrain-texture level switching under `I76_TERRAIN_TEX` (tile swaps level),
fog / sky colour or the time-of-day light table, render-interp. A 150 ms screen sampler ran through every mission
(`*-shots`, ~600 JPGs each) and can be mined for any bright frame offline.

## Fix test

- (a) `[Glide] MemorySizeOfTMU = 4096`, stock ZGLIDE: 0 flushes in 3 missions, setting verified by the readback
  (0x3ffff0), no crash, no wrong textures in the start dumps. As predicted statically (TEXTURE-DELIVERY s.2: the
  2 MB rewind bug needs > 4 MB).
- (b) ZGLIDE 0x1a93 fix + 16384: not run (time box); (a) already removes every flush.

## Recommendation

The flushes are real and the detail switches triple them; 4096 removes them at no measured cost, so it is a safe
cleanup, but it is not shown to fix the white flash. If the owner wants to try it: daily driver
`C:\Users\james\Games\Interstate76-2026-10-03\Interstate 76\dgVoodoo.wide.conf` (PLAY.bat copies it over dgVoodoo.conf at every launch), `[Glide]` key `MemorySizeOfTMU`, value `4096` (keep
`NumberOfTMUs = 1`; do not go above 4096 without the ZGLIDE patch). If the flash still appears with 4096, the cache
is excluded and the next suspect is the I76_TERRAIN_TEX level switching (A/B: best-wide minus I76_TERRAIN_TEX).
