# Windows bookmarks, archived 2026-09-06

The 7-bookmark set that sat in `saves/` until the Mac campaign set (scenes 2-15) replaced
it. Moved here whole rather than deleted, because a set is only installable with its own
index: `savegame.dir` addresses the `.cmp` files by name, so the two cannot be interleaved.

| slot | scene |
|---|---|
| save000 | 2 |
| save001 | 3 |
| save002 | 5 |
| save003 | 6 |
| save004 | 6 |
| save005 | 6 |
| save006 | 6 |

`save000`-`save002` are byte-identical to the Mac set's; `save003` is byte-identical to
`rescue-20260718/save003.cmp`. What only exists here is `save004` - the save recovered from
the 2026-09-05 field case (`PLAY-i76.ps1`) - and `save005`/`save006`, which are two names for
one file (identical bytes). `save006`'s scene was reconstructed as 6, not recovered; see
`../README.md`.

The index is intact (460 bytes, exactly `0x28 + 7 * 60`), so this set installs as-is:

```bash
pwsh -File saves/Install-Saves.ps1 -GameDir "C:\path\to\Interstate 76" -SaveDir saves/windows-20260906
```
