# Owner launchers fixed after the first pass (2026-10-17)

The owner's first pass over `OWNER-TESTS-2026-10-17` (lab `ced03f7`; results in
[OWNER-TEST-LIST.md](../OWNER-TEST-LIST.md), "Owner results 2026-10-17") left four launchers to fix. All four are fixed
in lab **`8104bf1`**. Three were verified on the emulator. The F2 driver (06 / 07) was not run live.

| launcher | problem | fix | verified |
|---|---|---|---|
| 02 / 03 (86Box logged) | 02 had no WASD keys: the retail folder of the logging disk has the stock keypad `INPUT.MAP` | the owner's WASD map is written into the retail folder of the session copy before boot, read back, and the keys are printed | in the guest, on the same map and write path (below) |
| 02 / 03 + `emu\PLAY-P166-LOGGED.bat` | graphics were lowest detail; the owner's ruling is ~33.3 ms frames | play default `lmir` (320x200, rear-view mirror full, the rest lowest) in `R33MS.DEF` / `G33MS.DEF` | retail sim P166 melee and T05, n 3 each, options read back from memory |
| 01 (clip) | the clip showed one frozen frame | the recorder no longer blocks on the encoder; the clip was re-recorded | new run: 6936 frames, longest gap 0.04 s |
| 06 / 07 (F2 bookmark) | the owner could not tell what the test asked | the bug is stated in one sentence, the clicks are automated, the launcher prints PASS / FAIL, and a hand fallback is given | static only: parse check, timeout path, refusal path |

## 1. WASD keys in 02 / 03

- **Source map.** `C:\I76GOLD\INPUT.MAP` on the logging disk (3754 B, md5 `03906b5b`). It is the same file on the par base.
- **Retail map.** The source map with the two Gold-only blocks `show_player_scores` and `show_team_scores` dropped
  (they are not in the retail exe's strings), plus the stock retail `throttle` / `steer` joystick axis blocks. The
  stock `radar_camera_toggle` block is left out because it binds W. The result is 4242 B, md5 `ccb6da72`.
- **Lint.** `tools/lint-input-map.py` against the retail exe (`6cc509ad`) is clean.
- **Gold lint.** The Gold map against the Gold exe reports only "no steer / throttle axis block". That warning is about
  joystick axes; keyboard play is not affected.
- **Write path.** `owner_tests.py` writes the map after copying the logging disk, before 86Box starts.
  - It uses `parrun.fat_replace`: an in-place write into the file's own cluster on the session copy, which refuses
    `emu\images`. It then reads the file back from the copy.
  - It prints `KEYS (retail): W throttle, S brake/reverse, A left, D right, Z e-brake, Space fire, Enter next weapon`.
  - Gold prints the keys of its own map. `owner_tests.py check` lints both maps.
- **Why not I76DRV `filehex` as briefed.** `filehex` holds 512 bytes (`fb[512]` in `i76drv.c`) and a script line is
  600 chars. The map is 4242 B. Rebuilding the shared `I76DRV.EXE` for this was not worth the risk to other lanes.
- **Guest check.** Par run `20261017-133955-owner-wasd-r166lmir-mel1-1` ran on a par base copy patched by the same
  function. The script was the `lmir` melee with I76DRV `keys W S A D`.
  - W: 0 to 55 m/s in 12 s.
  - S: stops the car (`stop` reached 0.11 m/s).
  - D and A: the heading turns in each 3 s steady phase. The forward vector went from (-1.00, 0.08) to
    (0.33, -0.94) on D and from (0.24, -0.96) to (-1.00, -0.04) on A.
- **PLAY-P166-LOGGED.** The bat keeps the logging disk's own maps. That disk holds the owner's saves and is not
  changed by this fix, so its retail folder still uses keypad 8/2/4/6.

## 2. Play default ~33.3 ms (02 / 03 / PLAY-P166-LOGGED)

- **Data already there.** The hardware matrix (lab `emu\results\hardware-matrix`) already had most of the answer.
  Lowest detail gave melee 27 ms and T05 on the ground 32 ms. `lmirtex` (the earlier ~40 ms R40MS) gave 36 / 41 ms.
  `lmir` had melee n 1 (30 ms) and no T05 run.
- **New runs.** Five more `lmir` runs on the retail 1.0 sim P166, headless, one VM at a time, with at most 2 86Box
  processes on the host. The table below has n 3 per context:

| retail sim P166 | melee | T05 descent | T05 on the ground |
|---|---|---|---|
| lowest (`r166low` / ref) | 26-27 | 30-31 | 31.5-32 |
| **`lmir` (play default)** | **31 [30-31]** | **32 [31-34]** | **36 [36-36]** |
| `lmirtex` (old R40MS) | 36 | 40 | 41 |

Values are the median sim_dt in ms: the median over runs of each run's median, with the run range in brackets.

- **Read-back.** The options block was read back from memory and matched the DEF in 6 of 6 runs.
- **Emulator speed.** Frame times are in guest ms and did not follow the emulator's speed. Melee read 30 ms at speed
  0.69 (3-4 VMs on the host) and 31 ms at 0.83-0.84 (2 VMs).
- **Choice.** `lmir` is the one setting that brackets 33.3 ms: melee is 7 % under it and T05 on the ground is 8 % over
  it. The setting one notch down is too fast and the one notch up is too slow. The custom detail sets between them
  (`lvis1`, `lvis2`, `lmirvis1`) have melee n 1 only.
- **DEF files.** `gen_hwmatrix.py play-defs` writes the files (read back):
  - `retail-plyr\R33MS.DEF`: 88 B, md5 `3a65561c`, retail default audio 3 / 5 / 10, flags 0.
  - `G33MS.DEF`: 96 B, md5 `e203577b`, the same detail bytes, Gold default audio 3 / 4 / 10, flags 0.
  - Gold has not been measured at `lmir`.
- **Who writes them.**
  - `owner_tests.py` `retail_def` / `gold_def` (02 / 03) write them through guest `filehex` with read-back. They
    check the audio bytes against the defaults code in each exe.
  - `owner_log.py play` writes both through a D:\PAR options-only script at every session start. `--options keep`
    skips this.
- **Not live-tested.** The options-only script of `PLAY-P166-LOGGED` has not been booted. It uses the same I76LOG and
  D:\PAR path that 02 used this morning. A dry run built the data disk with `PAR\SCRIPT.TXT` and `I76DRV.EXE`.

## 3. The 01 clip

- **Cause.** The clip came from run `20261016-231444-r166sim-t05c1v-1`. Its `run.json` shows `captured 6,
  repeated 7974`, with `capture_ms_mean null`: the capture thread never finished. Six 86Box processes were on the host.
  - The old `video.py` wrote every repeated frame as a raw 1.5 MB frame into ffmpeg from the capture thread.
  - The encoder ran single-threaded at BELOW_NORMAL and fell behind. The pipe write then blocked the capture thread.
  - The catch-up step wrote more repeats each time, so the thread never recovered.
- **Other clips.** The six other clips in `writeup\video` show no freeze of 5 s or more (ffmpeg `freezedetect`).
- **Other per-run video.** The arcade per-run video `20261016-224007-r166-t05clean-a-1\video.mp4` was also degraded
  (1567 frames captured, 3359 repeated). The 01 launcher no longer points to it.
- **Fix in `emu\tools\par\video.py`.**
  - Capture puts frames into a bounded queue (2 s). When the queue is full, the frame is dropped and counted; capture
    never blocks.
  - A writer thread encodes only the captured frames.
  - After stop, a retime pass writes the nominal frame rate from the host time stamps.
  - `run.json` gets `max_gap_s` and `frozen` (true when the gap is over 5 s).
  - Tested on a desktop window: 6 s run, then a run with a simulated 5 s encoder stall. Capture went on, 90 frames
    were dropped, the longest gap was 3 s, and the video timeline stayed real time (9.0 s).
- **Re-record.** Run `20261017-134408-r166sim-t05c1v-1`: headless, 1 VM, `ref-t05clean1-retail.txt`, emulator speed
  0.85. It captured 6936 unique frames with none dropped and a longest gap of 0.04 s.
  - The writeup clip is the 60 s descent cut from it: crest, jump, landing. It has no freeze of 2 s or more, and a
    thumbnail sheet shows the jump.
  - Playback runs in host time, so the game runs at the VM's speed (about 85-100 %).

## 4. 06 / 07: the F2 bookmark test

**The bug, as the banner now states it:** in Save Bookmark, typing a name, clicking off the name box, clicking back
into it and saving makes the stock game write the bookmark under a file name it never creates, so the bookmark
vanishes from the Load list. Sources: i76-map `shell/FIXES.md` F2 and `SAVE.md` section 4.

**Why this morning's control was inconclusive.** The control printed `OK` with the new bookmark `orphana` as
`save014.cmp`. That is consistent with Enter being pressed after the first name, which commits the save at once, so
the trigger never ran.

**`_lib\f2-drive.ps1` (new).** The driver:
- attaches read-only to the i76 started from the twin folder (and only that one);
- clicks main menu > TRIP > LOAD BOOKMARK > row 3, with the row index read back, > LOAD > ACCEPT SALVAGE > garage >
  SAVE BOOKMARK;
- types name 1 and clicks the paper at UI (560, 300), which is outside every Save-screen region in `SCREENS.md`;
- reads the slot `[0x10057f80]`, clicks the name box at (300, 138), and reads the slot again;
- types name 2, presses Enter, waits for `savegame.dir` to be written, and closes the game with WM_CLOSE.

Clicks use the leg-a method: the cursor is placed 1:1 and checked against the shell's own mouse before the button is
pressed. The expected slot readings are:
- stock shell: S ≥ 0 after the paper click, then -1 after the re-entry;
- F2 shell: S after both clicks.

**`twin-run.ps1` changes:**
- It runs `test-shell-f2.ps1` directly, which does the backup, the shell swap and restore, and the verdict file. The
  old route went through the twin's bat, whose trailing `pause` kept the owner's console lock held from 08:05 into the
  afternoon.
- Names are new on every run (`CTLA<hhmmss>` / `FIXA<hhmmss>`), because a repeated name would bring up the overwrite
  prompt.
- It prints PASS / FAIL from two independent readings: the slot in memory and whether the bookmark's file exists. The
  file check is what `dir_Load` applies to the Load list.
- If the driver stops, it judges on the file check alone.
- The banner has a six-step hand fallback with the expected screen at each step. For example, after the second click
  the name box empties.

**Not verified live.** Two things blocked a run under the console lock:
- This Windows session was disconnected (`query session`: Disc, no audio endpoint), so there was no input desktop for
  SetCursorPos and keybd_event.
- The lock was held by the `lab-whole-sim-tick` lane, and then by the owner's open 06 window.

Checked so far:
- all three scripts parse;
- the driver's timeout path writes its result and touches nothing;
- the driver refuses the daily-driver path.

One defect was found and fixed during that check. The first version could pick another lane's lab game through
`Get-GamePid`. It now matches only the twin's process and closes nothing else. The other lane's game was not affected:
its window handle was 0.

**One slip, now fixed.** When I tried to park what I took to be the owner's stale lock, the `lab-whole-sim-tick` lane
had re-taken the lock a moment before. I moved its live lock aside, saw that, and put it back unchanged within seconds.

## 5. What the owner still needs to do

- **02:** run it once and confirm that W / S / A / D drive the car in T05 and melee, and that the summary shows frames
  of ~30-36 ms.
- **03 (not run yet):** confirm the same for Gold, with the same graphic bytes. Gold has not been measured at `lmir`.
- **06 / 07 (first live run):** watch the clicks.
  - If 06 prints PASS ("control reproduced the bug") and 07 prints PASS ("the fix works"), item 48 is done.
  - If a `[driver] ERROR` line appears, follow the banner's steps and report the failing step. The driver log is next
    to `%TEMP%\owner-f2-*.json`.
- **01:** watch the new clip (item 52).
- **Open lock.** The owner's 06 window from this morning (pid 11876, at the twin bat's `pause`) still holds the console
  lock. Pressing a key in it releases the lock and restores the twin files from that window's 08:05 snapshot.
