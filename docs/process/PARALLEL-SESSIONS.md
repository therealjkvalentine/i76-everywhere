# Parallel Claude sessions — coordination protocol

Two (or more) Claude sessions run against this ONE working tree at once. They
share the filesystem AND the git HEAD. This is how they stay out of each other's
way and actually help each other.

## Hard rules (learned the hard way)

1. **Never `git checkout`/`switch`/`branch -f` a different branch.** HEAD is
   shared — switching branches moves it for *every* session, so the other
   session's next commit lands on your branch. (This happened 2026-07-18; it was
   recovered by fast-forwarding main.) Stay on `main`. If you need isolation,
   use a separate `git worktree` in a DIFFERENT directory, never a branch swap
   here.
2. **Commit small, commit often, prefix your lane.** Stage only your own hunks
   (`git add <specific files>`, never `git add -A`). Re-check `git status` right
   before staging — the other session may have edited the same files.
3. **Don't revert/rebase/reset shared history** while another session is active.
   All work is pushed; prefer additive fixes over history surgery.
4. **The live game process is shared too.** Only ONE session should write to
   game memory or dump heap at a time (writes/dumps perturb the other's reads).
   Reads are cheaper but still coordinate around active differentials.

## Division of labor that works (complementary, not duplicative)

- **Live / dynamic lane** (main thread): drive the running game, value-scan,
  differentials, the trainer overlay, field-testing controls.
- **Static / offline lane** (fable thread): disassemble i76.exe/DLLs on disk,
  research reimplementations, write methodology — never needs the live process,
  so it never contends.

They feed each other: the static lane found *ammo = int32 countdown in a weapon
sub-object* and *armor = int tenths ×8*, which tells the live lane exactly what
to scan for and why its flat scan missed. The live lane's HUD values give the
static lane ground-truth to confirm offsets. Keep this split.

## Lightweight "who's doing what" board
Update your line when you start a focus; keep it short.

- main lane: live memory scanning for ammo/armor addresses; trainer overlay.
- fable lane: static RE (structs, music, FFB), RE methodology, scope docs.
