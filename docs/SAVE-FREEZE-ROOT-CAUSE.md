# The save/popup freeze: root cause, proof, and the fix

**SOLVED 2026-08-10, diagnosed on a live hung process and proven by unsticking it.
FIX SHIPPED 2026-08-10 (the `u32x` USER32 proxy) — see "The shipped fix" below.**

## The shipped fix (u32x proxy) — deployed and verified

A USER32 coordinate-translation proxy (`i76-uncap-lab/src/u32x.c`, same technique as the
SMACKW32 music fix) is installed beside `i76shell.dll`, and the shell's import string
`USER32.dll` is retargeted to `u32x.dll`. 39 of the shell's 43 USER32 imports forward straight
through; four are intercepted to translate between real screen coordinates and the shell's
640×480 UI space (window client-rect + `stretched_ar` letterbox math). It **guarantees the shell
always receives an in-range coordinate**, so the hit-test always resolves and the poll loop can
never hang — and it is self-calibrating, so it is correct whether or not dgVoodoo pre-maps the
cursor, windowed or fullscreen, at any resolution.

Deploy/rollback: `i76-uncap-lab/tools/instruments/deploy-shellfix.ps1 -GameDir <dir>`
(`-Restore` / `-Status`); keeps `i76shell.dll.orig`. **Deployed to the portable install
2026-08-10.**

**Verified end-to-end:**
- Reproduced the freeze condition on the portable install (released the cursor clip, cursor at
  screen (2900,1200) → `GetCursorPos` returned the raw out-of-range (2900,1200)); the proxy
  translated it and the game stayed `Responding` at idle CPU. Same condition previously hung it.
- The real **"Overwrite an existing bookmark?" popup** — the exact one that froze — now dismisses
  from a click at its **visual** position (YES/NO), and a full save (SAVE → overwrite → YES →
  back to the garage, `save005.cmp` written) completes without a hang.
- Menus/garage/save-load all navigate by clicking where things visually are.
- Non-regression: normal menu navigation still works where dgVoodoo already maps the cursor.

## The other two save issues (found while fixing the freeze)

- **"Always says overwriting on a new save" — mechanism found, not the cursor.** The Save Bookmark
  screen pre-fills the name field with the **currently-loaded bookmark's name** (e.g. "Scene 2.").
  Pressing SAVE with that default name matches an existing entry → the overwrite prompt. It is not
  a slot bug; to make a genuinely new bookmark you must type a different name. With the freeze
  fixed, the honest path is: SAVE → YES overwrites your progress bookmark (works now), or type a
  new name for a new slot. A nicer fix would patch the shell to default the field to a fresh name
  — deferred (needs a shell patch).
- **The name text-entry is finicky — a real, separate shell bug.** The field is auto-focused on
  open, and characters are read through the shell's own key path; automated typing at 80 ms/key
  dropped 4 of 5 characters and backspace did not clear the default. This is the user's "hard to
  type, works sometimes" and is **not** addressed by the cursor proxy. Suspect the shell's
  GetAsyncKeyState/ToAscii polling in its 100%-CPU spin loop dropping keys. Fixing it would need a
  keyboard-path intercept or shell patch — deferred; human-speed typing may fare better than the
  automated test.
- **`savegame.dir` truncation is inherent and benign.** The engine writes the final dir entry
  truncated on every save (observed live: 304→364 after a save, last entry short) and reads its
  own truncated file fine. The canonical repo copy is likewise 304 bytes and loads correctly, so
  no repair is needed on Windows (the Mac launcher re-pads only as belt-and-suspenders).
- **The `save-01.cmp` allocator orphan is intermittent.** The test save allocated correctly
  (`save005`, highest+1); the −1 orphan did not reproduce this run.

---

*(Original diagnosis below, retained.)*

## The bug in one sentence

The 2D shell (`i76shell.dll`) polls **`GetCursorPos`, which returns SCREEN coordinates, and
compares them against its **640×480** button rectangles — so when the game window is larger than
640×480 (any modern fullscreen/scaled setup) the cursor is *never* inside a button, the
confirmation popup's poll loop can never exit, and it spins forever without pumping messages.

## The symptoms this explains (all of them, one cause)

| Symptom | Why |
|---|---|
| **"Saving freezes the game"** | The "Overwrite an existing bookmark?" popup spins waiting for a click it can never register |
| **Windows says "not responding"** | The poll loop never calls `PeekMessage`/`DispatchMessage`, so the window stops servicing its message queue — Windows declares it hung |
| **"The mouse won't move in the window"** | The game is not processing input or redrawing at all; the pointer freezes over the window |
| **"Works sometimes, not others"** | It works **when the physical cursor happens to be inside the top-left 640×480 region of the screen**. Anywhere else and the click is invisible to the shell |
| **"The mouse is in the wrong position"** | Same coordinate mismatch — the shell thinks the UI is at 0–639 × 0–479 while dgVoodoo stretches it across the whole window |

## The evidence chain (live, on the user's hung game — pid 22920)

1. **Process state:** `Responding = False`, **96–100% of one core**, 40 threads with exactly
   **1 Running**. So: a tight spin, *not* a deadlock (a deadlock would be ~0% CPU).
2. **No hidden modal dialog.** Enumerated every window owned by the process: only the game window,
   a hidden ActiveMovie/DirectShow window, and the force-feedback service window. The
   save/overwrite prompts are drawn *by the shell inside the game surface* — the DLL's native
   `MessageBoxA`/`DialogBoxParamA` calls are all error/multiplayer paths.
3. **Sampled the spinning thread's instruction pointer** (`Wow64SuspendThread` +
   `Wow64GetThreadContext`, 25 of 26 samples identical):
   `EIP = 0x768212AC` → `win32u.dll+0x12AC` → **`NtUserCallTwoParam`** (the multiplexed USER32
   syscall stub).
4. **Read the stack**: return address `0x76E761D1` → `user32.dll+0x261D1` →
   **`GetCursorPos`+0x11**. Deeper frames land in `i76shell.dll` (`+0x1FC93`, `+0xBD38`) and in
   **`AcGenral.dll`**, the Windows application-compatibility shim engine.
5. **The out-parameter buffer held `(2692, 1041)`** — a cursor POINT in *screen* coordinates on a
   3440×1440 display. The shell's UI space is 640×480. **That mismatch is the bug.**
6. **`GetClipCursor` on the hung process returned `(0,0)-(3440,1440)`** — i.e. the shell's usual
   `ClipCursor(0,0,640,480)` (which normally *forces* `GetCursorPos` to return in-range values)
   had been released. On a healthy shell the clip is 640×480; that is the shell's own workaround
   for reading raw screen coordinates, and when it is lost the popup can never be answered.

### The proof: the hang was released on demand

Predicted from the diagnosis: *a click at the button's position in **640×480 space** — i.e. in the
top-left corner of the screen, nowhere near where the button visually appears — should satisfy the
loop.* Tested on the live hung process:

```
clicked UI-space (486,260)  -> Responding=False
clicked UI-space (470,255)  -> Responding=True   *** UNSTUCK ***
```

CPU immediately fell from 96% to 7%. The visual position of that YES button was around screen
(2610, 780); the click that worked was at (470, 255). **That gap is the bug, measured.**

## Why it works on the Mac build

The Mac wrapper runs the **software renderer via DxWnd in a Wine virtual desktop at native
resolution** — the shell's window really is the size it thinks it is, so `GetCursorPos` returns
coordinates in the range the shell expects. The Windows path stretches a 640×480 surface across a
3440×1440 window, which breaks the assumption. (This matches the user's instinct that it was
"to do with the renderer helper".)

## Fixes, in order of preference

1. **Keep the cursor clipped to 640×480 while a shell screen is up.** This is what the shell
   already tries to do (`ClipCursor(0,0,640,480)`); the freeze happens when that clip is lost.
   A small helper that re-asserts `ClipCursor(0,0,640,480)` whenever the game is in a shell/menu
   state would prevent the hang entirely. **Lowest risk, no binary patching.**
2. **Run the shell at 1:1.** If the game window is genuinely 640×480 (windowed, or dgVoodoo
   configured not to stretch the menu), screen coordinates and UI coordinates agree and the bug
   cannot occur. Worth testing: does saving work reliably in windowed mode?
3. **Patch the shell's coordinate handling** — scale the `GetCursorPos` result into UI space
   before the hit test. Correct, but needs a hook/patch in `i76shell.dll`.
4. **Emergency unstick (works today, no changes):** when it freezes, **move the mouse into the
   top-left ~640×480 of the screen and click where the button would be in that space** (the popup
   is drawn centred, so YES/NO land around x≈450–500, y≈250–270). The game recovers instantly.

## Notes for follow-up

- **`AcGenral.dll` (the compat shim engine) is loaded** into the process even though the portable
  install's path has **no** entry in `AppCompatFlags\Layers` — Windows is matching `i76.exe`
  against the built-in shim database automatically. Other i76 paths on this machine *do* carry
  explicit layers (`DWM8And16BitMitigation`, and one with `16BITCOLOR DISABLEDWM HIGHDPIAWARE
  WINXPSP2`). Whether a shim contributes to losing the cursor clip is **not yet established** —
  the coordinate mismatch alone is sufficient to explain the hang.
- The "always says you are overwriting" prompt is a *separate* bug — the known save-slot allocator
  returning −1 (`sprintf("save%3.3d", -1)` → `save-01.cmp`), see
  [SAVE-FORMAT-GAPS.md](SAVE-FORMAT-GAPS.md).
- Tools built for this, reusable on any hung process:
  `i76-uncap-lab/tools/instruments/where-spinning.ps1` (sample EIP of a spinning 32-bit process
  and attribute it to a module) and `spin-args.ps1` (read the syscall's stack arguments).
