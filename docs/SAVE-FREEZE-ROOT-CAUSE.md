# The save/popup freeze: root cause, proof, and the fix

**Root cause SOLVED 2026-08-10** (diagnosed on a live hung process, proven by unsticking it).
**The v1 fix shipped 2026-08-10 did NOT work — corrected in v2 on 2026-08-16.** Read the v2
section first; the v1 write-up below it is kept because its *diagnosis* was right and only its
*decision rule* was wrong.

## v2 (2026-08-16) — why v1 failed in play, and the correction

v1 was reported still-freezing by the user on the portable install: loading a bookmark, then
opening Save Bookmark, left the mouse dead (and the in-mission Options/Abort menu mouse never
worked either — same shell, same cause). Diagnosed live on that stuck process:

- The process was **`Responding=True` at ~0% CPU** — *not* the v1 spin-hang. A different failure.
- **`FindWindowA` returned NULL for all four variants**, while `EnumWindows` found the window with
  a byte-exact `Interstate '76 Gold Edition` class *and* title. A proxy that cannot find the window
  computes `m.valid = 0` and **silently disables itself** — v1 could ship "installed" and be inert.
- Live geometry: client rect **3440x1440** → UI scale 3.0, so the 640x480 UI renders at screen
  **x = 760..2680** with 760px black bars. The cursor sat at screen **(370,479)** — i.e. inside the
  left black bar, real UI **(-130,160)** — but v1's guard saw "0<=370<=639, 0<=479<=479, must
  already be UI space" and **passed it through untranslated**.
- **The self-reinforcing deadlock:** the shell calls `ClipCursor(0,0,640,480)`. Until v1's
  `g_translate` flag was set it passed that through *untranslated*, trapping the pointer in the
  physical top-left 640x480 box — precisely the region where every coordinate looks "already
  mapped". So `g_translate` could never become 1, translation never started, and the mouse could
  never escape. That is the "can't see or move the mouse" the user reported.

**Proof (same method as the original diagnosis):** on the live stuck game, a click at UI-space
(420,429) — physically the top-left corner of the screen, nowhere near where CANCEL is drawn —
dismissed the Save Bookmark screen and returned to the mission. Confirms the shell was hit-testing
raw screen coordinates.

**The v2 correction (`src/u32x.c`):**
1. **Window discovery never uses a name.** `EnumWindows` filtered by `GetCurrentProcessId()` picks
   our own visible top-level window (skipping the hidden ActiveMovie/FFB helper windows);
   `FindWindowA`/`GetActiveWindow` remain only as last-ditch fallbacks.
2. **Translation is unconditional and derived from live geometry**, never from the magnitude of
   the coordinate. `g_translate` and the in-range guard are deleted. The one formula is *already
   the identity* when the window genuinely is 640x480 at the origin (scale 1, org 0) — the
   real-fullscreen / pre-mapped case — so a single rule is correct in every configuration with no
   guessing and no bootstrap state.
3. Results are still clamped into 0..639/0..479, so the shell always gets a resolvable coordinate
   and the popup poll loop still can never spin forever.
4. `ClipCursor` now always maps the UI rect onto the real on-screen content rect, so the pointer is
   confined to the **rendered UI** instead of the physical corner.

A `-DU32X_LOG` build (`u32x_log.dll`) writes every translation to
`i76-uncap-lab/captures/save/u32x.log` — use it to *verify* translation is happening rather than
assume it, which is the mistake v1 made.

> **Lesson worth keeping:** v1 was declared "verified" on the strength of a synthetic repro
> (releasing the clip and reading one translated coordinate) that never exercised the state the
> real bug lives in. A fix is verified when the *user's actual workflow* works, not when a probe
> returns the expected number.

---

## The v1 fix (u32x proxy) — SUPERSEDED, retained for its diagnosis

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
- **The name text-entry is finicky — a real, separate shell bug. Mechanism now traced (2026-08-16).**
  The field is auto-focused on open, and characters are read through the shell's own key path. It is
  **not** GetAsyncKeyState polling (an earlier guess); the key-read function is `i76shell.dll+0x1D630`:
  1. It first drains a **64-entry ring buffer** (head at `0x100D215C`, tail at `0x100D2160`, buffer at
     `0x100F6420`) — already-translated characters.
  2. If the ring is empty it calls **`PeekMessageA(&msg, NULL, WM_KEYFIRST(0x100), WM_KEYLAST(0x108),
     PM_REMOVE)`** and dispatches by message via a jump table, translating the VK to a character itself
     (through `+0x1D440` → `ToAscii`, not via `WM_CHAR`/`TranslateMessage`). The name-entry wrapper at
     `+0x1C110` calls `+0x1D630` then re-translates through `ToAscii` at `+0x1C11E`.

  So this is a **message-queue** path, not a poll-rate path. For every keystroke to land, two things must
  hold: (a) the game window has keyboard **focus** so `WM_KEYDOWN` reaches this thread's queue, and (b) no
  other pump drains `0x100..0x108` before this `PeekMessage` runs. That explains "works sometimes": it
  tracks focus, not luck. It is **not** touched by the cursor proxy — `My_PeekMessageA` only rewrites
  mouse-message lParams (`WM_MOUSEFIRST..WM_MOUSELAST`); keyboard messages forward through untouched, so
  the fix neither helps nor harms typing. The automated test dropped 4 of 5 chars because synthetic
  `keybd_event` injection races focus/queue delivery; **human-speed typing into a focused window should
  fare much better** — this is the first thing to confirm in the live test before any patch is designed.
  A real fix, if still needed, would be a keyboard-path shell patch (e.g. pre-seed focus, or widen the
  ring drain), not a cursor change — deferred.
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

---

## 2026-09-05: the cursor was TRAPPED, and the typing hang is a separate bug

Two findings from an automated session driving the game end to end. Both measured, not reasoned.

### 1. FIXED - the pointer could never reach a button (`CaptureMouse`)

`dgVoodoo.conf` had `CaptureMouse = true`. Measured live on the save screen:

```
cursor clip: 0,0-640,480          <- the OS cursor, clipped to the app's UI size
SAVE button: real (1821,1285)     <- where it is actually drawn
UI origin  : (760,0) scale 3.0    <- the rendered UI spans x=760..2680
```

The pointer was confined to the top-left 640x480 of a **3440x1440 desktop** - a corner of the
left black bar, where nothing is drawn. It could not physically be moved onto a button. That is
the whole of "I have to click once to get the cursor back", "can't click YES", and it is why the
confirm poll spins forever: the click it waits for is **unreachable**, not mistimed. Every fix
aimed at coordinate *translation* was treating a symptom - the coordinates were fine, the
pointer simply could not get there.

`CaptureMouse = false` fixes it. `u32x` is built for the FREE pointer and translates screen->UI
itself. Verified by automation: TRIP highlights on hover, and TRIP -> LOAD BOOKMARK -> LOAD ->
salvage -> SAVE BOOKMARK all click through.

### 2. NOT FIXED - typing dies after one character, and it is not a cursor problem

Reproduced automatically, deterministically: **first keystroke lands, the second hangs the game.**
No mouse involved. `IsHungAppWindow` true, ~5% of a core, thread in `ExecutionDelay`.

An instrumented `u32x` (logging every hooked call) shows the decisive fact:

> **The log goes completely silent the moment the Save Bookmark screen opens.** Not one call to
> `GetCursorPos`, `PeekMessageA`, `ClipCursor`, `GetAsyncKeyState` or `GetKeyState` afterwards -
> yet clicks on that screen still work (picking a row changes the name field).

So that screen's input does **not** pass through any USER32 import of `i76shell.dll` or
`i76.exe`. Combined with the ring-buffer note above, the shape is: the **main** loop pumps
messages and fills the 64-entry ring; the save screen's modal loop **drains the ring without
pumping**. It consumes whatever was already buffered - one character - and then spins forever on
an empty ring that nothing refills.

That also predicts what was observed: Windows declares the window hung, DWM ghosts it, and the
ghost takes the input, so nothing can recover it.

**Things tried that did NOT fix it**, so nobody repeats them:

- Pumping the queue from `My_PeekMessageA` when the keyboard-only filter is seen.
- Pumping from `My_GetCursorPos` (rate-limited keepalive).
- Hooking `GetAsyncKeyState` / `GetKeyState` and pumping there.

None fire, because the screen calls none of them.

**The next thing to try** is hooking something that screen *must* call every frame - it renders,
so the Glide or DDraw swap/flip path - and pumping there. That reaches the modal loop from the
only side still available. `I76PATCH.DLL` was checked and imports no USER32 at all, so it is not
the owner.

### 2026-09-06: the render path, found - and a warning about the repro

**The per-frame call is `i76.exe`'s `SetDIBitsToDevice`.** Found by elimination, each step
measured with an instrumented `u32x`:

| hooked | patched OK | called on the save screen |
|---|---|---|
| USER32 `GetCursorPos` / `PeekMessageA` / `ClipCursor` | yes | **no** |
| USER32 `GetAsyncKeyState` / `GetKeyState` | yes | **no** |
| `i76shell.dll` -> GDI32 `BitBlt` / `StretchBlt` | yes (`75C86DE0`) | **no** - the shell's GDI imports are the software/VESA fallback and stay cold in `-glide` |
| `ZGLIDE.DLL` -> glide2x `_grBufferSwap@4` | yes (`6F5714C5`) | **no** |
| **`i76.exe` -> GDI32 `SetDIBitsToDevice`** | **yes (`75C883E0`)** | **YES - 199 pumps during the save screen** |

Two traps worth keeping: the shell imports `MCGA.DLL`, `DISPDIB.DLL` and `vesa480.dll`, none of
which are even **present** in the game folder - dead legacy imports that look like the render
path and are not. And ZGLIDE imports glide2x by its **decorated** name, `_grBufferSwap@4`; the
undecorated string silently matches nothing and the patch reports success with a NULL original.

**But pumping there does NOT fix the hang.** With 199 pumps running on that screen,
`IsHungAppWindow` still goes true on the first keystroke and no character is accepted. So the
theory this file has been building on - *"nothing pumps, so Windows declares it hung, ghosts the
window, and the ghost eats the input"* - is **wrong, or at least incomplete**. Pumping is not
sufficient.

**And the automated repro is harsher than the real thing.** In the harness *zero* characters
land; the user reliably gets *one*, and can still click SAVE and complete a save. This file
already warned that synthetic `keybd_event` injection races focus/queue delivery - that warning
applies to everything measured above. **Anything tuned against this harness may be tuned against
an artifact.** The next person should confirm a candidate fix by hand before believing it.

### 2026-09-06 (later): it is not a typing bug - it is ONE EVENT AND DEAD

The sharpest characterisation yet, and it removes the keyboard from the picture entirely.

**The Save Bookmark screen accepts exactly ONE input event, then stops accepting any.** Shown
with the mouse alone, so no synthetic-keystroke caveat applies:

1. Screen opens - responsive, caret blinking, `IsHungAppWindow` false.
2. Click a list row -> **it works**: the name field updates to that row's text, caret shown.
3. `IsHungAppWindow` immediately true.
4. Click CANCEL. Nothing. Click again. Nothing. A third time. Nothing.

So "only one character can be typed" is a special case of a more general fault: the screen
services a single event and then wedges. The user's own workaround fits exactly - *"I had to
click somewhere to get it to let me type the first character"* - each interaction buys one event.

**`IsHungAppWindow` is a poor instrument here and misled this investigation.** It goes true as
soon as the screen is touched, *while the screen is still working* - the row click that set the
name was processed with the flag already true on the next sample. Hours went into "stop Windows
declaring it hung" (pumping from `PeekMessageA`, `GetCursorPos`, `GetAsyncKeyState`,
`SetDIBitsToDevice`) when the flag was never the fault. **Measure the symptom - did the name
change, did the button respond - not the proxy.**

**Also note the caret is a mode indicator.** Clicking the name field directly *clears* the caret
and leaves edit mode; typing then does nothing and does **not** wedge the screen. Clicking a
list row sets the name *and* shows the caret. Whatever holds the "one event" state is tied to
that mode.

**Still open**, and the next thing to establish: whether the count is exactly one event or one
event *per unit time* - i.e. does it recover after N seconds. That distinguishes a consumed
one-shot flag from something waiting on a tick that never arrives. It needs testing by hand,
because synthetic keystrokes land zero characters where a human lands one.
