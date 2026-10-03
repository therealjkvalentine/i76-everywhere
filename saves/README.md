# Bookmark saves

Mission bookmarks that ship with the repo, so a fresh install on any machine can jump
straight to a given scene instead of replaying up to it. `i76-save-editor.py` already
defaults to this directory, and `autotest/enter-mission5.ps1` drives the LOAD BOOKMARK path
against it.

```
save000.cmp .. saveNNN.cmp    one bookmark each
savegame.dir                  the index: which slot is which scene
```

Current contents - the Mac campaign run, scenes 2 through 15, lifted from the wrapper
2026-09-06. The names are what the LOAD board prints:

| slot | scene | name |
|---|---|---|
| save000 | 1 | *(unnamed)* |
| save001 | 2 | *(unnamed)* |
| save002 | 3 | *(unnamed)* |
| save008 | 5 | TRUTH |
| save009 | 6 | TURRET TEST |
| save010 | 7 | Yay! |
| save011 | 9 | *(unnamed)* |
| save012 | 10 | GOT IT |
| save013 | 11 | Easy Groove! |
| save014 | 12 | OOOH SHIT |
| save015 | 13 | TRUCK STP SECURE |
| save016 | 14 | County Line |
| save017 | 15 | So Many Turrets |

*Corrected 2026-10-01.* Every scene in the table used to read one too high and save017 "none": the editor's
directory model put the scene dword at the wrong offset (the next record's), so each row wore the next row's scene
and the last row looked truncated. The real record is `{u32 scene, name[32], file[16], u32 state, u32 0}` at
`4 + 60k`; `python i76-save-editor.py --dir saves --list` and `node tools/tests/test-save-editor-dir.mjs saves/savegame.dir`
now agree with the bytes.

Which scene a bookmark *plays* depends on its state field (sandbox-verified 2026-10-01, `docs/records/SAVES-LEG-B-RUN-2026-10-01.md`):
a post-mission save (state 1) plays scene+1; a save made from the garage (state 8) plays the scene as written. The
scenes in the table are the stored dwords.

Slots 003-007 are missing by history, not by accident - they were deleted from the Mac
install before this snapshot, and `rescue-20260718/` below is the only copy left. The index
addresses files by name, so the gap is legal.

List them at any time with:

```bash
python3 i76-save-editor.py --dir saves --list
```

### save017 has a scene after all (correction, 2026-10-01)

`save017` ("So Many Turrets") is the save the engine orphaned on 2026-07-19 and the launcher stub recovered
byte-identically (`docs/records/SAVE-ORPHAN-INVESTIGATION.md`). This section used to say its index record had lost its
scene dword to a "truncating write" and shipped as scene 0. There was no truncating write: the editor read the scene
from the following record, and for the last record there is none. Under the real frame the record reads scene 15,
the value the game wrote, and the directory is exactly 4 + 60 x 13 bytes plus the slack an older editor appended.

## Installing them

Windows, into whichever install you are testing:

```bash
pwsh -File saves/Install-Saves.ps1 -GameDir "C:\path\to\Interstate 76"
```

Mac (CrossOver/Sikarugir wrapper):

```bash
./saves/install-saves.sh
```

Both back up whatever is already there to `save-backup-<timestamp>/` beside the game before
copying, because installing overwrites the whole set - the index has to match the `.cmp`
files, so slots cannot be merged piecemeal.

## The other sets kept here

| directory | what it is |
|---|---|
| `lab-20261002/` | read-only copy of the sandbox set as of 2026-10-02 (`../i76-uncap-lab/game`): save000-008 incl. the Leg A/B bookmarks and the player's saves of that day, plus `reconfig.spc` / `trip4.spc` (same writer). Test fixtures for `tests/test_save_editor.py` and the base for `i76-calibration-saves.py`; installable (index exact, 544 B = 4 + 60 x 9). |
| `windows-20260906/` | the 7 bookmarks that shipped in this directory before the Mac set landed: scenes 2, 3, 5 and four at scene 6, off the Windows install. Includes the `save004.cmp` recovered from the 2026-09-05 field case (see `PLAY-i76.ps1`). Index is intact - installable. |
| `rescue-20260718/` | a whole-folder snapshot of the Mac game directory taken 2026-07-18, and the only surviving copy of slots 003-007. Its index is complete (844 bytes = 4 + 60 x 14 records; the old installers demanded 880 and refused it: fixed 2026-10-01). Its `save013` is the same file the live set above indexes as scene 11. |

Both are complete sets rather than loose files, so the PowerShell installer can take either
one directly:

```bash
pwsh -File saves/Install-Saves.ps1 -GameDir "C:\path\to\Interstate 76" -SaveDir saves/windows-20260906
```

`install-saves.sh` has no equivalent switch - it always installs the set sitting beside it -
so on a Mac, copy an archived set up into this directory first.

`save006` in `windows-20260906/` was once "reconstructed as 6" on the belief that its scene field had been lost
to a truncating write. Under the corrected frame the record reads scene 6 directly (state 8, name `z`); nothing was
lost. The directory carries 36 bytes of slack from the old editor, which the game ignores (it reads `count` records).

## Adding your own saves from another machine

The saves live loose in the game folder. Copy the whole set - the `.cmp` files **and**
`savegame.dir` together - into this directory, then commit.

On a Mac the game folder is inside the wrapper bundle:

```bash
cd ~/path/to/i76-everywhere
git pull
GAME=~/Applications/Sikarugir/"Interstate 76 - Software (DxWnd).app"/Contents/SharedSupport/prefix/drive_c/"GOG Games"/"Interstate 76"
cp "$GAME"/save0*.cmp "$GAME"/savegame.dir saves/
python3 i76-save-editor.py --dir saves --list      # sanity check before committing
git add saves && git commit -m "saves: bookmarks for scenes N..M from the Mac install" && git push
```

Glob `save0*.cmp`, not `save*.cmp`: an orphaned `save-01.cmp` in the game folder would
otherwise ride along, and the installers' own `save*.cmp` glob would then drop it into the
next machine's game folder, where the stub's orphan rescue can copy it over a live slot.

If you are replacing the set that is already here, move the old one into a dated
subdirectory instead of deleting it - the index and its `.cmp` files have to travel together
to stay installable.

Then on Windows, `git pull` and run `Install-Saves.ps1`.

## The index was never written short (correction, 2026-10-01)

For three months this section said the game wrote `savegame.dir` 36 bytes short and the launchers re-padded it at
every start. The game writes it exactly: `4 + 60 x count` bytes, a `u32 count` then 60-byte records
`{u32 scene, char[32] display name, char[16] file name, u32 state, u32 0}`. The "missing 36 bytes" were the editor's
model (`0x28` header, scene at `+0x18` of a record that started 36 bytes late), which read each record's scene from
the record after it. Consequences, now fixed: every scene the editor showed was one too high; the editor wrote scene
numbers into the wrong record; removing a slot shifted every remaining record by 36 bytes; the installers refused
game-written files; the launchers appended zero slack and kept `.trunc-*` copies of files that were whole.

The slack is harmless (the game reads `count` records) and the shipped directories keep theirs. Check a set with:

```bash
python3 i76-save-editor.py --dir saves --list
node tools/tests/test-save-editor-dir.mjs saves/savegame.dir
```
