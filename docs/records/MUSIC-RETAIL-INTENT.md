# Music intent of retail 1.0, and the proxy against it (2026-10-16)

The reference is the retail 1.0 exe (`I76.EXE` md5 `6cc509ad`, 1997-03-15) with its own shell DLL (`I76SHELL.DLL` md5
`7013d6ef`) and the original Play CD (data track 1 + audio tracks 2..17).
- **Method:** static only.
  - Ghidra export of the retail exe: `i76-map\ghidra\export-cd1997`.
  - Capstone on both shell DLLs and on our AiO exe (lab `game\i76.exe`, md5 `85de44a7`).
  - WRLD fields of the 40 retail mission files: lab `emu\work\retail-data\missions`. Sizes match the CD1 listing.
  - The existing emu traces: lab `emu\results\memtrace\*\mem.music.csv`, 41 runs.
- **Not done:** no game run, no listening. Nothing was installed in any game folder.
- **Background:** [docs/MUSIC-TRACK-MAP.md](../MUSIC-TRACK-MAP.md) (Gold / AiO, disc tables) and
  [EMU-MEMTRACE.md](EMU-MEMTRACE.md) section 6.

## 1. The retail music module (addresses: retail, then AiO / Gold)

| role | retail 1.0 | AiO / Gold | what it does |
|---|---|---|---|
| SetCdTrack | 0x4686b0 | 0x423320 | WRLD chunk handler (0x492fd0 retail) stores the mission's dword +8 in the track variable |
| PlayCdTrack(track, force) | 0x4686c0 | 0x423330 | see the rules below |
| StopCdMusic | 0x468800 | 0x4233d0 | MCI_STOP until the status reads stopped; clears playing and paused |
| pause / unpause | 0x468780 / 0x4687c0 (wrapped with the SFX pause: 0x4688d0 / 0x4688e0) | 0x4234a0 / 0x4234e0 | the toggle 0x478650 / 0x424190 |
| watchdog | 0x468830 | 0x423400 | runs every frame while music is marked playing |
| play(from, to) | 0x4787f0 | 0x424670 | MCI_PLAY, TMSF |
| variables | track 0x4dc7a0, paused 0x4dc7a4, playing 0x4dc7a8, loop 0x4dc7ac | 0x4ed800, 0x52456c, 0x524570, 0x524574 | |
| music level option | 0x5e14de (options block +0x0e) | 0x654b90 (+0x10) | |

**Rules (retail and AiO, the same code):**
- **PlayCdTrack does nothing while music is marked playing.**
  - Otherwise it closes and reopens the CD device, takes the new track (`-1` keeps the current one), and checks
    first <= track <= last.
  - **Music-level gate:** if the level is < 2 and force is 0, it returns: the track is kept, playing stays 0.
  - Then it plays and reads the status. If the status is not "playing", the track becomes -1 (silent until the next request).
  - If playing: playing = 1, and loop = (game state == 6, the shell).
- **Run rule:** from = track N, to = the start of track 15 when N < 15, else the start of N+1.
  - A mission plays **N..14 continuously**; 15, 16 and 17 play alone.
  - The 1997 exe has this rule. GOG's 2017 "pristine" exe plays one track only (MUSIC-TRACK-MAP).
- **TOC:** first track = 1 (hard-coded), last = MCI_STATUS_NUMBER_OF_TRACKS (capped at 50). Positions come from
  MCI_STATUS_POSITION + MCI_TRACK. The "end" entry is TMSF(last + 1).
- **Watchdog:**
  - It polls every **5 s in the shell (loop = 1) and every 60 s otherwise**.
  - If the status reads not ready or error, it clears playing.
  - If the status changed since the last read (the run ended), not paused, and level >= 2:
    - in the shell, it replays the same track;
    - otherwise it plays **track 2, as run 2..14**. The track variable keeps the mission's N.
  - **So the end of every run in a mission is followed by 0-60 s of silence**, then 2..14 (29:54), again and again.
- **Pause toggle:**
  - status playing: it saves the position and sends MCI_PAUSE;
  - status paused: MCI_RESUME (0x855);
  - status stopped: a new MCI_PLAY from the track.
  - The AiO status mapper 0x423fb0 maps 0x211 -> 4 (paused), like retail.
- **Volume:** auxSetVolume(level x 0xccc). Level 1 counts as 0.

## 2. Who asks for what (complete static list)

**Exe call sites (retail; the AiO / Gold sites are the same calls, listed in MUSIC-TRACK-MAP):**

| moment | code | music |
|---|---|---|
| boot movies (intro, credits SMK) | before the first shell | none started yet |
| mission start | WinMain: Stop, intro movie (its own SMK audio), then **PlayCdTrack(-1, force 0)** (0x401290 decompile l.525 / 557) | the mission's WRLD run, **only if the music level >= 2** |
| driving | watchdog | run N..14, gap 0-60 s, then 2..14 forever |
| Esc menu (0x44fc00) and mode switches (0x44fab0) | pause on entering, unpause on leaving | **continues where it was** (MCI_PAUSE / MCI_RESUME) |
| a movie in a mission (0x44e6e0) | pause at the start, unpause at the end (0x44e400 / 0x44ed90) | continues after the movie |
| Options screen opens in a mission (0x44b8f0) | PlayCdTrack(-1, **force 1**) | if stopped, restarts the current track, even at level < 2 |
| Options screen closes (0x44b9c0) | level < 2: Stop; in state 5: PlayCdTrack(-1, 0) | |
| outcome 1, won | Stop, then the outro movie | silence + the movie's audio |
| outcome 0 (failed) / 2 (aborted) | no music call | the run keeps playing through the mission-over menu until the shell |
| outcome 7, Replay | Stop, PlayCdTrack(-1, 0), then the reload runs the mission start again (Stop, Play) | **the track restarts from 0:00** |
| T17 won | Stop, OUT17F01.SMK, then the shell's end-of-campaign credits | see the shell table |

**Shell DLL call sites.** Every reference to the callback table was scanned: 7 sites in each DLL, the same structure.

| path | 1997 DLL (7013d6ef) | Gold DLL (deb41008) |
|---|---|---|
| every shell entry (boot, back from a mission) | 0x1002670b Stop, 0x10026717 **Play(15, force 1)** | 0x1001e4ac / 0x1001e4b9 Play(13, 1) |
| Credits open (Options > Credits, or the end of the campaign) | 0x10032964 Stop, 0x10032970 **Play(16, force 0)** | 0x10007af4 / 0x10007b01 Play(8, 0) |
| Credits leave | 0x100329e7 Stop, 0x10032a2b Stop, 0x10032a37 **Play(15, 1)** | 0x10007b77, 0x10007bb8, 0x10007bc4 Play(13, 1) |

- 15, 16 and 17 play alone, and loop = 1 in the shell, so each shell track **loops on itself**:
  - menu **Ovum Bisquit** (0:59);
  - credits **Malochio Down** (1:02), silent at music level < 2 (force 0).
- **No code path asks for track 17** (the Interstate '76 Theme).

## 3. The retail mission table (WRLD +8 of the 1997 CD MISSIONS\*.MSN, n = 40 files)

Run = the songs before the first gap. The run length is from the disc's track lengths (MUSIC-TRACK-MAP disc table).
After the run come 0-60 s of silence and then 2..14 (29:54), looping.

| WRLD | run (songs, length) | first song | retail missions | GOG data differs |
|---|---|---|---|---|
| 1 | data track: **open** (see section 6) | - | M06, S01, S02, S06 | GOG miss8 S01 = 2 |
| 2 | 2..14 (13, 29:54) | Never Get Outta The Car | T01, T15 | |
| 3 | 3..14 (12, 27:19) | Skeeter Gettin' Medieval | T02, T13, S03 | |
| 4 | 4..14 (11, 25:11) | Revenge Rocco Style | T03, T17, S04 | |
| 5 | 5..14 (10, 22:22) | Untitled #5 | T04, T14, S05, M05, M12, M14 | |
| 6 | 6..14 (9, 19:48) | The T'aint | T05, M04 | |
| 7 | 7..14 (8, 17:23) | Pimp Like Me | T06, S07, A01, M15 | **GOG T16 = 7** |
| 8 | 8..14 (7, 15:50) | Vigilante Shuffle | T07, M02, M07 | |
| 9 | 9..14 (6, 13:49) | Just Call Me Daddy | T08, M01 | |
| 10 | 10..14 (5, 11:48) | Desert Sky Groove | T09, M10 | |
| 11 | 11..14 (4, 9:19) | Untitled #11 | T10, M08 | |
| 12 | 12..14 (3, 7:07) | Henshin V3! | T11, M03 | |
| 13 | 13..14 (2, 4:52) | Mission Code: B.F.A.M. | T12, M13 | |
| 14 | 14 alone (2:33) | Untitled #13 | **T16**, M11 | |
| 15 | 15 alone (0:59) | Ovum Bisquit | M09 | |

- **The 1997 data and GOG data agree on 38 of 40 missions** (golden install, read-only: miss8 and miss16, 40 files each).
  - T16: 1997 = 14, GOG = 7 in both sets.
  - S01: 1997 = 1, GOG miss8 = 2, GOG miss16 = 1.
  - M01-M15 are the melee arenas; the campaign is T01-T17. The emu traces' melee asks for 9, which is M01.
- **The lab `game\miss8\M01.MSN` is the co-op replacement** (WRLD 2). The stock file is `M01.MSN.pre-coop`. The extra
  missions M41-M57 are co-op additions.

## 4. What the emu traces show, and why mission music never played there

- **Retail runs with the Gold-layout options file (n = 19 with a mission start):** the mission start reads
  track = WRLD (T05 6 in 11, melee 9 in 8), playing 0, loop 1.
  - Only the music-level gate leaves that state: the track is kept, playing is never set, and loop 1 is left over
    from the shell.
  - Each of the other three exits sets the track to -1 instead.
  - Playing turns 1 (loop 0) only after a forced request: the Options screen or the mission-over menu.
  - The Gold runs (n = 18) read -1: the Gold ISO has no audio tracks.
- **Why the level was below 2:**
  - Retail reads `I76PLYR.DEF` raw as its 0x58-byte block (0x44d660; defaults music 3, SFX 5, voice 10, channels 8; no
    version check).
  - Retail has no External Instruments and no Horizon Textures rows (menu records 0x4d9e04..0x4da29c). Its audio bytes
    therefore sit 2 lower than Gold's: music +0x0e, SFX +0x0f.
  - The emu copied the Gold-layout low-detail file in, so retail read music 0, SFX 0. It also read play flags = 1,
    which is **Arcade Phys.** (menu record 0x4d9b04, handler 0x44c390).
  - The graphics rows +0x00..+0x0d have the same meaning in both layouts, so the detail settings were right.
- **Already fixed by the emu lane today** (`emu\tools\memtrace\gen_scripts.py` 2026-10-16: `retail-plyr\RPLYR.DEF` in
  retail's layout: music 3, SFX 4, flags 0). This section confirms it from the music side.
- **Prediction, made before looking: with RPLYR.DEF the mission start reads playing = 1, loop = 0, track = WRLD.**
  - **Confirmed, n = 1:** `20261016-224135-r166sim-mloop-1` (its SCRIPT.TXT filehex has music 03, SFX 04, flags 0)
    reads track 9, playing 1, loop 0 at frame 8.
  - The run just before it, `20261016-223233-r166-t05clean-smoke-1`, still copied the Gold file and reads playing 0.
- **Side effect for the fps comparison:** retail ran with SFX level 0 (mixer volume 0) while Gold ran with SFX 4.
  Whether level 0 skips mixing work was not read. The "retail ~25 % faster than Gold" number may include it.

## 5. The proxy against retail: every mismatch

| # | behaviour | retail | proxy (default) | status |
|---|---|---|---|---|
| 1 | songs inside a mission run | continuous | the next song starts at the exe's next poll: **0-60 s of silence between songs** (lab logs 2026-10-04: changes 60.0-60.5 s apart) | **fixed, opt-in `I76_MUSIC_GAPLESS=1`** |
| 2 | Esc menu / movie | MCI_PAUSE, then MCI_RESUME: continues | the status never reads "paused", so the unpause re-issues PLAY. `I76_MUSIC_RESUME` turns that into a resume, except during the track-2 fallback, where it restarts the mission's run | **fixed, opt-in `I76_MUSIC_TRUE_PAUSE=1`** |
| 3 | Esc in the gap after a run ends | the toggle sends PLAY 17 -> 15 (end before start); a drive refuses it | plays 17.mp3 (the Theme on GOG's files) under the menu | **fixed with `I76_MUSIC_TRUE_PAUSE=1`**. Retail's refusal is assumed from the MCI rule, not measured |
| 4 | Replay, every shell entry | Stop, then Play: the track restarts from 0:00 | `I76_MUSIC_RESUME` (default on) resumes where it stopped | **taste.** `I76_MUSIC_RETAIL=1` sets RESUME off; `I76_MUSIC_RESUME=1` keeps it |
| 5 | menu / credits | 15 alone (Ovum Bisquit) / 16 alone (Malochio Down), looping | Gold DLL: 13 -> run 13..14, 8 -> run 8..14 | existing opt-in `I76_MUSIC_SHELL=1997`; taste |
| 6 | which song a track number is | disc order | GOG files 3/15/16/17 are disc 17/16/3/15 (length-matched, medium-high confidence) | existing opt-in `I76_MUSIC_DISC_ORDER=1`. **Needs one listen** before it becomes a default |
| 7 | T16 | 14 alone | 7..14 (GOG data) | **fixed, opt-in `I76_MUSIC_MISSIONS=1997`** |
| 8 | S01 | 1 | miss8 2, miss16 1 | not remapped. Which set our renderer loads was not checked |
| 9 | WRLD 1 (M06, S02, S06, retail S01) | open (section 6) | silence; the exe then sets the track to -1, so no fallback either | unchanged |
| 10 | run end | MCI_TO is a track start (exclusive) | exclusive since 2026-10-04 | matches |
| 11 | music level < 2 at mission start | no mission music; forced at the Options screen | transparent (the exe's own gate) | matches |
| 12 | cutscenes | Stop before the intro and outro; pause / resume around in-mission movies | transparent | matches. **`smack-music-fix` README is wrong** that "the game never stops CD music for FMV movies". It does. On GOG the bug came from a layer that ignores the exe's STOP / PAUSE |

**Umbrella:** `I76_MUSIC_RETAIL=1` turns on 1, 2/3, 5, 6 and 7, and RESUME off. Each switch can still be set alone.

**Proxy comments corrected:**
- "status poll every 5 s in a mission": it is 60 s in a mission, 5 s in the shell.
- "GOG numbering follows the CD, no translation needed": four files are not in disc order.
- The RESUME note now says why the restart happened.
- The data-track comment ("playing it produced SILENCE") stays as written, but it is unverified.

**Build:** lab `i76-uncap-lab\builds\music-retail-20261016\`.
- `Strlkup-mr2.dll`, md5 `1b32e557`, built from commit e025739 (MSVC x86, 0 warnings, the same 5 exports). One-click test: `MUSIC-RETAIL-TEST.bat`. (`Strlkup-mr1.dll` c271ae80 was the same hunks on 6779088.)
- Built from HEAD + `music-retail-mr1.patch` only, not from the working tree, which carries another lane's
  uncommitted edits.
- **Not run in game; the build only proves that it compiles.** All switches are off unless set, so with none set
  the music code behaves as before. The one exception is that `playing_now()` no longer advances a run while the
  mp3 reads "paused", which the old pause path never reached.

## 6. Open

- **WRLD 1 on a real CD.**
  - Retail accepts track 1 (first = 1) and sends MCI_PLAY from the data track to 15.
  - If the driver refuses, the status is not "playing", the track becomes -1, and the mission is silent with no
    fallback.
  - If the drive skips to audio, it plays 2..14.
  - Measurable in the emu (retail, RPLYR.DEF music 3): M06 Instant Melee, or S02 / S06. Read `cd_track` / `cd_playing`.
- **Gapless and true pause have not been run.** The log test is in the owner list, and an agent can run it on the lab
  twin.
- **The DISC_ORDER identification is length-only.**
- Whether GOG's own `win32.dll` music shim (used by `i76_pristine_fix.exe`, which has no WINMM import) honours
  STOP / PAUSE was not read.
