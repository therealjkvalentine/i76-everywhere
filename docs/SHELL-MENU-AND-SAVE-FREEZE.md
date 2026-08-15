# The shell, the menus, the cursor, and the save freeze — how the "fucky stuff" works

*Investigation of the save/menu/popup weirdness (2026-08-10). User symptoms: saving freezes the
game; the save-name text box is hard to type into and "works sometimes"; it always says you are
overwriting; the mouse ends up in the wrong position; and there seem to be several different
kinds of menu (launch, save, popups, inventory) that all behave differently.*

**They are all the same root system, and it is not the 3D game.** Interstate '76 is two programs
bolted together: the 3D **engine** (`i76.exe`) and a 2D **shell** (`i76shell.dll`, the GOG
build's rename of the Nitro Pack's `NITSHELL.DLL`) that draws every menu, form, save/load screen,
garage and popup. Almost all the weirdness is the shell, and the shell was written for a 1997
fullscreen 640×480 DirectDraw world that no longer exists under dgVoodoo + a modern overlay stack.

## The architecture (why there are "different menus")

- `i76.exe` calls `ShellMain` (exported from `i76shell.dll`) and **blocks in it** until you pick
  something (roanish RE: `game_session_run` builds a 32-entry callback table, calls `ShellMain`,
  and only resumes when it returns a result code). While a menu is up, the engine's own loop is
  paused and the **shell is driving**.
- The shell draws into the engine's 640×480 surface through those callbacks — so menus, the
  garage/inventory, the driver-entry form, the save screens and the confirmation popups are **all
  the same widget system**, not separate UIs. What looks like "different menus" is one shell in
  different modes.
- Confirmed by the DLL's imports: `i76shell.dll` pulls in `DialogBoxParamA`, `MessageBoxA`,
  `SendDlgItemMessageA`, `GetAsyncKeyState`, `GetKeyState`, `PeekMessageA`/`TranslateMessage`/
  `DispatchMessageA`, `SetCursorPos`, `ClipCursor`, `SetCursor`, `ShowCursor`, `WaitMessage`,
  `WaitForSingleObject`. It has **no dialog resources of its own** — the native `MessageBoxA`/
  `DialogBoxParamA` calls are all for **errors and multiplayer/modem** (23 MessageBoxA sites, all
  "Error"/"Notice"/network; 5 DialogBoxParamA sites, the modem/config dialogs). **The save and
  overwrite prompts are drawn by the shell in the game surface, not as native Windows dialogs.**

## Symptom 1 — "the mouse is in the wrong position" — CONFIRMED

The shell calls **`ClipCursor(0,0,640,480)`** — it traps the physical OS mouse inside a 640×480
box at the **top-left corner of the screen**, because that was the whole screen in 1997. Measured
live: game window `0,0–3440,1440` (fullscreen), but the cursor clip rect is `0,0–640,480` and the
OS cursor sits pinned at the x=639 clip edge. dgVoodoo's emulated cursor then remaps that 640-wide
strip across the full 3440-wide render, so:

- physical mouse travel is confined to a corner and scaled ~5.4× — small moves throw the pointer
  far, and it can feel stuck or misplaced;
- at the plain main menu dgVoodoo's remap happened to line up (the arrow rendered on TRIP where we
  clicked), so it is **not always** visibly wrong — it degrades when the scaling/overlay changes,
  which is exactly the "sometimes" pattern.

**Fix directions:** a dgVoodoo cursor option, running the shell windowed at native 640×480 so the
clip matches the surface, or neutralising the shell's `ClipCursor` (it fights the wrapper's own
cursor handling). Needs testing under the *user's* stack (see below).

## Symptom 2 — "typing the save name is weird, works sometimes" — focus-dependent input

The shell has a full Win32 message pump (`PeekMessage`+`TranslateMessage`+`DispatchMessage`).
`TranslateMessage` turns key-downs into `WM_CHAR` — and **`WM_CHAR` is only delivered to the window
that holds keyboard focus.** So the name box can only receive characters while the **game window
actually has focus**. The moment anything in the overlay stack (Lossless Scaling's overlay,
opentrack, the wheel helper) takes focus, keystrokes stop reaching the box — and clicking back on
the game restores it. That is precisely "works sometimes but not others."

(The shell also polls `GetAsyncKeyState`, which *is* global, for menu navigation — which is why you
can still move around a menu when you cannot type into a field. The two input paths behave
differently, which reads as inconsistency.)

## Symptom 3 — "saving freezes the game" — a spin, not a hang

Measured live in a menu: the shell burns **100% of one core** while idle, and the process stays
`Responding = True` (46 threads, 1 spinning in the poll loop, the rest in normal message waits).
So it is **not** a deadlock or a `WaitMessage` block — it is a busy poll loop that keeps pumping
messages. The "freeze" is therefore almost certainly **the shell stuck on the save-name screen
waiting for input that is not arriving** (same focus root as Symptom 2): you cannot type the name,
and often cannot cancel out either, so the game sits spinning on that screen forever = looks
frozen, is actually running. Under Lossless Scaling this is worse because you are looking at LS's
captured copy, which may not even show the shell's current screen.

A second, separate freeze candidate to rule out on the day: the **save file write**. The shell
formats names with `sprintf("save%3.3d.cmp")`, and the slot allocator is known to return −1 →
`save-01.cmp` (see [SAVE-FORMAT-GAPS.md](SAVE-FORMAT-GAPS.md)). A write down a bad path, or a
`WaitForSingleObject` on a file handle, could also stall — but the 100%-CPU spin points at input
starvation first.

## Symptom 4 — "it always says you are overwriting even when you're not"

The shell's strings include **"Overwrite an existing bookmark?"**, **"Overwrite the current
variant?"**, **"All vehicle slots are used ! Overwriting previous vehicle"**, and **"Enter Name"**.
The always-overwrite prompt is save-slot logic, and the prime suspect is the same allocator bug:
if the "find a free slot" routine returns −1 (not-found) even when slots are free, the save path
treats every save as landing on an occupied slot → always asks to overwrite, and writes
`save-01.cmp`. This is a code bug in `i76shell.dll`'s save path, testable by disassembling the
slot search and by watching the save directory during a save.

## The unifying diagnosis

Three of the four symptoms share one root: **the 1997 shell assumes it owns a fullscreen 640×480
window with exclusive focus and cursor**, and the modern stack (dgVoodoo scaling + Lossless
Scaling capture/overlay + opentrack + wheel helper, all fullscreen) violates every one of those
assumptions — the cursor gets clipped to a phantom corner, keyboard focus gets stolen from the
name box, and the shell spins forever waiting for input it will never see. The fourth (always-
overwrite) is a genuine save-slot code bug that also explains the orphaned `save-01.cmp` files.

## What to try next (in rough order of value)

1. **Reproduce under the real stack, minimally.** The freeze needs the user's fullscreen +
   Lossless Scaling + opentrack combination; the sandbox (dgVoodoo alone) shows the mechanism but
   not necessarily the hang. Test saves with LS **off**, then on, then windowed (Alt+Enter) — if
   windowed or LS-off saves cleanly, the fix is a focus/overlay configuration, not a patch.
2. **Focus fix.** Ensure the game window holds foreground during the shell — launch order, LS
   "capture without focus steal" if it exists, or a small helper that keeps the game foreground
   while a shell screen is up. The engine already needed `EnableInactiveAppState` for the *sim*;
   the shell needs true keyboard focus for `WM_CHAR`.
3. **Cursor fix.** Test dgVoodoo cursor options and/or windowed 640×480; if the shell's
   `ClipCursor(640×480)` is the culprit, it can be neutralised.
4. **The save-slot bug.** Disassemble the slot allocator in `i76shell.dll` (the `save%3.3d`
   formatter and its caller) to find why it returns −1; that one fix likely kills both "always
   overwriting" and the orphan `save-01.cmp`.

## Facts established (so nobody re-derives them)

- Menus/save/garage/popups are **one shell** (`i76shell.dll` = GOG rename of `NITSHELL.DLL`),
  drawn in the engine's 640×480 surface, driven by a blocking `ShellMain`.
- The save/overwrite prompts are **shell-drawn, not native dialogs** (the native `MessageBoxA`/
  `DialogBoxParamA` calls are all error/multiplayer).
- The shell **spins at 100% CPU** in a poll loop; it does not deadlock.
- Text entry needs **keyboard focus** (`WM_CHAR`); menu nav uses global `GetAsyncKeyState`.
- The cursor is **clipped to 640×480 at the screen origin** (`ClipCursor`) regardless of the real
  window size.
- Save filenames use `sprintf("save%3.3d")`; the slot allocator's −1 return is the likely root of
  both always-overwrite and `save-01.cmp`.
