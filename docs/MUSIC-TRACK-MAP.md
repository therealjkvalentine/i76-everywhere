# Interstate '76 music: the per-mission track map

*The game does NOT shuffle. Each mission names a CD track, and the engine plays
a continuous RUN starting there (looping the run) — so songs changing mid-mission
is by design. This doc has the extracted per-mission table, how it was obtained,
and the one field test that locks the numbering.*

*Status 2026-07-19: table extracted from the game's own mission files
(authoritative); the CD-track↔song-title mapping is a **hypothesis pending one
listen** (see "The experiment"). As far as we can find, this table does not
exist anywhere online.*

*Status 2026-10-04 (static audit, nothing launched): the front end DOES pick its
own tracks, the titles below were re-derived from published disc tables of
contents, and **GOG's `music\N.mp3` files are not in the original disc's order**
for four tracks. See the next section. It supersedes the July title hypothesis and
the "front end has no track of its own" line further down.*

## 2026-10-04: shell music, the real disc track lists, and GOG's file order

### Who starts CD music outside missions (static, capstone)

The shell DLL calls the exe through callback slot 20 = `0x423330 PlayCdTrack(track, force)` and slot 21 =
`0x4233d0 StopCdMusic` (`re\shell\CALLBACKS.md`). PlayCdTrack does nothing while music is already marked playing
(`[0x524570]`), so every shell site calls Stop first. A shell call runs in game state 6, so `[0x524574]` = 1 and
the 5 s poll replays the **same** track when it ends: shell music loops on itself.

| path | code | track asked: Gold/GOG DLL (pristine deb41008 = driver a300db63) | 1997 CD DLL (7013d6ef) |
|---|---|---|---|
| shell start = main menu (every return to the shell) | ShellMain 0x1001e4ac Stop, 0x1001e4b9 Play(**13**, force 1) (1997: 0x1002670b / 0x10026717) | **13** | **15** |
| Credits screen (Options > Credits, `OptionsMenu_Frame` 0x1000e7e0 sets screen 9) | `Credits_Open` 0x10007930: 0x10007af4 Stop, 0x10007b01 Play(**8**, force 0) (1997: 0x10032964 / 0x10032970) | **8** | **16** (0x10) |
| leaving Credits | `Credits_Frame` 0x10007bb8 Stop, 0x10007bc4 Play(13, 1) (1997: 0x10032a2b / 0x10032a37, 15) | 13 | 15 |
| **end of campaign** | after a won mission with trip scene == 0x11 (0x1001e5c5), ShellMain posts 0xC008; its handler 0x1001e17b sets screen 9 with `[0x10057a28]=1`, i.e. **the same Credits screen**; leaving it with that flag set goes to 0x10025980 instead of the menu | 8 (after 13 for a moment at shell start) | 16 |
| T17 outro movie before that | exe 0x404255 StopCdMusic, then OUT17F01.SMK through 0x49a070 (the movie's own Smacker audio) | none (CD stopped) | same |
| boot movies | exe 0x403037 `introf01.smk`, 0x4030e7 `credf01.smk` (the 60 s opening-credits movie, not the end credits), before the first shell; CD music not started yet | none | same |
| mission intro/outro movies | 0x40371c (intro, before mission music starts), 0x404265 (outro, after Stop); the SMK player pauses/resumes CD (0x4234a0 / 0x4234e0) | none: every .SMK carries its own audio track (header AudioRate[0] = 22050 Hz in all 29 GOG files) | same |
| in-mission options menu | 0x49514b Play(-1, force 1) / 0x49529a Play(-1, 0): restart the CURRENT track only if music had stopped (music level turned up) | current | same |
| `victory.rec` | `VictoryRecord_Update` 0x1002d340: network win statistics, no music | — | — |

The AiO and pristine exes have identical call sites (only the run end and some MCI-state code differ). The 1997 exe
(I76.EXE 6cc509ad) has the **same run rule as AiO**: 0x478803 `cmp esi,0xf / lea ebx,[esi+1] / jge / mov ebx,0xf`,
so the AiO "to 15" is the original 1997 behaviour and the GOG pristine "one track" is the Gold change. The 1997 exe
has the same flag (`0x46874c cmp eax,6`) and the same fallback to track 2 (`0x4688b4 push 2`).

Shell tracks in each run rule: 1997 menu 15 and credits 16 are >= 15, so each plays **alone** and loops. Gold
pristine: 13 alone, 8 alone, looping. **AiO (our driver): 13 -> 14 and 8 -> 14 as runs**, then the run restarts from
13 / 8; and with the proxy's inclusive-end bug (see the lab note) 15.mp3 is appended to each run.

### The discs (redump.org tables of contents; lengths are the disc's, not ours)

Original Play CD (redump [2938](http://redump.org/disc/2938/), [21541](http://redump.org/disc/21541/), 64228, 31703,
58554, 53327 all agree; 17 tracks = data + 16 audio). Gold Edition Play CD (redump
[21616](http://redump.org/disc/21616/), Xplosiv [42868](http://redump.org/disc/42868/) same layout; 14 tracks =
data + **13** audio, CD 2..14). Titles from Local Ditch's per-game lists (["CD audio by game", updated
2026-10-02](https://www.localditch.com/interstate-76/music/)); its downloadable FLACs' STREAMINFO lengths were read
(first 8 KB only) and match redump to 0.01 s, which ties each title to a length.

| disc track | original disc length | title | Gold disc |
|---|---|---|---|
| 2 | 2:35.0 | Never Get Outta The Car (short game edit; Gold has the 3:30 Extended Slap Mix) | 2 (3:30) |
| 3 | 2:07.5 | Skeeter Gettin' Medieval | 3 |
| 4 | 2:49.1 | Revenge Rocco Style | 4 |
| 5 | 2:34.3 | Untitled Track #5 (short edit; Gold 3:27) | 5 (3:27) |
| 6 | 2:25.2 | The T'aint | 6 |
| 7 | 1:32.7 | Pimp Like Me | 7 |
| 8 | 2:01.3 | Vigilante Shuffle | 8 |
| 9 | 2:00.5 | Just Call Me Daddy | 9 |
| 10 | 2:29.1 | Desert Sky Groove | 10 |
| 11 | 2:12.0 | Untitled Track #11 | 11 |
| 12 | 2:15.1 | Henshin V3! (short edit; Gold 2:55) | 12 (2:55) |
| 13 | 2:18.9 | Mission Code: B.F.A.M. | **absent** |
| 14 | 2:33.0 | Untitled Track #13 (LD also calls it #14; short edit; Gold 2:56) | **13** (2:56) |
| 15 | 0:59.2 | Ovum Bisquit | **14** |
| 16 | 1:02.2 | Malochio Down | **absent** |
| 17 | 1:02.0 (60 s + ~2 s) | Interstate '76 Theme | **absent** |

**The Gold disc lacks three songs: Mission Code: B.F.A.M. (original 13), Malochio Down (16) and the Interstate '76
Theme (17)**, and renumbers Untitled #13 to 13 and Ovum Bisquit to 14. (The task brief said 14 audio tracks; redump
counts 14 tracks including data.) Titles for 2/5/12/14 rest on position in Local Ditch's list only (our edits have
no FLAC of the same length); the rest are length-matched.

### GOG's files vs the disc (measured: MP3 frame walk of `music\*.mp3`, GOG pristine = driver = lab, same md5s)

GOG ripped the **original** disc (2.mp3 = 156.1 s is the short edit, not Gold's 210 s), but four files are out of
place:

| file | length | is disc track | song |
|---|---|---|---|
| 2, 4–14 | match disc 2, 4–14 to ±0.1 s (2.mp3 +1 s) | same number | as the table above |
| **3.mp3** | 60.11 s | **17** | **Interstate '76 Theme** (disc 3 is 127.5 s) |
| **15.mp3** | 62.30 s | **16** | Malochio Down |
| **16.mp3** | 127.50 s | **3** | Skeeter Gettin' Medieval |
| **17.mp3** | 59.27 s | **15** | Ovum Bisquit |

Length-only identification: 15/16/17 differ by 1-3 s, so 3.mp3 vs 15.mp3 rests on 60.11 matching the Theme FLAC
(60.05) and 62.30 matching Malochio (62.24). Confidence medium-high; one listen to 3.mp3 settles it.
`music-fix\strlkproxy.c` maps CD track N to `music\N.mp3` with no translation ("GOG's numbering follows the CD track
numbers"), so on our setup **CD track 3 plays the Theme** and 15/16/17 are rotated.

### Verdict: credits and menu

| setup | main menu | credits (Options or end of campaign) |
|---|---|---|
| 1997 original (1997 exe + DLL + original disc) | disc 15 **Ovum Bisquit**, alone, looping | disc 16 **Malochio Down**, alone, looping |
| Gold (Gold exe + DLL + Gold disc) | Gold 13 = Untitled #13 (long), alone, looping | Gold 8 = **Vigilante Shuffle**, alone, looping |
| GOG pristine (Gold exe + DLL + GOG mp3s) | 13.mp3 = Mission Code: B.F.A.M., alone | 8.mp3 = Vigilante Shuffle, alone |
| **ours** (AiO exe 6319abf7 + DLL a300db63 + proxy f9b0c481) | 13.mp3 B.F.A.M. -> 14.mp3 Untitled #13 -> (15.mp3 Malochio, proxy bug) -> repeat | 8.mp3 Vigilante -> Daddy -> Desert Sky -> #11 -> Henshin -> B.F.A.M. -> #13 -> (15.mp3 Malochio, proxy bug) -> repeat |

- **No version plays the title song at the credits.** No code path found requests disc 17 (the Theme) at all:
  shell 13/8 (Gold) or 15/16 (1997), mission WRLD values 1..15. (Static; hypothesis-grade for "never".)
- Our credits **song is right for Gold/GOG** (Vigilante Shuffle) but, because the AiO exe uses the 1997 run rule
  with the Gold DLL's numbers, it runs on through seven more songs instead of looping Vigilante.
- The **original 1997 credits song is Malochio Down** (and the menu Ovum Bisquit). The Gold DLL's 8/13 were chosen
  for the Gold disc, which had lost Malochio Down.
- Where we **do** play the Theme: every place CD track 3 is asked, because of GOG's file order. That is missions
  T02, T13, S03 (WRLD 3), the second song of runs starting at 2 (T01, T15, GOG S01), and the second song of the
  **after-run fallback 2..14** in every mission. On the disc those all played Skeeter Gettin' Medieval. If the
  owner heard "the title song" after a long mission or soon after the credits (a mission started next), this is
  the likeliest source. (Note: "track 2 = the theme" in the 2026-10-04 correction below means disc track 2,
  Never Get Outta The Car, not the Interstate '76 Theme.)

### 2026-10-04 lab test: built and measured (proxy 3a2c6d4a, lab twin, I76MUSIC_LOG=1)

All three are in `music-fix\strlkproxy.c` (switch rows in music-fix/README.md). The startup line
`music: run end exclusive, disc order ..., shell ..., resume on` names the active set. Tested on the twin
`i76-uncap-lab\game-dd-20261003` with 5 s silent stand-ins for 2/12/13/14.mp3 (originals restored and compared
with the driver's music folder afterwards: 16/16 identical). Logs: `i76-uncap-lab\autotest\runs\music-tmu-20261004\music-runs\*.log`.

- **The exe polls the CD every 60 s in a mission, not every 5 s.** A 5 s track is replaced at the next poll
  (`ended -> 13` 60.5 s after `PLAY track 12`, every run). The 5 s poll is the shell's (`[0x524574]` = state 6).
  So a mission run of N tracks always lasts at least N minutes of polls, whatever the mp3 lengths.
- **M03 / M09 by direct boot crash at frame 0 in the control too** (driver proxy f9b0c481: `CRASH 0xC0000005 at
  0x00000000`, return 0x40386E, state 5): melee arenas cannot be booted with `I76_MISSION`. The run-end test used
  T12 (WRLD 13, run 13..14) instead; M09 (15 alone) was not run live.
- **Run end, T12, n = 2 each:** exclusive (new default): `MCI_PLAY from=13 to=<start of 15> -> run 13..14`, 13 -> 14,
  then at the next poll **no track 15**: the exe's own fallback `MCI_PLAY from=2 ... -> run 2..14` follows
  immediately (confirms the state-5 theme fallback). `I76_MUSIC_TO_INCLUSIVE=1` (control): `run 13..15`,
  13 -> 14 -> **`PLAY track 15`** in both runs. T11 (run 12..14) showed 12 -> 13 -> 14 the same way (n = 1).
- **`I76_MUSIC_DISC_ORDER=1`, T02 (WRLD 3), n = 2:** `disc track 3 -> file 16.mp3 (disc order)`; control (off, n = 1)
  plays 3.mp3. The TOC the exe reads changes with it (`to=1057167119` vs `992875791`: the disc lengths moved).
- **`I76_MUSIC_SHELL=1997`, n = 2, control n = 2:** menu `run 13..14 -> disc 15 alone (file 17.mp3)`; Options >
  Credits `run 8..14 -> disc 16 alone (file 15.mp3)`; leaving Credits, 15 again. The exe's 5 s shell poll replays the
  track after it ends: credits replay at +63.6 s (15.mp3 = 62.3 s), menu at +60.3 s (17.mp3 = 59.3 s) (run 1). With
  `I76_MUSIC_RESUME` on, menu -> Credits -> menu logs `PLAY of a different run (16, paused run was 15): the paused
  track is closed`: a remapped shell run never resumes as a different track. Control: `run 13..14` (13 -> 14 at the
  5 s shell poll), `run 8..14`, with the exclusive end in force: no 15 in the shell either.
- Not tested live: shell -> mission -> shell with SHELL=1997 (by code: the mission's PLAY is a different run, so the
  paused shell track is closed; returning to the shell starts 17.mp3 from 0:00), the end-of-campaign credits.

### Proposed fix (proxy-side, opt-in, off by default) - BUILT 2026-10-04, see above

1. Land the inclusive-end fix from `i76-uncap-lab\docs\MUSIC-RUN-END-2026-10-04.md` first (it removes the
   stray 15.mp3 at the end of every run).
2. `I76_MUSIC_DISC_ORDER=1`: translate disc track -> file `{3:16, 15:17, 16:15, 17:3}`, identity otherwise, in
   `play_track()` **and** `track_len_ms()` (so the TOC lengths and positions the exe reads describe the disc
   order). Effect: WRLD-3 missions and the 2..14 fallback play Skeeter as on the disc; M09 (15) plays Ovum Bisquit.
3. `I76_MUSIC_SHELL=1997` (or `gold-loop`): when `[0x4c2164] == 6` (shell; same address in 9a232dcc and 6319abf7,
   getter 0x402610), rewrite an MCI_PLAY that starts at 13 to a one-track run of disc 15, and one at 8 to disc 16
   (1997: Ovum Bisquit menu, Malochio Down credits, each looping via the exe's own 5 s replay of `[0x4ed800]`).
   `gold-loop` keeps 13/8 but clamps the run to one track (GOG/Gold behaviour: Vigilante Shuffle alone).
   Alternative without a state read: patch the DLL immediates at load (0x10007b00 = 8, 0x10007bc3 = 0xd,
   0x1001e4b8 = 0xd; same bytes in deb41008 and a300db63), but the state check keeps the DLL file pristine.

Lab test plan (twin `C:\Users\james\i76-uncap-lab\game-dd-20261003` only, `I76MUSIC_LOG=1`, `I76_SKIP_MOVIES=1`):
1. Control, knobs off (n=2): boot to the menu, wait 70 s, Options > Credits, wait 70 s, leave. Expect
   `MCI_PLAY ... from=13 ... -> run 13..` then `from=8 ... -> run 8..`, files 13.mp3 / 8.mp3.
2. `I76_MUSIC_SHELL=1997 I76_MUSIC_DISC_ORDER=1` (n=2): expect `shell remap 13 -> 15` playing `17.mp3`, a replay of
   the same file after it ends (59 s + up to 5 s), then on Credits `8 -> 16` playing `15.mp3`, replaying after
   62 s; on leaving, back to `17.mp3`. Read `[0x4c2164]` with the trainer/peek to confirm 6 at each step.
3. `I76_MUSIC_DISC_ORDER=1` alone, `I76_MISSION=t02.msn`: expect `track 3 -> file 16.mp3`; with the knob off, 3.mp3.
4. Listen once to `3.mp3`, `15.mp3`, `16.mp3`, `17.mp3` (any player) to close the length-only identification.
5. End-of-campaign credits are the same `Credits_Open`; test 2 covers them unless a scene-0x11 bookmark exists.

## IMPORTANT: a mission does not play ONE song — it plays a RUN of tracks

**Corrected 2026-07-19** (this doc previously said "the engine plays that track",
which was wrong — the `MCI_PLAY` from/to computation was on screen and not read).

The mission's number is a **starting cue**, not a single selection. The play
function computes an END track too:

```
0x424684  mov edi,[esp+0x34]     ; edi = the mission's track (M01 -> 9)
0x424688  cmp edi, 0xf           ; >= 15 ?
0x42468b  lea esi,[edi+1]        ; "to" = track+1
0x42468e  jae skip
0x424690  mov esi, 0xf           ; else "to" = 15          <- the tell
...
0x424835  mov eax,[edi*4+0x524590]   ; dwFrom = position of the mission's track
0x42482e  mov esi,[esi*4+0x524590]   ; dwTo   = position of the end track
0x424844  mov ecx, 0xc               ; MCI_FROM | MCI_TO
0x424858  push 0x806                 ; MCI_PLAY
```

So a mission starting at track 9 plays **9 → 15 continuously**: tracks 9, 10,
11, 12, 13, 14 back to back (~13 minutes) before hitting the stop point.
Tracks **15 and up are the exception** — `from N to N+1`, i.e. that one track
alone (fitting, since track 17 is 59 s).

**Songs changing mid-mission is intended CD-era behaviour**, not a port bug: the
soundtrack plays on like an album from wherever the mission drops the needle,
rather than looping a 2-minute cue until you're sick of it.

This also reinterprets the shared numbers below: M05 / M12 / M14 all listing 5
are not three missions sharing one song — they share a *starting point in the
same run*.

### It DOES loop — the whole run, not one song

A watchdog re-issues playback when the run finishes (`0x423445` region):

```
0x423457  call 0x424550          ; probe: MCI_STATUS mode -> has playback ended?
0x42345e  je   ret
0x423460  mov  eax,[0x4ed800]    ; current track
0x423468  je   ret               ; -1 = none -> stay silent
0x42346a  mov  ecx,[0x524574]    ; state-derived flag (set from [0x4c2164] == 6)
0x423472  je   0x423477
0x423474  push eax               ; flag set -> REPLAY the mission's run from its track
0x423477  push 2                 ; flag clear -> fall back to track 2
0x423479  call 0x424670          ; MCI play
```

**Corrected 2026-10-04** (the paragraph here used to say a mission loops its own
run; that rested on the guess "6 = in-mission", which is backwards).
`[0x524574]` is written once, when music starts in 0x423330
(`0x4233ae call 0x402610; cmp eax,6; sete dl; mov [0x524574],edx`), and
`i76-map\subsystems\mission.md` has game state 6 = **shell running**, 5 =
mission running. A mission's music is started from WinMain at 0x4037e1 in state
5, so the flag is 0: when the mission's run ends the exe plays **track 2 (disc 2 =
Never Get Outta The Car; on our GOG files the run's 2nd song, 3.mp3, is the
Interstate '76 Theme) as a run 2..14**, re-polling every 60 s (0x42342c) rather than 5 s. The
shell (0x49514b, state 6) is where a track loops on itself. Not yet read live.

**The "to 15" is the AiO exe, not GOG pristine.** The disassembly above is from
the AiO exe (6319abf7 / 85de44a7). GOG pristine 9a232dcc has `cmp edi,1 / jge /
mov esi,1` at 0x424688 (and 0x4241a7): `to` = track+1, the mission track alone.
Also note `MCI_TO` is an end *position*: "to the start of track 15" stops before
15, so the AiO run is N..14, not N..15. Details and the proxy fix (it played 15
as an extra track): `i76-uncap-lab\docs\MUSIC-RUN-END-2026-10-04.md`.

## How the engine picks a track (static RE, i76.exe GOG Gold)

```
mission file (miss8/M01.MSN)  ->  'WRLD' chunk, first payload dword  = track
  chunk handler 0x4b8a10:  mov eax,[ebx+8] ; call 0x423320
  0x423320 (SetMusicTrack): mov [0x4ed800], eax        <- the live global
  play path 0x424670:
      cmp edi,[0x524588] / jl bail      ; bounds-check vs TOC FIRST track
      cmp edi,[0x52458c] / jg bail      ; ...and TOC LAST track
      sub edi, eax                      ; index = track - firstTrack
      mov eax,[edi*4 + 0x524590]        ; -> TOC seek position
      push 0x806                        ; MCI_PLAY
```

Key consequences:

- The WRLD value is a **literal CD track number**, validated against the disc's
  own table of contents — not an index into a playlist, not a random pick. It is
  the START of a run (see the section above), not the whole selection.
- There is **no `rand()`, no LCG, no incrementing counter** anywhere in the music
  module (0x423320–0x424b6b). The "it just shuffled" assumption is wrong.
- ~~The front end has no track of its own~~ **Wrong (2026-10-04).** `SetMusicTrack`'s
  only caller is the WRLD chunk handler, but the shell DLL starts music through
  callback 20 (`0x423330`) with its own numbers: menu 13, credits 8 (Gold DLL); 15
  and 16 in the 1997 DLL. See the 2026-10-04 section at the top.

Related globals: `0x4ed800` = current track (−1 = none), `0x524674` =
music-active flag, `0x4ed890` = MCI device, `0x524588`/`0x52458c` = TOC
first/last track, `0x524590[]` = per-track seek positions.

## The per-mission table (extracted from miss8/*.MSN)

Field = the raw WRLD dword = the track the mission's music RUN starts at (it then
plays on up to the start of track 15, i.e. through 14, on the AiO exe; then the
theme run from track 2 — see the 2026-10-04 correction above). "Predicted" applies the title hypothesis below.

**2026-10-04: the "predicted" columns below are superseded.** They used the July
off-by-one title hypothesis. Corrected titles are in the disc table at the top
(e.g. M01's 9 = Just Call Me Daddy, not Vigilante Shuffle; 15 = Ovum Bisquit on the
disc but Malochio Down in GOG's 15.mp3). Also, M01..M15 are the **melee arenas**; the
campaign is T01..T17 (`t%2.2d.msn`). Campaign values (GOG miss8 = miss16; 1997 CD
`MISSIONS\*.MSN` read from `Downloads\I76_CD1.ISO`):
T01 2, T02 3, T03 4, T04 5, T05 6, T06 7, T07 8, T08 9, T09 10, T10 11, T11 12, T12 13,
T13 3, T14 5, T15 2, **T16 7 (1997 CD: 14)**, T17 4. Scenarios S01 2 (miss16 and 1997: 1),
S02 1, S03 3, S04 4, S05 5, S06 1, S07 7. Every M/A value is identical on the 1997 CD.

| Mission | field (run START) | predicted first file | predicted first title |
|---|---|---|---|
| A01 | 7 | music/7.mp3 | The T'aint |
| M01 | 9 | music/9.mp3 | Vigilante Shuffle |
| M02 | 8 | music/8.mp3 | Pimp Like Me |
| M03 | 12 | music/12.mp3 | Untitled #11 |
| M04 | 6 | music/6.mp3 | Untitled #5 |
| M05 | 5 | music/5.mp3 | Revenge Rocco Style |
| M06 | 1 | — | (see "the value 1" below) |
| M07 | 8 | music/8.mp3 | Pimp Like Me |
| M08 | 11 | music/11.mp3 | Desert Sky Groove |
| M09 | 15 | music/15.mp3 | Tulip Waltz |
| M10 | 10 | music/10.mp3 | Just Call Me Daddy |
| M11 | 14 | music/14.mp3 | Untitled #13 |
| M12 | 5 | music/5.mp3 | Revenge Rocco Style |
| M13 | 13 | music/13.mp3 | Henshin V3! |
| M14 | 5 | music/5.mp3 | Revenge Rocco Style |
| M15 | 7 | music/7.mp3 | The T'aint |

Notes:
- M05 / M12 / M14 deliberately share track 5; M02 / M07 share 8; A01 / M15 share 7.
- `miss8` and `miss16` agree on every mission **except S01** (2 vs 1) — a real
  authored difference between the 8-bit and 16-bit mission sets, not corruption.
- **The value 1** (M06, S02, S06): on a mixed-mode CD track 1 is the DATA track.
  Either the original disc reported first-track = 2, making 1 an out-of-bounds
  "no music" sentinel, or it resolves to the data track and plays nothing. Both
  readings mean *silence by design* for those missions — worth confirming by ear.

Reproduce the table:
```
python3 - <<'EOF'
import glob,os,struct
G="<game dir>"
for f in sorted(glob.glob(G+"/miss8/*.MSN")):
    b=open(f,'rb').read(); i=b.find(b'WRLD')
    print(os.path.basename(f), struct.unpack_from('<i',b,i+8)[0])
EOF
```

## The title hypothesis (what needs one listen)

**Superseded 2026-10-04.** The "CD track N = Local Ditch combined entry N−1" rule is
wrong: redump's disc TOCs plus Local Ditch's per-game list give CD 8 = Vigilante
Shuffle, 9 = Just Call Me Daddy, etc. (the table at the top). The "Ruled out already"
paragraph below is also wrong for four files: GOG's 3/15/16/17.mp3 hold disc tracks
17/16/3/15. Kept for history.

Local Ditch's game-track listing is **audio-ordinal** numbered (their #1 =
"Interstate '76 Theme"). On a mixed-mode disc the first audio track is CD track
2, so `CD track N = their entry N−1`. That yields exactly **16 CD tracks
(2..17)**, which matches GOG's 16 shipped mp3s (`music/2.mp3`..`music/17.mp3`)
one-for-one — the main reason to believe it.

The residual risk is a silent off-by-one: the play path subtracts the TOC's
*first track*, and our DxWnd virtual CD reports `first=1` (it models the data
track — see `music/tracklen.nfo`). If the original disc reported `first=2`, the
same WRLD value could land one track away on this port.

**Ruled out already:** the file mapping itself. `setup-music.sh` hard-links
`music/N.mp3` → `TrackNN.mp3`, and dxwplay's regenerated TOC lists track 1 as
`type=d` (data) with tracks 2–17 as music whose durations match the mp3s exactly
(track 2 = 156 s ↔ `music/2.mp3` = 156.08 s, track 17 = 59 ↔ 59.30 s, spot-checked
with `afinfo`). So `TrackNN.mp3` really is redbook track NN.

## The experiment (one minute, settles the whole table)

1. Run `tools/i76-trainer.ahk` in the prefix (it now shows a `TRACK` line:
   the live value of `0x4ed800`, the predicted file, and the predicted title).
2. Load **M01**. The overlay should read `TRACK 9  music/9.mp3  "Vigilante Shuffle"`.
3. Listen.
   - Hear **Vigilante Shuffle** → hypothesis confirmed; this table is correct as
     written, mark it verified.
   - Hear **Just Call Me Daddy** (the *next* title) → the field is an audio
     ordinal, not a CD track: every predicted file/title shifts +1.
   - Hear something else entirely → the TOC index is off; capture the track
     number shown and the actual song, and re-derive.
4. Don't know the songs by name? Skip the titles — just play `music/9.mp3` in any
   player and compare it to what the mission played. That settles it without
   needing the titles at all, and is the more reliable test.

Then confirm the sentinel: load **M06** and check whether it is genuinely silent.

## Why this matters beyond trivia

- **Verification** — proves the port plays what the designers chose, per mission.
- **Re-scoring** — the mapping is one dword per mission file, so any mission's
  music can be changed without touching audio.
- **Now-playing** — `0x4ed800` + `0x524674` give a launcher/overlay the exact
  track and play state (see `tools/i76-trainer.ahk`).

Full disassembly notes: `scratchpad-fable/music-track-selection.md`.
Track titles: [Local Ditch](https://www.localditch.com/interstate-76/music/) ·
[Fandom](https://interstate76.fandom.com/wiki/Soundtrack) — neither documents
mission assignment.

## Sources: what's checkable vs what is confabulated

Asked repeatedly (2026-07-19) whether the mission↔song mapping is published.
**It is not.** What exists online is the *album*, which is a different product
from the game disc. Grading the available material:

| Claim | Verdict |
|---|---|
| The 32-track Bullmark album listing (titles, durations, personnel) | **Real** — [Fandom](https://interstate76.fandom.com/wiki/Soundtrack), [Discogs](https://www.discogs.com/release/992774-Bullmark-Interstate-76-Original-Game-Soundtrack), Soundtrack Central agree |
| Local Ditch's shorter "game track listing" | **Real**, and the closest thing to a game-disc listing — the basis of the title hypothesis above |
| Any prose "X plays during patrol missions / boss fights" mapping | **Unsupported.** No source documents it |
| "Tracks 2 through 32 were Redbook audio tracks [on the game disc]" | **False.** The disc has 16 audio tracks (2–17), total 32:56 — see below |
| "Tracks play sequentially or loop depending on mission length/pacing" | **Wrong mechanism.** It's a fixed per-mission start track and a fixed end track (15), looping |

**Album ≠ game disc** — the Fandom page itself says the album "contained most
tracks from the game as well as a few other tracks... that weren't featured in
the game". Measured locally:

```
game disc: 16 tracks, 1976 s = 32:56   (music/2.mp3 .. music/17.mp3)
album:     32 tracks, 3045 s = 50:45
```

Duration-matching the two is **suggestive but not conclusive** — several album
titles collide on length and two game tracks match nothing:

```
game  9 (121s) -> Vigilante Shuffle (119s)      <- mild support for the hypothesis
game  8 (121s) -> Vigilante Shuffle (119s)      <- identical length, collision
game  4 (169s) -> ** NO ALBUM MATCH **
game 12 (135s) -> ** NO ALBUM MATCH **
```

And these album tracks are **longer than the longest game track (2:49)**, so they
cannot be on the disc as released — yet confident-sounding write-ups assign them
to missions: They Call Me Swinger (3:18), Spineless Funk (3:06), Tulip Waltz
(3:35), Never Get Outta The Car Ext. (3:28), Macadamia Medley (5:39).

**Rule of thumb for this topic:** trust (1) the mission files, (2) the
disassembly, (3) your own ears against `music/N.mp3`. Treat any prose
mission→song mapping as invented until it cites one of those three.

### Verified-by-ear log (fill in as you identify tracks)

Predicted titles corrected 2026-10-04 (length-matched, see the top section).

| CD track | file | predicted title | heard | confirmed? |
|---|---|---|---|---|
| 3 (disc) | music/16.mp3 | Skeeter Gettin' Medieval | | |
| 17 (disc) | music/3.mp3 | Interstate '76 Theme | | |
| 5 | music/5.mp3 | Untitled Track #5 (short edit) | | |
| 7 | music/7.mp3 | Pimp Like Me | | |
| 8 | music/8.mp3 | Vigilante Shuffle | | |
| 9 | music/9.mp3 | Just Call Me Daddy | | |
| 11 | music/11.mp3 | Untitled Track #11 | | |
| 13 | music/13.mp3 | Mission Code: B.F.A.M. | | |
| 15 (disc) | music/17.mp3 | Ovum Bisquit | | |
| 16 (disc) | music/15.mp3 | Malochio Down | | |
