# Rescue snapshot — live wrapper saves, 2026-07-18

Full copy of the live game's save folder (the Sikarugir wrapper prefix), taken
2026-07-18 as a safety net during savegame.dir repair work. Kept in the repo the
same way `saves/` keeps reference saves.

Contents:

- `save000.cmp`–`save013.cmp` — the campaign saves as of the snapshot.
- `savegame.dir` — the directory file as captured (the engine truncates its
  newest entry on every save; the launcher stubs re-pad it — see CLAUDE.md /
  docs/VERIFIED-FIXES.md before "fixing" its size).
- `save-01.cmp` — the known engine-bug orphan: a fresh-slot save writes the dir
  entry as `saveNNN` but the file as `save-01.cmp` (`sprintf("save%03d", -1)` —
  the slot allocator returned not-found). Kept as the live specimen of that bug
  (documented in `i76-save-editor.py`).
- `savegame.dir.bak-*` / `.pre-edit` — the editor's timestamped backups from the
  13th–15th; gitignored by the repo's `*.bak-*`/`*.pre-*` rules, present only in
  the local copy.
