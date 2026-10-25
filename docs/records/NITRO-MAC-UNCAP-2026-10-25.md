# Nitro on the Macs: the 24 fps cap replaced by the decoupled tick (2026-10-25, nitro-mac-uncap lane)

Owner, 2026-10-25: "Whoa why would Nitro be at a 24 fps cap and not 60-ish on Mac?" It was a leftover. The Mac Nitro apps were
built on 2026-10-21 (NITRO-MAC-2026-10-21.md s.1) with `I76_FPS_CAP=24`: stock nitro.exe has no frame limiter, and at that time
`I76_SIM_TICK_MS` refused nitro-ai's `ai_FrameTick` site, so the 41.7 ms step came from the cap. The nitro-ai side was fixed two
days later (91d2b14, NITRO-MP-DESIGN s.0.5.11: the site is chained, `nitro-ai: ... already calls ... - chained`), and PC main Nitro
runs the tick (`OWNER-NITRO-ALL`: `I76_HIRES_CLOCK=1 I76_SIM_TICK_MS=41.667 I76_SIM_TICK_INPUT=1`, no cap; 112-120 fps,
NITRO-WIN11 s.3). The Mac env was never updated.

**Result: all three shipped Nitro apps now run the PC's tick under the Mac Gold apps' 120 fps cap. Median fps 24 -> 55-72 in P01,
the sim still steps 41.67 ms at 24.0 ticks/s, 0 CRASH, and a clone <-> clone LAN join at the new setting works (n 2).**

## 1. The change

In the prefix's `HKCU\Environment` (user.reg), and nothing else:

| key | before | after | why |
|---|---|---|---|
| `I76_FPS_CAP` | 24 | **120** | the Mac Gold apps' cap (`tools/mac-kit/payload/env/gold.env`: `I76_FPS_CAP=120`); "match Gold Mac's frame policy" |
| `I76_SIM_TICK_MS` | - | **41.667** | PC main Nitro's tick (the 1997 car step, 24 ticks/s) |
| `I76_SIM_TICK_INPUT` | - | **1** | PC main Nitro's (an early tick on input) |

Every other Nitro switch is kept as it was (`I76_HIRES_CLOCK=1`, the fixes, music, `I76_FPS_LOG=5`, the `OGL_*` keys). Gold Mac uses
the older fixed-step set (`I76_FIXED_STEP=24` + `FRAMERATE_FIXES` / `ENGINE_DT_FIX` / `RENDER_INTERP`), which is "no" on Nitro (music-fix
README Nitro table), so only its cap carries over. Proxy (3f27c797), nitshell (a32ffba6) and launcher (e61e4e57) are unchanged.

## 2. Test on clones first (MacBook, M5 Pro)

Clone `~/Applications/Sikarugir/I76 NITRO UNCAP.app` = `tools/mac-test-clone.sh make` of the shipped Nitro app (APFS clone, own bundle id,
null audio, movies skipped). Runner `nrun.sh` (lab `builds\nitro-mac-uncap-20261025\`): `open -n` with `I76_MISSION=p01`,
`I76_SKIP_MOVIES=1`, `I76_SKIP_CUTSCENES=1`, `I76_MUTE=1`, `I76_FRAME_LOG`, `I76_SIM_TICK_LOG=10` (counters only); stationary at the P01
start, nobody at the Mac; first 5 s dropped, the next ~60 s used; median = median of 1 s bins, 1 % low = 1000 / p99 frame period. Each
run ends only its own app (its wineserver -k, then its own bundle's processes).

| run | env | median fps | 1 % low | sim tick (the proxy's counters) | CRASH |
|---|---|---|---|---|---|
| lap-before-1, -2 | shipped (cap 24) | 24.0, 24.0 | 24.0, 24.0 | the cap: sim dt 41.664-41.667 ms per frame | 0, 0 |
| lap-after-1 .. -4 | uncap | 81.5, 74.7, 82.0, 83.5 | 35.6, 35.4, 36.3, 35.5 | lap-after-4: `1442 ticks / 60.1 s gameplay (24.012 /s), 5202 display frames ... player steps hist 1:1440 ... (41.67 ms)` | 0 x 4 |

The log of every uncap boot: `fps-cap: 120.000 fps`, `sim-tick: ON - whole sim every 41.667 ms (24.000 ticks/s; vehicle stepper count 1 x
41.67 ms); 12/12 sim gates, 4/4 display hooks, 16/16 draw-side holds, 7/7 cosmetic sites`, `nitro-ai: site ai_FrameTick at 0x432e24 already
calls ... (stock 0x4076f0) - chained`, `nitro-ai: ON (all 12 sites)`. The frame-log CSV's sim_dt column reads 41.667 on every display frame
under the tick (it shows the tick's held value), so the tick rate is taken from the proxy's `sim-tick:` counter lines, not from the CSV.

The 1 % low (about 35 fps) is a frame of about 28 ms every so often; the fps lines show `work 11-14 ms avg, 25-55 ms max`. The cap of 120
is not reached on any Mac (the display is 120 Hz on the MacBook only). n 4 clone rows on one Mac; spread of the median 74.7-83.5.

## 3. The LAN check (clone <-> clone, n 2)

Host = the MacBook clone, joiner = a clone of the M2 tester Mac's shipped Nitro app (`~/i76-nitro-uncap-20261025/I76 NITRO UNCAP.app` there,
same make, same uncap env). Both with the lab instrument nmpdrv **8d298467** as Strlkup.dll in chain mode and the shipped proxy 3f27c797 as
strlkprx.dll (the relay spike's pairing), the shipped IPXWrapper 06a01d0f on UDP 54792 (LAN mode, broadcast), stock Combat session (row 0),
n01, 6 slots; host hold 260 s, joiner 150 s (`uj.sh`, `lan.sh`). Both sides at 41.667 ms, as PC main Nitro.

| run | joiner listed | join | both sides after (host / joiner) | ticks / s (host / joiner) | CRASH |
|---|---|---|---|---|---|
| lan1 | `'Gumball Rally' species 025c players 1/6` | 2nd try: the first JOIN GAME sat 20 s at state 6 net 0, the instrument's own retry (CANCEL, JOIN again) got in | state 5, net 1, players 2, held to t+165 s / t+95 s+ | 24.005 / 24.008 | 0 / 0 |
| lan2 | the same | first try | state 5, net 1, players 2 to t+150 s / t+90 s+ | 24.0 / 24.0 | 0 / 0 |

Not run: a Mac <-> PC join at the new setting (both PC consoles were held by other lanes: desktop `.fps-lock` frame-profile + 5 queued,
laptop `.fps-lock` fix-step). The PC already runs 41.667, so a Mac at 41.667 is now the same tick on both ends; before today it was the cap's
41.667 on the Mac against the tick's 41.667 on the PC. The one stalled first JOIN GAME (lan1) is n 1 of 2 and the retry is the instrument's
standard path (`NMP_JOIN_RETRY`); a person would click JOIN GAME again.

## 4. The shipped apps

On each Mac: no game running, the app not running; `apply.sh` backs up user.reg to `<game folder>\_rollback-uncap-20261025\user.reg`
(+ `MANIFEST.md5`), edits the three keys, reads back the `[Environment]` keys and `diff`s against the backup (exactly the 3 + 1 lines), and
checks the proxy md5 (3f27c797 before and after, unchanged on all three). Then one P01 boot with `nrun.sh` (muted with `I76_MUTE=1`, the app's
real audio driver; only that app ended afterwards). The boys' Macs: no sudo, no prompt, only the Nitro app and our own folder
`~/i76-nitro-uncap-20261025` touched.

| Mac | before (shipped, cap 24), median / 1 % low | after (shipped, uncap), median / 1 % low | ticks / s after | CRASH |
|---|---|---|---|---|
| MacBook (M5 Pro) | 24.0 / 24.0 (the clone, n 2) | **71.5 / 34.7** (n 1) | 24.010 | 0 |
| M2 tester (the M2 tester) | 24.0 / 24.0 (n 1) | **55.2 / 47.5** (n 1); its clone 71.8 / 39.8 (n 1) | 23.996 | 0 |
| M4 Max tester (the M4 Max tester) | 24.0 / 24.0 (n 1, 125 frames: the Mac slept mid-run) | **about 112** (`fps: 112.4` / `112.8` over the 5 s it stayed awake, n 2; no 60 s window, see below) | 23.4 over the first 6-8 s (start-up included) | 0, 0 |

Backups (user.reg md5): MacBook 94656262, the M2 tester 94383f95, the M4 Max tester 48626dac.

**Undo** (game closed): `cp "<game folder>/_rollback-uncap-20261025/user.reg" "<app>/Contents/SharedSupport/prefix/user.reg"`, where the
game folder is `<app>/Contents/SharedSupport/prefix/drive_c/GOG Games/Interstate 76 Nitro`. To go back to a 24 fps cap only, set
`I76_FPS_CAP` back to 24 and delete the two `I76_SIM_TICK_*` lines.

**The M4 Max tester Mac sleeps under the run.** Its lid is closed and it runs on battery (`AppleClamshellState = Yes`, 80 %,
discharging), so `caffeinate -d -i` (added to nrun.sh) cannot keep it awake: every boot got 5-8 s of mission frames, then one frame of
189-565 s while the Mac slept. The two after-boots read `fps: 112.4 (563 frames / 5.0 s)` and `112.8 (565 frames / 5.0 s)`, i.e. near the
120 cap, and 0 CRASH; a 60 s median and 1 % low need the Mac open (or on power). Two more things on that Mac: its `python3` is the
unlicensed Xcode stub, so the first apply's edit did not run (the read-back showed `I76_FPS_CAP=24` and no tick keys, and its first
"after" boot was therefore one more cap-24 boot); the edit was redone with `setenv.pl` (perl; byte-identical to setenv.py's on a test copy,
and idempotent). The backup was taken before either boot, so it is the pre-change file; the diff after the edit is the 3 + 1 lines plus
Wine's own timestamps.

The fps difference between a shipped app and its clone on the same Mac (M2 tester 55.2 against 71.8, MacBook 71.5 against 74.7-83.5) is
n 1 per shipped row and not explained; one known difference is the audio driver (the shipped apps use CoreAudio, the clones Wine's null
driver).

## 5. Repo

- `tools/mac-kit/payload/env/nitro.env` (what the Mac Kit writes into a new Nitro app's user.reg) and `tools/nitro-mac/make-nitro-app.sh`
  (the 10-21 installer): `I76_FPS_CAP=120`, `I76_SIM_TICK_MS=41.667`, `I76_SIM_TICK_INPUT=1`. Neither was re-run end to end here; the kit
  writes the env file's lines verbatim (`i76-mac-kit.sh` line ~330), and the result is the same key set the shipped apps now carry.
- **The Deck has no such leftover:** `deck/kit/i76-env.sh` / `i76-env-mp.sh` / `setup-deck-wide.sh` are Gold-only (no Nitro env anywhere
  under `deck/`); they carry Gold's fixed-step set (`I76_HIRES_CLOCK=1`, `I76_FIXED_STEP=24`, no `I76_FPS_CAP`). Not changed (the Deck lane's).
- Lab: `builds\nitro-mac-uncap-20261025\` (nrun.sh, an.py, setenv.py / setenv.pl, apply.sh, uj.sh, lan.sh); run logs and CSVs on the Macs in
  `~/i76-nitro-uncap-20261025/{out,runs}` and copied to the lab folder's `out\`.

## 6. Left on the Macs

- Clones (delete when done; nothing else uses them): MacBook `~/Applications/Sikarugir/I76 NITRO UNCAP.app`, M2 tester
  `~/i76-nitro-uncap-20261025/I76 NITRO UNCAP.app`. Both still carry the instrument as Strlkup.dll (`uj.sh unprep` puts the proxy back).
- `~/i76-nitro-uncap-20261025` on each Mac (scripts, logs, the user.reg copies).
