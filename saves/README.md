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
| save000 | 2 | *(unnamed)* |
| save001 | 3 | *(unnamed)* |
| save002 | 5 | *(unnamed)* |
| save008 | 6 | TRUTH |
| save009 | 7 | TURRET TEST |
| save010 | 9 | Yay! |
| save011 | 10 | *(unnamed)* |
| save012 | 11 | GOT IT |
| save013 | 12 | Easy Groove! |
| save014 | 13 | OOOH SHIT |
| save015 | 14 | TRUCK STP SECURE |
| save016 | 15 | County Line |
| save017 | **none - see below** | So Many Turrets |

Slots 003-007 are missing by history, not by accident - they were deleted from the Mac
install before this snapshot, and `rescue-20260718/` below is the only copy left. The index
addresses files by name, so the gap is legal.

List them at any time with:

```bash
python3 i76-save-editor.py --dir saves --list
```

### save017 ships with no scene, on purpose

`save017` ("So Many Turrets") is the save the engine orphaned on 2026-07-19 and the launcher
stub recovered byte-identically (`docs/SAVE-ORPHAN-INVESTIGATION.md`; it is still the twin of
that session's `save-01.cmp`). Its index record lost its scene dword to the truncating write
described at the bottom of this file, and that byte **was never written** - there is nothing
to recover. It ships exactly as the game left it: scene 0, which the engine reads as "play
Scene 1".

It was very likely 16 - it is the next save after `save016` / scene 15, from the same evening
- but that is a guess about a byte nobody has, so the set ships the game's own value instead
of a fabricated one. Set it with the editor if you want the bookmark to jump properly.

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
| `windows-20260906/` | the 7 bookmarks that shipped in this directory before the Mac set landed: scenes 2, 3, 5 and four at scene 6, off the Windows install. Includes the `save004.cmp` recovered from the 2026-09-05 field case (see `PLAY-i76.ps1`). Index is intact - installable. |
| `rescue-20260718/` | a whole-folder snapshot of the Mac game directory taken 2026-07-18, and the only surviving copy of slots 003-007. **Its index is truncated** (844 bytes, needs 880 for its 14 records), so both install scripts will refuse it by design - treat it as a data archive, and note its cut tail entry `save013` is the same file the live set above indexes as scene 12. |

Both are complete sets rather than loose files, so the PowerShell installer can take either
one directly:

```bash
pwsh -File saves/Install-Saves.ps1 -GameDir "C:\path\to\Interstate 76" -SaveDir saves/windows-20260906
```

`install-saves.sh` has no equivalent switch - it always installs the set sitting beside it -
so on a Mac, copy an archived set up into this directory first.

`save006` in `windows-20260906/` lost its scene field to the same truncating write and was
**reconstructed as 6**, not recovered: its two siblings `save004`/`save005` are scene 6 and
byte-identical in size, so 6 is the only consistent value - but it is an inference, and the
original byte is gone.

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

## The index is written short - watch for it

The game writes `savegame.dir` **36 bytes short**, cutting the tail off the record it just
wrote. The last bookmark then has no scene number, and the shell lists it wrong or not at all.

A correct file is exactly `0x28 + count * 60` bytes: a 0x28 header whose first dword is the
record count, then 60 bytes per record - name at `+0`, flags at `+0x10`, **scene at `+0x18`**,
and the entry's display name in the 32 bytes *preceding* it (`0x08 + 60k`).

`PLAY-i76.ps1` re-pads a short file at launch and keeps a `.trunc-<timestamp>` copy, and the
Mac launcher stub does the same, so this mostly repairs itself - which is why the shipped
`savegame.dir` is 876 bytes where 13 records need only 820. That padding is deliberate; never
trim it back down. But **check the count before committing saves** - a truncated index
committed here would ship the bug to every machine:

```bash
python3 i76-save-editor.py --dir saves --list      # a truncated tail shows "mission ?"
```

Padding restores the file's length, not the lost dword: a record that was cut still reads
scene 0 afterwards, which is exactly what happened to `save017` above.
