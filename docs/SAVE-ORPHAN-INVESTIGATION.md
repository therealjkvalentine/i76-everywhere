# The orphaned-save bug: what's established, what's still open

*A save made 2026-07-19 15:22 "vanished": `savegame.dir` listed `save017` but the
file on disk was `save-01.cmp`. Data was intact and recovered byte-identical.
This doc records the causation investigation — including what we could NOT rule
out — because "it's a vanilla engine bug" had been asserted in this repo's notes
without ever being tested.*

## Symptom

A fresh-slot save writes the **directory entry** as `saveNNN` but the **file** as
`save-01.cmp`. The bookmark then points at a nonexistent file, so the save looks
lost in-game while sitting on disk intact.

## Recovery (proven)

Copy the orphan onto the slot the directory expects. Done 2026-07-19:
`save-01.cmp` → `save017.cmp`, byte-identical, all 13 bookmarks then resolved.
Automated since — see `rescueOrphanSave()` in `i76-launch-stub.swift` (boot +
mid-session behind the same >3 s quiescence guard as the dir padding).
That is **recovery, not prevention**: the engine still writes the orphan; you
just never see the consequence.

## Causation: suspects tested

The user's challenge — "isn't it more likely we broke this?" — was correct to
raise. Three port-introduced suspects were tested:

| Suspect | Verdict | Evidence |
|---|---|---|
| Our `savegame.dir` padding (`padSaveDir`) | **CLEARED** | Oldest orphan on disk: Jul 14 **14:27**. `padSaveDir` committed Jul 14 **15:15** (b77f297) — 48 min later. The orphan predates the padding existing. |
| Our `.bak-*` / `.pre-edit` clutter confusing a file scan | **CLEARED** | `I76SHELL_1083.DLL` imports FindFirstFileA/FindNextFileA, but its **only** glob pattern is `addon\*.lvl`. There is no `save*.cmp` enumeration, so extra files in the folder are invisible to the allocator. |
| Our save editor writing `savegame.dir` | **NOT CLEARED** | The editor shipped Jul 13 21:52 and had written that file (`save006.cmp.pre-edit`, Jul 13 20:29) **before** the first orphan on Jul 14 14:27. The slot gaps (003–007 absent) are consistent with editor/deletion activity. Cannot be excluded. |

## What is genuinely established

- The filename is built **inside the game's own DLL**: `I76SHELL_1083.DLL`
  contains `save%3.3d.cmp` and `save%3.3d`. Nothing we ship writes a negative
  slot (grepped: the only repo hits are comments *describing* the bug).
- The bug was **reproduced 2/2 on 2026-07-14** during save-editor work, days
  before the memory-RE work began (first Ghidra commit 2026-07-18), and was
  observed again 2026-07-15 — where it was noted **intermittent**
  ("save010/011 got real filenames, the session's last save became save-01.cmp
  again"). See `SAVE-FORMAT-GAPS.md`.
- Intermittency **undercuts the "slot exhaustion" theory**, so pruning slots is
  housekeeping, not a cure.

## What is NOT established (do not repeat these as fact)

1. **`sprintf("save%03d", -1)`** — repeated throughout this repo's notes as the
   mechanism. It does not fit: `%3.3d` of −1 yields `-001`, not `-01`
   (`python3 -c "print('save%3.3d' % -1)"` → `save-001`). The *allocator
   returning not-found* is well supported; the exact format call that produces
   `-01` is **still unidentified**.
2. **"It's a vanilla engine bug."** Never tested. No public report of this exact
   symptom was found — community discussion of I'76 saves is about `savegame.dir`
   being essential to back up, not about orphaned files.

## The decisive experiment (not yet run)

Start from a **virgin `savegame.dir`** (move every save aside; game closed), then
make three fresh-slot saves in-game **without the editor ever touching them**.

- Orphan appears → genuinely the engine; vanilla behaviour; rescue patch is the
  right answer and the editor is exonerated.
- No orphan → our editor's directory writes are implicated, and that is a real
  bug to fix at the source rather than paper over.

Back up first (a full copy was taken to `save-backup-<ts>/` in the game folder on
2026-07-19). Run it with the game closed — the engine rewrites `savegame.dir` on
every save.
