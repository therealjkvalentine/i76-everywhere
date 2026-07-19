# Interstate '76 music: the per-mission track map

*The game does NOT shuffle. Each mission names the CD track it wants, and the
engine plays that track. This doc has the extracted per-mission table, how it
was obtained, and the one field test that locks the numbering.*

*Status 2026-07-19: table extracted from the game's own mission files
(authoritative); the CD-track↔song-title mapping is a **hypothesis pending one
listen** (see "The experiment"). As far as we can find, this table does not
exist anywhere online.*

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
  own table of contents — not an index into a playlist, not a random pick.
- There is **no `rand()`, no LCG, no incrementing counter** anywhere in the music
  module (0x423320–0x424b6b). The "it just shuffled" assumption is wrong.
- The **front end has no track of its own**: `SetMusicTrack`'s only caller is the
  WRLD chunk handler. Menus/office replay whatever the last mission set. So
  hearing a mission's song in the office is authentic 1997 behavior, not a port bug.

Related globals: `0x4ed800` = current track (−1 = none), `0x524674` =
music-active flag, `0x4ed890` = MCI device, `0x524588`/`0x52458c` = TOC
first/last track, `0x524590[]` = per-track seek positions.

## The per-mission table (extracted from miss8/*.MSN)

Field = the raw WRLD dword. "Predicted" applies the hypothesis below.

| Mission | field | predicted file | predicted title |
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
