# Logging the owner's own 86Box play sessions (2026-10-16)

The owner's playthroughs on the emulated P166 (retail 1.0, software, lowest detail) are now recorded by the same
per-frame memory logger as the reference runs (I76MEM, `EMU-MEMTRACE.md`). A logged session gives the same CSV files as
a par run, so the analysers read it. Tools and the how-to: lab `emu\README.md`, "Owner play logging".

- **Launcher:** lab `emu\PLAY-P166-LOGGED.bat` (one double-click). It plays, then collects the logs when 86Box closes.
- **Not touched:** the owner's own route (`run-vm.ps1 pbs-p166`), `vm\pbs-p166\`, `images\w95pb-hdd.img` and every
  snapshot. The owner disk's sha256 and timestamp were checked before and after the copy: unchanged.
- **Not done:** no visible session was started (the console session was disconnected all night; agents run 86Box only
  headless). The visible route is the owner test below.

## How it works

- **Logging play disk** `images\w95pb-hdd-memlog-20261016.img`: a copy of `w95pb-hdd.img` (source sha256 `c8e7da85...`,
  made 22:35). One change: `C:\WINDOWS\WIN.INI` `run=` -> `run=D:\MEMLOG\I76LOG.EXE` (5188 -> 5208 bytes, written in
  place, read back). A file-by-file comparison against the source found only WIN.INI different (1425 files).
- **Machine:** the owner's own `vm\pbs-p166\86box.cfg` and CMOS. Only three lines change: C: (the logging disk), D: (a
  fresh 100 MB data disk per launch) and the CD (disc 2 by default). Sound is as in the owner's config.
- **In the guest:** I76LOG (`probe\i76log.c`, 4.6 KB, Win95-clean imports) starts I76MEM. I76MEM waits for `I76.EXE`,
  logs every frame until the game exits, then I76LOG starts the next one. Every game start is one session
  (`D:\MEMLOG\S01.BIN`, `S02.BIN`, ...).
- **Afterwards:** `owner_log.py` copies `D:\MEMLOG\*` out (read only) into `emu\results\memtrace\owner-<date>-<time>\`:
  - `raw\`: the binary traces and logs;
  - `sNN\mem.phys.csv / mem.frames.csv / mem.music.csv`;
  - `summary.md`, with per session:
    - the exe, in-mission fps, physics step and logger coverage;
    - each mission (start point, top speed, distance, wreck);
    - the **Arcade Phys. flag** (entity 0x10000);
    - every airborne stretch of 0.5 s or more;
    - **T05 canyon descents**: landing-analyse `jump()`, found by position (the car passing x = 6900 westbound on the
      canyon road);
    - g;
    - the decoded music intent.
- **Saves:** saves made in a logged session stay on the logging disk, and `w95pb-hdd.img` keeps its own.
  `owner_log.py snapshot --date YYYYMMDD` makes a fresh copy of the owner's disk. It never overwrites an existing one.
- **Music intent** (`tools\memtrace\music.py`, also in `analyse.py` and `summarise.py`) decodes the requested track
  with the 1997 disc's title (`docs\MUSIC-TRACK-MAP.md`), the playing / loop flags and the 1997 run rule. The reference
  runs decode as:
  - retail melee: track 9, Just Call Me Daddy;
  - retail T05: track 6, The T'aint;
  - Gold: none (the Gold ISO has no audio tracks).

## Self-test (headless, P166, retail 1.0 + disc 2, Instant Melee)

**Setup.** Script `tools\par\scripts\ownlog-melee.txt` on par copies of the logging disk. I76LOG starts the script's
player only when `D:\PAR\SCRIPT.TXT` exists, which an owner session does not have. Each run:

- settle 10 s;
- throttle 20 s;
- a 2 s glance;
- exit;
- shutdown.

I76FPS ran in both conditions. "Off" means the data disk had no `I76MEM.EXE`, so I76LOG logged "no logger" and exited.
The I76MEM build was `2026-10-16a`, sha256 `74F3C23C...`, frozen for all runs; it includes the retail AI-list reads.

**The chain works.** In every logger-on run (n = 4):

- WIN.INI started I76LOG;
- I76LOG started I76MEM;
- I76MEM identified retail 1.0 by signature and logged the mission;
- after the game exited, I76LOG armed session 2;
- the files were collected and converted, and `analyse.py` read the CSV.

Per run: 2,303-2,391 in-mission frames, 99.6-99.7 % of frames with one step, every record post-physics, 11-16
frames missed by the logger (0.5-0.7 %), and speed = |velocity| to 1e-5.

**Arcade flag check.** The first run copied the Gold-layout `I76PLYR.DEF` into the retail folder. Its summary flagged
Arcade Phys. ON in 2,399 / 2,399 frames. The three runs with the retail-layout file (`retail-plyr\RPLYR.DEF`) show it
off in 0 / ~2,350 frames each. This confirms the other lane's finding, and shows the owner summary catches it.

**Overhead** (I76FPS, guest time, fps):

| condition | n | settle | throttle 20 s | after | all segments |
|---|---|---|---|---|---|
| logger off | 3 | 37.39 +- 0.61 | 36.13 +- 1.42 | 37.19 +- 1.52 | 36.70 +- 1.24 (38.14 / 36.06 / 35.91) |
| logger on | 3 | 37.87 +- 0.20 | 37.09 +- 0.19 | 36.83 +- 0.73 | 37.22 +- 0.13 (37.36 / 37.18 / 37.11) |

- **No cost was resolved.** On minus off is +0.5 fps. The off condition's own A/A spread is 2.2 fps (6 %). This test
  cannot see a 2 % cost; it neither confirms nor contradicts the earlier -2.7 % (Gold, n = 4).
- **Host load was high.** 4-7 86Box VMs ran on the host during these runs (other lanes; cap 4), and the VMs ran at
  0.55-0.69 of real time. The guest-time fps should not depend on that, but the off spread is larger than in the
  earlier quiet runs (sd 0.3-0.6).
- **Melee spawn points are random,** so throttle segments cross different ground.
- **Failed runs:** two off runs exited early and were excluded. One exited because I deleted its disk copy while
  86Box started. One exited because `probe\out\I76MEM.EXE` was missing while another lane rebuilt it (FileNotFoundError).

**Raw data** is in lab `emu\results\par\20261016-*-ownlog-ab-*` and `emu\results\memtrace\owner-test-*`.

## Caveats

- **Shut Windows down before closing 86Box.** The logs must reach the data disk; Windows 95 caches writes. The summary
  then lists what was collected. If 86Box is closed without a shutdown, the last records may be missing.
- **The analysers' frame skipped total includes the mission-end gap.** `analyse.py`'s `frames.skipped` counts the
  frame-counter jump when a mission ends (238,719 in the first run). The owner summary counts misses only in steps of 1-5
  frames and reports larger gaps separately.
- **Copies from probe\out.** The launcher takes `I76MEM.EXE` / `I76LOG.EXE` from `probe\out` at launch, and records
  their sha256 in `session.json`. A lane rebuilding at that moment breaks the launch; run it again.
- **Retail options file.** Never copy the Gold 96-byte file into the retail folder: retail reads its +0x54 as Arcade
  Phys. on. The owner's disk has no retail `I76PLYR.DEF` (retail defaults); the summary shows the flag either way.
