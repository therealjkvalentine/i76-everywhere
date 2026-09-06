# Bookmark saves

Mission bookmarks that ship with the repo, so a fresh install on any machine can jump
straight to a given scene instead of replaying up to it. `i76-save-editor.py` already
defaults to this directory, and `autotest/enter-mission5.ps1` drives the LOAD BOOKMARK path
against it.

```
save000.cmp .. saveNNN.cmp    one bookmark each
savegame.dir                  the index: which slot is which scene
```

Current contents:

| slot | scene |
|---|---|
| save000 | 2 |
| save001 | 3 |
| save002 | 5 |
| save003 | 6 |
| save004 | 6 |
| save005 | 6 |
| save006 | 6 |

List them at any time with:

```bash
python3 i76-save-editor.py --dir saves --list
```

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

## Adding your own saves from another machine

The saves live loose in the game folder. Copy the whole set - the `.cmp` files **and**
`savegame.dir` together - into this directory, then commit.

On a Mac the game folder is inside the wrapper bundle:

```bash
cd ~/path/to/i76-everywhere
git pull
GAME=~/Applications/Sikarugir/"Interstate 76 - Software (DxWnd).app"/Contents/SharedSupport/prefix/drive_c/"GOG Games"/"Interstate 76"
cp "$GAME"/save*.cmp "$GAME"/savegame.dir saves/
python3 i76-save-editor.py --dir saves --list      # sanity check before committing
git add saves && git commit -m "saves: bookmarks for scenes N..M from the Mac install" && git push
```

Then on Windows, `git pull` and run `Install-Saves.ps1`.

## The index is written short - watch for it

The game writes `savegame.dir` **36 bytes short**, cutting the tail off the record it just
wrote. The last bookmark then has no scene number, and the shell lists it wrong or not at all.

A correct file is exactly `0x28 + count * 60` bytes: a 0x28 header whose first dword is the
record count, then 60 bytes per record - name at `+0`, flags at `+0x10`, **scene at `+0x18`**,
and an optional one-character suffix at `+0x1C` (what makes a bookmark read `SCENE 6.  Z`).

`PLAY-i76.ps1` re-pads a short file at launch and keeps a `.trunc-<timestamp>` copy, so this
mostly repairs itself. But **check the count before committing saves** - a truncated index
committed here would ship the bug to every machine:

```bash
python3 i76-save-editor.py --dir saves --list      # a truncated tail shows "mission ?"
```

`save006`'s scene field was lost to exactly this and has been **reconstructed as 6**, not
recovered: its two siblings `save004`/`save005` are scene 6 and byte-identical in size, so 6
is the only consistent value - but it is an inference, and the original byte is gone.
