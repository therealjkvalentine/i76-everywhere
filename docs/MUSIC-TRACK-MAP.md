# Interstate '76 music: the per-mission track map

*The game does NOT shuffle. Each mission names a CD track, and the engine plays
a continuous RUN starting there (looping the run) — so songs changing mid-mission
is by design. This doc has the extracted per-mission table, how it was obtained,
and the one field test that locks the numbering.*

*Status 2026-07-19: table extracted from the game's own mission files
(authoritative); the CD-track↔song-title mapping is a **hypothesis pending one
listen** (see "The experiment"). As far as we can find, this table does not
exist anywhere online.*

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

So: in the mission state the run **loops from the mission's own track**; outside
it, playback falls back to **track 2** (almost certainly the theme — consistent
with the front end having no track of its own). `0x4c2164` is the game-state
global (`0x402610` is just `return [0x4c2164]`); the ==6 comparison is what
selects looping vs fallback. GUESS: 6 = in-mission/shell-active; not yet
confirmed live.

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
- The **front end has no track of its own**: `SetMusicTrack`'s only caller is the
  WRLD chunk handler. Menus/office replay whatever the last mission set. So
  hearing a mission's song in the office is authentic 1997 behavior, not a port bug.

Related globals: `0x4ed800` = current track (−1 = none), `0x524674` =
music-active flag, `0x4ed890` = MCI device, `0x524588`/`0x52458c` = TOC
first/last track, `0x524590[]` = per-track seek positions.

## The per-mission table (extracted from miss8/*.MSN)

Field = the raw WRLD dword = the track the mission's music RUN starts at (it then
plays on through track 15, looping). "Predicted" applies the title hypothesis below.

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

| CD track | file | predicted title | heard | confirmed? |
|---|---|---|---|---|
| 5 | music/5.mp3 | Revenge Rocco Style | | |
| 7 | music/7.mp3 | The T'aint | | |
| 8 | music/8.mp3 | Pimp Like Me | | |
| 9 | music/9.mp3 | Vigilante Shuffle | | |
| 11 | music/11.mp3 | Desert Sky Groove | | |
