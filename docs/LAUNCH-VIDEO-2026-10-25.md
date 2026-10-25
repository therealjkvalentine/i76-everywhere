# Launch video: shot list, pipeline, rights (2026-10-25)

Owner's ask: "capture video of our improvements and make a hype video for launch": before-and-after footage, the multiplayer
menu with a zoom on co-op / AI joining, a tongue-in-cheek fast scroll of the top ~100 improvements, the telemetry / FFB / debug
views, the I'76 theme over the top, and "could you automate the creation of this?". Later ruling (owner, via main): every clip is
a **1920x1080 window capture at 60 fps**, never the 3440x1440 desktop.

Pipeline: `tools/launch-video/` (section 2). Captures and renders: lab `captures\launch-video\` (raw shots, work folders,
drafts; nothing large goes into the repo). Twin: lab `launchvid-20261025` (twin of `test-gold`, proxy 5d6f9828, see TWIN.md
inside; delete or archive it when the lane ends).

Tools on this PC: **ffmpeg 9.0.2** (winget `Gyan.FFmpeg`, full build; installed 2026-10-25 by this lane, not on PATH until a new
shell: `lv-lib.ps1` finds it in the winget package folder). **OBS Studio 32.2.2** is installed but not used: ffmpeg does the
whole job unattended. Measured on this PC: ffmpeg's NVENC does **not** open (driver 560.94 is older than ffmpeg 9's NVENC API),
`gdigrab` of the desktop reaches ~20 fps, `ddagrab` (Desktop Duplication) + Media Foundation hardware H.264 (`h264_mf
-hw_encoding 1`) holds 58-60 fps at 1920x804 (n 1, idle desktop) and is what `record-shot.ps1` uses on the 1920x1080 window rect.
Full 3440x1440 capture with the same chain made only 26 fps, one more reason for the 1080p window.

## 1. Shot list

"auto" = recorded by `record-shot.ps1 -Shot <name>` (shots.psd1): one boot of the twin in a 1920x1080 window at the top left
(`dgVoodoo.lv1080.conf`: [Glide] 3840x2160 supersample, AppControlledScreenMode false; `I76_ASPECT 1920x1080` and
`I76_U32X_MENU_ASPECT 1920:1080` for every preset but stock; `lv-keeper.ps1` holds the window rect), direct mission boot through
`autotest\proxy-run.ps1` (muted per pid, own shm suffix), handbrake + S for `Still` s then W for `Drive` s, ffmpeg ddagrab on the
window rect at 60 fps, telemetry logged with the host clock (`tel-udp.py`, `I76_TELEMETRY=27760`) so the on-screen fps / mph
counters come from **the same run** as the pixels. Hill route = `I76_START_POS 7972,101.8,44035,-90,6` on T05 (hill top facing
west, the map edge and the barn in view; RC-DRAW-FPS s.3, the far-edge lane's `hill` route). Canyon = T05's own start.

| # | shot | how it is captured | duration | on screen | v1 |
|---|---|---|---|---|---|
| 1 | Title card | composed (`card`) | 3.5 s | INTERSTATE '76 / EVERYWHERE / "the 1997 game, fixed for 2026" | yes |
| 2 | **Side-by-side, same route**: stock vs PLAY.bat | auto `route-stock` (preset stock = PLAY-VANILLA's set **plus GOG's I76PATCH.DLL put back for that boot** = the 20 fps game as GOG ships it; PLAY-VANILLA itself runs I76PATCH.disabled = ~60 fps dgVoodoo pacing, FIX-INVENTORY s.0) and `route-all` (OWNER-2300-ALL = PLAY.bat), hill route, 3 s still + 22 s drive each; composed `sbs` (two 960x540 halves, labels above, counters below) | 14 s | labels STOCK (GOG, 20 FPS LIMITER) / I'76 EVERYWHERE; live counters `FPS  MPH  600 M / 2300 M` from each run's telemetry; caption "Draw distance 600 m -> 2300 m, 20 fps -> 120 fps, whole sim locked to the 1997 41.667 ms step" (REBASELINE s.5, CHANGELOG 2026-10-03, TICK-FINISH) | yes |
| 3 | Frame-rate and tick counter overlay | on every game shot with `counters: true` (compose.py from `overlay.json`); the tick value is the run's own proxy line (`sim-tick: ON - whole sim every 41.667 ms`, summary.txt) | - | `120 FPS 45 MPH` style, Consolas, per 0.25 s | yes |
| 4 | Far-edge fade before / after | auto `fade-before` (ALL minus `I76_GLIDE_FOG`, `I76_GLIDE_FOG_ALPHA`) vs `route-all`, hill route; `sbs` | 6 s | HARD EDGE / FEATHERED; "last 25 % of the 2300 m view feathers to transparent" (FAR-EDGE-FADE s.15) | yes |
| 5 | Terrain morph close-up, slow motion | auto `morph-before` (ALL minus the five MORPH / SHADE_SMOOTH keys) vs `route-all`; `sbs` with a 960x540 crop of the mid-distance and `speed 0.5` | 8 s | STOCK SPLITS / GEOMORPH, "0.5x SPEED"; "shading steps 16 -> 32-40 grey levels" (TERRAIN-POPS s.0). The geomorph px numbers of TERRAIN-MORPH s.0 were measured on the table build, not the shipped stateless one: not captioned | yes |
| 6 | Rear mirror before / after | auto `mirror-before` (ALL minus the seven MIRROR keys) vs `mirror-after`, canyon start, `sbs` of the mirror crop (x 1180 y 300, 420x190 in the 1080p window) | 6 s | "Mirror far clip 100 m -> 1000 m, main view's terrain art (cost 1.2 %)" (MIRROR-DETAIL s.2, s.7) | yes |
| 7 | One-pass sky | auto `sky-twopass` (`I76_SKY_MIRROR=1`) vs `sky-onepass`, car held 10 s at the canyon start, `sbs` | 6 s | "the mirror pass scrolled the clouds a second time: 2x -> 1x" (skymirror.c, OTL 2026-10-23) | no (shots defined, not recorded) |
| 8 | Jump with the nose-dive (0.91) | needs the jump replay harness (TICK-FINISH s.22.6: stored start + scripted run-up) wired into `record-shot.ps1` as a route; before = `I76_JUMP_NOSE` stripped | 6 s | "nose-down off the lip eased 9 %: 0 of 12 wrecks vs 1 of 12" (TICK-FINISH s.22.6) | **missing** |
| 9 | Multiplayer menu, zoom on co-op / AI | v1: `still` zoom on the host form (lab `captures\coop-list-20261018\a-list12.png`, the 640x480 shell: Co-op Scene 1-3 in AREA OF PLAY). Next: a live capture of HOST -> AREA OF PLAY scrolling (record-shot menu route; the menus click by `Click-UI` coordinates) | 6.5 s | CO-OP SCENES / AI CARS IN EVERY ARENA / JOINERS SPAWN 27 M FROM THE HOST / CANCEL 5 S -> 1.4-2.1 S (LAN-FIXES s.1, s.3, s.4) | still only |
| 10 | Four-player LAN, cars agreeing across screens (PC + Macs) | owner session: PC host captured by ffmpeg (record-shot with `--windowed` launch) + each Mac with `screencapture -v` / QuickTime, synced on a horn / a shot; composed as a 2x2 grid | 10 s | "4 players, 3 machines, one arena" | **missing (owner + Macs)** |
| 11 | The same build on a Mac | Mac screen recording of the Gold app (the M2 tester's or the MacBook) at 1080p | 5 s | "same proxy, same fixes, macOS (Wine)" | **missing (Mac)** |
| 12 | 86Box P166 reference beside ours | `PLAY-P166.bat` capture of the 86Box window (ddagrab on its rect) + `route-all` on T05, `sbs` | 8 s | "tuned to the 1997 tick: 41.667 ms, as a P166 ran it" | **missing (needs the emulator run, ~10 min boot)** |
| 13 | 60-second Patch Kit install | screen capture of `INSTALL.bat` / Patch Kit on a clean GOG copy (laptop bench, native 1080p), sped to 10 s with a timer | 10 s | "GOG copy -> patched in 60 s" | **missing** |
| 14 | FFB page beside the game | v1: `panel` = `route-all` at 1280x720 + the FFB page (http://127.0.0.1:17691/ layout) replayed from the panel lane's recorded DryRun drive (`ffb-panel-replay.py`, lab `captures\ffb-panel-20261025\p3.states.jsonl`, Playwright + Edge headless, values interpolated 5 Hz -> 30 Hz). Next: a simultaneous capture (PLAY.bat `--windowed 1280x720 --panel` on the owner's wheel) | 9 s | "14 channels from the engine's own state, live tuning page" (RC s.8, FFB-PANEL s.1) | yes (replayed data, not the same drive) |
| 15 | Telemetry / debug views | the I76 Debug page and the trainer, screen-captured beside a drive (same `panel` layout) | 6 s | "every engine value live" | **missing** |
| 16 | Fast scroll of ~100 improvements | composed `crawl` from `tools/launch-video/data/improvements.txt` (108 lines; sources per line in `improvements-sources.tsv`) | 9 s | ALSO IN THIS BUILD / "108 improvements, 9 seconds" / "(pause to read. we did.)" | yes |
| 17 | Credits card | composed | 6 s | community map authors, Dege (dgVoodoo 2), IPXWrapper, opentrack, AutoHotkey, vahokif (I26, prior art); "Interstate '76 (c) 1997 Activision. Fan project, not affiliated." | yes |
| 18 | End card | composed | 3.5 s | github.com/therealjkvalentine/i76-everywhere | yes |

## 2. Pipeline (`tools/launch-video/`)

| file | does |
|---|---|
| `lv-lib.ps1` | ffmpeg lookup; `Wait-LvConsole` / `Exit-LvConsole`: CONSOLE-LOCK.md (no i76 / nitro running, exclusive create of `.console-owner` and `.fps-lock`, a line in `.fps-queue`, waits behind older live queue lines, poll 60 s) |
| `shots.psd1` | the game shots: mission, preset, Strip / Keys, start position, still / drive seconds, Patch20 |
| `record-shot.ps1 -Shot <name> [-DryRun]` | one shot, one boot, one console acquisition (s.1 "auto"); output `captures\launch-video\raw\<shot>\<stamp>\` video.mp4, tel.csv, overlay.json, capture.json, env.txt, boot.txt, mciproxy-run.log, summary.txt |
| `record-batch.ps1 -Shots a, b, c` | several shots, one PowerShell each (no key leaks between shots), console released between boots |
| `lv-keeper.ps1` | holds the game window at 0,0 1920x1080 (the exe resizes its popup to the screen) |
| `tel-udp.py` / `shot-stats.py` | telemetry with the host clock; the overlay series and the run's fps / distance summary |
| `ffb-panel-replay.py` | the FFB page fed with a recorded interposer session, filmed headless (Playwright + Edge), no game, no console |
| `make-music.py` | the royalty-free soundtrack (s.3) |
| `compose.py --timeline <json> --out <mp4> [--music <wav>] [--theme <mp3>]` | renders each segment (card / clip / sbs / still / panel / crawl) to 1080p60, concatenates, muxes each music track (loudnorm -16 LUFS); `--only 0,5` renders single segments for preview |
| `timeline-v1.json` | the draft-v1 cut: segment, source shot, in / out, crop, speed, caption |
| `data/improvements.txt` | the crawl list (top first) |

**One command per stage** (PowerShell, from `tools\launch-video`):

```
.\record-batch.ps1 -Shots route-stock, route-all, fade-before, morph-before, mirror-before, mirror-after   # queues for the console
python ffb-panel-replay.py --states <lab>\captures\ffb-panel-20261025\p3.states.jsonl --out <lab>\captures\launch-video\raw\ffb-panel --from 64 --seconds 24
python make-music.py --out <lab>\captures\launch-video\work\groove.wav --seconds 95
python compose.py --timeline timeline-v1.json --out <lab>\captures\launch-video\draft-v1.mp4 --music <...>\groove.wav --theme "<games>\I76\Interstate 76 Gold\Interstate 76\music\2.mp3"
```

Rules it keeps: it never touches a main copy (the theme mp3 is only read), never mutes the host (proxy `I76_MUTE` + the per-pid
watcher from proxy-run), stops only the game it started (proxy-run), and holds the console for one boot at a time (~1-3 min).
The laptop bench (native 1080p) can run the same shots with `laptop-bench\laptop-run.ps1` once the twin is copied there; not
wired yet.

## 3. Music and rights

- **Two renders of every cut.** `draft-v1.mp4` carries **"Groove 76"**, a 1970s-funk track synthesised by `make-music.py`
  (numpy, no samples, no third-party audio), written for this project and dedicated to the public domain (**CC0 1.0**): safe for
  the README, GitHub, YouTube. `draft-v1-theme.mp4` carries **the game's own theme** (the soundtrack's first track,
  `music\2.mp3` of the GOG install, Arion Salazar / Bullmark, (c) 1997 Activision): the owner's risk, for private / preview use
  only. Do not attach the -theme render to the repo or a release; YouTube will likely Content-ID it.
- Game footage of a commercial game in a fan project's showcase is the usual fan-video practice; the end card says the game is
  Activision's and the project is not affiliated. No game files are distributed by the video.

## 4. README: a playable clip at the top

GitHub renders an inline **player** only for a video uploaded through the web editor (drag the .mp4 into README.md's edit box or
an issue: it becomes a `https://github.com/user-attachments/assets/<id>` URL, max 10 MB on free plans); a repo-relative .mp4 or
a release asset shows only a link. A **GIF in the repo** renders and autoplays everywhere. The repo's own size rule is <= 2 MB per
file (RELEASE-PLAN 5). So:

1. `teaser.gif` (made by the pipeline, 960 px, ~6 s of the side-by-side, < 2 MB) goes to `docs/media/launch-teaser.gif` and sits
   at the top of README.md, linking to the full video;
2. the full `draft-vN.mp4` (groove render) is dragged into the README edit box once by the owner (the only way to get the
   user-attachments player; there is no API for it), or attached to the v1.1.0 release and linked.

Snippet for the top of README.md (after step 2, replace the link):

```
<p align="center"><a href="LINK-TO-FULL-VIDEO"><img src="docs/media/launch-teaser.gif" width="960" alt="Interstate '76 Everywhere: stock vs ours on the same route"></a></p>
```

## 5. Draft v1 (2026-10-25 09:00)

`captures\launch-video\draft-v1.mp4` (CC0 groove) and `draft-v1-theme.mp4` (game theme): 1920x1080, 60 fps, AAC, **63.5 s**.
The terrain-morph segment is not in it, because `morph-before` was still queued at render time. Teaser GIF:
`captures\launch-video\launch-teaser.gif`. The first render was 5.8 MB, so the defaults are now 720 px, 10 fps, 4.5 s, about 2 MB.

Shots, all on twin `launchvid-20261025` (proxy 5d6f9828), each 1920x1080 at 57-60 capture fps. Every summary in
`raw\<shot>\<stamp>\summary.txt`:

| shot | render fps while captured (telemetry) | steps/s | notes |
|---|---|---|---|
| route-stock (GOG 20 fps limiter, stretched 16:9) | 20.0 | 23 | 600 m |
| route-all (3 takes) | 87-92 | 24 | take 1 had another lane's firewall prompts in frame; take 2 captured only 45 fps (ffmpeg at below-normal priority, reverted); take 3 (084743) is the one used |
| mirror-before / mirror-after | 109 / 97 | 24 | canyon start |
| fade-before | 101 | 24 | the feathered edge is hard to see in this view (stills dropped) |
| morph-before | 90 | 24 | |

Findings from these runs:
- **The capture costs frame rate.** Uncaptured, the same preset holds 118-120 fps (RC gate row 9). While ddagrab plus the
  CPU NV12 conversion run on the 4-core 7700K, it holds 87-109 fps. The counters show the recorded rate, and the caption says so.
- **Telemetry is one datagram per sim tick** on the tick builds (24/s) and one per frame on stock. The overlay therefore takes
  rendered fps from the frame counter (`frame`, simclock_frame_count) and steps/s from `step_count`.
- **`I76_START_POS` places the car about 6 s after the player is live.** Each run lands at a slightly different capture
  time. Fixed in v2 by aligning on telemetry (next section).
- The stock picture with no aspect key, in a 16:9 window, is the 4:3 camera stretched. v2 shows stock at 640x480 / 4:3, pillarboxed.

## 6. v2 (owner feedback on v1)

Owner: (1) exact sync, (2) make draw distance and popping obvious, using the T05 opening fly-in with cutscenes not skipped,
(3) combat with FFB / weapons, (4) smoothness at 20 vs 120 fps and head look, (5) the owner can drive what scripts cannot.

- **Sync (`compose.py`, `"align"` per clip):**
  - `move` counts in / out from the first moment the car moves after the hill placement: speed crosses 0.5 m/s after the
    last standstill in the first 15 s, interpolated between telemetry samples.
  - `sim` maps in / out to the mission's own `sim_time` stamp. It is used for the scripted opening.
  - Each render writes `<out>.align.txt` with the anchors and the mph agreement of every side-by-side.
  - Test, route-stock vs route-all: anchors at capture 4.154 / 3.892 s. The mph curves agree to within 0.1 mph over the first
    6 s (13.1/13.0, 25.0/24.9, 53.0/52.9, 74.7/74.7). After about 7 s the two drives physically diverge (a crest at 96 mph).
- **Opening fly-in:** `record-shot.ps1` shots with `Opening = $true` launch without proxy-run, which would press Esc and skip
  the opening. Movies are skipped, the scripted opening is not. The window is held at size, nothing is pressed, the capture
  runs `Still` seconds, then the run stops the game it started. Shots: `opening-stock43` and `opening-all`.
- **Stock at 4:3:** shots `*-stock43` use `dgVoodoo.lv43-640.conf` ([Glide] 640x480) in a 1440x1080 window, with GOG's
  I76PATCH 20 fps limiter. That is the 1997 look on this PC.
- **Smoothness:** `slalom-stock43` vs `slalom-all` (a scripted A / D weave on the hill road), with counters.
- **Glances:** `glance-all` (Left / Right / Down keys while driving) beside `route-all` (the fixed view). Opentrack head look is
  an owner take.
- **Owner takes** (`RECORD-TAKE.bat <tag> <seconds> [x,y,w,h]` = `record-window.ps1`, records the running window at 60 fps, no
  launch, no input):
  - combat: Instant Melee with AI, wheel + `--panel`, rect `0,0,1920,1080` with the game at 1280x720 and the page beside it;
  - headlook: opentrack, T05;
  - jump: the T05 canyon ramp.
- Timeline: `timeline-v2.json`. Stills list: `stills-v1.json`, written by `make-stills.py` to `captures\launch-video\stills`.
