# Windowed game "pops out of alignment" every 2 s; 2x full screen cropped on 1080p (2026-10-25)

Owner report (blocks recording): "when the game is played in a window it pops in and out of alignment every second or two.
PLAY.bat --mission t05 --windowed 1280x720. This happened in a ton of clips." Seen on the desktop and the laptop: "the view zooms in
and moves to the center for a flash, then goes back." Folded in: issue #125 (LAPTOP-1080P-WINDOW-2026-10-25.md), the same conf.

**Cause: dgVoodoo makes a window the size of its [Glide] render target and re-applies that size every 2.000 s.** `-Windowed`
asked for a 2x supersample (render target 2560x1440 for a 1280x720 window), so every 2 s dgVoodoo grew the window to 2560x1440
(centred on the desktop) and the launcher's keeper shrank it back 20-280 ms later. The picture zoomed to the top-left quarter and
moved, then a black frame, then a frame or two 2 px off, then normal. The keeper is not the trigger: with it stopped the window
simply stays 2560x1440. Issue #125 is the same rule without a keeper: a full-screen launch with `FullScreenMode = false` gets a
window the size of the render target (3840x2160 on a 1920x1080 panel), and the panel shows its top-left quarter.

**Fixes (PLAY-i76.ps1):** `26d57cc` -Windowed sets `[Glide] Resolution` = the window (render scale 1, AA kept) and
`CenterAppWindow = false` for the launch. `92965f8` (#125): a full-screen launch whose render target is larger than the display
sets `FullScreenMode = true` for that launch (`FullscreenAttributes = fake` kept). Either way `dgVoodoo.conf` goes back when the
game exits, and the installed confs are not changed.

## 1. Evidence from the existing clips (lab `captures\launch-video\raw`, ffmpeg frame steps)

- `glance-all` (1920x1080 window, lv1080 conf with [Glide] 3840x2160): a black frame + 1-3 px border change at 1.62, 3.60, 5.62,
  7.60, 9.60, 11.60, 13.60, 15.60, 17.62 s. **The period is 2.00 s.** The frames before each black one show the top-left 1920x1080 of a
  much larger picture (radar and weapon panel ~2x).
- `route-all`, `slalom-all`: the same black frames on the same 2 s grid, with some missing. `opening-stock43` (640-wide 4:3 conf): 3
  in 45 s.
- The recorder (`record-shot.ps1` + `lv-keeper.ps1`) and `PLAY-i76.ps1 -Windowed` both keep a window smaller than the render target,
  so both show it. The owner's live repro (plain PLAY.bat) is the launcher's keeper.

## 2. Window timeline (probe: per-2 ms GetWindowRect / GetClientRect / style of the game's top-level windows)

Lab `tools\windowed-align\walign-probe.ps1` (also `desk-rows.ps1`, `fs-rows.ps1`, `fit-rows.ps1`, `laptop-fit.ps1`). OWNER-2300-ALL,
t05 direct boot, movies skipped, FFB off, muted per process.

| run | machine | window rect over time | result |
|---|---|---|---|
| A, before the fix, 1280x720 | laptop 1920x1080 | 1280x720, then **2560x1440 at x.89 s every 2.000 s**, back to 1280x720 30-280 ms later (n 30 cycles in 60 s) | pops |
| B, before, keeper stopped at 40 s | laptop | the last jump to 2560x1440 at 41.9 s **stays** | the keeper only undoes it |
| C, `-RenderScale 1`, 1280x720 | laptop | 1280x720, one move to the centre at 6.5 s, then still for 70 s | no pops |
| before, 1280x720 (D1, desk-head720) | desktop 3440x1440 | **2560x1440 at (440,0)** (centred) every 2.000 s, back after 50-280 ms; 54 changes | pops |
| fix 26d57cc without CenterAppWindow, 1280x720 / 1920x1080 | desktop | one move to (1080,360) / (760,180) at ~12.6 s, then still | no pops, centred |
| fix 26d57cc, 1280x720 / 1920x1080 (fix720-b, fix1080-b) | desktop | (0,0) from 5 s to the end, 2 rect changes in total | no pops |
| test-gold, fix, 1280x720 (tg-win720) | desktop | (0,0) 1280x720 to the end | no pops |
| fix, 1280x720 (fit-win720) | laptop | (0,0) 1280x720 to the end | no pops |

## 3. Captures (ddagrab of the window rect, 60 fps; frame diff and border scan per frame, `captures\windowed-align\edges.py`)

| capture | frames | black frames | frames with mean abs diff > 40 | largest diff |
|---|---|---|---|---|
| before, 1280x720, 30 s | 1800 | 3 | 41, in bursts at 0.53, 2.53, 4.52 ... 28.53 s (every 2.0 s) | 85.8 |
| fix, 1280x720, 60 s | 3600 | 0 | 0 | 15.4 |
| fix, 1920x1080, 60 s | 3600 | 0 | 0 | 9.8 |
| fix + top left, 1280x720, 60 s | 3600 | 0 | 0 | 8.8 |
| fix + top left, 1920x1080, 60 s | 3600 | 0 | 1 = the death camera cut at 55.9 s (borders unchanged) | 46.7 |
| test-gold, 1280x720, 60 s | 3600 | 0 | 0 | 11.4 |

The car drove in every capture (mean diff 1.2-1.3 per frame, contact sheets show the road moving). n 1 per row on the desktop.

Cost: a windowed game is now rendered at the window's size with the AA setting, not 2x2 supersampled. Any supersample in a window
brings the 2 s resize back (dgVoodoo has no separate render-target size in a window that we found); the launcher logs
"render scale 2 not used in a window".

## 4. Full screen larger than the display (issue #125)

| run (PLAY-i76 as deployed, default launch, `--mission t05`) | machine | final window | picture |
|---|---|---|---|
| `FullScreenMode = false` (as installed), movie skipped | desktop | **6880x2880** at 13 s | top-left quarter (screenshot) |
| `false`, briefing movie played | desktop | 3440x1440 | whole (how the owner usually plays) |
| `true` (fs-rows, n 2) / launcher fix 92965f8, movie skipped | desktop | 3440x1440 | whole; fps 88-101 (false: 80-88) |
| launcher fix, movie played | desktop | 3440x1440 | whole |
| launcher fix, movie skipped, n 3 | laptop 1920x1080 | 1920x1080 | whole (screenshots); was 3840x2160 cropped (LAPTOP-1080P-WINDOW) |
| launcher fix, Nitro (nitro-tick42, render 3840x2160), n 2 | laptop | 1920x1080 | whole on boot 1; boot 2 minimised at 8 s (see below) |

- The desktop was cropped too, but only when the movie is skipped (the skip-cutscenes / mission-boot path). With the movie the game's
  own mode change left the window at the screen size, which is why the owner never saw it.
- **Alt+Enter** (desktop, fix): the first press makes dgVoodoo windowed at the render-target size (6880x2880, cropped, as the old
  conf always was), the second goes back to 3440x1440. dgVoodoo's own toggle, unchanged. For a window use `--windowed`.
- **Menu pointer:** not exercised by these boots (direct mission boot). The cursor map follows the live client rect (cursormap.c),
  which is now the screen size in both paths, the same as the owner's normal movie path.
- Two laptop boots (Gold with the movie, Nitro boot 2) ended minimised (`st B4000000`, client 0x0) at ~8 s. The screenshots show an
  Edge "Microsoft Rewards" window in front: it took the focus, and the exe minimises itself when it loses activation (unchanged
  stock behaviour; LAPTOP-1080P-WINDOW saw the same with `false`). The Nitro "Unhandled Exception" of that record did not recur
  in 2 boots.

## 5. Launch-video recordings

The recorder's own conf had the same problem (`dgVoodoo.lv1080.conf`, [Glide] 3840x2160 in a 1920x1080 window): every clip
recorded through 2026-10-25 afternoon has a zoomed flash every 2 s. Lab `launchvid-20261025\Interstate 76\dgVoodoo.lv1080.conf` is now
[Glide] 1920x1080 and `CenterAppWindow = false` (previous kept as `.pre-walign`); `record-shot.ps1` and LAUNCH-VIDEO-2026-10-25.md
say so. Clips need re-recording.

## 6. Deployed

- dev-gold, test-gold: `Interstate 76\PLAY-i76.ps1` = 92965f8 (previous 5ab9ccb9 kept as `PLAY-i76.ps1.5ab9ccb9-pre-walign`).
  Main not touched.
- Patch Kit 0.8.1 draft rebuilt from 92965f8 (proxy unchanged, c54210f8): `Interstate76-Patch-Kit-i76-everywhere-v0.8.1-92965f8.zip`.
  Not published.
- The laptop bench's own copies for this lane (`walign\gold`, `walign\nitro` in the bench folder; retire with this record).
